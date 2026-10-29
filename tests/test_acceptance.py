import copy
import json
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    Ed25519PrivateKey = None

from chilicrisp import acceptance, development
from chilicrisp.contracts import validate
from chilicrisp.runner import file_hash
from test_core import test_directory
from test_core import example


@unittest.skipIf(Ed25519PrivateKey is None, "Install the acceptance or dev extra")
class AcceptanceTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        key = Ed25519PrivateKey.generate()
        policy = {"campaign": "heldout-v1", "public_key": key.public_key().public_bytes_raw().hex(),
                  "policy_sha256": "a"*64, "evaluator_sha256": "b"*64}
        champions = []
        for name in ("initial", "improved"):
            source = root / name
            source.mkdir()
            (source / "program.py").write_text("# " + name)
            champions.append({"id": name, "source": name, "source_hash": development.identity(source),
                "verification": {"public": "native_budget_confirmation", "sealed": "not_run", "production": "not_accepted"}})
        state = {"kind": "measured_development_session", "state": "STOPPED", "pending": None,
            "plan": {"evaluation": {"backend": "linux_cgroup"}, "acceptance": policy},
            "lineage_id": uuid.uuid4().hex, "champions": champions, "champion": 1,
            "controller_sha256": file_hash(development.__file__), "acceptances": [], "events": []}
        (root / "state.json").write_text(json.dumps(state))
        request = development.acceptance_request(root)
        body = {name: request["expected"][name] for name in ("campaign", "lineage_id",
            "baseline_source_hash", "candidate_source_hash", "policy_sha256", "evaluator_sha256")}
        body.update(schema_version="0.1", verdict="passed")
        return root, key, request, body

    def test_signed_receipt_marks_verified_without_production_approval_and_cannot_replay(self):
        with test_directory() as directory:
            root, key, _, body = self.fixture(directory)
            receipt = root / "receipt.json"
            receipt.write_text(json.dumps(acceptance.sign(body, key)))
            state = development.accept(root, receipt)
            self.assertEqual(state["champions"][1]["acceptance_state"], "verified_champion")
            self.assertEqual(state["champions"][1]["verification"]["production"], "not_accepted")
            self.assertEqual(state["stop_reason"], "final_acceptance_passed")
            with self.assertRaisesRegex(ValueError, "once"):
                development.accept(root, receipt)
            with self.assertRaisesRegex(ValueError, "terminal"):
                development.rollback(root, "initial", "Cannot learn from sealed feedback", trusted_local=True)

    def test_signature_tampering_wrong_key_and_all_binding_changes_are_rejected(self):
        with test_directory() as directory:
            root, key, _, body = self.fixture(directory)
            original = (root / "state.json").read_bytes()
            valid = acceptance.sign(body, key)
            variants = [acceptance.sign(body, Ed25519PrivateKey.generate())]
            modified = copy.deepcopy(valid)
            modified["body"]["verdict"] = "rejected"
            variants.append(modified)
            for field in ("campaign", "lineage_id", "baseline_source_hash", "candidate_source_hash", "policy_sha256", "evaluator_sha256"):
                changed = {**body, field: "different" if field == "campaign" else "c" * len(body[field])}
                variants.append(acceptance.sign(changed, key))
            for variant in variants:
                receipt_path = root / "invalid-receipt.json"
                receipt_path.write_text(json.dumps(variant))
                with self.subTest(variant=variant["body"]), self.assertRaises(ValueError):
                    development.accept(root, receipt_path)
                self.assertEqual((root / "state.json").read_bytes(), original)

    def test_rejected_receipt_is_terminal_but_preserves_experimental_champion(self):
        with test_directory() as directory:
            root, key, _, body = self.fixture(directory)
            receipt = root / "receipt.json"
            receipt.write_text(json.dumps(acceptance.sign({**body, "verdict": "rejected"}, key)))
            state = development.accept(root, receipt)
            self.assertEqual(state["champion"], 1)
            self.assertEqual(state["champions"][1]["acceptance_state"], "experimental_champion")
            self.assertEqual(state["stop_reason"], "final_acceptance_rejected")

    def test_source_drift_blocks_receipt_import_and_hidden_receipt_fields_are_disallowed(self):
        from jsonschema import ValidationError
        with test_directory() as directory:
            root, key, _, body = self.fixture(directory)
            signed = acceptance.sign(body, key)
            with self.assertRaises(ValidationError):
                validate({**signed, "hidden_failure": "secret"}, "acceptance-receipt")
            (root / "improved/program.py").write_text("# changed")
            receipt = root / "receipt.json"
            receipt.write_text(json.dumps(signed))
            with self.assertRaisesRegex(ValueError, "changed"):
                development.accept(root, receipt)

    def test_reference_failure_interrupts_without_signing_and_consumes_campaign(self):
        with test_directory() as directory:
            root, key, request, _ = self.fixture(directory)
            vault = root / "vault"
            vault.mkdir()
            secret = vault / "input"
            secret.write_bytes(b"")
            manifest = example()
            manifest["workloads"][0]["input"] = str(secret)
            manifest_path = vault / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            policy = {"schema_version": "0.1", "campaign": "heldout-v1", "manifest": str(manifest_path),
                "manifest_sha256": file_hash(manifest_path), "benchmark_workload": "correct", "transfer_budget": 67108864,
                "repetitions": 3, "seed": 1, "wall_seconds": 10, "max_trials": 10,
                "maximum_latency_regression": .15, "minimum_memory_improvement": .1}
            policy_path = vault / "policy.json"
            policy_path.write_text(json.dumps(policy))
            key_path = vault / "key"
            key_path.write_bytes(key.private_bytes_raw())
            request["expected"].update(policy_sha256=file_hash(policy_path), evaluator_sha256=acceptance.implementation())
            mkdir = Path.mkdir
            with patch.object(acceptance.sys, "platform", "linux"), \
                 patch.object(Path, "mkdir", autospec=True, side_effect=lambda path, *args, **kwargs: mkdir(path, *args, **{**kwargs, "mode": 0o777})), \
                 patch.object(acceptance.os, "chmod"), \
                 patch.object(acceptance, "private_path", side_effect=lambda path, *_args, **_kwargs: Path(path).resolve()), \
                 patch.object(acceptance.evaluation, "identities", return_value={}), \
                 patch.object(acceptance.evaluation, "trial", side_effect=[{"outcome": "pass"}, {"outcome": "pass"}, {"outcome": "wrong_output"}]), \
                 patch.object(acceptance, "sign") as signing:
                with self.assertRaisesRegex(ValueError, "reference baseline"):
                    acceptance.grade(request, policy_path, key_path, vault)
                with self.assertRaises(FileExistsError):
                    acceptance.grade(request, policy_path, key_path, vault)
            signing.assert_not_called()
            report = json.loads(next(vault.glob("attempt-*/report.json")).read_text())
            self.assertEqual(report["status"], "interrupted")

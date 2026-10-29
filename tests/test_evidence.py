import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from chilicrisp.doctor import diagnose
from chilicrisp.evidence import seal, verify
from chilicrisp.project import compare, initialize
from chilicrisp.skill import export
from test_core import example, test_directory


class ToolPolicyTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        baseline = root / "baseline"
        baseline.mkdir()
        (baseline / "check.py").write_text("from pathlib import Path\nassert Path('value').read_text() == 'good'\n")
        (baseline / "value").write_text("good")
        candidate = root / "candidate"
        import shutil
        shutil.copytree(baseline, candidate)
        config = initialize(baseline, [sys.executable, "check.py"])
        return baseline, candidate, config

    def test_weakened_tests_are_rejected_before_candidate_execution(self):
        with test_directory() as directory:
            _, candidate, config = self.fixture(directory)
            (candidate / "value").write_text("bad")
            (candidate / "check.py").write_text("print('fake pass')")
            record, result = compare(config, candidate, Path(directory) / "runs", trusted_local=True)
            self.assertEqual(result["decision"], "candidate_rejected")
            self.assertEqual(result["evaluations"]["candidate"]["outcome"], "contract_changed")
            self.assertEqual(result["evaluations"]["candidate"]["commands"], [])
            self.assertTrue(verify(record)["valid"])

    def test_build_cannot_rewrite_correctness_contract(self):
        with test_directory() as directory:
            _, candidate, config = self.fixture(directory)
            settings = json.loads(config.read_text())
            settings["build"] = [sys.executable, "-c", "from pathlib import Path; Path('check.py').write_text('pass')"]
            config.write_text(json.dumps(settings))
            _, result = compare(config, candidate, Path(directory) / "runs", trusted_local=True)
            self.assertEqual(result["decision"], "baseline_failed")
            self.assertEqual(result["evaluations"]["baseline"]["outcome"], "contract_changed")
            self.assertEqual(len(result["evaluations"]["baseline"]["commands"]), 1)

    def test_output_and_record_edits_fail_integrity_checks(self):
        with test_directory() as directory:
            _, candidate, config = self.fixture(directory)
            record, result = compare(config, candidate, Path(directory) / "runs", trusted_local=True)
            self.assertTrue(verify(record)["valid"])
            output = record.parent / "candidate-test/stdout"
            output.write_bytes(b"changed")
            self.assertFalse(verify(record)["valid"])
            result["decision"] = "candidate_rejected"
            record.write_text(json.dumps(result))
            checks = verify(record)["checks"]
            self.assertFalse(next(c["passed"] for c in checks if c["check"] == "record_digest"))

    def test_protected_paths_cannot_escape_source(self):
        with test_directory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            for paths in (["../outside"], [".git/config"], ["missing"]):
                with self.subTest(paths=paths), self.assertRaises(ValueError):
                    initialize(source, [sys.executable, "-c", "pass"], protected_paths=paths)
            self.assertFalse((source / ".chilicrisp/project.json").exists())

    def test_verification_checks_required_stages_beyond_digest(self):
        with test_directory() as directory:
            _, candidate, config = self.fixture(directory)
            record, result = compare(config, candidate, Path(directory) / "runs", trusted_local=True)
            result["config"]["build"] = [sys.executable, "-c", "pass"]
            record.write_text(json.dumps(result))
            seal(record)
            verification = verify(record)
            self.assertFalse(verification["valid"])
            self.assertTrue(next(c["passed"] for c in verification["checks"] if c["check"] == "record_digest"))
            self.assertFalse(next(c["passed"] for c in verification["checks"] if c["check"] == "candidate.decision"))

    def test_doctor_checks_artifacts_after_backend_preflight(self):
        manifest = copy.deepcopy(example())
        with patch("chilicrisp.runner.preflight", return_value={}), \
             patch("chilicrisp.runner.tree_hash", return_value="f" * 64):
            result = diagnose(manifest)
        check = next(c for c in result["checks"] if c["name"] == "manifest_preflight")
        self.assertEqual(check["status"], "unavailable")
        self.assertIn("Rootfs hash", check["detail"])

    def test_skill_export_is_bundled_and_never_overwrites(self):
        with test_directory() as directory:
            destination = Path(directory) / "chili-dev"
            export(destination)
            self.assertIn("name: chili-dev", (destination / "SKILL.md").read_text())
            self.assertTrue((destination / "agents/openai.yaml").is_file())
            with self.assertRaises(FileExistsError):
                export(destination)

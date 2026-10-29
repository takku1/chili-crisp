import copy
import json
from pathlib import Path
import struct
import time
import unittest
from unittest.mock import patch

from chilicrisp import build, evaluation
from chilicrisp.runner import file_hash, tree_hash
from test_core import example, test_directory


def elf(marker=0):
    data = bytearray(64)
    data[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<HHI", data, 16, 2, 62, 1)
    data[-1] = marker
    return bytes(data)


class BuildTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        runtime = root / "compiler"
        runtime.mkdir()
        (runtime / "candidate").mkdir()
        source = root / "source"
        source.mkdir()
        (source / "program.c").write_text("invalid C that must never be compiled on the host")
        policy = root / "export.json"
        policy.write_text(json.dumps({"schema_version": "0.1", "format": "elf64-lsb-x86_64", "maximum_bytes": 1024}))
        input_file = root / "input"
        input_file.write_bytes(b"")
        manifest = example()
        manifest["isolation"]["seccomp"] = "pilot_build_v1"
        manifest["target"].update(rootfs=str(runtime), rootfs_hash=tree_hash(runtime))
        workload = manifest["workloads"][0]
        workload.pop("expected_stdout_hash")
        workload.update(input=str(input_file), oracle={"kind": "build_elf_v1", "policy_path": str(policy), "policy_hash": file_hash(policy)})
        path = root / "manifest.json"
        path.write_text(json.dumps(manifest))
        calls = []

        def trial(value, workload, budget, **kwargs):
            trial_id = str(len(calls))
            calls.append(copy.deepcopy(value))
            output = Path(value["evidence_directory"]) / trial_id
            output.mkdir(parents=True)
            payload = self.payloads[min(len(calls)-1, len(self.payloads)-1)]
            (output / "stdout").write_bytes(payload)
            (output / "lifecycle.json").write_text(json.dumps({"state": "FINALIZED"}))
            import hashlib
            result = {"schema_version": "0.1", "experiment_id": "test", "trial_id": trial_id,
                "candidate_hash": "0"*64, "manifest_hash": hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest(),
                "measurement_mode": "whole_program", "workload_id": workload, "phase": "exploration",
                "requested_budget_bytes": budget, "effective_budget_bytes": budget, "outcome": "pass",
                "metrics": {}, "artifact_hashes": {"stdout": file_hash(output / "stdout"), "lifecycle.json": file_hash(output / "lifecycle.json")},
                "preflight_record": {}, "lifecycle": "FINALIZED", "error": None,
                "cost": {"wall_seconds": .1, "runner_cpu_seconds": .01, "target_cpu_seconds": .05,
                    "test_invocations": 1, "tool_calls": None, "model_tokens": None, "model_cost": None}}
            (output / "result.json").write_text(json.dumps(result))
            return result
        self.payloads = [elf(), elf()]
        return root, source, path, calls, trial

    def test_bounded_header_parser_rejects_format_architecture_and_volume_errors(self):
        build.check_elf(elf(), 1024)
        wrong_machine = bytearray(elf())
        struct.pack_into("<H", wrong_machine, 18, 183)
        for data, cap in ((b"not ELF", 1024), (elf(), 63), (bytes(wrong_machine), 1024)):
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                build.check_elf(data, cap)

    def test_repeated_exports_are_retained_and_cache_tampering_blocks_reuse(self):
        with test_directory() as directory:
            root, source, manifest, calls, trial = self.fixture(directory)
            # Windows permissions are not part of this mocked compiler unit test.
            with patch.object(build, "run_trial", side_effect=trial), patch.object(Path, "chmod"):
                result = build.compile_candidate(source, manifest, root / "build", 67108864, time.monotonic()+10)
            self.assertEqual(result["status"], "retained")
            self.assertEqual(len(calls), 2)
            artifact = build.verify_cached(source, manifest, root / "build", 67108864)
            (artifact / "program").write_bytes(elf(2))
            with self.assertRaisesRegex(ValueError, "identity"):
                build.verify_cached(source, manifest, root / "build", 67108864)

    def test_nondeterministic_exports_are_not_retained(self):
        with test_directory() as directory:
            root, source, manifest, _, trial = self.fixture(directory)
            self.payloads = [elf(1), elf(2)]
            with patch.object(build, "run_trial", side_effect=trial):
                with self.assertRaisesRegex(ValueError, "byte-identical"):
                    build.compile_candidate(source, manifest, root / "build", 67108864, time.monotonic()+10)
            self.assertFalse((root / "build/artifacts").exists())
            self.assertEqual(json.loads((root / "build/build-record.json").read_text())["status"], "rejected")

    def test_build_profile_cannot_be_used_as_program_runtime(self):
        with test_directory() as directory:
            _, _, manifest, _, _ = self.fixture(directory)
            with self.assertRaisesRegex(ValueError, "runtime seccomp"):
                evaluation.manifest({"evaluation": {"manifest": str(manifest), "benchmark_workload": "correct"}})

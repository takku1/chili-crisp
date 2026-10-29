import copy
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import uuid
import threading
import unittest
from unittest.mock import patch

from jsonschema import ValidationError
from chilicrisp.capture import capture, drain
from chilicrisp.controller import explore
from chilicrisp.frontier import Frontier, Policy
from chilicrisp.lifecycle import Lifecycle
from chilicrisp.runner import ROOT, run_trial, validate
from chilicrisp.runner import finish_trial
import time
from chilicrisp.recovery import recover


def example():
    return json.loads((ROOT / "examples/experiment.json").read_text())


@contextmanager
def test_directory():
    # Windows Python 3.12's mode=0700 temp directory ACL excludes this
    # managed execution identity. Inherit workspace ACLs for test artifacts.
    path = ROOT / ("test-artifacts-" + uuid.uuid4().hex)
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path)


class SchemaTests(unittest.TestCase):
    def test_manifest_rejects_network_and_unknown_fields(self):
        manifest = example()
        validate(manifest, "experiment")
        manifest["isolation"]["network"] = "host"
        with self.assertRaises(ValidationError):
            validate(manifest, "experiment")
        manifest = example()
        manifest["isolation"]["privileged"] = True
        with self.assertRaises(ValidationError):
            validate(manifest, "experiment")

    def test_cross_field_policy_validation(self):
        with self.assertRaises(ValueError):
            Policy(initial_budget=4096, minimum_budget=8192)


class FrontierTests(unittest.TestCase):
    def test_all_pass_floor_is_not_invention(self):
        f = Frontier(Policy(initial_budget=65536, minimum_budget=32768,
                            confirmation_trials=1))
        for _ in range(10):
            decision, budget, reason = f.next()
            if decision != "EXPLORE":
                break
            f.record("pass")
        self.assertEqual((decision, reason),
                         ("STOP", "minimum_budget_reached_without_failure"))
        self.assertIsNone(f.failing)

    def test_timeout_does_not_establish_memory_failure(self):
        f = Frontier(Policy(initial_budget=65536, minimum_budget=4096,
                            confirmation_trials=1))
        f.record("pass")
        f.next()
        f.record("timeout")
        self.assertEqual(f.next(), ("STOP", None, "latency_pressure_requires_diagnosis"))
        self.assertIsNone(f.failing)

    def test_confirmation_and_refinement(self):
        f = Frontier(Policy(initial_budget=65536, minimum_budget=4096,
                            confirmation_trials=2, max_trials=30))
        for _ in range(30):
            decision, budget, reason = f.next()
            if decision != "EXPLORE":
                break
            f.record("pass" if budget >= 32768 else "oom")
        self.assertEqual(decision, "INVENT")
        self.assertGreaterEqual(f.passing, 32768)
        self.assertLess(f.failing, 32768)
        self.assertLessEqual(len(f.history), 30)

    def test_noise_never_becomes_clean_boundary(self):
        f = Frontier(Policy(initial_budget=65536, minimum_budget=4096,
                            confirmation_trials=2))
        f.record("pass")
        f.next()
        f.record("oom")
        self.assertEqual(f.next(), ("STOP", None, "noisy_point_inconclusive"))

    def test_cap_is_hard(self):
        f = Frontier(Policy(initial_budget=65536, minimum_budget=4096, max_trials=1))
        f.record("pass")
        self.assertEqual(f.next(), ("STOP", None, "trial_cap"))

    def test_controller_stops_on_infrastructure_failure(self):
        calls = []
        def trial(*args, **kwargs):
            calls.append(args)
            return {"trial_id": "fixture", "outcome": "cleanup_failure"}
        result = explore(example(), trial)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result[0]["reason"], "baseline_cleanup_failure")

    def test_controller_uses_measured_baseline_and_reserves_trials(self):
        manifest = example()
        manifest["search"].update(minimum_budget=4096, max_trials=8, confirmation_trials=1)
        calls = []
        def trial(manifest, workload, budget, **kwargs):
            calls.append(budget)
            return {"trial_id": str(len(calls)), "outcome": "pass",
                    "metrics": {"memory_peak": {"status": "available", "value": 40000}}}
        result = explore(manifest, trial)[0]
        self.assertEqual(calls[:3], [None, None, None])
        self.assertEqual(calls[3], 45056)
        self.assertEqual(result["initial_budget_bytes"], 45056)
        self.assertLessEqual(len(calls), 8)
        self.assertEqual(result["decision"], "STOP")
        self.assertIsNone(result["failing"])

    def test_unstable_baseline_never_starts_descent(self):
        calls = []
        def trial(*args, **kwargs):
            calls.append(args[2])
            return {"trial_id": "fixture", "outcome": "timeout"}
        result = explore(example(), trial)[0]
        self.assertEqual(calls, [None])
        self.assertEqual(result["reason"], "baseline_timeout")


class CaptureTests(unittest.TestCase):
    def test_finite_stream_hashed_without_unbounded_storage(self):
        with test_directory() as temporary:
            path = Path(temporary) / "out"
            overflow, summary = threading.Event(), {}
            drain(io.BytesIO(b"x" * 100000), path, 128, overflow, summary)
            self.assertTrue(overflow.is_set())
            self.assertEqual(path.stat().st_size, 128)
            self.assertGreater(summary["bytes"], 128)
            self.assertLessEqual(summary["bytes"], 8192)
            self.assertEqual(summary["hash_scope"], "retained_prefix")
            self.assertEqual(summary["sha256"], hashlib.sha256(b"x" * 128).hexdigest())

    def test_real_output_flood_is_bounded(self):
        with test_directory() as temporary:
            process = subprocess.Popen([sys.executable, str(ROOT / "tests/workload.py"), "flood"],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                event, summaries, threads = capture(process, Path(temporary), 1024)
                self.assertTrue(event.wait(5))
            finally:
                process.kill()
                process.wait(timeout=5)
                for thread in threads:
                    thread.join(timeout=5)
            self.assertEqual((Path(temporary) / "stdout").stat().st_size, 1024)


class LifecycleTests(unittest.TestCase):
    def test_failed_journal_never_prevents_cleanup(self):
        with test_directory() as temporary:
            path = Path(temporary)
            life = Lifecycle(path / "lifecycle.json", {})
            life.move("PREFLIGHT_VALIDATED")
            result = dict(trial_id="fixture", outcome="runner_failure", lifecycle="FINALIZED",
                          error="original error", cost={}, artifact_hashes={})
            with patch.object(life, "save", side_effect=OSError("journal write failed")), \
                 patch("chilicrisp.runner.cleanup_cgroup") as cleanup:
                finish_trial(result, path, life, path / "cgroup", True, None, [],
                             time.monotonic(), time.process_time(), 0)
            cleanup.assert_called_once()
            self.assertEqual(result["lifecycle"], "RECOVERY_REQUIRED")
            self.assertIn("original error", result["error"])
            self.assertIn("journal write failed", result["error"])
            self.assertTrue((path / "emergency.json").exists())

    def test_result_write_failure_preserves_original_error(self):
        original = Path.write_text
        def fail_result(path, *args, **kwargs):
            if path.name == "result.json":
                raise OSError("injected result storage failure")
            return original(path, *args, **kwargs)
        with test_directory() as temporary:
            manifest = example()
            manifest["evidence_directory"] = temporary
            with patch("chilicrisp.runner.preflight", side_effect=RuntimeError("original preflight failure")), \
                 patch.object(Path, "write_text", fail_result):
                result = run_trial(manifest, "correct", 67108864)
            self.assertEqual(result["lifecycle"], "RECOVERY_REQUIRED")
            self.assertIn("original preflight failure", result["error"])
            self.assertIn("injected result storage failure", result["error"])
            self.assertEqual(len(list(Path(temporary).glob("*/emergency.json"))), 1)
            with self.assertRaisesRegex(RuntimeError, "requires recovery"):
                run_trial(manifest, "correct", 67108864)

    def test_journal_initialization_failure_has_emergency_record(self):
        with test_directory() as temporary:
            manifest = example()
            manifest["evidence_directory"] = temporary
            with patch("chilicrisp.lifecycle.Lifecycle.save", side_effect=OSError("journal denied")):
                result = run_trial(manifest, "correct", 67108864)
            self.assertEqual(result["outcome"], "runner_failure")
            self.assertEqual(result["lifecycle"], "RECOVERY_REQUIRED")
            self.assertIn("journal denied", result["error"])
            self.assertEqual(len(list(Path(temporary).glob("*/emergency.json"))), 1)

    def test_illegal_transition_and_durable_recovery_marker(self):
        with test_directory() as temporary:
            path = Path(temporary) / "lifecycle.json"
            life = Lifecycle(path, {})
            with self.assertRaises(ValueError):
                life.move("RUNNING")
            life.move("TERMINATING")
            life.move("COLLECTING")
            life.move("RECOVERY_REQUIRED")
            self.assertEqual(json.loads(path.read_text())["state"], "RECOVERY_REQUIRED")

    def test_unsupported_host_produces_schema_valid_evidence(self):
        with test_directory() as temporary:
            manifest = example()
            manifest["evidence_directory"] = temporary
            with patch("chilicrisp.runner.preflight", side_effect=RuntimeError("fixture unsupported")):
                result = run_trial(manifest, "correct", 67108864)
            self.assertEqual(result["outcome"], "unsupported")
            self.assertEqual(result["cost"]["test_invocations"], 0)
            self.assertEqual(result["lifecycle"], "FINALIZED")
            validate(result, "result")

    def test_failed_cleanup_blocks_next_trial(self):
        with test_directory() as temporary:
            manifest = example()
            manifest["evidence_directory"] = temporary
            path = Path(temporary) / "unfinished"
            path.mkdir()
            Lifecycle(path / "lifecycle.json", {"cgroup": "not-a-real-cgroup"})
            with self.assertRaisesRegex(RuntimeError, "requires recovery"):
                run_trial(manifest, "correct", 67108864)


@unittest.skipUnless(sys.platform == "linux" and os.environ.get("CHILI_FIXTURE_MANIFEST"),
                     "requires Linux, delegated cgroup and explicit fixture rootfs manifest")
class NativeIsolationTests(unittest.TestCase):
    def test_failed_cleanup_is_recorded_and_recoverable(self):
        manifest = json.loads(Path(os.environ["CHILI_FIXTURE_MANIFEST"]).read_text())
        with test_directory() as temporary:
            manifest["evidence_directory"] = temporary
            manifest["workloads"][0]["arguments"] = ["correct"]
            try:
                with patch("chilicrisp.runner.cleanup_cgroup", side_effect=OSError("injected cleanup failure")):
                    result = run_trial(manifest, manifest["workloads"][0]["id"], 67108864)
                self.assertEqual(result["outcome"], "cleanup_failure")
                self.assertEqual(result["lifecycle"], "RECOVERY_REQUIRED")
                with self.assertRaisesRegex(RuntimeError, "requires recovery"):
                    run_trial(manifest, manifest["workloads"][0]["id"], 67108864)
            finally:
                for journal in Path(temporary).glob("*/lifecycle.json"):
                    recover(journal, manifest["isolation"]["cgroup_parent"])

    def test_native_failure_fixtures(self):
        original = json.loads(Path(os.environ["CHILI_FIXTURE_MANIFEST"]).read_text())
        with test_directory() as temporary:
            for mode, expected in [("correct", "pass"), ("wrong", "wrong_output"),
                                   ("timeout", "timeout"), ("flood", "output_limit"),
                                   ("isolation", "pass"), ("oom", "oom")]:
                with self.subTest(mode=mode):
                    manifest = copy.deepcopy(original)
                    manifest["evidence_directory"] = temporary
                    manifest["workloads"][0]["arguments"] = [mode]
                    manifest["limits"]["timeout_seconds"] = 2
                    result = run_trial(manifest, manifest["workloads"][0]["id"], 67108864)
                    self.assertEqual(result["outcome"], expected, result.get("error"))


if __name__ == "__main__":
    unittest.main()

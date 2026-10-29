import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from chilicrisp.integrations.benchexec import probe
from chilicrisp.integrations.openevolve import FrozenEvaluator
from chilicrisp.runner import ROOT, file_hash, run_trial


class ProbeTests(unittest.TestCase):
    def test_unsupported_host_never_imports_linux_executor_or_creates_files(self):
        with patch("chilicrisp.integrations.benchexec.sys.platform", "win32"):
            self.assertEqual(probe(ROOT / "never-created-probe")["status"], "unsupported")
        self.assertFalse((ROOT / "never-created-probe").exists())


@unittest.skipUnless(importlib.util.find_spec("openevolve"), "install the evolution extra")
class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "examples/experiment.json").read_text())
        self.source = Path(__file__)
        self.manifest["target"]["source_hash"] = file_hash(self.source)
        self.calls = []

    def trial(self, manifest, workload, budget, **kwargs):
        self.calls.append((manifest, workload, budget, kwargs))
        return dict(schema_version="0.1", experiment_id=manifest["experiment_id"],
            trial_id="test-trial", candidate_hash=manifest["target"]["rootfs_hash"],
            manifest_hash=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            measurement_mode="whole_program", workload_id=workload, phase="exploration",
            requested_budget_bytes=budget, effective_budget_bytes=budget, outcome="pass",
            metrics={name: dict(value=value, unit=unit, method="test double", status="available")
                for name, value, unit in (("memory_peak", 1000000, "bytes"),
                                          ("elapsed", .2, "seconds"))},
            artifact_hashes={}, preflight_record={}, lifecycle="FINALIZED", error=None,
            cost=dict(wall_seconds=.2, runner_cpu_seconds=.01, target_cpu_seconds=.1,
                      test_invocations=1, tool_calls=None, model_tokens=None, model_cost=None))

    def evaluator(self, **kwargs):
        return FrozenEvaluator(self.manifest, 67108864, trial=kwargs.pop("trial", self.trial),
                               **kwargs)

    def test_real_openevolve_result_repeated_workloads_and_frozen_policy(self):
        from openevolve.evaluation_result import EvaluationResult
        evaluator = self.evaluator(repetitions=2)
        self.manifest["workloads"][0]["expected_stdout_hash"] = "f" * 64
        result = evaluator(self.source)
        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(len(self.calls), 2)
        self.assertGreater(result.metrics["combined_score"], 0)
        self.assertEqual(result.metrics["public_pass"], 1)
        self.assertNotEqual(self.calls[0][0]["workloads"][0]["expected_stdout_hash"], "f" * 64)
        self.assertNotIn("sealed:", json.dumps(result.artifacts))

    def test_changed_source_never_reaches_runner(self):
        self.manifest["target"]["source_hash"] = "f" * 64
        result = self.evaluator()(self.source)
        self.assertEqual(result.metrics["combined_score"], 0)
        self.assertEqual(self.calls, [])

    def test_failed_unavailable_and_mismatched_trials_cannot_score(self):
        for update in ({"outcome": "wrong_output"}, {"outcome": "unsupported"},
                       {"lifecycle": "RECOVERY_REQUIRED"}, {"candidate_hash": "f" * 64},
                       {"manifest_hash": "f" * 64}, {"metrics": {}},
                       {"effective_budget_bytes": None}):
            with self.subTest(update=update):
                def trial(*args, **kwargs):
                    result = self.trial(*args, **kwargs)
                    result.update(copy.deepcopy(update))
                    result["error"] = "private oracle /srv/secret"
                    return result
                result = self.evaluator(trial=trial)(self.source)
                self.assertEqual(result.metrics["combined_score"], 0)
                self.assertNotIn("secret", json.dumps(result.artifacts))

    def test_deadline_stops_before_launch(self):
        evaluator = self.evaluator()
        with patch("chilicrisp.integrations.openevolve.time.monotonic", side_effect=[0, 301]):
            result = evaluator(self.source)
        self.assertEqual(result.metrics["combined_score"], 0)
        self.assertEqual(self.calls, [])

    def test_caps_and_budget_validation(self):
        with self.assertRaises(ValueError):
            self.evaluator(repetitions=31)
        with self.assertRaises(ValueError):
            FrozenEvaluator(self.manifest, 67108865)

    @unittest.skipIf(__import__("sys").platform == "linux", "portable unsupported-host path")
    def test_real_runner_unsupported_host_fails_closed(self):
        import shutil
        import uuid
        evidence = ROOT / ("test-artifacts-" + uuid.uuid4().hex)
        self.manifest["evidence_directory"] = str(evidence)
        try:
            result = self.evaluator(trial=run_trial)(self.source)
            self.assertEqual(result.metrics["combined_score"], 0)
            self.assertIn("unsupported", result.artifacts["public_evaluation"])
        finally:
            if evidence.exists():
                shutil.rmtree(evidence)

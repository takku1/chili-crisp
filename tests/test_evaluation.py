import copy
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from chilicrisp import evaluation
from chilicrisp.runner import tree_hash
from test_core import example, test_directory


class NativeEvaluationTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        source = root / "source"
        source.mkdir()
        (source / "program.py").write_text("raise RuntimeError('must not execute on host')")
        value = example()
        path = root / "manifest.json"
        path.write_text(json.dumps(value))
        plan = {"evaluation": {"backend": "linux_cgroup", "manifest": str(path),
            "benchmark_workload": "correct", "initial_budget": 67108864},
            "objective": "enforced_budget_bytes", "artifact_paths": [], "quantum": 4096,
            "minimum_target": 4096, "regression_limits": {"wall_seconds": .15}}
        result = {"schema_version": "0.1", "experiment_id": "test", "trial_id": "test",
            "candidate_hash": "0"*64, "manifest_hash": "0"*64, "measurement_mode": "whole_program",
            "workload_id": "correct", "phase": "exploration", "requested_budget_bytes": 33554432,
            "effective_budget_bytes": 33554432, "outcome": "pass", "metrics": {},
            "artifact_hashes": {}, "preflight_record": {}, "lifecycle": "FINALIZED", "error": None,
            "cost": {"wall_seconds": .1, "runner_cpu_seconds": .01, "target_cpu_seconds": .05,
                "test_invocations": 1, "tool_calls": None, "model_tokens": None, "model_cost": None}}
        return plan, source, result

    def test_budget_and_frozen_source_go_to_runner_without_host_execution(self):
        with test_directory() as directory:
            plan, source, result = self.fixture(directory)
            with patch.object(evaluation, "run_trial", return_value=result) as runner:
                observed = evaluation.trial(plan, source, Path(directory) / "out", 33554432, time.monotonic()+10)
            self.assertEqual(observed["outcome"], "pass")
            manifest, workload, budget = runner.call_args.args
            self.assertEqual(budget, 33554432)
            self.assertEqual(workload, "correct")
            self.assertEqual(manifest["target"]["source_hash"], tree_hash(source))
            self.assertEqual(manifest["target"]["source_mount"], {"path": str(source.resolve()), "tree_hash": tree_hash(source)})

    def test_cleanup_setup_and_effective_limit_failures_stop_evaluation(self):
        with test_directory() as directory:
            plan, source, result = self.fixture(directory)
            for change in ({"outcome": "cleanup_failure"}, {"outcome": "unsupported"},
                           {"lifecycle": "RECOVERY_REQUIRED"}, {"effective_budget_bytes": 67108864}):
                with self.subTest(change=change), patch.object(evaluation, "run_trial", return_value={**result, **change}):
                    with self.assertRaises(evaluation.CleanupRequired):
                        evaluation.trial(plan, source, Path(directory) / "out", 33554432, time.monotonic()+10)

    def test_native_policy_rejects_host_build_and_unaligned_targets(self):
        with test_directory() as directory:
            plan, _, _ = self.fixture(directory)
            with self.assertRaisesRegex(ValueError, "build"):
                evaluation.prepare(plan, {"build": ["untrusted-build"]})
            plan["quantum"] = 1
            with self.assertRaisesRegex(ValueError, "page aligned"):
                evaluation.prepare(plan, {"build": None})
            local = copy.deepcopy(plan)
            local.pop("evaluation")
            with self.assertRaisesRegex(ValueError, "require"):
                evaluation.prepare(local, {"build": None})

    def test_measured_peak_arm_keeps_fixed_ceiling_and_other_objectives_are_rejected(self):
        from chilicrisp import development
        with test_directory() as directory:
            plan, _, _ = self.fixture(directory)
            state = {"plan": plan, "target": 16777216}
            self.assertEqual(development._candidate_budget(state), 16777216)
            plan["objective"] = "native_memory_peak_bytes"
            self.assertEqual(development._candidate_budget(state), 67108864)
            plan["objective"] = "wall_seconds"
            with self.assertRaisesRegex(ValueError, "objective"):
                evaluation.prepare(plan, {"build": None})

    def test_expired_budget_prevents_runner_launch(self):
        with test_directory() as directory:
            plan, source, _ = self.fixture(directory)
            with patch.object(evaluation, "run_trial") as runner:
                with self.assertRaisesRegex(ValueError, "deadline"):
                    evaluation.trial(plan, source, Path(directory) / "out", 33554432, time.monotonic()-1)
            runner.assert_not_called()

    def test_unfinished_sibling_trial_blocks_new_output_and_controller_recovery(self):
        from chilicrisp import development
        with test_directory() as directory:
            plan, source, _ = self.fixture(directory)
            root = Path(directory)
            sibling = root / "native-evidence/previous/trial"
            sibling.mkdir(parents=True)
            journal = sibling / "lifecycle.json"
            journal.write_text(json.dumps({"state": "RECOVERY_REQUIRED"}))
            (root / "state.json").write_text(json.dumps({"kind": "measured_development_session", "plan": plan}))
            with patch.object(evaluation, "run_trial") as runner:
                with self.assertRaises(evaluation.CleanupRequired):
                    evaluation.trial(plan, source, root / "runs/new", 33554432,
                        time.monotonic()+10, evidence_root=root / "native-evidence")
                with self.assertRaises(evaluation.CleanupRequired):
                    development.recover(root, owner_stopped=True)
            runner.assert_not_called()
            journal.write_text(json.dumps({"state": "FINALIZED"}))
            (sibling / "emergency.json").write_text("{}")
            with self.assertRaises(evaluation.CleanupRequired):
                evaluation.ensure_clean(root / "native-evidence")
            journal.write_text(json.dumps({"state": "FINALIZED", "recovery": {"owner": "stopped"}}))
            evaluation.ensure_clean(root / "native-evidence")

import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

from chilicrisp import cpu
from chilicrisp.contracts import validate
from test_core import example, test_directory


class CpuPolicyTests(unittest.TestCase):
    def test_explicit_quota_schema_and_legacy_manifest(self):
        manifest = example()
        validate(manifest, "experiment")
        manifest["isolation"]["cpu"] = {"quota_usec": 20000, "period_usec": 100000}
        validate(manifest, "experiment")
        self.assertEqual(cpu.settings(manifest["isolation"]["cpu"]), {"cpu.max": "20000 100000"})
        for config in ({"quota_usec": 1, "period_usec": 100000},
                       {"quota_usec": 20000, "period_usec": 1000001},
                       {"quota_usec": 20000}, {"quota_usec": 20000, "period_usec": 100000, "cores": 2}):
            invalid = copy.deepcopy(manifest)
            invalid["isolation"]["cpu"] = config
            with self.subTest(config=config), self.assertRaises(ValidationError):
                validate(invalid, "experiment")

    def test_delegation_scheduler_and_ancestor_gates(self):
        with test_directory() as directory:
            parent = Path(directory)
            subtree = parent / "cgroup.subtree_control"
            subtree.write_text("memory pids")
            config = {"quota_usec": 20000, "period_usec": 100000}
            ancestors = [{"cpu.max": "max 100000"}]
            with self.assertRaisesRegex(RuntimeError, "delegated cpu"):
                cpu.preflight(parent, ancestors, config, 0)
            subtree.write_text("memory pids cpu")
            self.assertEqual(cpu.preflight(parent, ancestors, config, 0)["requested"], config)
            with self.assertRaisesRegex(RuntimeError, "fair-class"):
                cpu.preflight(parent, ancestors, config, 1)
            with self.assertRaisesRegex(RuntimeError, "ancestor"):
                cpu.preflight(parent, [{"cpu.max": "50000 100000"}], config, 0)
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                cpu.preflight(parent, [{}], config, 0)

    def test_usage_throttling_and_unavailable_metrics(self):
        metrics = cpu.metrics({"cpu.stat": "usage_usec 250000\nuser_usec 200000\nsystem_usec 50000\n"})
        self.assertEqual(metrics["cpu_usage"]["value"], .25)
        self.assertEqual(metrics["cpu_throttled"]["status"], "unavailable")
        self.assertIsNone(metrics["cpu_local_throttled"]["value"])
        metrics = cpu.metrics({"cpu.stat": "usage_usec 250000\nnr_periods 12\nnr_throttled 11\nthrottled_usec 900000\n",
                               "cpu.stat.local": "throttled_usec 950000\n"})
        self.assertEqual(metrics["cpu_throttled_periods"]["value"], 11)
        self.assertEqual(metrics["cpu_throttled"]["value"], .9)
        self.assertEqual(metrics["cpu_local_throttled"]["value"], .95)


class CpuSweepTests(unittest.TestCase):
    def setUp(self):
        self.manifest = example()
        self.calls = []

    def trial(self, manifest, workload, budget, **kwargs):
        self.calls.append((copy.deepcopy(manifest), workload, budget, kwargs))
        quota = manifest["isolation"]["cpu"]
        return {"schema_version": "0.1", "experiment_id": manifest["experiment_id"],
            "trial_id": str(len(self.calls)), "candidate_hash": manifest["target"]["rootfs_hash"],
            "manifest_hash": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            "measurement_mode": "whole_program", "workload_id": workload, "phase": "exploration",
            "requested_budget_bytes": budget, "effective_budget_bytes": budget, "outcome": "pass",
            "metrics": cpu.metrics({"cpu.stat": "usage_usec 100000\nuser_usec 80000\nsystem_usec 20000\nnr_periods 1\nnr_throttled 0\nthrottled_usec 0\n"}),
            "artifact_hashes": {}, "preflight_record": {"effective": cpu.settings(quota)},
            "lifecycle": "FINALIZED", "error": None,
            "cost": {"wall_seconds": .1, "runner_cpu_seconds": .01, "target_cpu_seconds": .05,
                "test_invocations": 1, "tool_calls": None, "model_tokens": None, "model_cost": None}}

    def sweep(self, **kwargs):
        return cpu.sweep(self.manifest, [100000, 50000, 20000], memory_budget=67108864,
                         trial=kwargs.pop("trial", self.trial), **kwargs)

    def test_seeded_schedule_preserves_manifest_and_counts_all_trials(self):
        original = copy.deepcopy(self.manifest)
        result = self.sweep(repetitions=2, seed=19)
        self.assertEqual(result["decision"], "COMPLETED")
        self.assertEqual(result["attempted_trials"], 6)
        self.assertEqual(self.manifest, original)
        sequence = [(r["quota_usec"], r["repetition"]) for r in result["records"]]
        again = self.sweep(repetitions=2, seed=19)
        self.assertEqual(sequence, [(r["quota_usec"], r["repetition"]) for r in again["records"]])
        self.assertEqual(len(set(sequence)), 6)

    def test_trial_and_wall_caps_stop_without_launch(self):
        self.manifest["search"]["max_trials"] = 1
        with self.assertRaisesRegex(ValueError, "trial cap"):
            self.sweep()
        self.assertFalse(self.calls)
        self.manifest["search"]["max_trials"] = 30
        self.manifest["limits"]["experiment_seconds"] = 1
        with patch("chilicrisp.cpu.time.monotonic", side_effect=[0, 2]):
            result = self.sweep()
        self.assertEqual(result["reason"], "experiment_time_cap")
        self.assertEqual(result["attempted_trials"], 0)

    def test_timeout_is_observed_and_other_failures_stop(self):
        def timeout(*args, **kwargs):
            result = self.trial(*args, **kwargs)
            result["outcome"] = "timeout"
            return result
        result = self.sweep(repetitions=1, trial=timeout)
        self.assertEqual(result["decision"], "COMPLETED")
        self.assertTrue(all(r["outcome"] == "timeout" for r in result["records"]))
        for outcome in ("oom", "wrong_output", "unsupported", "cleanup_failure"):
            def failure(*args, **kwargs):
                result = self.trial(*args, **kwargs)
                result["outcome"] = outcome
                return result
            result = self.sweep(repetitions=1, trial=failure)
            self.assertEqual(result["reason"], outcome)
            self.assertEqual(result["attempted_trials"], 1)

    def test_wrong_identity_or_effective_limit_cannot_complete(self):
        for kind in ("identity", "quota"):
            def invalid(*args, **kwargs):
                result = self.trial(*args, **kwargs)
                if kind == "identity":
                    result["manifest_hash"] = "f" * 64
                else:
                    result["preflight_record"]["effective"]["cpu.max"] = "max 100000"
                return result
            result = self.sweep(trial=invalid)
            self.assertEqual(result["decision"], "STOP")
            self.assertEqual(result["attempted_trials"], 1)

    def test_unavailable_cpu_measurements_cannot_complete(self):
        def missing(*args, **kwargs):
            result = self.trial(*args, **kwargs)
            result["metrics"] = {}
            return result
        result = self.sweep(trial=missing)
        self.assertEqual(result["reason"], "cpu_measurement_unavailable")
        self.assertEqual(result["attempted_trials"], 1)

import copy
import json
from pathlib import Path
import unittest

from chilicrisp.pressure import summarize
from chilicrisp.resources import capabilities
from chilicrisp.runner import run_trial
from test_core import example, test_directory


class PressureTests(unittest.TestCase):
    def test_actual_unsupported_record_and_duplicate_rejection(self):
        with test_directory() as directory:
            manifest = example()
            manifest["evidence_directory"] = directory
            # A missing rootfs must fail preflight before any workload starts.
            manifest["target"]["rootfs"] = str(Path(directory) / "missing")
            result = run_trial(manifest, manifest["workloads"][0]["id"], 4096)
            report = summarize(directory)
            self.assertEqual(report["trial_count"], 1)
            self.assertEqual(report["points"][0]["outcomes"], {result["outcome"]: 1})
            duplicate = Path(directory) / "duplicate"
            duplicate.mkdir()
            (duplicate / "result.json").write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                summarize(directory)

    def test_conditions_and_missing_measurements(self):
        with test_directory() as directory:
            manifest = example()
            manifest["evidence_directory"] = directory
            manifest["target"]["rootfs"] = str(Path(directory) / "missing")
            record = run_trial(manifest, manifest["workloads"][0]["id"], 4096)
            # Synthetic finalized measurements test aggregation only, not Linux.
            for index, (value, budget) in enumerate([(2, 4096), (4, 4096), (9, 8192)]):
                item = copy.deepcopy(record)
                item.update(trial_id=f"synthetic-{index}", outcome="pass", lifecycle="FINALIZED",
                            requested_budget_bytes=budget)
                item["metrics"] = {"elapsed": dict(value=value, unit="seconds",
                    method="synthetic", status="available")}
                target = Path(directory) / str(index)
                target.mkdir()
                (target / "result.json").write_text(json.dumps(item))
            report = summarize(directory)
            self.assertEqual(len(report["points"]), 2)
            point = next(p for p in report["points"] if p["conditions"]["requested_budget_bytes"] == 4096)
            measurement = point["measurements"]["elapsed"][0]
            self.assertEqual(measurement["median"], 3)
            self.assertEqual(measurement["unavailable_count"], 1)

    def test_capabilities_are_declarations(self):
        result = capabilities()
        self.assertEqual(result["host_preflight"], "not_run")
        self.assertEqual(result["resources"]["cpu_bandwidth"]["enforcement"], "cgroup cpu.max")
        result["resources"]["memory"]["search"] = False
        self.assertTrue(capabilities()["resources"]["memory"]["search"])

"""OpenEvolve feedback for owner-frozen artifacts, never host execution of source."""
import copy
import hashlib
import json
import math
from pathlib import Path
import time

from ..frontier import Policy
from ..runner import file_hash, run_trial, validate


class FrozenEvaluator:
    """Callable implementing OpenEvolve's evaluate(program_path) contract.

    The owner supplies a frozen manifest for a single-source candidate whose
    source_hash is SHA256(program_path). A different proposal requires a new
    trusted build and manifest. This adapter cannot build or promote candidates.
    Use outside the candidate agent's writable account and filesystem boundary.
    """

    def __init__(self, manifest, budget, *, repetitions=1, trial=run_trial):
        validate(manifest, "experiment")
        policy = Policy(**manifest["search"])
        if type(budget) is not int or budget < policy.minimum_budget:
            raise ValueError("budget must be an integer at or above the policy minimum")
        if budget % policy.page_size:
            raise ValueError("budget must be page aligned")
        if type(repetitions) is not int or repetitions < 1:
            raise ValueError("repetitions must be positive")
        if repetitions * len(manifest["workloads"]) > policy.max_trials:
            raise ValueError("evaluation exceeds the trial cap")
        self._manifest = copy.deepcopy(manifest)
        self._budget = budget
        self._repetitions = repetitions
        self._trial = trial

    def __call__(self, program_path):
        # Lazy import: base installs have no OpenEvolve or model dependencies.
        from openevolve.evaluation_result import EvaluationResult

        def feedback(reason, records, peaks=(), elapsed=()):
            valid = reason == "public_checks_passed"
            metrics = {"combined_score": 0.0, "public_pass": float(valid),
                       "measurement_valid": float(valid)}
            if valid:
                metrics.update(memory_peak_bytes=float(max(peaks)),
                               elapsed_seconds=float(max(elapsed)),
                               combined_score=1 / (1 + max(peaks) / self._budget))
            # Only public outcomes and IDs enter model feedback, never oracle
            # policies, reference arrays, host paths, raw output, or tracebacks.
            return EvaluationResult(metrics=metrics, artifacts={
                "public_evaluation": json.dumps({"reason": reason, "trials": records,
                    "scope": "public exploration only; no promotion or transfer acceptance"})})

        manifest = copy.deepcopy(self._manifest)
        if file_hash(Path(program_path)) != manifest["target"]["source_hash"]:
            return feedback("candidate_not_frozen", [])
        deadline = time.monotonic() + manifest["limits"]["experiment_seconds"]
        records, peaks, elapsed = [], [], []
        for _ in range(self._repetitions):
            for workload in manifest["workloads"]:
                if time.monotonic() >= deadline:
                    return feedback("experiment_time_cap", records)
                result = self._trial(copy.deepcopy(manifest), workload["id"], self._budget,
                                     experiment_deadline=deadline)
                validate(result, "result")
                manifest_hash = hashlib.sha256(
                    json.dumps(manifest, sort_keys=True).encode()).hexdigest()
                if (result["candidate_hash"] != manifest["target"]["rootfs_hash"]
                        or result["manifest_hash"] != manifest_hash
                        or result["experiment_id"] != manifest["experiment_id"]
                        or result["phase"] != "exploration"
                        or result["workload_id"] != workload["id"]
                        or result["requested_budget_bytes"] != self._budget
                        or result["lifecycle"] != "FINALIZED"):
                    return feedback("invalid_trial_identity_or_lifecycle", records)
                records.append({"trial_id": result["trial_id"], "outcome": result["outcome"]})
                if result["outcome"] != "pass":
                    return feedback(result["outcome"], records)
                if result["effective_budget_bytes"] != self._budget:
                    return feedback("effective_budget_unavailable", records)
                for name, destination in (("memory_peak", peaks), ("elapsed", elapsed)):
                    metric = result["metrics"].get(name, {})
                    value = metric.get("value")
                    if (metric.get("status") != "available"
                            or metric.get("unit") != ("bytes" if name == "memory_peak" else "seconds")
                            or type(value) not in (int, float)
                            or not math.isfinite(value) or value <= 0):
                        return feedback("measurement_unavailable", records)
                    destination.append(value)
        return feedback("public_checks_passed", records, peaks, elapsed)

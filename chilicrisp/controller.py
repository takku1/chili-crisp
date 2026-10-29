"""Public-workload frontier controller. No hidden grading or candidate edits."""
import argparse
import json
from pathlib import Path
import time
import math
from dataclasses import replace

from .frontier import Frontier, Policy
from .runner import run_trial, validate


def explore(manifest, trial=run_trial):
    validate(manifest, "experiment")
    deadline = time.monotonic() + manifest["limits"]["experiment_seconds"]
    summaries = []
    for workload in manifest["workloads"]:
        policy = Policy(**manifest["search"])
        records = []
        baseline = []
        baseline_error = None
        config = manifest.get("baseline", {"trials": 3, "margin_fraction": .1})
        if config["trials"] >= policy.max_trials:
            baseline_error = "insufficient_trial_budget_for_baseline"
        else:
            for _ in range(config["trials"]):
                if time.monotonic() >= deadline:
                    baseline_error = "experiment_time_cap"
                    break
                result = trial(manifest, workload["id"], None, experiment_deadline=deadline)
                baseline.append(result)
                peak = result.get("metrics", {}).get("memory_peak", {})
                if result["outcome"] != "pass":
                    baseline_error = "baseline_" + result["outcome"]
                    break
                if peak.get("status") != "available" or not isinstance(peak.get("value"), (int, float)) or peak["value"] <= 0:
                    baseline_error = "baseline_peak_unavailable"
                    break
        if baseline_error:
            summaries.append(dict(workload_id=workload["id"], decision="STOP", reason=baseline_error,
                                  baseline=baseline, records=[], passing=None, failing=None))
            break
        measured_peak = max(r["metrics"]["memory_peak"]["value"] for r in baseline)
        initial = max(policy.minimum_budget,
            math.ceil(measured_peak * (1 + config["margin_fraction"]) / policy.page_size) * policy.page_size)
        frontier = Frontier(replace(policy, initial_budget=initial,
                                    max_trials=policy.max_trials - len(baseline)))
        while True:
            decision, budget, reason = frontier.next()
            if time.monotonic() >= deadline:
                decision, budget, reason = "STOP", None, "experiment_time_cap"
            if decision != "EXPLORE":
                break
            result = trial(manifest, workload["id"], budget, experiment_deadline=deadline)
            records.append({"trial_id": result["trial_id"], "budget": budget,
                            "outcome": result["outcome"], "decision_reason": reason})
            if result["outcome"] not in {"pass", "oom", "timeout", "wrong_output"}:
                decision, reason = "STOP", result["outcome"]
                break
            frontier.record(result["outcome"])
        summaries.append(dict(workload_id=workload["id"], decision=decision,
            reason=reason, baseline=baseline, measured_peak_bytes=measured_peak,
            initial_budget_bytes=initial, records=records,
            performance_pressure=[r for r in records if r["outcome"] == "timeout"],
            passing=frontier.passing, failing=frontier.failing))
        if reason in {"experiment_time_cap", "cleanup_failure", "runner_failure", "unsupported"}:
            break
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    result = explore(json.loads(args.manifest.read_text()))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

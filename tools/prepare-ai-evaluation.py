"""Freeze an AI decoder proposal for protected native evaluation, without importing it."""
import argparse
import ast
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    work = args.work
    request = json.loads((work / "request.json").read_text())
    candidate = work / "candidate/chilicrisp/fields.py"
    ast.parse(candidate.read_text())
    baseline = work / "baseline/chilicrisp/fields.py"
    plan = {"kind": "model_source_participation_pilot", "agent_source": "Codex CLI structured response",
        "baseline_decoder_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest(),
        "candidate_decoder_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
        "workload": {"field_count": 500000, "decode_iterations": 16},
        "memory_budget_bytes": 67108864, "cpu_quota_usec": 100000, "cpu_period_usec": 100000,
        "exploration_blocks": 3, "confirmation_blocks": 3, "seed": 47,
        "minimum_peak_reduction_bytes": 2097152, "maximum_median_elapsed_regression_fraction": .15,
        "maximum_candidate_peak_bytes": request["initial_measured_target_bytes"],
        "maximum_native_trials": 14, "native_experiment_seconds": 180,
        "adaptation_policy": "At most one retry after public rejection, relaxing target from 20% to 10% below freshly measured control; no retry after heldout grading",
        "candidate_host_execution": "none; AST parsing only",
        "scope": "AI participation and protected evaluation pilot, not a matched causal comparison"}
    (work / "plan.json").write_text(json.dumps(plan, indent=2))
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()

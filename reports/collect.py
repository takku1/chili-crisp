"""Refresh local validation evidence; these are not optimization benchmarks."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def main():
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        [sys.executable, "-m", "chilicrisp.runner", "validate", "examples/experiment.json"],
    ]
    records = []
    for index, command in enumerate(commands):
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
        artifact = REPORTS / ("tests.log" if index == 0 else "manifest-validation.log")
        artifact.write_text(result.stdout + result.stderr, encoding="utf-8")
        records.append({"command": command, "exit_code": result.returncode,
                        "output_file": artifact.name})
    from chilicrisp.frontier import Frontier, Policy
    policy = Policy(initial_budget=65536, minimum_budget=4096,
                    confirmation_trials=2, max_trials=30)
    frontier = Frontier(policy)
    decisions = []
    while True:
        decision, budget, reason = frontier.next()
        record = dict(decision=decision, budget=budget, reason=reason)
        if decision != "EXPLORE":
            decisions.append(record)
            break
        outcome = "pass" if budget >= 32768 else "oom"
        record["synthetic_outcome"] = outcome
        decisions.append(record)
        frontier.record(outcome)
    synthetic = dict(kind="synthetic_policy_simulation_not_workload_measurement",
                     oracle="pass iff budget >= 32768 bytes", decisions=decisions,
                     passing=frontier.passing, failing=frontier.failing,
                     trial_count=len(frontier.history))
    (REPORTS / "synthetic-frontier.json").write_text(json.dumps(synthetic, indent=2))
    hashes = {}
    for directory, pattern in [("chilicrisp", "*.py"), ("tests", "*.py"), ("schemas", "*.json")]:
        for file in sorted((ROOT / directory).glob(pattern)):
            hashes[file.relative_to(ROOT).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    metadata = dict(collected_at_utc=datetime.now(timezone.utc).isoformat(),
                    platform=platform.platform(), python=sys.version,
                    commands=records, source_sha256=hashes)
    (REPORTS / "validation-run.json").write_text(json.dumps(metadata, indent=2))
    print(json.dumps({"commands": records, "synthetic_frontier": synthetic}, indent=2))
    return int(any(record["exit_code"] for record in records))


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())

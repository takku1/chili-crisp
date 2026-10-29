"""Unprivileged native fixture worker, invoked by native-fixtures.py."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB / "source"))

from chilicrisp.recovery import recover  # noqa: E402 -- use the copied checkout
from chilicrisp.runner import run_trial, tree_hash  # noqa: E402
from chilicrisp.cpu import sweep  # noqa: E402


def main():
    relative = next(line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines()
                    if line.startswith("0::"))
    parent = Path("/sys/fs/cgroup") / relative.lstrip("/")
    manager = parent / "manager"
    manager.mkdir()
    (manager / "cgroup.procs").write_text(str(os.getpid()))
    (parent / "cgroup.subtree_control").write_text("+memory +pids +cpu")
    # The service's own cpu.max is administrator-owned. Exercise only a fresh
    # child owned by this delegated worker, never relax service ownership.
    parent = parent / "experiments"
    parent.mkdir()
    (parent / "cgroup.subtree_control").write_text("+memory +pids +cpu")
    manifest = json.loads((LAB / "source/examples/experiment.json").read_text())
    manifest["target"].update(rootfs=str(LAB / "rootfs"), rootfs_hash=tree_hash(LAB / "rootfs"),
        source_hash=hashlib.sha256((LAB / "rootfs/fixtures/workload.py").read_bytes()).hexdigest(),
        build_identity="minimal host Python runtime; " + sys.version)
    manifest["workloads"][0]["input"] = str(LAB / "empty-input")
    manifest["isolation"]["cgroup_parent"] = str(parent)
    manifest["evidence_directory"] = str(LAB / "evidence")
    manifest["limits"]["timeout_seconds"] = 2
    (LAB / "manifest.json").write_text(json.dumps(manifest, indent=2))
    observations = []
    for mode, expected in [("correct", "pass"), ("wrong", "wrong_output"),
                           ("timeout", "timeout"), ("flood", "output_limit"),
                           ("isolation", "pass"), ("oom", "oom")]:
        selected = copy.deepcopy(manifest)
        selected["workloads"][0]["arguments"] = [mode]
        result = run_trial(selected, "correct", 67108864)
        observations.append({"mode": mode, "expected": expected, "outcome": result["outcome"],
                             "error": result["error"], "trial_id": result["trial_id"]})
        print(json.dumps(observations[-1]), flush=True)
    with patch("chilicrisp.runner.cleanup_cgroup", side_effect=OSError("injected cleanup failure")):
        result = run_trial(manifest, "correct", 67108864)
    journal = LAB / "evidence" / result["trial_id"] / "lifecycle.json"
    recovery = recover(journal, str(parent))
    observations.append({"mode": "cleanup_recovery", "expected": "cleanup_failure",
                         "outcome": result["outcome"], "recovery": recovery})
    cpu_manifest = copy.deepcopy(manifest)
    cpu_manifest["isolation"]["cpu"] = {"quota_usec": 20000, "period_usec": 100000}
    cpu_manifest["workloads"][0]["arguments"] = ["cpu"]
    cpu_manifest["limits"]["timeout_seconds"] = 6
    result = run_trial(cpu_manifest, "correct", 67108864)
    measurements = result["metrics"]
    cpu_verified = (result["outcome"] == "pass"
        and result["preflight_record"].get("effective", {}).get("cpu.max") == "20000 100000"
        and measurements.get("cpu_throttled_periods", {}).get("value", 0) > 0
        and measurements.get("cpu_usage", {}).get("value", 0) >= .25)
    observations.append({"mode": "cpu_bandwidth", "expected": "pass",
        "outcome": result["outcome"], "cpu_verified": cpu_verified,
        "trial_id": result["trial_id"], "metrics": measurements})
    cpu_manifest["limits"]["timeout_seconds"] = .15
    result = run_trial(cpu_manifest, "correct", 67108864)
    observations.append({"mode": "cpu_wall_timeout", "expected": "timeout",
                         "outcome": result["outcome"], "trial_id": result["trial_id"]})
    # Test only this worker's delegated service, restoring its original policy.
    original_quota = (parent / "cpu.max").read_text()
    try:
        (parent / "cpu.max").write_text("50000 100000")
        result = run_trial(cpu_manifest, "correct", 67108864)
        observations.append({"mode": "cpu_ancestor_rejection", "expected": "unsupported",
                             "outcome": result["outcome"], "error": result["error"]})
    finally:
        (parent / "cpu.max").write_text(original_quota)
    try:
        (parent / "cgroup.subtree_control").write_text("-cpu")
        result = run_trial(cpu_manifest, "correct", 67108864)
        observations.append({"mode": "cpu_delegation_rejection", "expected": "unsupported",
                             "outcome": result["outcome"], "error": result["error"]})
    finally:
        (parent / "cgroup.subtree_control").write_text("+cpu")
    cpu_manifest["limits"]["timeout_seconds"] = 6
    sweep_result = sweep(cpu_manifest, [100000, 50000], memory_budget=67108864,
                         repetitions=2, seed=7)
    (LAB / "cpu-sweep.json").write_text(json.dumps(sweep_result, indent=2))
    observations.append({"mode": "cpu_sweep", "expected": "COMPLETED",
        "outcome": sweep_result["decision"], "attempted_trials": sweep_result["attempted_trials"]})
    leaks = sorted(path.name for path in parent.glob("chili-*") if path.is_dir())
    passed = (all(item["expected"] == item["outcome"] for item in observations)
        and not leaks and cpu_verified and sweep_result["attempted_trials"] == 4)
    summary = {"passed": passed, "observations": observations, "remaining_trial_cgroups": leaks}
    (LAB / "native-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

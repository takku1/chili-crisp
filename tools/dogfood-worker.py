"""Owner-controlled paired self-test using the real Chili Crisp runner."""
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB / "source"))

from chilicrisp.runner import run_trial, tree_hash, validate  # noqa: E402


def main():
    plan = json.loads((LAB / "dogfood-plan.json").read_text())
    relative = next(line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines()
                    if line.startswith("0::"))
    service = Path("/sys/fs/cgroup") / relative.lstrip("/")
    manager = service / "manager"
    manager.mkdir()
    (manager / "cgroup.procs").write_text(str(os.getpid()))
    (service / "cgroup.subtree_control").write_text("+memory +pids +cpu")
    parent = service / "experiments"
    parent.mkdir()
    (parent / "cgroup.subtree_control").write_text("+memory +pids +cpu")
    manifests = {}
    for name, root in (("baseline", LAB / "rootfs"), ("candidate", LAB / "candidate-rootfs")):
        manifest = json.loads((LAB / "source/examples/experiment.json").read_text())
        manifest["experiment_id"] = "self-test-decoder-" + name
        manifest["target"].update(rootfs=str(root), rootfs_hash=tree_hash(root),
            source_hash=plan[f"{name}_decoder_sha256"], build_identity="frozen Python " + sys.version,
            command=["/usr/bin/python3", "/fixtures/decoder.py"])
        workload = manifest["workloads"][0]
        workload.update(id="maximum-field-stream", input=str(LAB / "decoder-input"),
            input_hash=plan["input_sha256"], expected_stdout_hash=plan["expected_stdout_hash"],
            arguments=[str(plan["workload"]["decode_iterations"])])
        manifest["isolation"].update(cgroup_parent=str(parent), cpu={
            "quota_usec": plan["cpu_quota_usec"], "period_usec": plan["cpu_period_usec"]})
        manifest["limits"].update(timeout_seconds=10, experiment_seconds=plan["native_experiment_seconds"])
        manifest["evidence_directory"] = str(LAB / "evidence")
        validate(manifest, "experiment")
        manifests[name] = manifest
    randomizer = random.Random(plan["seed"])
    schedule = [("warmup", -1, name) for name in ("baseline", "candidate")]
    for phase, count in (("exploration", plan["exploration_blocks"]),
                         ("confirmation", plan["confirmation_blocks"])):
        for block in range(count):
            order = ["baseline", "candidate"]
            randomizer.shuffle(order)
            schedule.extend((phase, block, name) for name in order)
    plan.update(schedule=schedule, manifests=manifests,
        environment={"uname": list(os.uname()),
                     "lscpu": subprocess.run(["lscpu"], capture_output=True, text=True, check=True).stdout},
        driver_sha256=hashlib.sha256((LAB / "rootfs/fixtures/decoder.py").read_bytes()).hexdigest())
    (LAB / "dogfood-plan.json").write_text(json.dumps(plan, indent=2))
    records = []
    deadline = time.monotonic() + plan["native_experiment_seconds"]
    reason = None

    def phase_summary(phase):
        selected = [r for r in records if r["phase"] == phase]
        summaries = {}
        for name in ("baseline", "candidate"):
            observations = [r["result"] for r in selected if r["variant"] == name]
            if len(observations) != plan[f"{phase}_blocks"] or any(r["outcome"] != "pass" for r in observations):
                return {"eligible": False, "reason": "incomplete_or_failed_trials"}
            summaries[name] = {metric: statistics.median(r["metrics"][metric]["value"] for r in observations)
                               for metric in ("memory_peak", "elapsed", "cpu_usage")}
        reduction = summaries["baseline"]["memory_peak"] - summaries["candidate"]["memory_peak"]
        regression = summaries["candidate"]["elapsed"] / summaries["baseline"]["elapsed"] - 1
        return {"eligible": reduction >= plan["minimum_peak_reduction_bytes"]
                and regression <= plan["maximum_median_elapsed_regression_fraction"]
                and summaries["candidate"]["memory_peak"] <= plan.get("maximum_candidate_peak_bytes", float("inf")),
                "medians": summaries, "peak_reduction_bytes": reduction,
                "elapsed_regression_fraction": regression}

    for phase, block, name in schedule:
        if phase == "confirmation" and not phase_summary("exploration")["eligible"]:
            reason = "exploration_threshold_not_met"
            break
        if len(records) >= plan["maximum_native_trials"] or time.monotonic() >= deadline:
            reason = "experiment_budget_exhausted"
            break
        selected = copy.deepcopy(manifests[name])
        if phase == "confirmation" and "heldout_confirmation" in plan:
            hidden = plan["heldout_confirmation"]
            selected["workloads"][0].update(input=hidden["input"], input_hash=hidden["input_hash"],
                                           expected_stdout_hash=hidden["expected_stdout_hash"])
        observation = run_trial(selected, "maximum-field-stream",
                                plan["memory_budget_bytes"], experiment_deadline=deadline)
        validate(observation, "result")
        records.append({"phase": phase, "block": block, "variant": name, "result": observation})
        (LAB / "dogfood-measurements.json").write_text(json.dumps(records, indent=2))
        print(json.dumps({"phase": phase, "block": block, "variant": name,
              "trial_id": observation["trial_id"], "outcome": observation["outcome"],
              "metrics": observation["metrics"]}), flush=True)
        if observation["outcome"] != "pass" or observation["lifecycle"] != "FINALIZED":
            reason = "trial_failed"
            break
    exploration = phase_summary("exploration")
    confirmation = phase_summary("confirmation")
    leaks = sorted(path.name for path in parent.glob("chili-*") if path.is_dir())
    supported = reason is None and exploration["eligible"] and confirmation["eligible"] and not leaks
    summary = {"status": "supported_improvement" if supported else "inconclusive",
        "reason": reason, "attempted_trials": len(records), "exploration": exploration,
        "confirmation": confirmation, "remaining_trial_cgroups": leaks,
        "scope": "one host, maximum supported decoder stream, whole-program measurements; no production promotion"}
    (LAB / "dogfood-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if supported else 1


if __name__ == "__main__":
    raise SystemExit(main())

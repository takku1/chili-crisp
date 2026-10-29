"""CPU bandwidth policy and cgroup accounting; no CPU-time exhaustion guesses."""
import copy
import hashlib
import json
import math
import random
import time


def settings(config):
    """An explicit quota/period pair limits bandwidth, not cumulative CPU time."""
    return {"cpu.max": f"{config['quota_usec']} {config['period_usec']}"}


def preflight(parent, ancestors, config, scheduler):
    if "cpu" not in (parent / "cgroup.subtree_control").read_text().split():
        raise RuntimeError("CPU experiments require the delegated cpu controller")
    # Linux SCHED_OTHER, SCHED_BATCH and SCHED_IDLE use the fair scheduler.
    if scheduler not in {0, 3, 5}:
        raise RuntimeError("CPU bandwidth experiments require a fair-class scheduler")
    for ancestor in ancestors:
        value = ancestor.get("cpu.max")
        if value is None:
            raise RuntimeError("CPU ancestor bandwidth setting is unavailable")
        quota, period = value.split()
        if quota != "max":
            raise RuntimeError("Finite ancestor cpu.max interferes with controlled CPU experiments")
        if int(period) <= 0:
            raise RuntimeError("Invalid ancestor CPU period")
    return {"requested": dict(config), "scheduler": scheduler,
            "scope": "whole cgroup bandwidth ceiling; no reserved CPU capacity"}


def metrics(counters):
    result = {}
    cpu_stat = {key: int(value) for key, value in
                (line.split() for line in counters["cpu.stat"].splitlines())}
    for key, name, divisor, unit in (
        ("usage_usec", "cpu_usage", 1000000, "seconds"),
        ("user_usec", "cpu_user", 1000000, "seconds"),
        ("system_usec", "cpu_system", 1000000, "seconds"),
        ("nr_periods", "cpu_periods", 1, "count"),
        ("nr_throttled", "cpu_throttled_periods", 1, "count"),
        ("throttled_usec", "cpu_throttled", 1000000, "seconds"),
    ):
        available = key in cpu_stat
        result[name] = {"value": cpu_stat[key] / divisor if available else None,
                        "unit": unit, "method": f"cgroup_v2.cpu.stat.{key}",
                        "status": "available" if available else "unavailable"}
    local = {key: int(value) for key, value in
             (line.split() for line in counters.get("cpu.stat.local", "").splitlines())}
    available = "throttled_usec" in local
    result["cpu_local_throttled"] = {
        "value": local["throttled_usec"] / 1000000 if available else None,
        "unit": "seconds", "method": "cgroup_v2.cpu.stat.local.throttled_usec",
        "status": "available" if available else "unavailable"}
    return result


def sweep(manifest, quotas, *, period_usec=100000, memory_budget, repetitions=3,
          seed=0, trial=None):
    """Run a predeclared randomized quota grid at a fixed memory limit.

    No adaptive boundary or optimization acceptance is inferred from these trials.
    """
    from .contracts import validate
    from .frontier import Policy
    from .runner import run_trial

    validate(manifest, "experiment")
    Policy(**manifest["search"])
    if type(repetitions) is not int or not 1 <= repetitions <= 1000:
        raise ValueError("repetitions must be an integer between 1 and 1000")
    if not quotas or any(type(quota) is not int for quota in quotas) or len(set(quotas)) != len(quotas):
        raise ValueError("quotas must be distinct positive integer microsecond values")
    search = manifest["search"]
    if (type(memory_budget) is not int or memory_budget < search["minimum_budget"]
            or memory_budget % search["page_size"]):
        raise ValueError("fixed memory budget must be page aligned and at least the policy minimum")
    if type(seed) is not int:
        raise ValueError("schedule seed must be an integer")
    workload_ids = [workload["id"] for workload in manifest["workloads"]]
    if len(set(workload_ids)) != len(workload_ids):
        raise ValueError("workload IDs must be unique")
    seconds = manifest["limits"]["experiment_seconds"]
    if not math.isfinite(seconds):
        raise ValueError("experiment duration must be finite")
    plan = []
    for quota in quotas:
        selected = copy.deepcopy(manifest)
        selected["isolation"]["cpu"] = {"quota_usec": quota, "period_usec": period_usec}
        validate(selected, "experiment")
        for repetition in range(repetitions):
            for workload_id in workload_ids:
                plan.append((selected, workload_id, quota, repetition))
    if len(plan) > search["max_trials"]:
        raise ValueError("CPU sweep exceeds the total trial cap")
    random.Random(seed).shuffle(plan)
    result = {"kind": "cpu_bandwidth_sweep", "decision": "COMPLETED",
              "reason": "planned_points_complete", "seed": seed,
              "fixed_memory_budget_bytes": memory_budget, "period_usec": period_usec,
              "quotas_usec": list(quotas), "repetitions": repetitions,
              "planned_trials": len(plan), "attempted_trials": 0, "records": [],
              "limitations": ["CPU bandwidth ceilings are not reserved CPU capacity.",
                  "Timeout remains a wall-time outcome, not CPU-time exhaustion.",
                  "This grid is public exploration; no frontier or acceptance is inferred."]}
    deadline = time.monotonic() + seconds
    trial = run_trial if trial is None else trial
    for selected, workload_id, quota, repetition in plan:
        if time.monotonic() >= deadline:
            result.update(decision="STOP", reason="experiment_time_cap")
            break
        observation = trial(copy.deepcopy(selected), workload_id, memory_budget,
                            experiment_deadline=deadline)
        result["attempted_trials"] += 1
        validate(observation, "result")
        manifest_hash = hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest()
        if (observation["manifest_hash"] != manifest_hash
                or observation["candidate_hash"] != selected["target"]["rootfs_hash"]
                or observation["experiment_id"] != selected["experiment_id"]
                or observation["workload_id"] != workload_id
                or observation["phase"] != "exploration"
                or observation["requested_budget_bytes"] != memory_budget
                or observation["lifecycle"] != "FINALIZED"):
            result.update(decision="STOP", reason="invalid_trial_identity_or_lifecycle")
            break
        record = {"trial_id": observation["trial_id"], "workload_id": workload_id,
                  "quota_usec": quota, "repetition": repetition,
                  "manifest_hash": manifest_hash, "outcome": observation["outcome"],
                  "metrics": observation["metrics"]}
        result["records"].append(record)
        if observation["outcome"] not in {"pass", "timeout"}:
            result.update(decision="STOP", reason=observation["outcome"])
            break
        effective = observation["preflight_record"].get("effective", {})
        if (effective.get("cpu.max") != f"{quota} {period_usec}"
                or observation["effective_budget_bytes"] != memory_budget):
            result.update(decision="STOP", reason="effective_resource_limit_mismatch")
            break
        for name, unit in (("cpu_usage", "seconds"), ("cpu_user", "seconds"),
                           ("cpu_system", "seconds"), ("cpu_periods", "count"),
                           ("cpu_throttled_periods", "count"), ("cpu_throttled", "seconds")):
            metric = observation["metrics"].get(name, {})
            value = metric.get("value")
            if (metric.get("status") != "available" or metric.get("unit") != unit
                    or type(value) not in (int, float) or not math.isfinite(value)
                    or value < 0 or (name == "cpu_usage" and value == 0)):
                result.update(decision="STOP", reason="cpu_measurement_unavailable")
                break
        if result["decision"] == "STOP":
            break
    return result

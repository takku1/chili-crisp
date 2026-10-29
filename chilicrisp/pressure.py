"""Aggregate recorded trials without inferring unmeasured resource boundaries."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

from .runner import validate


def summarize(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f"Evidence directory does not exist: {directory}")
    groups = {}
    identities = set()
    for path in sorted(directory.rglob("result.json")):
        raw = path.read_bytes()
        result = json.loads(raw)
        validate(result, "result")
        identity = (result["experiment_id"], result["trial_id"])
        if identity in identities:
            raise ValueError(f"Duplicate trial identity: {identity}")
        identities.add(identity)
        # Pin the entire preflight record conservatively: different effective
        # host/ancestor constraints must never silently share a measured point.
        conditions = {name: result[name] for name in (
            "experiment_id", "candidate_hash", "manifest_hash", "workload_id",
            "measurement_mode", "phase", "requested_budget_bytes",
            "effective_budget_bytes", "preflight_record")}
        key = json.dumps(conditions, sort_keys=True, allow_nan=False)
        group = groups.setdefault(key, {"conditions": conditions, "trials": []})
        metrics = result["metrics"]
        for metric in metrics.values():
            if metric["status"] == "available" and not math.isfinite(metric["value"]):
                raise ValueError(f"Non-finite measurement in {path}")
        group["trials"].append({"trial_id": result["trial_id"],
            "path": path.relative_to(directory).as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "outcome": result["outcome"], "lifecycle": result["lifecycle"],
            "metrics": metrics})
    points = []
    for key in sorted(groups):
        group = groups[key]
        trials = group["trials"]
        group["outcomes"] = dict(sorted(Counter(t["outcome"] for t in trials).items()))
        group["measurements"] = {}
        for name in sorted({name for t in trials for name in t["metrics"]}):
            # Methods and units are separate measurement populations.
            populations = {}
            for trial in trials:
                metric = trial["metrics"].get(name)
                if metric and metric["status"] == "available" and trial["lifecycle"] == "FINALIZED":
                    populations.setdefault((metric["unit"], metric["method"]), []).append(metric["value"])
            group["measurements"][name] = [
                {"unit": unit, "method": method, "available_count": len(values),
                 "unavailable_count": len(trials) - len(values),
                 "values": values, "minimum": min(values),
                 "median": statistics.median(values), "maximum": max(values)}
                for (unit, method), values in sorted(populations.items())]
        points.append(group)
    return {"schema_version": "0.1", "kind": "observed_pressure_map",
            "trial_count": len(identities), "points": points,
            "limitations": ["Only recorded points; no interpolation or causal diagnosis.",
                "Raw artifacts and host enforcement require independent verification.",
                "Recovery-required measurements are excluded from statistics."]}

"""Native evaluation adapter: only the runner executes candidate source.

Runtime provisioning is owner work. This adapter never invokes project build,
test or benchmark commands on the host and never imports candidate modules.
"""
import copy
import json
from pathlib import Path
import time

from .contracts import validate
from .runner import file_hash, preflight, run_trial, tree_hash


class CleanupRequired(ValueError):
    """Unresolved execution or evaluator failures require owner recovery."""


def native(plan):
    return plan.get("evaluation", {}).get("backend") == "linux_cgroup"


def manifest(plan):
    value = json.loads(Path(plan["evaluation"]["manifest"]).read_text(encoding="utf-8"))
    validate(value, "experiment")
    if "source_mount" in value["target"]:
        raise ValueError("The development controller owns the candidate mount")
    ids = [workload["id"] for workload in value["workloads"]]
    if len(ids) != len(set(ids)) or plan["evaluation"]["benchmark_workload"] not in ids:
        raise ValueError("Native workload IDs must be unique and include the benchmark")
    return value


def identities(plan):
    value = manifest(plan)
    result = {"manifest": file_hash(plan["evaluation"]["manifest"]),
              "runtime": tree_hash(value["target"]["rootfs"]), "adapter": file_hash(__file__)}
    from . import runner, seccomp, capture, lifecycle, cpu, fields, oracles
    for module in (runner, seccomp, capture, lifecycle, cpu, fields, oracles):
        result[module.__name__] = file_hash(module.__file__)
    if result["runtime"] != value["target"]["rootfs_hash"]:
        raise ValueError("Native runtime identity mismatch")
    for workload in value["workloads"]:
        digest = file_hash(workload["input"])
        if digest != workload["input_hash"]:
            raise ValueError("Native input identity mismatch")
        result[workload["id"] + ":input"] = digest
        if "oracle" in workload:
            oracle = workload["oracle"]
            digest = file_hash(oracle["policy_path"])
            if digest != oracle["policy_hash"]:
                raise ValueError("Native oracle identity mismatch")
            result[workload["id"] + ":oracle"] = digest
            policy = json.loads(Path(oracle["policy_path"]).read_text())
            if "reference_path" in policy:
                digest = file_hash(policy["reference_path"])
                if digest != policy["reference_hash"]:
                    raise ValueError("Native field reference identity mismatch")
                result[workload["id"] + ":reference"] = digest
    return result


def prepare(plan, project):
    if not native(plan):
        if plan["objective"] in {"enforced_budget_bytes", "native_memory_peak_bytes"}:
            raise ValueError("Native metrics require the linux_cgroup backend")
        return
    if project["build"] is not None:
        raise ValueError("Native source evaluation does not support build commands")
    if plan["objective"] != "enforced_budget_bytes" or plan["artifact_paths"]:
        raise ValueError("Native development currently requires enforced_budget_bytes without artifacts")
    if set(plan["regression_limits"]) - {"wall_seconds", "native_memory_peak_bytes"}:
        raise ValueError("Unsupported native regression metric")
    value = manifest(plan)
    page = value["search"]["page_size"]
    if any(number % page for number in
           (plan["quantum"], plan["minimum_target"], plan["evaluation"]["initial_budget"])):
        raise ValueError("Native targets and initial budget must be page aligned")
    destination = Path(value["target"]["rootfs"]) / "candidate"
    if destination.is_symlink() or not destination.is_dir() or any(destination.iterdir()):
        raise ValueError("Native runtime requires an empty real /candidate directory")
    identities(plan)
    preflight(value, plan["evaluation"]["initial_budget"])


def ensure_clean(root):
    """All per-trial directories share one recovery boundary for the session."""
    root = Path(root)
    for path in root.rglob("lifecycle.json"):
        if json.loads(path.read_text())["state"] != "FINALIZED":
            raise CleanupRequired("Unfinished native lifecycle requires recovery: " + str(path))
    for path in root.rglob("emergency.json"):
        journal = path.parent / "lifecycle.json"
        saved = json.loads(journal.read_text()) if journal.exists() else {}
        if saved.get("state") != "FINALIZED" or not saved.get("recovery"):
            raise CleanupRequired("Native emergency diagnostic requires recovery: " + str(path))


def trial(plan, source, output, budget, deadline, workload=None, *, evidence_root=None):
    if time.monotonic() >= deadline:
        raise ValueError("Native experiment deadline exhausted")
    ensure_clean(evidence_root or output)
    value = copy.deepcopy(manifest(plan))
    source = Path(source).resolve()
    digest = tree_hash(source)
    value["target"].update(source_hash=digest, source_mount={"path": str(source), "tree_hash": digest})
    value["evidence_directory"] = str(Path(evidence_root or output).resolve())
    result = run_trial(value, workload or plan["evaluation"]["benchmark_workload"],
                       int(budget), experiment_deadline=deadline)
    validate(result, "result")
    if result["outcome"] == "cleanup_failure" or result["lifecycle"] != "FINALIZED":
        raise CleanupRequired("Native trial requires cleanup; inspect its lifecycle journal")
    # Environment/setup failures are not optimization failures; stop the session.
    if result["outcome"] in {"unsupported", "runner_failure"}:
        raise CleanupRequired("Native evaluator failed; inspect evidence before recovery: " + str(result["error"]))
    if result["outcome"] == "pass" and result["effective_budget_bytes"] != int(budget):
        raise CleanupRequired("Native effective memory budget differs from the controller request")
    return result


def measurement(plan, source, output, budget, deadline, *, evidence_root=None):
    result = trial(plan, source, output, budget, deadline, evidence_root=evidence_root)
    if result["outcome"] != "pass":
        raise ValueError("Native benchmark failed: " + result["outcome"])
    metrics = {"enforced_budget_bytes": int(budget),
               "native_memory_peak_bytes": result["metrics"]["memory_peak"]["value"],
               "wall_seconds": result["metrics"]["elapsed"]["value"]}
    # The runner owns the output oracle. Its raw result and lifecycle remain in output.
    record = {"outcome": "pass", "metrics": metrics, "enforcement": "linux_cgroup",
              "metric_quality": {"enforced_budget_bytes": {"tier": "enforced_survival", "scope": "passed declared workload at this limit; not a minimum boundary"},
                  "native_memory_peak_bytes": {"tier": "kernel_accounting", "scope": "cgroup charged memory.peak; qualified warm cache"},
                  "wall_seconds": {"tier": "repeated_timing", "scope": "runner elapsed under the declared memory budget"}},
              "trial_id": result["trial_id"], "capture": {"stdout": {
                  "sha256": result["artifact_hashes"]["stdout"]}}}
    Path(output).mkdir(parents=True, exist_ok=evidence_root is None)
    (Path(output) / "measurement.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record

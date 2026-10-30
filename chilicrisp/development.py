"""Resumable measured development: agent proposals, controller-owned decisions.

This is an owner-controlled local experiment loop, not automatic production
promotion. The caller supplies research/code; this module owns the moving target.
"""
from contextlib import contextmanager
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import statistics
import sys
import time
import uuid

import psutil

from .contracts import validate
from .evidence import verify
from .measure import METRIC_QUALITY, environment, measure
from .project import EXCLUDED, compare, execute, initialize, load_project, protected_contract, snapshot
from .runner import file_hash
from . import evaluation


CleanupRequired = evaluation.CleanupRequired


def identity(root):
    root = Path(root)
    digest = hashlib.sha256()

    def error(failure):
        raise failure

    for current, directories, files in os.walk(root, followlinks=False, onerror=error):
        current = Path(current)
        directories[:] = sorted(name for name in directories if name not in EXCLUDED
                                 and not name.endswith(".egg-info"))
        for name in [*directories, *sorted(files)]:
            path = current / name
            if path.is_symlink() or path.is_junction():
                raise ValueError("Source links are unsupported")
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                item = [relative, "directory"]
            elif path.is_file():
                item = [relative, path.stat().st_mode, file_hash(path)]
            else:
                raise ValueError("Special source file is unsupported")
            digest.update(json.dumps(item).encode("utf-8") + b"\n")
    return digest.hexdigest()


def _save(directory, state):
    temporary = directory / "state.tmp"
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(state, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, directory / "state.json")


def status(directory):
    state = json.loads((Path(directory) / "state.json").read_text(encoding="utf-8"))
    if state.get("kind") != "measured_development_session":
        raise ValueError("Not a development session")
    return state


@contextmanager
def _lock(directory):
    path = directory / "controller.lock"
    try:
        with path.open("x", encoding="ascii") as stream:
            stream.write(str(os.getpid()))
    except FileExistsError:
        raise ValueError("Session is locked; inspect its owner before explicit recovery") from None
    try:
        yield
    finally:
        path.unlink()


def _plan(path):
    path = Path(path).resolve()
    plan = json.loads(path.read_text(encoding="utf-8"))
    validate(plan, "development")
    seconds = plan["objective"].endswith("seconds")
    defaults = {"artifact_paths": [], "regression_limits": {"wall_seconds": .15},
        "reductions": [.25, .1, .05], "quantum": .001 if seconds else 1,
        "minimum_target": .001 if seconds else 1, "repetitions": 3,
        "confirmation_repetitions": 3, "max_generations": 10, "max_stagnation": 3,
        "max_commands": 200, "wall_seconds": 3600, "seed": 0}
    plan = {**defaults, **plan}
    validate(plan, "development")
    for value in [plan["quantum"], plan["minimum_target"], plan["wall_seconds"],
                  *plan["reductions"], *plan["regression_limits"].values()]:
        if not math.isfinite(value):
            raise ValueError("Development policy numbers must be finite")
    if plan["reductions"] != sorted(plan["reductions"], reverse=True):
        raise ValueError("Failure reductions must progress from larger to smaller steps")
    if plan["objective"] == "artifact_bytes" and not plan["artifact_paths"]:
        raise ValueError("Artifact objective needs explicit artifact paths")
    project, root = load_project(path.parent / plan["project_config"])
    if not project["protected_paths"]:
        raise ValueError("Development sessions require explicit protected correctness files")
    if evaluation.native(plan):
        plan["evaluation"]["manifest"] = str((path.parent / plan["evaluation"]["manifest"]).resolve())
        if "build" in plan["evaluation"]:
            plan["evaluation"]["build"]["manifest"] = str((path.parent / plan["evaluation"]["build"]["manifest"]).resolve())
    elif "acceptance" in plan:
        raise ValueError("Sealed acceptance currently requires the native source-only backend")
    evaluation.prepare(plan, project)
    return plan, project, root


def _remaining(state):
    remaining = state["deadline_epoch"] - time.time()
    if remaining > state["plan"]["wall_seconds"] + 1:
        raise ValueError("System clock moved backwards; session deadline cannot be trusted")
    return max(0, remaining)


def _runtime_identities(plan, project):
    if evaluation.native(plan):
        return evaluation.identities(plan)
    result = {}
    for label, command in (("benchmark", plan["benchmark_command"]),
                           ("test", project["test"]), ("build", project["build"])):
        if command is None:
            continue
        executable = shutil.which(command[0])
        if executable is None:
            raise ValueError("Command executable is unavailable: " + command[0])
        path = Path(executable).resolve()
        # Microsoft Store Python exposes an executable alias that cannot be
        # opened as a regular file. Pin the actual running interpreter instead.
        if os.path.normcase(str(path)) == os.path.normcase(str(Path(sys.executable).resolve())):
            path = Path(psutil.Process().exe()).resolve()
        result[label] = {"path": str(path), "sha256": file_hash(path)}
    return result


def _reserve(directory, state, commands, action):
    if state["pending"] is not None:
        raise ValueError("Interrupted action requires explicit recovery; it will not be replayed")
    if _remaining(state) <= 0 or state["reserved_commands"] + commands > state["plan"]["max_commands"]:
        state.update(state="STOPPED", stop_reason="experiment_budget_exhausted")
        _save(directory, state)
        raise ValueError("Experiment wall/command budget is exhausted")
    state["reserved_commands"] += commands
    state["pending"] = {"id": uuid.uuid4().hex, "action": action, "reserved_commands": commands}
    state["state"] = "EVALUATING"
    _save(directory, state)


def _champion(directory, state):
    if state.get("controller_sha256") != file_hash(__file__):
        raise ValueError("Controller implementation changed; start a new lineage")
    champion = state["champions"][state["champion"]]
    root = directory / champion["source"]
    if identity(root) != champion["source_hash"]:
        raise ValueError("Frozen champion source has changed")
    return champion, root


def _candidate_budget(state):
    """Scarcity enforces the target; the measured-peak arm keeps one fixed ceiling."""
    if state["plan"]["objective"] == "native_memory_peak_bytes":
        return state["plan"]["evaluation"]["initial_budget"]
    return state["target"]


def _target(state):
    plan = state["plan"]
    champion = state["champions"][state["champion"]]
    value = champion["metrics"][plan["objective"]]
    reduction = plan["reductions"][min(state["stagnation"], len(plan["reductions"]) - 1)]
    target = max(plan["minimum_target"], math.floor(value * (1 - reduction) / plan["quantum"]) * plan["quantum"])
    if target >= value:
        state.update(state="STOPPED", stop_reason="minimum_or_resolution_reached", target=None)
    else:
        state.update(state="AWAITING_CANDIDATE", target=target)


def _experiment_memory(state, limit=8):
    """Bounded observations for proposers; never treat research claims as results."""
    attempts = []
    for generation in state["generations"][-limit:]:
        attempts.append({key: generation[key] for key in
            ("id", "parent", "source_hash", "target", "decision", "reason", "repeat_of")
            if key in generation})
        attempts[-1]["measurements"] = {phase: values["medians"]
            for phase, values in generation.get("phases", {}).items() if "medians" in values}
        if "pressure_probe" in generation:
            attempts[-1]["pressure_probe"] = {key: generation["pressure_probe"][key]
                for key in ("outcome", "requested_budget_bytes", "effective_budget_bytes", "metrics")}
    return {"scope": "public session observations only; research claims are not measured evidence",
        "total_attempts": len(state["generations"]), "omitted_attempts": max(0, len(state["generations"]) - limit),
        "attempts": attempts}


def request(directory):
    directory = Path(directory).resolve()
    state = status(directory)
    if state["pending"] is not None:
        raise ValueError("Resolve the interrupted action before requesting another candidate")
    if state["state"] != "AWAITING_CANDIDATE":
        raise ValueError("Session is not awaiting a candidate")
    champion, root = _champion(directory, state)
    return {"kind": "development_request", "generation": len(state["generations"]) + 1,
        "concept": state["plan"]["concept"], "champion_source": str(root),
        "champion_source_hash": champion["source_hash"], "objective": state["plan"]["objective"],
        "measured_baseline": champion["metrics"], "target": state["target"],
        "target_basis": ("enforced Linux cgroup memory budget; public correctness and repeated survival"
            if evaluation.native(state["plan"]) else "median local measurements; no scarcity limit is enforced"),
        "regression_limits": state["plan"]["regression_limits"],
        "protected_paths": state["project"]["protected_paths"],
        "previous_attempt": state["generations"][-1] if state["generations"] else None,
        "experiment_memory": _experiment_memory(state),
        "instructions": ["Research the limiting work and record source references and a falsifiable hypothesis.",
            "Create a separate candidate source directory and preserve the protected behavior.",
            "Use public experiment memory to avoid failed approaches; explain intentional retries under changed targets.",
            "Submit the candidate plus research JSON; the controller owns all measurements and decisions."]}


def _correctness(directory, state, candidate, action):
    _, root = _champion(directory, state)
    if evaluation.native(state["plan"]):
        output = directory / "runs" / action
        output.mkdir(parents=True, exist_ok=False)
        records = []
        for name, source in (("baseline", root), ("candidate", candidate)):
            workspace = output / name
            snapshot(source, workspace)
            if protected_contract(workspace, state["project"]["protected_paths"]) != state["correctness_contract"]:
                raise ValueError("Native candidate changed protected correctness files")
            budget = (state["champions"][state["champion"]]["metrics"] or {}).get(
                "enforced_budget_bytes", state["plan"]["evaluation"]["initial_budget"])
            if name == "candidate" and (state.get("pending") or {}).get("action") == "candidate":
                budget = _candidate_budget(state)
            for workload in evaluation.manifest(state["plan"])["workloads"]:
                result = evaluation.trial(state["plan"], workspace,
                    output / (name + "-" + str(len(records))), budget,
                    time.monotonic() + _remaining(state), workload["id"], evidence_root=directory / "native-evidence")
                records.append(result)
                if result["outcome"] != "pass":
                    record = output / "native-correctness.json"
                    record.write_text(json.dumps(records, indent=2), encoding="utf-8")
                    return record, {"decision": "correctness_failed"}
        record = output / "native-correctness.json"
        record.write_text(json.dumps(records, indent=2), encoding="utf-8")
        return record, {"decision": "public_tests_passed"}
    config = initialize(root, state["project"]["test"], state["project"]["build"],
                        protected_paths=state["project"]["protected_paths"]) if not (root / ".chilicrisp/project.json").exists() else root / ".chilicrisp/project.json"
    # The immutable owner policy, including time/output limits, owns this config.
    project = {**state["project"], "root": ".."}
    config.write_text(json.dumps(project, indent=2), encoding="utf-8")
    record, result = compare(config, candidate, directory / "runs" / action,
        trusted_local=True, experiment_deadline=time.monotonic() + _remaining(state))
    if any(evaluation.get("outcome") == "cleanup_failure" for evaluation in result["evaluations"].values()):
        raise CleanupRequired("Correctness execution needs process cleanup before another attempt")
    if not verify(record)["valid"]:
        raise ValueError("Correctness comparison evidence failed verification")
    return record, result


def _bench(directory, state, workspace, output, expected_stdout=None, expected_source=None, budget=None):
    if expected_source is not None and identity(workspace) != expected_source:
        raise ValueError("Build/test changed source outside declared build/cache directories")
    before = protected_contract(workspace, state["project"]["protected_paths"])
    if before != state["correctness_contract"]:
        raise ValueError("Benchmark workspace correctness contract differs")
    if evaluation.native(state["plan"]):
        result = evaluation.measurement(state["plan"], workspace, output,
            budget or state["plan"]["evaluation"]["initial_budget"], time.monotonic() + _remaining(state),
            evidence_root=directory / "native-evidence")
    else:
        result = measure(state["plan"]["benchmark_command"], workspace, output,
            state["project"], time.monotonic() + _remaining(state), state["plan"]["artifact_paths"])
    if result["outcome"] == "cleanup_failure":
        raise CleanupRequired("Benchmark execution needs process cleanup before another attempt")
    if result["outcome"] != "pass":
        raise ValueError("Benchmark command failed: " + result["outcome"])
    if protected_contract(workspace, state["project"]["protected_paths"]) != before:
        raise ValueError("Benchmark changed protected correctness files")
    if expected_source is not None and identity(workspace) != expected_source:
        raise ValueError("Benchmark changed source outside declared build/cache directories")
    digest = result["capture"]["stdout"]["sha256"]
    if expected_stdout is not None and digest != expected_stdout:
        raise ValueError("Benchmark output differs from the frozen baseline")
    for metric in {state["plan"]["objective"], *state["plan"]["regression_limits"]}:
        value = result["metrics"][metric]
        if value is None or not math.isfinite(value) or value < 0:
            raise ValueError("Required benchmark metric unavailable: " + metric)
        if metric.startswith("sampled_") and (result["samples"] < 3 or (
                metric in {"sampled_cpu_seconds", "sampled_peak_rss_bytes"} and value == 0)):
            raise ValueError("Workload is too short for the required sampled metric; batch more work")
    return result


def _medians(records):
    return {metric: statistics.median(record["metrics"][metric] for record in records)
            if all(record["metrics"][metric] is not None for record in records) else None
            for metric in records[0]["metrics"]}


def _verification(plan, baseline=False):
    if evaluation.native(plan):
        return {"public": "native_baseline" if baseline else "native_budget_confirmation",
                "sealed": "not_run", "production": "not_accepted"}
    sampled = METRIC_QUALITY[plan["objective"]]["tier"] == "screening_sample"
    public = ("baseline_sampled" if sampled else "baseline_public") if baseline else (
        "sampled_screening" if sampled else "public_confirmation")
    return {"public": public, "sealed": "not_run", "production": "not_accepted"}


def _finish(directory, state):
    state["pending"] = None
    if len(state["generations"]) >= state["plan"]["max_generations"]:
        state.update(state="STOPPED", stop_reason="generation_cap")
    elif state["stagnation"] >= state["plan"]["max_stagnation"]:
        state.update(state="STOPPED", stop_reason="stagnation_cap")
    elif _remaining(state) <= 0:
        state.update(state="STOPPED", stop_reason="wall_cap")
    else:
        _target(state)
    _save(directory, state)


def create(plan_path, directory, *, trusted_local=False):
    created = time.time()
    plan, project, root = _plan(plan_path)
    if not trusted_local and not evaluation.native(plan):
        raise ValueError("Development runs need --trusted-local host execution")
    directory = Path(directory).resolve()
    if directory == root or root.is_relative_to(directory) or (
            directory.is_relative_to(root) and directory.relative_to(root).parts[0] not in EXCLUDED):
        raise ValueError("Session must be outside source or inside an excluded directory")
    directory.mkdir(parents=True, exist_ok=False)
    source = directory / "champions" / "initial"
    source.parent.mkdir()
    state = {"schema_version": "0.1", "kind": "measured_development_session", "state": "STARTING",
        "lineage_id": uuid.uuid4().hex, "acceptances": [],
        "plan": plan, "project": project, "environment": environment(),
        "runtime_identities": _runtime_identities(plan, project),
        "controller_sha256": file_hash(__file__),
        "created_epoch": created, "deadline_epoch": created + plan["wall_seconds"],
        "reserved_commands": 0, "pending": None, "stagnation": 0, "target": None,
        "champion": 0, "champions": [{"id": "initial", "source": "champions/initial",
            "source_hash": None, "metrics": None}], "generations": [], "events": [],
        "correctness_contract": None}
    _save(directory, state)
    with _lock(directory):
        correctness_count = (2 * len(evaluation.manifest(plan)["workloads"]) if evaluation.native(plan)
                             else 2 * (1 + (project["build"] is not None)))
        _reserve(directory, state, correctness_count + plan["repetitions"] + evaluation.build_reservation(plan), "baseline")
        try:
            source_hash = snapshot(root, source)
            state["champions"][0]["source_hash"] = source_hash
            state["correctness_contract"] = protected_contract(source, project["protected_paths"])
            _save(directory, state)
            record, result = _correctness(directory, state, source, "baseline")
            if result["decision"] != "public_tests_passed":
                raise ValueError("Initial baseline correctness failed")
            workspace = record.parent / "baseline"
            observations = []
            for index in range(plan["repetitions"]):
                observation = _bench(directory, state, workspace, record.parent / f"measure-{index}",
                    observations[0]["capture"]["stdout"]["sha256"] if observations else None,
                    expected_source=source_hash)
                observations.append(observation)
            state["stdout_hash"] = observations[0]["capture"]["stdout"]["sha256"]
            state["champions"][0].update(metrics=_medians(observations),
                verification=_verification(plan, baseline=True),
                correctness_record=str(record.relative_to(directory)))
            state["events"].append({"kind": "baseline_measured", "source_hash": source_hash})
            _finish(directory, state)
        except BaseException as error:
            state.update(state="INTERRUPTED", error=f"{type(error).__name__}: {error}")
            _save(directory, state)
            raise
    return state


def submit(directory, candidate, research_path, *, trusted_local=False,
           expected_generation=None, expected_parent=None):
    directory = Path(directory).resolve()
    if Path(research_path).stat().st_size > 1048576:
        raise ValueError("Research record exceeds 1 MiB")
    research = json.loads(Path(research_path).read_text(encoding="utf-8"))
    validate(research, "research")
    with _lock(directory):
        state = status(directory)
        if not trusted_local and not evaluation.native(state["plan"]):
            raise ValueError("Development runs need --trusted-local host execution")
        if state["state"] != "AWAITING_CANDIDATE" or state["pending"] is not None:
            raise ValueError("Session is not ready for a candidate")
        if environment() != state["environment"]:
            raise ValueError("Measurement environment changed; start a new lineage")
        if _runtime_identities(state["plan"], state["project"]) != state["runtime_identities"]:
            raise ValueError("Command runtime changed; start a new lineage")
        champion, _ = _champion(directory, state)
        if ((expected_generation is not None and expected_generation != len(state["generations"]) + 1)
                or (expected_parent is not None and expected_parent != champion["source_hash"])):
            raise ValueError("Proposal belongs to an earlier session request")
        plan = state["plan"]
        correctness_count = (2 * len(evaluation.manifest(plan)["workloads"]) + 1 if evaluation.native(plan)
                             else 2 * (1 + (state["project"]["build"] is not None)))
        reserve = correctness_count + evaluation.build_reservation(plan) + 2 * (
            plan["repetitions"] + plan["confirmation_repetitions"])
        _reserve(directory, state, reserve, "candidate")
        generation = {"id": len(state["generations"]) + 1, "parent": champion["id"],
            "target": state["target"], "research": research, "evidence_stage": "proposed",
            "decision": "rejected", "phases": {}}
        state["pending"]["generation"] = generation
        _save(directory, state)
        action = f"generation-{generation['id']}-{state['pending']['id']}"
        frozen = directory / "candidates" / action
        frozen.parent.mkdir(exist_ok=True)
        try:
            if not Path(candidate).is_dir():
                raise ValueError("Candidate source directory is missing")
            generation["source_hash"] = snapshot(Path(candidate).resolve(), frozen)
            generation["repeat_of"] = [previous["id"] for previous in state["generations"]
                if previous.get("source_hash") == generation["source_hash"]]
            generation["source"] = str(frozen.relative_to(directory))
            _save(directory, state)
            if evaluation.native(plan) and plan["objective"] == "enforced_budget_bytes":
                generation["pressure_probe"] = evaluation.trial(plan,
                    directory / champion["source"], directory / "runs" / (action + "-pressure"),
                    state["target"], time.monotonic() + _remaining(state), evidence_root=directory / "native-evidence")
                _save(directory, state)
            record, comparison = _correctness(directory, state, frozen, action)
            generation["correctness_record"] = str(record.relative_to(directory))
            if comparison["decision"] != "public_tests_passed":
                raise ValueError("Candidate correctness comparison failed")
            workspaces = {name: record.parent / name for name in ("baseline", "candidate")}
            randomizer = random.Random(plan["seed"] + generation["id"])
            for phase, repetitions in (("exploration", plan["repetitions"]),
                                       ("confirmation", plan["confirmation_repetitions"])):
                observations = {"baseline": [], "candidate": []}
                generation["phases"][phase] = {"records": []}
                for block in range(repetitions):
                    order = ["baseline", "candidate"]
                    randomizer.shuffle(order)
                    for name in order:
                        output = record.parent / f"{phase}-{block}-{name}"
                        result = _bench(directory, state, workspaces[name], output, state["stdout_hash"],
                            expected_source=champion["source_hash"] if name == "baseline" else generation["source_hash"],
                            budget=(_candidate_budget(state) if name == "candidate" else champion["metrics"].get("enforced_budget_bytes")))
                        observations[name].append(result)
                        generation["phases"][phase]["records"].append(
                            {"variant": name, "block": block, "measurement": str((output / "measurement.json").relative_to(directory))})
                medians = {name: _medians(values) for name, values in observations.items()}
                generation["phases"][phase]["medians"] = medians
                if medians["candidate"][plan["objective"]] > state["target"]:
                    raise ValueError("Measured candidate did not meet the resource target")
                for metric, regression in plan["regression_limits"].items():
                    if medians["candidate"][metric] > medians["baseline"][metric] * (1 + regression):
                        raise ValueError("Measured regression exceeds policy: " + metric)
            _champion(directory, state)
            if identity(frozen) != generation["source_hash"]:
                raise ValueError("Frozen candidate source changed during evaluation")
            generation.update(decision="accepted_experimental", evidence_stage="measured",
                              verification=_verification(plan))
            state["champions"].append({"id": action, "source": generation["source"],
                "source_hash": generation["source_hash"],
                "verification": _verification(plan),
                "metrics": generation["phases"]["confirmation"]["medians"]["candidate"]})
            state["champion"] = len(state["champions"]) - 1
            state["stagnation"] = 0
        except evaluation.CleanupRequired as error:
            state.update(state="INTERRUPTED", error=str(error))
            _save(directory, state)
            raise
        except Exception as error:
            generation["reason"] = f"{type(error).__name__}: {error}"
            state["stagnation"] += 1
        except BaseException as error:
            state.update(state="INTERRUPTED", error=f"{type(error).__name__}: {error}")
            _save(directory, state)
            raise
        state["generations"].append(generation)
        state["events"].append({"kind": generation["decision"], "generation": generation["id"],
                                "champion": state["champions"][state["champion"]]["id"]})
        _finish(directory, state)
        return state


def recover(directory, *, owner_stopped=False):
    if not owner_stopped:
        raise ValueError("Check that no executor owns this session, then supply --owner-stopped")
    directory = Path(directory).resolve()
    if evaluation.native(status(directory)["plan"]):
        evaluation.ensure_clean(directory / "native-evidence")
    stale = directory / "controller.lock"
    if stale.exists():
        stale.unlink()
    with _lock(directory):
        state = status(directory)
        if state["pending"] is None:
            raise ValueError("Session has no interrupted action")
        state["events"].append({"kind": "interrupted_action_discarded", "action": state["pending"]})
        if state["pending"]["action"] == "baseline":
            state.update(state="STOPPED", stop_reason="interrupted_baseline", pending=None)
            _save(directory, state)
        else:
            _champion(directory, state)
            if state["pending"]["action"] == "candidate":
                generation = state["pending"].get("generation", {
                    "id": len(state["generations"]) + 1, "phases": {}})
                generation.update(decision="interrupted", reason="Owner discarded an interrupted action")
                state["generations"].append(generation)
            state["stagnation"] += 1
            _finish(directory, state)
        return state


def rollback(directory, champion_id, reason, *, trusted_local=False):
    if not reason.strip():
        raise ValueError("Rollback requires a recorded reason")
    directory = Path(directory).resolve()
    with _lock(directory):
        state = status(directory)
        if state.get("acceptances"):
            raise ValueError("Final acceptance is terminal; start a new lineage for further work")
        if not trusted_local and not evaluation.native(state["plan"]):
            raise ValueError("Rollback requires --trusted-local for host execution")
        if state["pending"] is not None:
            raise ValueError("Recover the interrupted action before rollback")
        if environment() != state["environment"]:
            raise ValueError("Measurement environment changed; start a new lineage")
        if _runtime_identities(state["plan"], state["project"]) != state["runtime_identities"]:
            raise ValueError("Command runtime changed; start a new lineage")
        selected = next((index for index, champion in enumerate(state["champions"])
                         if champion["id"] == champion_id), None)
        if selected is None:
            raise ValueError("Rollback target is not a retained champion")
        target = copy.deepcopy(state)
        target["champion"] = selected
        champion, source = _champion(directory, target)
        correctness_count = (2 * len(evaluation.manifest(state["plan"])["workloads"])
            if evaluation.native(state["plan"]) else 2 * (1 + (state["project"]["build"] is not None)))
        _reserve(directory, state, correctness_count + evaluation.build_reservation(state["plan"])
                 + state["plan"]["repetitions"], "rollback")
        action = "rollback-" + state["pending"]["id"]
        try:
            record, result = _correctness(directory, target, source, action)
            if result["decision"] != "public_tests_passed":
                raise ValueError("Retained champion no longer passes correctness")
            observations = [_bench(directory, state, record.parent / "candidate",
                record.parent / f"measure-{index}", state["stdout_hash"], champion["source_hash"],
                budget=champion["metrics"].get("enforced_budget_bytes"))
                for index in range(state["plan"]["repetitions"])]
            state["champions"].append({**champion, "id": action, "metrics": _medians(observations),
                                        "verification": _verification(state["plan"], baseline=True),
                                        "rollback_of": champion_id})
            state["champion"] = len(state["champions"]) - 1
            state["stagnation"] = 0
            state["events"].append({"kind": "rollback", "champion": action,
                                    "previous_artifact": champion_id, "reason": reason})
            _finish(directory, state)
        except BaseException as error:
            state.update(state="INTERRUPTED", error=f"{type(error).__name__}: {error}")
            _save(directory, state)
            raise
        return state


def acceptance_request(directory):
    directory = Path(directory).resolve()
    state = status(directory)
    if "acceptance" not in state["plan"] or not evaluation.native(state["plan"]):
        raise ValueError("Session has no pinned sealed acceptance policy")
    if state["pending"] is not None or state.get("acceptances"):
        raise ValueError("Resolve pending work; final acceptance is allowed only once")
    champion, source = _champion(directory, state)
    if champion["verification"]["public"] != "native_budget_confirmation":
        raise ValueError("Final acceptance needs an experimentally retained native candidate")
    initial = state["champions"][0]
    baseline = directory / initial["source"]
    if identity(baseline) != initial["source_hash"]:
        raise ValueError("Initial baseline source changed")
    expected = {**state["plan"]["acceptance"], "lineage_id": state["lineage_id"],
                "baseline_source_hash": initial["source_hash"], "candidate_source_hash": champion["source_hash"]}
    return {"kind": "sealed_acceptance_request", "baseline_source": str(baseline),
            "candidate_source": str(source), "expected": expected}


def export_acceptance_request(directory, destination):
    """Copy frozen sources beside a relative request for a grader on another account or host.

    The copies carry no trust: the grader re-snapshots them against the pinned hashes.
    """
    from .project import snapshot
    request = acceptance_request(directory)
    destination = Path(destination)
    destination.mkdir()
    for name in ("baseline", "candidate"):
        if snapshot(Path(request[name + "_source"]), destination / name) != request["expected"][name + "_source_hash"]:
            raise ValueError("Exported source differs from its frozen identity")
        request[name + "_source"] = name
    with (destination / "request.json").open("x", encoding="utf-8") as stream:
        json.dump(request, stream, indent=2)
    return request


def accept(directory, receipt_path):
    from .acceptance import verify_receipt
    directory = Path(directory).resolve()
    if Path(receipt_path).stat().st_size > 32768:
        raise ValueError("Acceptance receipt exceeds 32 KiB")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    with _lock(directory):
        requested = acceptance_request(directory)
        verdict = verify_receipt(receipt, requested["expected"])
        state = status(directory)
        champion, _ = _champion(directory, state)
        state["acceptances"].append(receipt)
        champion["verification"].update(sealed=verdict, transfer=verdict)
        champion["acceptance_state"] = "verified_champion" if verdict == "passed" else "experimental_champion"
        state.update(state="STOPPED", stop_reason="final_acceptance_" + verdict)
        state["events"].append({"kind": "final_acceptance", "verdict": verdict,
            "receipt_sha256": file_hash(receipt_path), "candidate_source_hash": champion["source_hash"]})
        _save(directory, state)
        return state


def run(directory, agent_command, *, trusted_local=False):
    """Drive the same request/submit protocol with a caller-selected agent CLI.

    The command receives {request}, {response}, {workspace} argument tokens. Its
    response must be research-schema JSON; code edits stay in the proposal copy.
    """
    if not trusted_local or not isinstance(agent_command, list) or not agent_command or any(
            not isinstance(argument, str) or not argument for argument in agent_command):
        raise ValueError("Agent execution requires --trusted-local and a JSON command array")
    directory = Path(directory).resolve()
    while True:
        state = status(directory)
        if state["state"] == "STOPPED":
            return state
        if state["state"] != "AWAITING_CANDIDATE":
            raise ValueError("Resolve the interrupted action before running an agent")
        with _lock(directory):
            state = status(directory)
            proposal = request(directory)
            _reserve(directory, state, 1, "agent")
            action = directory / "runs" / ("agent-" + state["pending"]["id"])
            action.mkdir(parents=True)
            workspace = action / "proposal"
            _, champion = _champion(directory, state)
            snapshot(champion, workspace)
            proposal["candidate_workspace"] = str(workspace)
            proposal["response_format"] = "research.schema.json: hypothesis, mechanism, falsification, sources"
            request_file, response_file = action / "request.json", action / "research.json"
            request_file.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
            replacements = {"{request}": str(request_file), "{response}": str(response_file),
                            "{workspace}": str(workspace)}
            command = [replacements.get(argument, argument) for argument in agent_command]
            try:
                execution = execute(command, workspace, action / "command", state["project"],
                                    time.monotonic() + _remaining(state))
                if execution["outcome"] != "pass":
                    raise ValueError("Agent command failed: " + execution["outcome"])
                if response_file.stat().st_size > 1048576:
                    raise ValueError("Agent response exceeds 1 MiB")
                research = json.loads(response_file.read_text(encoding="utf-8"))
                validate(research, "research")
                _champion(directory, state)
                state["events"].append({"kind": "agent_proposal", "request": str(request_file.relative_to(directory)),
                                        "response": str(response_file.relative_to(directory))})
                state["pending"] = None
                state["state"] = "AWAITING_CANDIDATE"
                _save(directory, state)
            except BaseException as error:
                state.update(state="INTERRUPTED", error=f"{type(error).__name__}: {error}")
                _save(directory, state)
                raise
        # A competing controller may acquire the lock between these actions.
        state = submit(directory, workspace, response_file, trusted_local=True,
                       expected_generation=proposal["generation"],
                       expected_parent=proposal["champion_source_hash"])

"""Trusted local build/test comparisons, separate from isolated pressure trials."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import uuid

from .capture import capture
from .contracts import validate
from .evidence import seal
from .runner import file_hash


EXCLUDED = {".git", ".chilicrisp", ".venv", "venv", "__pycache__", ".pytest_cache",
            ".ruff_cache", "build", "dist", "artifacts", "node_modules", "target"}


def load_project(path):
    path = Path(path).resolve()
    value = json.loads(path.read_text(encoding="utf-8"))
    validate(value, "project")
    for name in ("command_seconds", "comparison_seconds"):
        if not math.isfinite(value[name]):
            raise ValueError(f"{name} must be finite")
    root = (path.parent / value["root"]).resolve()
    if not root.is_dir():
        raise ValueError(f"Project root does not exist: {root}")
    value.setdefault("protected_paths", infer_protected(root, value["test"]))
    protected_contract(root, value["protected_paths"])
    return value, root


def initialize(root, test, build=None, protected_paths=None):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Project root does not exist: {root}")
    value = {"schema_version": "0.1", "root": "..", "build": build,
             "test": test, "command_seconds": 300, "comparison_seconds": 1200,
             "output_bytes_per_stream": 1048576}
    path = root / ".chilicrisp" / "project.json"
    validate(value, "project")
    value["protected_paths"] = infer_protected(root, test) if protected_paths is None else protected_paths
    validate(value, "project")
    protected_contract(root, value["protected_paths"])
    path.parent.mkdir(exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    return path


def infer_protected(root, command):
    paths = ["tests"] if (root / "tests").is_dir() else []
    for argument in command[1:]:
        path = Path(argument)
        if not path.is_absolute() and (root / path).is_file():
            paths.append(path.as_posix())
    return sorted(set(paths))


def protected_contract(root, paths):
    """Hash declared correctness files; paths may not escape snapshot scope."""
    records = {}
    for name in paths:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"Protected path must be relative within source: {name}")
        if any(part in EXCLUDED or part.endswith(".egg-info") for part in relative.parts):
            raise ValueError(f"Protected path is excluded from snapshots: {name}")
        path = root / relative
        if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Protected path is a link or outside source: {name}")
        if not path.exists():
            raise ValueError(f"Protected correctness path missing: {name}")
        entries = [path, *sorted(path.rglob("*"))] if path.is_dir() else [path]
        for entry in entries:
            if any(part in EXCLUDED for part in entry.relative_to(root).parts):
                continue
            if entry.is_symlink() or entry.is_junction():
                raise ValueError(f"Protected correctness path contains a link: {entry}")
            key = entry.relative_to(root).as_posix()
            if entry.is_file():
                records[key] = {"sha256": file_hash(entry), "executable": bool(entry.stat().st_mode & 0o111)}
            elif entry.is_dir():
                records[key] = {"kind": "directory"}
            else:
                raise ValueError(f"Protected path is not a regular file: {entry}")
    return records


def snapshot(source, destination):
    """Copy regular source files; reject links, special files and junctions.

    Both inputs are trusted. This is reproducibility bookkeeping, not a sandbox.
    """
    digest = hashlib.sha256()
    destination.mkdir()
    def traversal_error(error):
        raise error

    for current, directories, files in os.walk(source, followlinks=False, onerror=traversal_error):
        current = Path(current)
        directories[:] = sorted(d for d in directories if d not in EXCLUDED
                                 and not d.endswith(".egg-info"))
        for name in [*directories, *sorted(files)]:
            original = current / name
            if original.is_symlink() or original.is_junction():
                raise ValueError(f"Source links are unsupported: {original}")
            relative = original.relative_to(source)
            target = destination / relative
            if original.is_dir():
                target.mkdir()
                digest.update(json.dumps([relative.as_posix(), "directory"]).encode("utf-8") + b"\n")
            elif original.is_file():
                shutil.copy2(original, target)
                entry = [relative.as_posix(), target.stat().st_mode, file_hash(target)]
                digest.update(json.dumps(entry).encode("utf-8") + b"\n")
            else:
                raise ValueError(f"Special source file is unsupported: {original}")
    return digest.hexdigest()


def persist(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def stop(process):
    if os.name == "nt":
        if process.poll() is None:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)


def execute(command, workspace, directory, config, deadline, observer=None):
    directory.mkdir()
    started = time.monotonic()
    result = {"command": command, "outcome": "runner_failure", "exit_code": None,
              "elapsed_seconds": None, "capture": {}, "error": None}
    process = None
    threads = []
    try:
        if started >= deadline:
            result["outcome"] = "comparison_timeout"
            return result
        process = subprocess.Popen(command, cwd=workspace, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=os.name != "nt")
        overflow, streams, threads = capture(process, directory, config["output_bytes_per_stream"])
        command_deadline = min(deadline, started + config["command_seconds"])
        while True:
            if observer is not None:
                observer.sample(process)
            if process.poll() is not None:
                result["outcome"] = "pass" if process.returncode == 0 else "failed"
                break
            if overflow.is_set():
                result["outcome"] = "output_limit"
                break
            if time.monotonic() >= command_deadline:
                result["outcome"] = "timeout"
                break
            time.sleep(.01)
        stop(process)
        for thread in threads:
            thread.join(timeout=2)
        result["exit_code"] = process.returncode
        result["capture"] = streams
        if any(t.is_alive() for t in threads):
            result.update(outcome="cleanup_failure", error="Capture remains open; inspect descendant processes")
        elif any("error" in stream for stream in streams.values()):
            result.update(outcome="runner_failure", error="Output capture failed")
        elif overflow.is_set():
            result["outcome"] = "output_limit"
    except Exception as error:
        result.update(outcome="runner_failure", error=f"{type(error).__name__}: {error}")
    finally:
        if process and process.poll() is None:
            stop(process)
        result["elapsed_seconds"] = time.monotonic() - started
        persist(directory / "command.json", result)
    return result


def compare(config_path, candidate, output, *, trusted_local=False, experiment_deadline=None):
    if not trusted_local:
        raise ValueError("Local commands need --trusted-local: they run with your host permissions")
    config, baseline = load_project(config_path)
    candidate = Path(candidate).resolve()
    output = Path(output).resolve()
    if not candidate.is_dir():
        raise ValueError("Candidate must be an existing source directory")
    for source in (baseline, candidate):
        if output == source or source.is_relative_to(output):
            raise ValueError("Output must not contain a source directory")
        if output.is_relative_to(source) and output.relative_to(source).parts[0] not in EXCLUDED:
            raise ValueError("Output inside source must be under an excluded directory such as .chilicrisp")
    output.mkdir(parents=True, exist_ok=True)
    run = output / ("comparison-" + uuid.uuid4().hex)
    run.mkdir()
    result = {"schema_version": "0.1", "kind": "trusted_local_comparison",
              "run_id": run.name, "state": "RUNNING", "config": config,
              "sources": {"baseline": str(baseline), "candidate": str(candidate)},
              "evaluations": {}, "decision": None,
              "limitations": ["Host commands are trusted and unconfined; snapshots are writable.",
                  "Build/test elapsed time is diagnostic, not a performance benchmark.",
                  "No resource-pressure enforcement, sealed grading, or automatic promotion.",
                  "Windows descendant cleanup is best effort; avoid commands that detach processes."]}
    record = run / "comparison.json"
    persist(record, result)
    deadline = time.monotonic() + config["comparison_seconds"]
    if experiment_deadline is not None:
        deadline = min(deadline, experiment_deadline)
    try:
        # Freeze both source inputs before executing either one's commands.
        for name, source in (("baseline", baseline), ("candidate", candidate)):
            workspace = run / name
            source_hash = snapshot(source, workspace)
            result["evaluations"][name] = {"source_hash": source_hash, "commands": [],
                                            "outcome": "pending"}
            persist(record, result)
        contract = protected_contract(run / "baseline", config["protected_paths"])
        result["correctness_contract"] = contract
        for name in ("baseline", "candidate"):
            evaluation = result["evaluations"][name]
            try:
                if protected_contract(run / name, config["protected_paths"]) != contract:
                    raise ValueError("Protected correctness files differ from baseline")
            except ValueError as error:
                evaluation.update(outcome="contract_changed", error=str(error))
            for stage in ("build", "test"):
                if evaluation["outcome"] == "contract_changed":
                    break
                command = config[stage]
                if command is None:
                    continue
                observation = execute(command, run / name, run / f"{name}-{stage}", config, deadline)
                evaluation["commands"].append({"stage": stage, **observation})
                evaluation["outcome"] = observation["outcome"]
                try:
                    if protected_contract(run / name, config["protected_paths"]) != contract:
                        raise ValueError("Command changed protected correctness files")
                except ValueError as error:
                    evaluation.update(outcome="contract_changed", error=str(error))
                persist(record, result)
                if evaluation["outcome"] != "pass":
                    break
            if evaluation["outcome"] != "pass" and name == "baseline":
                result["decision"] = "baseline_failed"
                break
        else:
            result["decision"] = ("public_tests_passed" if
                result["evaluations"]["candidate"]["outcome"] == "pass" else "candidate_rejected")
        result["state"] = "FINALIZED"
    except BaseException as error:
        result.update(state="INTERRUPTED" if isinstance(error, (KeyboardInterrupt, SystemExit)) else "FAILED",
                      decision="no_acceptance", error=f"{type(error).__name__}: {error}")
        persist(record, result)
        raise
    persist(record, result)
    validate(result, "comparison")
    seal(record)
    return record, result

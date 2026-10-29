"""Linux-only bubblewrap/cgroup runner. Never executes an unconfined fallback."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from jsonschema import Draft202012Validator
from .capture import capture
from .frontier import Policy
from .lifecycle import Lifecycle

ROOT = Path(__file__).resolve().parents[1]


def validate(value, name):
    # Installed wheels carry schemas beside the modules; source checkouts use
    # the authoritative top-level directory. Never use the working directory.
    directory = Path(__file__).resolve().parent / "schemas"
    if not directory.is_dir():
        directory = ROOT / "schemas"
    if name not in {"experiment", "result", "field-oracle", "ocean-oracle"}:
        raise ValueError(f"unknown schema: {name}")
    schema = json.loads((directory / f"{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(value)


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hash(root):
    """Hash paths, modes, link targets, and contents; never traverse symlinks."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("rootfs must be a real directory")
    digest = hashlib.sha256()
    for item in sorted(root.rglob("*")):
        stat = item.lstat()
        record = [item.relative_to(root).as_posix(), stat.st_mode]
        if item.is_symlink():
            record.append(os.readlink(item))
        elif item.is_file():
            record.append(file_hash(item))
        elif not item.is_dir():
            raise ValueError("rootfs contains a special file")
        digest.update(json.dumps(record, separators=(",", ":")).encode() + b"\n")
    return digest.hexdigest()


def read_keys(path):
    return {key: int(value) for key, value in
            (line.split() for line in path.read_text().splitlines())}


def cleanup_cgroup(cgroup):
    if not cgroup.exists():
        return
    (cgroup / "cgroup.kill").write_text("1")
    deadline = time.monotonic() + 5
    while read_keys(cgroup / "cgroup.events").get("populated"):
        if time.monotonic() > deadline:
            raise RuntimeError("target process tree did not exit")
        time.sleep(.02)
    cgroup.rmdir()


def finish_trial(result, directory, life, cgroup, configured, process, threads, started, cpu, invoked):
    """Cleanup cannot depend on successful journal, hashing, or result writes."""
    errors = [] if life else ["lifecycle journal unavailable"]

    def attempt(label, operation):
        try:
            return operation()
        except BaseException as error:
            errors.append(f"{label}: {type(error).__name__}: {error}")
            return None

    if life and life.data["state"] not in {"TERMINATING", "COLLECTING"}:
        attempt("journal termination", lambda: life.move("TERMINATING"))
    before_cleanup = len(errors)
    if configured:
        attempt("cleanup", lambda: cleanup_cgroup(cgroup))
    if process:
        attempt("process wait", lambda: process.wait(timeout=5))
    for thread in threads:
        attempt("capture join", lambda: thread.join(timeout=5))
        if thread.is_alive():
            errors.append("capture thread still alive")
    cleanup_failed = len(errors) > before_cleanup
    if life and life.data["state"] == "TERMINATING":
        attempt("journal collection", lambda: life.move("COLLECTING"))
    result["cost"].update(wall_seconds=time.monotonic() - started,
        runner_cpu_seconds=time.process_time() - cpu, test_invocations=invoked,
        tool_calls=None, model_tokens=None, model_cost=None)
    result["cost"].setdefault("target_cpu_seconds", None)
    if life and not errors:
        attempt("journal finalization", lambda: life.move("FINALIZED"))
    artifacts = attempt("artifact enumeration", lambda: list(directory.iterdir())) or []
    for artifact in artifacts:
        if artifact.name in {"result.json", "emergency.json"}:
            continue
        value = attempt("artifact hash " + artifact.name, lambda: file_hash(artifact))
        if value is not None:
            result["artifact_hashes"][artifact.name] = value
    if not errors:
        attempt("result validation", lambda: validate(result, "result"))
    if not errors:
        attempt("result persistence", lambda: (directory / "result.json").write_text(
            json.dumps(result, indent=2)))
    if errors:
        result["outcome"] = "cleanup_failure" if cleanup_failed else "runner_failure"
        result["lifecycle"] = "RECOVERY_REQUIRED"
        result["error"] = "; ".join(filter(None, [result["error"], *errors]))
        if life:
            life.data["state"] = "RECOVERY_REQUIRED"
            life.data["transitions"].append("RECOVERY_REQUIRED")
            attempt("recovery marker", life.save)
        # Independent low-level path: diagnostics, not a schema-validated trial.
        emergency = dict(kind="emergency_diagnostic", result=result, failures=errors,
                         trial_id=result["trial_id"], cgroup=str(cgroup))
        try:
            descriptor = os.open(str(directory / "emergency.json"),
                                 os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(emergency, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException as error:
            # If storage is unavailable, return the diagnostic to the caller.
            result["error"] += f"; emergency persistence: {type(error).__name__}: {error}"
    return result


def preflight(manifest, budget):
    if sys.platform != "linux":
        raise RuntimeError("Linux cgroup v2 and bubblewrap are required")
    if os.getuid() == 0:
        raise RuntimeError("pilot runner must execute as an unprivileged user")
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RuntimeError("bubblewrap unavailable")
    version = subprocess.run([bwrap, "--version"], capture_output=True, text=True,
                             timeout=5, check=True).stdout.strip()
    numbers = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
    if not numbers or tuple(map(int, numbers.groups())) < (0, 12, 0):
        raise RuntimeError("bubblewrap >= 0.12.0 required for safe rootfs setup")
    help_text = subprocess.run([bwrap, "--help"], capture_output=True, text=True,
                               timeout=5, check=True).stdout
    for flag in ("--size", "--disable-userns", "--seccomp", "--unshare-all"):
        if flag not in help_text:
            raise RuntimeError(f"bubblewrap missing required feature {flag}")
    parent = Path(manifest["isolation"]["cgroup_parent"]).resolve()
    mount = Path("/sys/fs/cgroup").resolve()
    if not parent.is_relative_to(mount) or parent == mount:
        raise RuntimeError("a delegated cgroup parent is required")
    controllers = (parent / "cgroup.subtree_control").read_text().split()
    if not {"memory", "pids"}.issubset(controllers):
        raise RuntimeError("memory and pids controllers must already be delegated and enabled")
    ancestors = []
    for ancestor in [parent, *parent.parents]:
        if ancestor == mount:
            break
        entry = {"path": str(ancestor)}
        for name in ("memory.max", "memory.high", "memory.swap.max", "pids.max"):
            value = (ancestor / name).read_text().strip()
            entry[name] = value
            if (budget is not None and name in {"memory.max", "memory.high"}
                    and value != "max" and int(value) <= budget):
                raise RuntimeError(f"ancestor {name} interferes with budget")
        ancestors.append(entry)
    for huge in Path("/sys/kernel/mm/hugepages").glob("*/free_hugepages"):
        if int(huge.read_text()):
            raise RuntimeError("explicit huge pages available; pilot does not account for these")
    return {"bwrap": bwrap, "bwrap_version": version, "bwrap_hash": file_hash(bwrap),
            "ancestors": ancestors,
            "cache_policy": "qualified_warm; no cold-cache claim",
            "kernel": os.uname().release,
            "pressure": Path("/proc/pressure/memory").read_text(),
            "thp": Path("/sys/kernel/mm/transparent_hugepage/enabled").read_text()}


def run_trial(manifest, workload_id, budget, experiment_deadline=None):
    validate(manifest, "experiment")
    Policy(**manifest["search"])
    if budget is not None and (budget <= 0 or budget % manifest["search"]["page_size"]):
        raise ValueError("trial budget must be positive and page aligned")
    workloads = [w for w in manifest["workloads"] if w["id"] == workload_id]
    if len(workloads) != 1:
        raise ValueError("workload IDs must uniquely identify a workload")
    workload = workloads[0]
    trial_id = uuid.uuid4().hex
    directory = Path(manifest["evidence_directory"]).resolve() / trial_id
    for journal in directory.parent.glob("*/lifecycle.json"):
        if json.loads(journal.read_text())["state"] != "FINALIZED":
            raise RuntimeError(f"unfinished trial requires recovery: {journal}")
    for diagnostic in directory.parent.glob("*/emergency.json"):
        journal = diagnostic.parent / "lifecycle.json"
        state = json.loads(journal.read_text()) if journal.exists() else {}
        if state.get("state") != "FINALIZED" or not state.get("recovery"):
            raise RuntimeError(f"emergency diagnostic requires recovery: {diagnostic}")
    rootfs = Path(manifest["target"]["rootfs"]).resolve()
    if directory.is_relative_to(rootfs) or rootfs.is_relative_to(directory):
        raise ValueError("evidence and rootfs must be separate")
    directory.mkdir(parents=True, exist_ok=False)
    cgroup = Path(manifest["isolation"]["cgroup_parent"]) / f"chili-{trial_id}"
    life = None
    started, cpu = time.monotonic(), time.process_time()
    result = dict(schema_version="0.1", experiment_id=manifest["experiment_id"],
                  trial_id=trial_id, candidate_hash=manifest["target"]["rootfs_hash"],
                  manifest_hash=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
                  measurement_mode="whole_program", workload_id=workload_id,
                  phase="baseline" if budget is None else "exploration",
                  requested_budget_bytes=budget, effective_budget_bytes=None,
                  outcome="unsupported", metrics={}, artifact_hashes={}, preflight_record={},
                  cost={}, lifecycle="FINALIZED", error=None)
    process = None
    threads = []
    invoked = 0
    configured = False
    try:
        life = Lifecycle(directory / "lifecycle.json", {"trial_id": trial_id, "cgroup": str(cgroup)})
        result["preflight_record"] = preflight(manifest, budget)
        if tree_hash(rootfs) != manifest["target"]["rootfs_hash"]:
            raise RuntimeError("rootfs identity mismatch")
        for mountpoint in ("proc", "dev", "tmp"):
            item = rootfs / mountpoint
            if item.is_symlink() or not item.is_dir():
                raise RuntimeError(f"rootfs {mountpoint} must be a real directory")
        input_path = Path(workload["input"]).resolve()
        if file_hash(input_path) != workload["input_hash"]:
            raise RuntimeError("input identity mismatch")
        oracle_policy = None
        field_reference = None
        if "oracle" in workload:
            oracle = workload["oracle"]
            policy_path = Path(oracle["policy_path"]).resolve()
            if policy_path.is_relative_to(rootfs):
                raise RuntimeError("oracle policy must be outside candidate rootfs")
            if file_hash(policy_path) != oracle["policy_hash"]:
                raise RuntimeError("oracle policy identity mismatch")
            oracle_policy = json.loads(policy_path.read_text())
            field_mode = oracle["kind"] == "worldgame_fields_v1"
            validate(oracle_policy, "field-oracle" if field_mode else "ocean-oracle")
            if field_mode:
                from .fields import decode
                reference_path = Path(oracle_policy["reference_path"]).resolve()
                if reference_path.is_relative_to(rootfs):
                    raise RuntimeError("reference fields must be outside candidate rootfs")
                if reference_path.stat().st_size > 4000017:
                    raise RuntimeError("reference fields exceed decoder limit")
                reference_data = reference_path.read_bytes()
                if hashlib.sha256(reference_data).hexdigest() != oracle_policy["reference_hash"]:
                    raise RuntimeError("field reference identity mismatch")
                field_reference = decode(reference_data)
                if len(field_reference) != oracle_policy["field_count"]:
                    raise RuntimeError("reference field count mismatch")
            result["preflight_record"]["oracle"] = dict(
                policy_hash=oracle["policy_hash"], comparator_hash=file_hash(ROOT / "chilicrisp" / ("fields.py" if field_mode else "oracles.py")))
        from .seccomp import compile_filter
        import resource
        with compile_filter() as seccomp:
            life.move("PREFLIGHT_VALIDATED")
            cgroup.mkdir()
            configured = True
            settings = {"memory.max": "max" if budget is None else budget, "memory.swap.max": 0,
                        "memory.high": "max", "memory.oom.group": 1,
                        "pids.max": manifest["isolation"]["pids"]}
            for name, value in settings.items():
                (cgroup / name).write_text(str(value))
                if (cgroup / name).read_text().strip() != str(value):
                    raise RuntimeError(f"effective setting mismatch: {name}")
            if not (cgroup / "cgroup.kill").exists():
                raise RuntimeError("cgroup.kill required for process-tree cleanup")
            result["effective_budget_bytes"] = budget
            result["preflight_record"]["effective"] = settings
            life.move("CGROUP_CONFIGURED")
            # preexec performs no workload execution; forked Python launcher
            # overhead/inherited pages are a disclosed accounting limitation.
            def enter():
                (cgroup / "cgroup.procs").write_text(str(os.getpid()))
                resource.setrlimit(resource.RLIMIT_NOFILE,
                                   (manifest["isolation"]["file_descriptors"],) * 2)
                resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
                resource.setrlimit(resource.RLIMIT_FSIZE,
                                   (manifest["isolation"]["scratch_bytes"],) * 2)

            command = [result["preflight_record"]["bwrap"], "--unshare-all",
                       "--disable-userns", "--die-with-parent", "--new-session",
                       "--uid", "65534", "--gid", "65534", "--cap-drop", "ALL",
                       "--ro-bind", str(rootfs), "/", "--proc", "/proc", "--dev", "/dev",
                       "--remount-ro", "/dev",
                       "--size", str(manifest["isolation"]["scratch_bytes"]), "--tmpfs", "/tmp",
                       "--clearenv", "--setenv", "PATH", "/usr/bin:/bin",
                       "--setenv", "HOME", "/tmp", "--chdir", "/tmp",
                       "--seccomp", str(seccomp.fileno()), "--",
                       *manifest["target"]["command"], *workload["arguments"]]
            life.move("RUNNING")
            execution_started = time.monotonic()
            with input_path.open("rb") as input_stream:
                process = subprocess.Popen(command, stdin=input_stream, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, preexec_fn=enter, pass_fds=(seccomp.fileno(),))
            invoked = 1
            overflow, summaries, threads = capture(process, directory,
                manifest["limits"]["output_bytes_per_stream"])
            deadline = time.monotonic() + manifest["limits"]["timeout_seconds"]
            if experiment_deadline is not None:
                deadline = min(deadline, experiment_deadline)
            result["outcome"] = "inconclusive"
            while process.poll() is None:
                if overflow.is_set():
                    result["outcome"] = "output_limit"
                    break
                if time.monotonic() >= deadline:
                    result["outcome"] = "timeout"
                    break
                time.sleep(.01)
            execution_seconds = time.monotonic() - execution_started
            life.move("TERMINATING")
            (cgroup / "cgroup.kill").write_text("1")
            process.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=5)
            if any(thread.is_alive() for thread in threads):
                raise RuntimeError("output capture failed to terminate")
            life.move("COLLECTING")
            counters = {name: (cgroup / name).read_text() for name in
                        ("memory.peak", "memory.events", "memory.stat", "cpu.stat")}
            (directory / "counters.json").write_text(json.dumps(counters, indent=2))
            (directory / "capture.json").write_text(json.dumps(summaries, indent=2))
            result["metrics"]["memory_peak"] = dict(value=int(counters["memory.peak"]),
                unit="bytes", method="cgroup_v2.memory.peak", status="available")
            result["metrics"]["elapsed"] = dict(value=execution_seconds, unit="seconds",
                method="monotonic; launcher and sandbox included", status="available")
            if any("error" in summary for summary in summaries.values()):
                raise RuntimeError("output capture failed")
            if overflow.is_set():
                result["outcome"] = "output_limit"
            elif result["outcome"] == "inconclusive":
                if read_keys(cgroup / "memory.events").get("oom_kill", 0):
                    result["outcome"] = "oom"
                elif process.returncode != 0:
                    result["outcome"] = "wrong_output"
                else:
                    if oracle_policy is None:
                        result["outcome"] = ("pass" if summaries["stdout"]["sha256"] ==
                            workload["expected_stdout_hash"] else "wrong_output")
                    else:
                        from .oracles import check_ocean
                        try:
                            if field_reference is not None:
                                from .fields import decode, compare
                                actual = decode((directory / "stdout").read_bytes())
                                error = compare(actual, field_reference, oracle_policy["atol"], oracle_policy["rtol"])
                                verification = dict(pass_checks=True, field_count=len(actual),
                                    max_absolute_error=error, scope="differential field equivalence")
                            else:
                                verification = check_ocean((directory / "stdout").read_text(encoding="utf-8"), oracle_policy)
                            result["outcome"] = "pass"
                        except (ValueError, UnicodeError) as error:
                            verification = dict(pass_checks=False, error=str(error))
                            result["outcome"] = "wrong_output"
                        (directory / "verification.json").write_text(json.dumps(verification, indent=2))
            result["cost"]["target_cpu_seconds"] = read_keys(cgroup / "cpu.stat")["usage_usec"] / 1e6
            if tree_hash(rootfs) != manifest["target"]["rootfs_hash"]:
                raise RuntimeError("rootfs changed during trial")
    except BaseException as error:
        result["error"] = f"{type(error).__name__}: {error}"
        result["outcome"] = "runner_failure" if invoked or life is None else "unsupported"
    finally:
        finish_trial(result, directory, life, cgroup, configured, process, threads, started, cpu, invoked)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    check = commands.add_parser("validate")
    check.add_argument("manifest", type=Path)
    hashing = commands.add_parser("hash-rootfs")
    hashing.add_argument("rootfs", type=Path)
    trial = commands.add_parser("trial")
    trial.add_argument("manifest", type=Path)
    trial.add_argument("--workload", required=True)
    trial.add_argument("--budget", required=True, type=int)
    args = parser.parse_args()
    if args.operation == "hash-rootfs":
        print(tree_hash(args.rootfs))
        return
    manifest = json.loads(args.manifest.read_text())
    validate(manifest, "experiment")
    Policy(**manifest["search"])
    if args.operation == "validate":
        print("Manifest valid; runtime preflight has not run.")
    else:
        result = run_trial(manifest, args.workload, args.budget)
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["outcome"] == "pass" else 1)


if __name__ == "__main__":
    main()

"""Trusted-fixture compatibility probe, not a candidate execution backend."""
import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import signal
import sys


FIXTURES = {
    "correct": "print('ok')",
    "timeout": "import time; time.sleep(60)",
    "oom": "chunks=[]\nwhile True: chunks.append(bytearray(1048576))",
}


def probe(directory):
    """Exercise BenchExec itself; never weaken the existing runner on failure."""
    if sys.platform != "linux":
        return {"status": "unsupported", "reason": "BenchExec requires Linux", "trials": []}
    if os.getuid() == 0:
        return {"status": "unsupported", "reason": "use an unprivileged account", "trials": []}
    from benchexec.runexecutor import RunExecutor

    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    report = {"status": "incomplete", "benchexec_version": version("BenchExec"),
              "scope": "trusted fixtures only; full Chili Crisp contract remains unvalidated",
              "trials": []}
    executor = RunExecutor(use_namespaces=True, network_access=False, cgroup_access=False)
    previous = {}

    def stop(signum, frame):
        executor.stop()
        raise SystemExit(128 + signum)

    try:
        # Upstream explicitly requires stop() instead of KeyboardInterrupt.
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, stop)
        for name, source in FIXTURES.items():
            raw = executor.execute_run(args=[sys.executable, "-c", source],
                output_filename=str(directory / f"{name}.stdout"),
                error_filename=str(directory / f"{name}.stderr"),
                memlimit=64 * 1024 * 1024, walltimelimit=2,
                maxLogfileSize=65536, write_header=False)
            exitcode = raw.get("exitcode")
            observed = raw.get("terminationreason")
            if observed is None:
                observed = ("pass" if exitcode is not None and exitcode.value == 0
                            and (directory / f"{name}.stdout").read_bytes() == b"ok\n"
                            else "unexpected_exit")
            expected = {"correct": "pass", "timeout": "walltime", "oom": "memory"}[name]
            report["trials"].append({"fixture": name, "expected": expected,
                "observed": observed, "matched": observed == expected,
                "raw": {key: str(value) for key, value in raw.items()}})
        report["status"] = ("fixtures_passed" if all(t["matched"] for t in report["trials"])
                            else "fixtures_failed")
    finally:
        executor.stop()
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        (directory / "probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="new evidence directory")
    args = parser.parse_args()
    try:
        report = probe(args.directory)
    except (ImportError, OSError, RuntimeError, SystemExit) as error:
        if isinstance(error, SystemExit) and error.code != 1:
            raise
        report = {"status": "unsupported", "reason": str(error), "trials": []}
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "fixtures_passed" else 1)


if __name__ == "__main__":
    main()

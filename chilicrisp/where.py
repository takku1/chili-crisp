"""Where memory goes: top Python allocation sites near the peak.

This is a diagnostic run, separate from the measured ones, because tracing
slows the program down and adds memory of its own. It works for Python
commands only: the wrapper below is inserted in front of the script or `-m`
module, runs it under tracemalloc and records the allocation sites when traced
memory is close to its peak.
"""
import json
import os
from pathlib import Path
import time

from .project import execute

TOP = 10

# Runs inside the measured interpreter. A watcher thread takes a snapshot each
# time traced memory grows 10% past the last snapshot, so the kept snapshot is
# within about 10% of the true peak.
WRAPPER = r"""
import json, os, runpy, sys, threading, time, tracemalloc
tracemalloc.start(1)
out = os.environ["CHILICRISP_WHERE_OUT"]
state = {"snapshot": None, "size": 0, "done": False}
lock = threading.Lock()
def take():
    current, _ = tracemalloc.get_traced_memory()
    if current > state["size"] * 1.1 or state["snapshot"] is None:
        snapshot = tracemalloc.take_snapshot()
        with lock:
            state.update(snapshot=snapshot, size=current)
def watch():
    while not state["done"]:
        take()
        time.sleep(0.02)
watcher = threading.Thread(target=watch, daemon=True)
watcher.start()
def finish():
    state["done"] = True
    watcher.join(1)
    take()
    _, peak = tracemalloc.get_traced_memory()
    with lock:
        snapshot, size = state["snapshot"], state["size"]
    tracemalloc.stop()
    stats = snapshot.statistics("lineno") if snapshot else []
    sites = [{"file": s.traceback[0].filename, "line": s.traceback[0].lineno, "bytes": s.size,
              "count": s.count} for s in stats[:%(top)d] if s.size >= size * 0.01]
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"traced_peak_bytes": peak, "snapshot_bytes": size, "sites": sites}, handle)
args = sys.argv[1:]
# Hold the script's globals until the final snapshot: runpy drops them on
# return, which would free module-level data before it is seen.
namespace = None
try:
    if args[:1] == ["-m"]:
        sys.argv = [args[1], *args[2:]]
        namespace = runpy.run_module(args[1], run_name="__main__", alter_sys=True)
    else:
        sys.argv = args
        sys.path.insert(0, os.path.dirname(os.path.abspath(args[0])))
        namespace = runpy.run_path(args[0], run_name="__main__")
finally:
    finish()
    del namespace
""" % {"top": TOP}


def instrument(command):
    """Insert the wrapper before the script or `-m`; None if this is not a Python command."""
    name = Path(command[0]).name.lower() if command else ""
    if not (name.startswith("python") or name in {"py", "py.exe"}):
        return None
    for index, token in enumerate(command[1:], 1):
        if token == "-m" or token.endswith(".py"):
            return [*command[:index], "-c", WRAPPER, *command[index:]]
        if not token.startswith("-"):
            return None
    return None


def where(command, workspace, directory, timeout):
    """Run `command` once under tracing; return the top allocation sites or an error."""
    wrapped = instrument(command)
    if wrapped is None:
        return {"error": "memory breakdown needs a Python command: python [options] script.py ... or -m module"}
    result_path = Path(directory).resolve() / "where.json"
    config = {"command_seconds": timeout, "output_bytes_per_stream": 4 * 1024 * 1024}
    previous = os.environ.get("CHILICRISP_WHERE_OUT")
    os.environ["CHILICRISP_WHERE_OUT"] = str(result_path)
    try:
        run = execute(wrapped, workspace, Path(directory), config, time.monotonic() + timeout)
    finally:
        if previous is None:
            os.environ.pop("CHILICRISP_WHERE_OUT", None)
        else:
            os.environ["CHILICRISP_WHERE_OUT"] = previous
    if not result_path.is_file():
        return {"error": f"diagnostic run ended with {run['outcome']} and wrote no breakdown"}
    found = json.loads(result_path.read_text(encoding="utf-8"))
    root = Path(workspace).resolve()
    for site in found["sites"]:
        path = Path(site["file"])
        if path.is_absolute() and path.resolve().is_relative_to(root):
            site["file"] = path.resolve().relative_to(root).as_posix()
    return found

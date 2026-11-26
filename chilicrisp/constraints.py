"""Constraint briefs: design against an imagined machine, verify on a real one.

A brief gives a coding agent a target to design for (a story, hard budgets and
rules). `check` runs the agent's work on the current machine, measures it and
reports whether it fits. Nothing is emulated or enforced by the kernel; budgets
are checked after the fact. Linux cgroup enforcement remains a separate,
optional tier (see docs/current/enforced/).
"""
from copy import deepcopy
import fnmatch
import json
import os
from pathlib import Path
import re
import statistics
import sys
import time

import psutil

from .contracts import validate
from .measure import Monitor, artifact_size, environment
from .project import EXCLUDED, execute, persist
from .where import where as breakdown


# Brief budget name -> (measurement key, unit, label, measurement quality).
METRICS = {
    "peak_memory_bytes": ("peak_memory_bytes", "bytes", "Peak memory",
                          "max of sampled process-tree RSS and the largest per-process lifetime peak"),
    "wall_seconds": ("wall_seconds", "seconds", "Wall time", "elapsed time of the whole command"),
    "cpu_seconds": ("sampled_cpu_seconds", "seconds", "CPU time", "sampled user+system CPU of observed processes"),
    "artifact_bytes": ("artifact_bytes", "bytes", "Artifact size", "logical bytes of the declared artifact paths"),
    "io_read_bytes": ("sampled_io_read_bytes", "bytes", "Bytes read", "sampled I/O counters; platform-specific"),
    "io_write_bytes": ("sampled_io_write_bytes", "bytes", "Bytes written", "sampled I/O counters; platform-specific"),
}

DEFAULT_HINTS = [
    "Memory over budget: stream instead of loading everything; use compact representations "
    "(arrays, packed structs, bytes) instead of object graphs; shorten object lifetimes.",
    "Allocation spikes: reuse buffers, use fixed-size pools or arenas, avoid temporary copies.",
    "Cost grows with input size: change the algorithm (complexity, chunking, external memory) "
    "rather than tuning constants.",
    "Time over budget: localize the working set, avoid recomputation, cache only what is reused.",
    "Artifact over budget: drop dependencies, compress or derive data at build time, strip what is never read.",
]

PROFILES = {
    "half": {
        "schema_version": "1.0", "name": "half",
        "story": "Same machine, half the room. Another tenant just took half of the memory this "
                 "program uses today. It must keep producing identical output without getting slower.",
        "budgets": {"peak_memory_bytes": "50%", "wall_seconds": "110%"},
        "rules": ["Behavior and output stay identical.", "No new third-party dependencies."],
    },
    "quarter": {
        "schema_version": "1.0", "name": "quarter",
        "story": "The program now runs as one of four copies on the same box. It gets a quarter of "
                 "today's memory. Small trims will not get there: rethink the data layout or the flow.",
        "budgets": {"peak_memory_bytes": "25%", "wall_seconds": "150%"},
        "rules": ["Behavior and output stay identical.", "Trading some speed for memory is allowed within the time budget."],
    },
    "handheld": {
        "schema_version": "1.0", "name": "handheld",
        "story": "This ships on a battery-powered handheld with 16 MiB of RAM shared with everything "
                 "else, a slow CPU and no network. The user will notice any pause longer than a second.",
        "budgets": {"peak_memory_bytes": "16MiB", "wall_seconds": "1s", "cpu_seconds": "1s"},
        "rules": ["No network access.", "No new third-party dependencies.", "Behavior and output stay identical."],
        "forbid": [{"pattern": r"\b(requests|urllib|httpx|socket)\b", "glob": "*.py",
                    "why": "the device has no network"}],
    },
    "edge-function": {
        "schema_version": "1.0", "name": "edge-function",
        "story": "This runs as a cold-started edge function: 128 MiB of memory, a 250 ms response "
                 "budget including startup, a 1 MiB deploy bundle and no writable disk.",
        "budgets": {"peak_memory_bytes": "128MiB", "wall_seconds": "250ms", "io_write_bytes": "0B"},
        "rules": ["Stateless: nothing persists between invocations.", "Startup counts toward the time budget."],
    },
    "floppy": {
        "schema_version": "1.0", "name": "floppy",
        "story": "The whole deliverable has to fit on a 1.44 MB floppy disk and run on a 1990s "
                 "workstation with 32 MiB of RAM.",
        "budgets": {"artifact_bytes": "1474560B", "peak_memory_bytes": "32MiB"},
        "rules": ["Everything needed at runtime is inside the declared artifacts."],
    },
}

_UNITS = {"B": 1, "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4,
          "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "TiB": 1024**4, "s": 1, "ms": 0.001}
_QUANTITY = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(%|[KMGT]i?B|B|ms|s)?\s*$")


def parse_quantity(value, unit):
    """Return ('absolute', amount) or ('relative', fraction of baseline)."""
    if isinstance(value, bool):
        raise ValueError("Budget must be a number or quantity string")
    if isinstance(value, (int, float)):
        return "absolute", float(value)
    match = _QUANTITY.match(value)
    if not match:
        raise ValueError(f"Unreadable budget: {value!r}")
    amount, suffix = float(match.group(1)), match.group(2)
    if suffix == "%":
        return "relative", amount / 100
    if suffix is None:
        return "absolute", amount
    if (unit == "bytes") != suffix.endswith("B"):
        raise ValueError(f"Budget {value!r} has the wrong unit; expected {unit}")
    return "absolute", amount * _UNITS[suffix]


def load(spec):
    """Load a brief from a profile name or a JSON file, applying `extends`."""
    if isinstance(spec, dict):
        brief = deepcopy(spec)
    elif str(spec) in PROFILES:
        brief = deepcopy(PROFILES[str(spec)])
    else:
        path = Path(spec)
        if not path.is_file():
            raise ValueError(f"No profile or brief file named {spec!r}; try `chilicrisp profiles`")
        brief = json.loads(path.read_text(encoding="utf-8"))
    validate(brief, "brief")
    parent_name = brief.pop("extends", None)
    if parent_name:
        if parent_name not in PROFILES:
            raise ValueError(f"Unknown profile to extend: {parent_name}")
        parent = deepcopy(PROFILES[parent_name])
        merged = {**parent, **brief, "budgets": {**parent["budgets"], **brief["budgets"]}}
        for key in ("rules", "forbid", "hints", "artifacts", "writes"):
            merged[key] = [*parent.get(key, []), *brief.get(key, [])]
        brief = merged
    for name, value in brief["budgets"].items():
        parse_quantity(value, METRICS[name][1])
    return brief


def resolve(brief, baseline=None):
    """Turn budgets into absolute limits; relative ones need baseline medians."""
    resolved = {}
    for name, value in brief["budgets"].items():
        key, unit = METRICS[name][0], METRICS[name][1]
        kind, amount = parse_quantity(value, unit)
        entry = {"declared": value, "unit": unit, "kind": kind, "limit": None}
        if kind == "absolute":
            entry["limit"] = amount
        elif baseline and baseline.get(key) is not None:
            entry.update(limit=baseline[key] * amount, baseline=baseline[key])
        resolved[name] = entry
    return resolved


def _lifetime_peak(process):
    """Per-process peak resident memory where the OS records it."""
    if os.name == "nt":
        return getattr(process.memory_info(), "peak_wset", None)
    status = Path(f"/proc/{process.pid}/status")
    if status.exists():
        for line in status.read_text(encoding="ascii", errors="replace").splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024
    return None


EXACT_NOTE = ("cgroup memory.peak of a systemd user scope: the whole process tree, exact except growth in "
              "the last ~10 ms; includes page cache charged to the run")


def exact_memory_prefix():
    """Command prefix that runs a command in its own systemd user scope, or raise why it can't."""
    import shutil
    import subprocess
    if not sys.platform.startswith("linux"):
        raise ValueError("--exact-memory needs Linux with cgroup v2 and a systemd user manager")
    if not shutil.which("systemd-run"):
        raise ValueError("--exact-memory needs systemd-run")
    probe = subprocess.run(["systemd-run", "--user", "--scope", "--quiet", "--", "cat", "/proc/self/cgroup"],
                           capture_output=True, text=True, timeout=30)
    if probe.returncode != 0 or ".scope" not in probe.stdout:
        raise ValueError("--exact-memory could not start a systemd user scope: "
                         + (probe.stderr.strip() or probe.stdout.strip() or "no output"))
    return ["systemd-run", "--user", "--scope", "--quiet", "--"]


class PeakMonitor(Monitor):
    """Adds OS-recorded per-process peaks so short spikes between samples still count.

    With `exact`, the command runs in its own systemd user scope and the scope's
    cgroup memory.peak (a high-water mark of the whole tree) replaces the estimate.
    """

    def __init__(self, exact=False):
        super().__init__()
        self.lifetime = {}
        self.exact = exact
        self.peak_file = None
        self.cgroup_peak = None

    def _read_cgroup_peak(self, pid):
        if self.peak_file is None:
            try:
                line = Path(f"/proc/{pid}/cgroup").read_text(encoding="ascii").strip().splitlines()[-1]
            except OSError:
                return
            path = line.split("::", 1)[-1]
            if not path.endswith(".scope") or "/user@" not in path:
                return  # systemd-run has not moved itself into the scope yet
            self.peak_file = Path("/sys/fs/cgroup" + path) / "memory.peak"
        try:
            value = int(self.peak_file.read_text(encoding="ascii"))
        except (OSError, ValueError):
            return
        self.cgroup_peak = max(self.cgroup_peak or 0, value)

    def sample(self, process):
        super().sample(process)
        if self.exact:
            self._read_cgroup_peak(process.pid)
        try:
            root = psutil.Process(process.pid)
            processes = [root, *root.children(recursive=True)]
        except psutil.Error:
            return
        for child in processes:
            try:
                peak = _lifetime_peak(child)
                if peak:
                    key = (child.pid, child.create_time())
                    self.lifetime[key] = max(self.lifetime.get(key, 0), peak)
            except (psutil.Error, OSError, ValueError):
                continue

    def metrics(self):
        values = super().metrics()
        candidates = [v for v in (values["sampled_peak_rss_bytes"], max(self.lifetime.values(), default=None))
                      if v is not None]
        values["peak_memory_bytes"] = max(candidates) if candidates else None
        if self.exact:
            values["estimated_peak_memory_bytes"] = values["peak_memory_bytes"]
            values["peak_memory_bytes"] = self.cgroup_peak
        return values


def _fingerprint(root, skip):
    """Size and modification time of every file, to notice runs that leave state behind."""
    state = {}
    for current, directories, files in os.walk(root):
        current = Path(current)
        directories[:] = [d for d in directories
                          if d not in {".git", ".chilicrisp", "__pycache__"} and (current / d) != skip]
        for name in files:
            path = current / name
            try:
                stat = path.stat()
            except OSError:
                continue
            state[path.relative_to(root).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return state


def _changes(before, after):
    return {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}


def _run_once(command, workspace, directory, timeout, artifacts, shown=None, prefix=()):
    monitor = PeakMonitor(exact=bool(prefix))
    command = [*prefix, *command]
    config = {"command_seconds": timeout, "output_bytes_per_stream": 4 * 1024 * 1024}
    result = execute(command, workspace, directory, config, time.monotonic() + timeout, observer=monitor)
    if shown is not None:
        # Hidden input: keep its arguments out of everything written next to the report.
        result["command"] = shown
        persist(directory / "command.json", {k: v for k, v in result.items() if k != "metrics"})
    values = {"wall_seconds": result["elapsed_seconds"], **monitor.metrics()}
    try:
        values["artifact_bytes"] = artifact_size(workspace, artifacts) if artifacts else None
    except (ValueError, OSError) as error:
        result.update(outcome="runner_failure", error=str(error))
        values["artifact_bytes"] = None
    result.update(metrics=values, samples=monitor.samples)
    persist(directory / "measurement.json", result)
    return result


def _summarize(runs):
    keys = {METRICS[name][0] for name in METRICS}
    medians = {}
    for key in sorted(keys):
        values = [run["metrics"].get(key) for run in runs if run["metrics"].get(key) is not None]
        medians[key] = statistics.median(values) if values else None
    digests = {run["capture"].get("stdout", {}).get("sha256") for run in runs}
    return {"runs": len(runs), "passed": sum(run["outcome"] == "pass" for run in runs),
            "outcomes": [run["outcome"] for run in runs], "metrics": medians,
            "min_samples": min((run["samples"] for run in runs), default=0),
            "stdout_sha256": digests.pop() if len(digests) == 1 else None,
            "stdout_stable": len(digests) == 0}


def scan(brief, workspace):
    """Find source lines that break the brief's `forbid` rules."""
    violations = []
    rules = [(re.compile(rule["pattern"]), rule.get("glob", "*"), rule["why"]) for rule in brief.get("forbid", [])]
    if not rules:
        return violations
    root = Path(workspace)
    for current, directories, files in os.walk(root):
        directories[:] = sorted(d for d in directories if d not in EXCLUDED and not d.endswith(".egg-info"))
        for name in sorted(files):
            path = Path(current) / name
            if path.stat().st_size > 2 * 1024 * 1024:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            relative = path.relative_to(root).as_posix()
            for pattern, glob, why in rules:
                if not fnmatch.fnmatch(name, glob) and not fnmatch.fnmatch(relative, glob):
                    continue
                for number, line in enumerate(lines, 1):
                    if pattern.search(line):
                        violations.append({"file": relative, "line": number, "pattern": pattern.pattern,
                                           "why": why, "text": line.strip()[:200]})
    return violations


def check(spec, command, workspace, out, *, baseline_workspace=None, repeat=3, timeout=300.0,
          same_output=False, where=False, ratchet=None, tolerance=0.10, exact_memory=False):
    """Measure `command` against a brief. Returns a report; verdict 'fits' means every check passed."""
    brief = load(spec)
    if not command:
        raise ValueError("Give the command to measure after `--`")
    if repeat < 1:
        raise ValueError("--repeat must be at least 1")
    if tolerance < 0:
        raise ValueError("--tolerance can't be negative")
    scope = exact_memory_prefix() if exact_memory else ()
    if same_output and baseline_workspace is None:
        raise ValueError("--same-output needs --baseline")
    workspace = Path(workspace).resolve()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    artifacts = brief.get("artifacts", [])
    arms = ["candidate"] + (["baseline"] if baseline_workspace is not None else [])
    roots = {"candidate": workspace, "baseline": Path(baseline_workspace).resolve() if baseline_workspace else None}
    skip = out.resolve()
    initial = {arm: _fingerprint(roots[arm], skip) for arm in arms}
    changed = {arm: set() for arm in arms}
    declared = brief.get("inputs")
    inputs_args = [item["args"] for item in declared or [{"args": []}]]
    inputs = []
    for number, item in enumerate(declared or [{"args": []}], 1):
        hidden = item.get("hidden", False)
        runs = {arm: [] for arm in arms}
        prefix = f"in{number}-" if declared else ""
        for index in range(repeat):
            # Alternate the order so drift (thermal, cache, background load) does not favour one side.
            for arm in (arms if index % 2 == 0 else list(reversed(arms))):
                runs[arm].append(_run_once([*command, *item["args"]], roots[arm], out / f"{prefix}{arm}-{index}",
                                           timeout, artifacts, shown=[*command, "<hidden>"] if hidden else None,
                                           prefix=scope))
                changed[arm].update(_changes(initial[arm], _fingerprint(roots[arm], skip)))
        inputs.append({"label": (f"input {number}" + (" (hidden)" if hidden else "")) if declared else None,
                       "hidden": hidden, "args": None if hidden else item["args"],
                       "candidate": _summarize(runs["candidate"]),
                       "baseline": _summarize(runs["baseline"]) if "baseline" in runs else None})
    # Budgets are judged on the last (largest) input; correctness on every input.
    candidate, baseline = inputs[-1]["candidate"], inputs[-1]["baseline"]
    budgets = resolve(brief, baseline["metrics"] if baseline else None)
    findings = []
    for name, entry in budgets.items():
        value = candidate["metrics"].get(METRICS[name][0])
        entry["measured"] = value
        if entry["limit"] is None:
            entry["status"] = "needs_baseline"
            findings.append(f"{name}: relative budget {entry['declared']} needs --baseline")
        elif value is None:
            entry["status"] = "unmeasured"
            findings.append(f"{name}: no measurement (declare `artifacts` or batch more work)")
        else:
            entry["headroom"] = None if entry["limit"] == 0 else 1 - value / entry["limit"]
            entry["status"] = "within" if value <= entry["limit"] else "over"
            if entry["status"] == "over":
                findings.append(f"{name}: {_format(value, entry['unit'])} is over "
                                f"{_format(entry['limit'], entry['unit'])}")
            elif entry["limit"] == 0 and METRICS[name][0].startswith("sampled_"):
                findings.append(f"{name}: measured 0 against a zero budget, but this counter is sampled; "
                                "activity between samples can be missed. Use the enforced tier if "
                                "zero must be guaranteed.")
    sampled = any(METRICS[name][0].startswith("sampled_") or name == "peak_memory_bytes" for name in budgets)
    if sampled and candidate["min_samples"] < 3:
        findings.append("Few samples were taken; the command finishes too fast for reliable sampling. "
                        "Batch more work per run.")
    violations = scan(brief, workspace)
    findings += [f"{v['file']}:{v['line']} breaks a rule ({v['why']})" for v in violations]
    output_ok, failed = True, []
    for entry in inputs:
        own, base = entry["candidate"], entry["baseline"]
        label = f"{entry['label']}: " if entry["label"] else ""
        if own["passed"] < own["runs"] or (base and base["passed"] < base["runs"]):
            failed.append(f"{label}Command failed: candidate {own['outcomes']}"
                          + (f", baseline {base['outcomes']}" if base else ""))
        if not own["stdout_stable"]:
            output_ok = False
            findings.append(f"{label}Candidate stdout differs between runs")
        if same_output and base is not None and own["stdout_sha256"] != base["stdout_sha256"]:
            output_ok = False
            findings.append(f"{label}Candidate stdout differs from the baseline")
    allowed = brief.get("writes", [])
    # Paths the baseline also changes are the program's normal output, not a cache.
    written = sorted(path for path in changed["candidate"] - changed.get("baseline", set())
                     if not any(fnmatch.fnmatch(path, glob) for glob in allowed))
    if written:
        shown = ", ".join(written[:5]) + (f" and {len(written) - 5} more" if len(written) > 5 else "")
        findings.append(f"The candidate changed files in its directory during the check ({shown}). If a later "
                        "run reads them back, the measurements can't be trusted. Declare expected output "
                        "files under `writes` in the brief.")
    saved = _load_ratchet(ratchet, brief) if ratchet else {}
    regressed = []
    for name, entry in budgets.items():
        previous, value = saved.get(name), entry.get("measured")
        if previous is not None and value is not None and value > previous * (1 + tolerance):
            regressed.append(name)
            findings.append(f"{name}: {_format(value, entry['unit'])} regressed past the ratchet "
                            f"({_format(previous, entry['unit'])} + {tolerance:.0%})")
    statuses = {entry["status"] for entry in budgets.values()}
    if failed:
        verdict = "broken"
        findings[:0] = failed
    elif not output_ok or violations:
        verdict = "broken"
    elif "over" in statuses or regressed:
        verdict = "over_budget"
    elif statuses - {"within"} or written:
        verdict = "incomplete"
    else:
        verdict = "fits"
    ratchet_state = None
    if ratchet:
        tightened = dict(saved)
        if verdict == "fits":
            for name, entry in budgets.items():
                if entry.get("measured") is not None:
                    tightened[name] = min(saved.get(name, entry["measured"]), entry["measured"])
            persist(Path(ratchet), {"kind": "chilicrisp_ratchet", "brief": brief["name"], "metrics": tightened})
        ratchet_state = {"file": str(ratchet), "previous": saved or None, "tolerance": tolerance,
                         "regressed": regressed, "updated": verdict == "fits"}
    located = None
    if where:
        # Separate, unmeasured run: tracing slows the program and adds memory of its own.
        located = breakdown([*command, *inputs_args[-1]], workspace, out / "where", timeout)
        if "error" in located:
            findings.append(f"Memory breakdown unavailable: {located['error']}")
    shared = deepcopy(brief)
    for item in shared.get("inputs", []):
        if item.get("hidden"):
            item["args"] = ["<hidden>"]
    report = {"kind": "constraint_check", "verdict": verdict, "brief": shared, "command": command,
              "workspace": str(workspace), "baseline_workspace": str(roots["baseline"]) if baseline else None,
              "repeat": repeat, "budgets": budgets, "candidate": candidate, "baseline": baseline,
              "inputs": inputs if declared else None, "changed_files": written, "where": located,
              "ratchet": ratchet_state,
              "rule_violations": violations, "findings": findings, "environment": environment(),
              "enforcement": "none: measured after the fact on this machine",
              "measurement_notes": {name: EXACT_NOTE if exact_memory and name == "peak_memory_bytes"
                                    else METRICS[name][3] for name in budgets}}
    persist(out / "report.json", report)
    report["report"] = str(out / "report.json")
    return report


def _load_ratchet(path, brief):
    path = Path(path)
    if not path.is_file():
        return {}
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved.get("kind") != "chilicrisp_ratchet" or saved.get("brief") != brief["name"]:
        raise ValueError(f"{path} is not a ratchet for brief {brief['name']!r}")
    return saved["metrics"]


def _format(value, unit):
    if value is None:
        return "n/a"
    if unit == "bytes":
        for suffix, size in (("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024)):
            if abs(value) >= size:
                return f"{value / size:.1f} {suffix}"
        return f"{value:.0f} B"
    return f"{value * 1000:.0f} ms" if value < 1 else f"{value:.2f} s"


def _judging(brief):
    """How inputs and leftover files are judged, without revealing hidden inputs."""
    writes = brief.get("writes", [])
    notes = ["Every run must start from the same files. Don't keep results between runs: files the "
             "command creates or changes in the project are flagged"
             + (f", except declared outputs ({', '.join(f'`{w}`' for w in writes)})." if writes else ".")]
    inputs = brief.get("inputs")
    if inputs:
        shown = [f"`{' '.join(i['args']) or '(no arguments)'}`" for i in inputs if not i.get("hidden")]
        hidden = len(inputs) - len(shown)
        parts = shown + ([f"{hidden} hidden input{'s' if hidden > 1 else ''} you won't see"] if hidden else [])
        notes.append(f"It runs on {len(inputs)} inputs, smallest first: {', '.join(parts)}. The command must "
                     "succeed and the output must match on every one of them. Budgets are judged on the last "
                     "(largest) input.")
    return [line for note in notes for line in ("", note)]


def _limits(budgets):
    """Measurement caveats the agent should know, so it neither over-trusts nor games the numbers."""
    notes = []
    if "peak_memory_bytes" in budgets:
        notes.append("Peak memory across several processes is approximate: shared pages can be counted "
                     "twice, and peaks in short-lived child processes can be missed. Fit the budget for "
                     "real; don't rely on splitting work across processes.")
    zero = [METRICS[name][2].lower() for name, entry in budgets.items()
            if entry["limit"] == 0 and METRICS[name][0].startswith("sampled_")]
    if zero:
        notes.append(f"A zero budget ({', '.join(zero)}) means none at all, even though a brief burst "
                     "between samples might not be measured.")
    return [line for note in notes for line in ("", note)]


def _where_lines(located, peak):
    if not located or not located.get("sites"):
        return []
    lines = ["", "## Where memory goes", "",
             f"Python allocations still alive near the traced peak ({_format(located['snapshot_bytes'], 'bytes')}"
             + (f"; the measured process peak was {_format(peak, 'bytes')}" if peak else "")
             + "). Interpreter overhead and memory held by C extensions aren't included.", "",
             "| Site | Size | Blocks |", "| --- | --- | --- |"]
    lines += [f"| `{s['file']}:{s['line']}` | {_format(s['bytes'], 'bytes')} | {s['count']} |" for s in located["sites"]]
    return lines


def render(spec, report=None):
    """Agent-facing markdown for a brief, optionally filled in with a previous check's numbers."""
    brief = load(spec)
    budgets = report["budgets"] if report else resolve(brief)
    lines = [f"# Constraint brief: {brief['name']}", "", f"> {brief['story']}", "",
             "## Budgets", "", "| Resource | Budget | Baseline today | Last measured |", "| --- | --- | --- | --- |"]
    for name, entry in budgets.items():
        unit = entry["unit"]
        budget = _format(entry["limit"], unit) if entry["limit"] is not None else ""
        if entry["kind"] == "relative":
            budget = f"{budget} ({entry['declared']} of baseline)".strip() if budget else f"{entry['declared']} of baseline"
        lines.append(f"| {METRICS[name][2]} | {budget} | {_format(entry.get('baseline'), unit)} | "
                     f"{_format(entry.get('measured'), unit)} |")
    rules = brief.get("rules", []) + [f"Must not match `{r['pattern']}`"
                                      + (f" in `{r['glob']}`" if r.get("glob") else "") + f": {r['why']}. (checked)"
                                      for r in brief.get("forbid", [])]
    if rules:
        lines += ["", "## Rules", "", *[f"- {rule}" for rule in rules]]
    if brief.get("artifacts"):
        lines += ["", "Artifact size counts: " + ", ".join(f"`{a}`" for a in brief["artifacts"]) + "."]
    lines += ["", "## How this is judged", "",
              "Your work runs on an ordinary machine, several times, alternating with the original. "
              "The median of each measurement must fit its budget, the command must succeed every time, "
              "and output must match the original exactly. Nothing is emulated: the budgets are a design "
              "target, not a sandbox. Don't game the measurement (for example by moving work outside the "
              "measured command); that defeats the exercise.",
              *_judging(brief),
              *_limits(budgets),
              "", "## Design pressure", "",
              "These budgets are set below what the current design needs on purpose. Small trims "
              "usually won't close the gap. Find what actually consumes the resource, then change the "
              "approach. Say what you expect to save before you change it.", ""]
    lines += [f"- {hint}" for hint in [*brief.get("hints", []), *DEFAULT_HINTS]]
    if report:
        findings = [f"- {f}" for f in report["findings"]] or ["- Everything fits."]
        lines += ["", f"## Last check: {report['verdict']}", "", *findings]
        lines += _where_lines(report.get("where"), report["candidate"]["metrics"].get("peak_memory_bytes"))
    return "\n".join(lines) + "\n"


def profiles():
    return {name: {"story": p["story"], "budgets": p["budgets"]} for name, p in PROFILES.items()}

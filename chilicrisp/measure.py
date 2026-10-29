"""Trusted local process measurements with explicit sampled accounting limits."""
import importlib.metadata
import os
from pathlib import Path
import platform
import sys

import psutil

from .project import execute, persist
from .runner import file_hash


METRICS = {"wall_seconds", "sampled_peak_rss_bytes", "sampled_cpu_seconds",
           "artifact_bytes", "sampled_io_read_bytes", "sampled_io_write_bytes"}
METRIC_QUALITY = {
    "artifact_bytes": {"tier": "exact_declared_volume", "scope": "logical bytes in selected files"},
    "wall_seconds": {"tier": "repeated_timing", "scope": "instrumented command and cleanup"},
    **{name: {"tier": "screening_sample", "scope": "observed process samples; incomplete coverage possible"}
       for name in METRICS if name.startswith("sampled_")},
}


def environment():
    return {"platform": platform.platform(), "machine": platform.machine(),
            "cpu_count": os.cpu_count(), "python": sys.version,
            "psutil": importlib.metadata.version("psutil"), "collector_sha256": file_hash(__file__)}


class Monitor:
    def __init__(self):
        self.samples = 0
        self.peak = None
        self.cpu = {}
        self.io = {}
        self.errors = set()

    def sample(self, process):
        try:
            root = psutil.Process(process.pid)
            processes = [root, *root.children(recursive=True)]
        except psutil.Error as error:
            self.errors.add(type(error).__name__)
            return
        rss, observed = 0, False
        for child in processes:
            try:
                key = (child.pid, child.create_time())
                with child.oneshot():
                    rss += child.memory_info().rss
                    observed = True
                    times = child.cpu_times()
                    self.cpu[key] = max(self.cpu.get(key, 0), times.user + times.system)
                    try:
                        counters = child.io_counters()
                        previous = self.io.get(key, (0, 0))
                        self.io[key] = (max(previous[0], counters.read_bytes),
                                        max(previous[1], counters.write_bytes))
                    except (psutil.Error, AttributeError, NotImplementedError) as error:
                        self.errors.add(type(error).__name__)
            except psutil.Error as error:
                self.errors.add(type(error).__name__)
        if observed:
            self.samples += 1
            self.peak = max(self.peak or 0, rss)

    def metrics(self):
        return {"sampled_peak_rss_bytes": self.peak,
                "sampled_cpu_seconds": sum(self.cpu.values()) if self.cpu else None,
                "sampled_io_read_bytes": sum(value[0] for value in self.io.values()) if self.io else None,
                "sampled_io_write_bytes": sum(value[1] for value in self.io.values()) if self.io else None}


def artifact_size(workspace, paths):
    if not paths:
        return None
    workspace = Path(workspace).resolve()
    seen = set()
    total = 0
    for name in paths:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Artifact paths must stay within the measured workspace")
        target = workspace / relative
        if not target.exists():
            raise ValueError(f"Declared artifact is missing: {name}")
        for path in [target, *sorted(target.rglob("*"))] if target.is_dir() else [target]:
            if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(workspace):
                raise ValueError("Artifact links or escaped paths are unsupported")
            if path.is_file() and path not in seen:
                total += path.stat().st_size
                seen.add(path)
            elif not path.is_file() and not path.is_dir():
                raise ValueError("Artifact contains a special file")
    return total


def measure(command, workspace, directory, config, deadline, artifact_paths=()):
    monitor = Monitor()
    result = execute(command, workspace, directory, config, deadline, observer=monitor)
    values = {"wall_seconds": result["elapsed_seconds"], **monitor.metrics()}
    try:
        values["artifact_bytes"] = artifact_size(workspace, artifact_paths)
    except (ValueError, OSError) as error:
        result.update(outcome="runner_failure", error=str(error))
        values["artifact_bytes"] = None
    result.update(metrics=values, metric_quality=METRIC_QUALITY,
                  samples=monitor.samples, collector_errors=sorted(monitor.errors),
                  environment=environment(), enforcement="none",
                  limitations=["Trusted host execution; no resource scarcity is enforced.",
                    "RSS is a sampled sum across observed processes and may double-count shared pages.",
                    "Short-lived processes and CPU/I/O after their last sample can be missed.",
                    "I/O counters have platform-specific semantics; artifact bytes are logical file sizes."])
    persist(Path(directory) / "measurement.json", result)
    return result

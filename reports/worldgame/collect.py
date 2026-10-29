"""Normal Windows baseline only. No resource limit or optimization claim."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from chilicrisp.capture import capture


class Memory(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
            "PagefileUsage", "PeakPagefileUsage")]


def main():
    if sys.platform != "win32":
        raise SystemExit("This collector measures Windows process counters only")
    directory = Path(__file__).parent / datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")
    directory.mkdir()
    source = Path(r"Z:\worldgame")
    executable = ROOT / "artifacts/worldgame-target/release/examples/oceanbench.exe"
    metadata = dict(kind="normal_windows_baseline_no_enforced_scarcity",
        collected_at=datetime.now(timezone.utc).isoformat(), platform=platform.platform(),
        binary=str(executable), binary_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
        build_command=["cargo", "build", "--locked", "--offline", "--release", "-p", "mote-core",
                       "--example", "oceanbench", "--manifest-path", str(source / "Cargo.toml"),
                       "--target-dir", str(ROOT / "artifacts/worldgame-target")],
        cache_policy="uncontrolled sequential runs; first run not excluded",
        accounting="single Windows process; GetProcessMemoryInfo lifetime peak counters",
        trials=[])
    for command, key in [(["git", "-C", str(source), "rev-parse", "HEAD"], "source_revision"),
                         (["git", "-C", str(source), "status", "--porcelain"], "source_status"),
                         (["rustc", "--version"], "rustc"), (["cargo", "--version"], "cargo")]:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        metadata[key] = dict(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)
    metadata["source_files_sha256"] = {
        file.relative_to(source).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in [source / "Cargo.toml", source / "Cargo.lock",
                     *sorted((source / "crates/mote-core").rglob("*.rs"))]}
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    for index in range(3):
        trial_dir = directory / str(index + 1)
        trial_dir.mkdir()
        start = time.monotonic()
        process = subprocess.Popen([str(executable)], cwd=trial_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        overflow, summaries, threads = capture(process, trial_dir, 1048576)
        peak_ws = peak_commit = None
        samples = 0
        reason = "completed"
        try:
            while True:
                memory = Memory()
                memory.cb = ctypes.sizeof(memory)
                if psapi.GetProcessMemoryInfo(int(process._handle), ctypes.byref(memory), memory.cb):
                    peak_ws = max(peak_ws or 0, memory.PeakWorkingSetSize)
                    peak_commit = max(peak_commit or 0, memory.PeakPagefileUsage)
                    samples += 1
                if process.poll() is not None:
                    break
                if overflow.is_set() or time.monotonic() - start > 120:
                    reason = "output_limit" if overflow.is_set() else "timeout"
                    process.kill()
                    break
                time.sleep(.02)
        finally:
            process.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=5)
        trial = dict(index=index + 1, exit_code=process.returncode, reason=reason,
            elapsed_seconds=time.monotonic() - start, peak_working_set_bytes=peak_ws,
            peak_commit_bytes=peak_commit, memory_counter_samples=samples, output=summaries)
        metadata["trials"].append(trial)
        (directory / "baseline.json").write_text(json.dumps(metadata, indent=2))
        print(json.dumps(trial), flush=True)
        if process.returncode or reason != "completed":
            break
    print(str(directory / "baseline.json"))


if __name__ == "__main__":
    main()

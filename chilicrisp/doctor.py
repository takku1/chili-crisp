"""Read-only setup diagnostics. Native fixture results remain a separate gate."""
import ctypes.util
import importlib.metadata
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys


def diagnose(manifest=None):
    checks = []

    def add(name, ready, detail):
        checks.append({"name": name, "status": "ready" if ready else "unavailable", "detail": detail})

    add("python", sys.version_info >= (3, 12), platform.python_version())
    try:
        add("jsonschema", True, importlib.metadata.version("jsonschema"))
    except importlib.metadata.PackageNotFoundError:
        add("jsonschema", False, "Install Chili Crisp's declared dependencies")
    try:
        add("psutil", True, importlib.metadata.version("psutil"))
    except importlib.metadata.PackageNotFoundError:
        add("psutil", False, "Install Chili Crisp's declared dependencies")
    linux = sys.platform == "linux"
    add("linux", linux, platform.platform())
    if linux:
        add("unprivileged_identity", os.geteuid() != 0, f"uid={os.geteuid()}")
        executable = shutil.which("bwrap")
        version, supported = None, False
        if executable:
            try:
                probe = subprocess.run([executable, "--version"], capture_output=True, text=True,
                                       timeout=5, check=True)
                version = probe.stdout.strip()
                numbers = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
                supported = bool(numbers and tuple(map(int, numbers.groups())) >= (0, 12, 0))
            except (OSError, subprocess.SubprocessError) as error:
                version = str(error)
        add("bubblewrap", supported, version or "Install bubblewrap >=0.12.0")
        add("libseccomp", ctypes.util.find_library("seccomp") is not None, "Host shared library lookup")
        controllers = Path("/sys/fs/cgroup/cgroup.controllers")
        available = controllers.read_text().split() if controllers.is_file() else []
        add("cgroup_v2_controllers", {"memory", "pids"}.issubset(available), available)
    preflight = None
    if manifest is None:
        add("manifest_preflight", False, "Supply --manifest to check rootfs experiment prerequisites and delegation")
    if manifest is not None:
        from .runner import file_hash, preflight as probe, tree_hash, validate
        validate(manifest, "experiment")
        try:
            preflight = probe(manifest, manifest["search"]["initial_budget"])
            if tree_hash(manifest["target"]["rootfs"]) != manifest["target"]["rootfs_hash"]:
                raise ValueError("Rootfs hash does not match the frozen artifact")
            for workload in manifest["workloads"]:
                if file_hash(workload["input"]) != workload["input_hash"]:
                    raise ValueError(f"Input hash mismatch: {workload['id']}")
                oracle = workload.get("oracle")
                if oracle and file_hash(oracle["policy_path"]) != oracle["policy_hash"]:
                    raise ValueError(f"Oracle policy hash mismatch: {workload['id']}")
            add("manifest_preflight", True, "Read-only preflight passed; fixtures not executed")
        except Exception as error:
            add("manifest_preflight", False, f"{type(error).__name__}: {error}")
    return {"kind": "setup_diagnostics", "checks": checks,
            "local_workflow_ready": all(c["status"] == "ready" for c in checks[:3]),
            "native_prerequisites_ready": linux and all(c["status"] == "ready" for c in checks),
            "native_validation": "not_run", "preflight": preflight}

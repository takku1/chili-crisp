"""Provision a fresh disposable Ubuntu fixture lab and run a delegated service.

Run with sudo inside the selected Linux VM. Only a fresh lab and transient
service are created; existing labs, system security policy and workloads remain.
"""
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import tempfile


def provision(*, worker_name="native-worker.py", prepare=None):
    if sys.platform != "linux" or os.geteuid() != 0:
        raise SystemExit("Run as root inside the disposable Ubuntu research VM")
    source = Path(__file__).resolve().parents[1]
    account = pwd.getpwnam("chili-runner")
    lab = Path(tempfile.mkdtemp(prefix="fixture-", dir="/home/chili-runner/chili-lab"))
    checkout = lab / "source"
    checkout.mkdir()
    for name in ("chilicrisp", "tests", "examples"):
        shutil.copytree(source / name, checkout / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("pyproject.toml", "README.md", "MANIFEST.in"):
        shutil.copy2(source / name, checkout / name)
    venv = lab / "venv"
    subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)], check=True)
    python = venv / "bin/python"
    subprocess.run([str(python), "-m", "pip", "install", "jsonschema>=4.26,<5", "psutil>=7.2,<8"], check=True)
    rootfs = lab / "rootfs"
    for name in ("usr/bin", "fixtures", "proc", "dev", "tmp"):
        (rootfs / name).mkdir(parents=True)
    executable = Path(sys.executable).resolve()
    shutil.copy2(executable, rootfs / "usr/bin/python3")
    stdlib = Path(f"/usr/lib/python{sys.version_info.major}.{sys.version_info.minor}")
    shutil.copytree(stdlib, rootfs / stdlib.relative_to("/"),
                    ignore=shutil.ignore_patterns("__pycache__", "site-packages", "dist-packages"))
    binaries = [executable, *stdlib.rglob("*.so")]
    libraries = set()
    for binary in binaries:
        linked = subprocess.run(["ldd", str(binary)], capture_output=True, text=True, check=True).stdout
        libraries.update(re.findall(r"(/[^\s()]+)", linked))
    for library in sorted(libraries):
        target = rootfs / library.lstrip("/")
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(library, target)
    shutil.copy2(source / "tests/workload.py", rootfs / "fixtures/workload.py")
    (lab / "empty-input").write_bytes(b"")
    shutil.copy2(source / "tools" / worker_name, lab / "worker.py")
    frozen_roots = [rootfs]
    if prepare is not None:
        frozen_roots.extend(prepare(lab, rootfs))
    for path in [lab, *lab.rglob("*")]:
        if not any(path.is_relative_to(frozen) for frozen in frozen_roots):
            os.chown(path, account.pw_uid, account.pw_gid)
    # Owner-controlled fixture artifact; the unprivileged runner cannot modify it.
    for frozen in frozen_roots:
        for path in [frozen, *frozen.rglob("*")]:
            if not path.is_symlink():
                path.chmod(path.stat().st_mode & ~0o222)
    unit = "chili-" + lab.name
    command = ["systemd-run", "--wait", "--pipe", "--collect", "--service-type=exec",
               "--unit", unit, "--property=User=chili-runner", "--property=Delegate=yes",
               "--property=WorkingDirectory=" + str(checkout), str(python), str(lab / "worker.py")]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (lab / "native.log").write_text(completed.stdout)
    print(completed.stdout)
    destination = source / "artifacts" / ("native-" + lab.name)
    destination.mkdir(parents=True)
    for name in ("native.log", "native-summary.json", "manifest.json", "cpu-sweep.json",
                 "dogfood-plan.json", "dogfood-measurements.json", "dogfood-summary.json"):
        if (lab / name).exists():
            shutil.copy2(lab / name, destination / name)
    if (lab / "evidence").exists():
        shutil.copytree(lab / "evidence", destination / "evidence")
    if (lab / "development-session").exists():
        shutil.copytree(lab / "development-session", destination / "development-session")
    for name in ("development-plan.json", "development-manifest.json"):
        if (lab / name).exists():
            shutil.copy2(lab / name, destination / name)
    print(json.dumps({"lab": str(lab), "evidence": str(destination),
                      "exit_code": completed.returncode}, indent=2))
    return completed.returncode


def main():
    return provision()


if __name__ == "__main__":
    raise SystemExit(main())

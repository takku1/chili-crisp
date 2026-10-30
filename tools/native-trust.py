"""Run the compiled sealed-acceptance flow across separate Unix accounts.

Root acts only as owner/provisioner. chili-agent proposes source, chili-runner
operates the development controller, chili-grader holds the vault and signing
key. Each phase runs as its own account; probes record what each account can
reach outside its role. Run with sudo inside a disposable Ubuntu host or CI VM.
"""
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import tempfile

ACCOUNTS = ("chili-runner", "chili-agent", "chili-grader")
# Paths each account may legitimately reach in the probe list; everything else must be refused.
ALLOWED = {
    "chili-agent": set(),
    "chili-runner": {"read controller/plan.json", "read controller/session/state.json",
                     "write controller/plan.json", "write controller/session/state.json",
                     "write exchange/request/request.json"},
    "chili-grader": {"read vault/key", "read vault/input", "read vault/policy.json",
                     "write vault/policy.json", "write receipts/receipt.json"},
}


def _load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def own(path, account, directory_mode, file_mode):
    entry = pwd.getpwnam(account)
    for item in [path, *path.rglob("*")]:
        os.chown(item, entry.pw_uid, entry.pw_gid, follow_symlinks=False)
        if not item.is_symlink():
            item.chmod(directory_mode if item.is_dir() else file_mode)


def main():
    if sys.platform != "linux" or os.geteuid() != 0:
        raise SystemExit("Run as root inside a disposable Ubuntu host")
    for account in ACCOUNTS:
        try:
            pwd.getpwnam(account)
        except KeyError:
            subprocess.run(["useradd", "--system", "--no-create-home", "--shell", "/usr/sbin/nologin", account], check=True)
    source = Path(__file__).resolve().parents[1]
    base = Path("/srv/chili-trust")
    base.mkdir(mode=0o755, exist_ok=True)
    lab = Path(tempfile.mkdtemp(prefix="lab-", dir=base))
    lab.chmod(0o755)
    checkout = lab / "source"
    checkout.mkdir()
    for name in ("chilicrisp", "examples"):
        shutil.copytree(source / name, checkout / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(source / "tests", checkout / "tests", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "test-artifacts-*"))
    venv = lab / "venv"
    subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)], check=True)
    python = str(venv / "bin/python")
    subprocess.run([python, "-m", "pip", "install", "-q", "jsonschema>=4.26,<5", "psutil>=7.2,<8", "cryptography>=46,<51"], check=True)
    rootfs = _load("native-fixtures").runtime_rootfs(source, lab)
    _load("native-build").prepare(lab, rootfs)
    (lab / "empty-input").write_bytes(b"")
    for name in ("native-trust-roles.py", "acceptance-audit.py"):
        shutil.copy2(source / "tools" / name, lab / name)
    # Everything provisioned so far stays root-owned. Copies from a drvfs/Windows
    # checkout arrive 0777, so trusted code gets explicit modes; frozen roots lose write bits.
    own(checkout, "root", 0o755, 0o644)
    for name in ("native-trust-roles.py", "acceptance-audit.py"):
        (lab / name).chmod(0o644)
    for frozen in (lab / "rootfs", lab / "compiler-rootfs"):
        for path in [frozen, *frozen.rglob("*")]:
            if not path.is_symlink():
                path.chmod(path.stat().st_mode & ~0o222)
    for name in ("controller", "vault", "agent", "exchange", "receipts"):
        (lab / name).mkdir()
    units = {"develop": "chili-trust-run-" + lab.name, "grade": "chili-trust-grade-" + lab.name}
    parents = {phase: f"/sys/fs/cgroup/system.slice/{unit}.service/experiments" for phase, unit in units.items()}
    roles = [python, str(lab / "native-trust-roles.py")]

    def as_account(account, phase):
        completed = subprocess.run(["runuser", "-u", account, "--", *roles, phase, str(lab)],
                                   cwd=checkout, capture_output=True, text=True)
        if completed.returncode:
            raise RuntimeError(f"{phase} as {account} failed:\n{completed.stderr[-3000:]}")
        return json.loads(completed.stdout)

    def as_unit(account, phase):
        completed = subprocess.run(["systemd-run", "--wait", "--pipe", "--collect", "--quiet", "--service-type=exec",
            "--unit", units[phase], "--property=User=" + account, "--property=Delegate=yes",
            "--property=WorkingDirectory=" + str(checkout), *roles, phase, str(lab)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if completed.returncode:
            raise RuntimeError(f"{phase} unit as {account} failed:\n{completed.stdout[-2000:]}{completed.stderr[-3000:]}")
        return json.loads(completed.stdout)

    subprocess.run([*roles, "owner-setup", str(lab), parents["develop"], parents["grade"]], cwd=checkout,
                   check=True, stdout=subprocess.DEVNULL)
    # The 0700 directory protects the controller; files keep 0644 because source modes
    # are part of the exported identity the grader must re-read.
    own(lab / "controller", "chili-runner", 0o700, 0o644)
    own(lab / "vault", "chili-grader", 0o700, 0o600)
    own(lab / "agent", "chili-agent", 0o755, 0o644)
    own(lab / "exchange", "chili-runner", 0o755, 0o644)
    own(lab / "receipts", "chili-grader", 0o755, 0o644)
    summary = {"lab": str(lab), "accounts": {}}
    summary["propose"] = as_account("chili-agent", "propose")
    summary["develop"] = as_unit("chili-runner", "develop")
    summary["forge"] = as_account("chili-agent", "forge")
    summary["grade"] = as_unit("chili-grader", "grade")
    violations = []
    for account in ACCOUNTS:
        outcome = as_account(account, "probe")
        summary["accounts"][account] = outcome
        for attempt, result in outcome.items():
            if result == "absent" or (result == "allowed") != (attempt in ALLOWED[account]):
                violations.append(f"{account}: {attempt} {result}")
    summary["accept"] = as_account("chili-runner", "accept")
    audit = subprocess.run(["runuser", "-u", "chili-grader", "--", "env", "PYTHONPATH=" + str(checkout), python,
        str(lab / "acceptance-audit.py"), str(lab / "vault"), "--session", str(lab / "exchange/accepted")],
        cwd=checkout, capture_output=True, text=True)
    if audit.returncode:
        violations.append("audit failed: " + audit.stderr[-2000:])
    else:
        summary["audit"] = json.loads(audit.stdout)
    if summary["accept"]["forged_receipt"] == "imported" or summary["accept"]["genuine_receipt"] != "passed":
        violations.append("receipt import: " + json.dumps(summary["accept"]))
    leaks = summary["develop"]["remaining_cgroups"] + summary["grade"]["remaining_cgroups"]
    if leaks:
        violations.append("leaked cgroups: " + ", ".join(leaks))
    summary["violations"] = violations
    summary["status"] = "failed" if violations else "passed"
    destination = source / "artifacts" / ("trust-" + lab.name)
    destination.mkdir(parents=True)
    (destination / "trust-summary.json").write_text(json.dumps(summary, indent=2))
    for name in ("exchange", "receipts"):
        shutil.copytree(lab / name, destination / name)
    shutil.copytree(lab / "controller/session", destination / "development-session")
    print(json.dumps(summary, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Collect local status evidence; no candidate mutation or model calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chilicrisp.runner import tree_hash, file_hash

DEST = ROOT / "reports" / ("status-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
DEST.mkdir()
PY = sys.executable
records = []


def run(name, command, timeout=60):
    start = time.monotonic()
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=timeout)
        output = result.stdout + result.stderr
        code = result.returncode
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b"") + (error.stderr or b"") + b"\nCHECK TIMED OUT"
        code = None
    except OSError as error:
        output, code = str(error).encode(), None
    (DEST / f"{name}.log").write_bytes(output)
    record = dict(name=name, command=[str(arg) for arg in command], exit_code=code,
                  seconds=round(time.monotonic() - start, 3), log=f"{name}.log",
                  log_sha256=hashlib.sha256(output).hexdigest())
    text = output.decode("utf-8", errors="replace")
    record["tail"] = text[-1800:]
    if name == "unit-tests":
        count = re.search(r"Ran (\d+) tests", text)
        skipped = re.search(r"OK \(skipped=(\d+)\)", text)
        record["tests_run"] = int(count[1]) if count else None
        record["tests_skipped"] = int(skipped[1]) if skipped else 0
    print(f"{name}: exit={code}, {record['seconds']}s", flush=True)
    return record


def source_identity(path):
    return {"mote_core_tree": tree_hash(path / "crates/mote-core"),
            "cargo_toml": file_hash(path / "Cargo.toml"),
            "cargo_lock": file_hash(path / "Cargo.lock")}


checks = [
    ("unit-tests", [PY, "-m", "unittest", "discover", "-s", "tests", "-v"]),
    ("adapter-lint", [PY, "-m", "ruff", "check", "--no-cache", "chilicrisp/integrations",
                      "tests/test_integrations.py", "setup.py"]),
    ("manifest", [PY, "-m", "chilicrisp.runner", "validate", "examples/experiment.json"]),
    ("benchexec", [PY, "-m", "chilicrisp.integrations.benchexec", str(DEST / "benchexec")]),
    ("wsl", ["wsl", "--list", "--quiet"]),
    ("docker", ["docker", "version", "--format", "{{.Server.Version}}"]),
    ("rust", ["rustc", "+1.98.0", "--version"]),
]
with ThreadPoolExecutor(max_workers=4) as pool:
    records.extend(pool.map(lambda args: run(*args), checks))

records.append(run("pep517-build", [PY, "-m", "build", "--no-isolation"]))
if records[-1]["exit_code"] != 0:
    records.append(run("setuptools-build", [PY, "setup.py", "sdist", "bdist_wheel"]))
records.append(run("wheel-smoke", [PY, "tools/check-wheel.py"]))
dist_files = sorted((ROOT / "dist").glob("chilicrisp-*"))
records.append(run("twine", [PY, "-m", "twine", "check", *map(str, dist_files)]))

candidate = Path(r"Z:\worldgame")
baseline = ROOT / "artifacts/worldgame-frozen"
identities = {"baseline_before": source_identity(baseline),
              "candidate_before": source_identity(candidate)}
records.append(run("worldgame-baseline", [PY, "verification/worldgame/check.py", "--source",
                                         str(baseline)], timeout=300))
reference = None
if records[-1]["exit_code"] == 0:
    lines = (DEST / "worldgame-baseline.log").read_text(encoding="utf-8").splitlines()
    reference = Path(lines[0].strip()) if lines else None
    if reference and (reference / "results.json").is_file():
        records.append(run("worldgame-candidate", [PY, "verification/worldgame/check.py",
                            "--source", str(candidate), "--reference", str(reference)], timeout=300))
records.append(run("worldgame-core-tests", ["cargo", "+1.98.0", "test", "--offline", "--locked",
    "--manifest-path", str(candidate / "Cargo.toml"), "-p", "mote-core", "--target-dir",
    str(ROOT / "artifacts/status-worldgame-tests")], timeout=240))
identities.update(baseline_after=source_identity(baseline), candidate_after=source_identity(candidate))
versions = {}
for name in ("jsonschema", "openevolve", "BenchExec", "setuptools", "build", "ruff", "twine"):
    try:
        versions[name] = version(name)
    except PackageNotFoundError:
        versions[name] = None
report = dict(generated_utc=datetime.now(timezone.utc).isoformat(), python=sys.version,
              platform=sys.platform, versions=versions, checks=records,
              source_identities=identities, worldgame_reference=str(reference) if reference else None,
              artifacts={p.name: file_hash(p) for p in dist_files if p.is_file()},
              native_fixture_manifest_configured=bool(os.environ.get("CHILI_FIXTURE_MANIFEST")))
(DEST / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"REPORT: {DEST}", flush=True)

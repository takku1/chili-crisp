"""Owned negative control for tiered verification, not generated-code execution."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chilicrisp.runner import tree_hash

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
destination = ROOT / "reports" / ("screening-" + stamp)
destination.mkdir()
baseline = ROOT / "artifacts/worldgame-frozen"
candidate = ROOT / "artifacts" / ("incorrect-solver-" + stamp)
candidate.mkdir()
manifest = (baseline / "Cargo.toml").read_text()
old_members = 'members = ["crates/mote-core", "crates/mote-render", "crates/mote-game"]'
assert manifest.count(old_members) == 1
manifest = manifest.replace(old_members, 'members = ["crates/mote-core"]')
manifest = manifest.replace('default-members = ["crates/mote-game"]', 'default-members = ["crates/mote-core"]')
(candidate / "Cargo.toml").write_text(manifest)
shutil.copyfile(baseline / "Cargo.lock", candidate / "Cargo.lock")
shutil.copytree(baseline / "crates/mote-core", candidate / "crates/mote-core")
source = candidate / "crates/mote-core/src/numerics.rs"
original = source.read_text()
needle = "            if residual <= tolerance {\n"
assert original.count(needle) == 1
# Deliberately corrupt arrays after satisfying convergence, while preserving
# the success report. The independent analytic oracle must catch this.
changed = original.replace(needle, needle + "                x.iter_mut().for_each(|v| *v *= 0.99);\n")
source.write_text(changed)
(destination / "candidate.diff").write_text("".join(difflib.unified_diff(
    original.splitlines(True), changed.splitlines(True),
    fromfile="baseline/numerics.rs", tofile="negative-control/numerics.rs")))
baseline_hash = tree_hash(baseline / "crates/mote-core")
candidate_hash = tree_hash(candidate / "crates/mote-core")
reference = ROOT / "reports/worldgame/field-checks/20261029T041033487475Z"
records = []
for name, path, tier in (("good-screen", baseline, "screen"),
                         ("good-full", baseline, "full"),
                         ("bad-screen", candidate, "screen")):
    command = [sys.executable, "verification/worldgame/check.py", "--source", str(path),
               "--reference", str(reference), "--tier", tier]
    started = time.monotonic()
    run = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180)
    (destination / f"{name}.log").write_bytes(run.stdout + run.stderr)
    lines = run.stdout.decode().splitlines()
    evidence_path = Path(lines[0]) / "results.json" if lines else None
    evidence = json.loads(evidence_path.read_text()) if evidence_path and evidence_path.exists() else None
    records.append(dict(name=name, command=command, exit_code=run.returncode,
        elapsed_seconds=time.monotonic() - started,
        evidence=str(evidence_path), result=evidence))
    print(name, "exit", run.returncode, "evidence", evidence_path, flush=True)

stable = baseline_hash == tree_hash(baseline / "crates/mote-core")
checks = {
    "source_changed": candidate_hash != baseline_hash,
    "baseline_unchanged": stable,
    "good_screen_passed": records[0]["exit_code"] == 0 and records[0]["result"]["outcome"] == "pass",
    "good_full_passed": records[1]["exit_code"] == 0 and records[1]["result"]["outcome"] == "pass",
    "bad_candidate_compiled": records[2]["result"] is not None and records[2]["result"]["build_exit_code"] == 0,
    "bad_screen_rejected": records[2]["exit_code"] == 1 and records[2]["result"]["outcome"] == "reject",
    "no_acceptance_claim": all(record["result"] and not record["result"]["acceptance_eligible"] for record in records),
}
report = dict(kind="trusted negative-control screening pilot", checks=checks,
    baseline_source_hash=baseline_hash, candidate_source_hash=candidate_hash,
    candidate=str(candidate), diff_sha256=hashlib.sha256((destination / "candidate.diff").read_bytes()).hexdigest(),
    records=records, native_measurements=None, model_generated=False,
    promotion="not attempted; native resource and acceptance gates unavailable")
(destination / "results.json").write_text(json.dumps(report, indent=2))
print("REPORT:", destination, flush=True)
if not all(checks.values()):
    raise SystemExit("screening pilot checks failed; inspect retained evidence")

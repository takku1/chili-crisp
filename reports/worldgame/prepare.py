"""Freeze build inputs and grade saved outputs; does not run scarcity trials."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from chilicrisp.oracles import check_ocean
from chilicrisp.runner import file_hash, validate


def main():
    source = Path(r"Z:\worldgame")
    report = Path(__file__).parent
    original = json.loads((report / "run-20261029T013847905892Z/baseline.json").read_text())
    selected = [source / "Cargo.toml", source / "Cargo.lock", source / "README.md"]
    selected += sorted(file for file in (source / "crates").rglob("*") if file.is_file())
    for file in selected:
        if file.is_symlink():
            raise RuntimeError("snapshot refuses symlink source inputs")
    files = {file.relative_to(source).as_posix(): file.read_bytes() for file in selected}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    mismatches = [name for name, expected in original["source_files_sha256"].items()
                  if hashes.get(name) != expected]
    if mismatches:
        raise RuntimeError("source changed since baseline: " + ", ".join(mismatches))
    # Fail rather than freeze a source tree observed changing during collection.
    for name, expected in hashes.items():
        if file_hash(source / name) != expected:
            raise RuntimeError("source changed during snapshot: " + name)
    source_id = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    archive = report / ("worldgame-source-" + source_id[:16] + ".zip")
    if not archive.exists():
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, data in sorted(files.items()):
                bundle.writestr(name, data)
    with zipfile.ZipFile(archive) as bundle:
        archived = {name: hashlib.sha256(bundle.read(name)).hexdigest() for name in bundle.namelist()}
    if archived != hashes:
        raise RuntimeError("snapshot archive verification failed")
    metadata = dict(created_at=datetime.now(timezone.utc).isoformat(),
        source_manifest_sha256=source_id, archive=archive.name, archive_sha256=file_hash(archive),
        files_sha256=hashes, scope="workspace Cargo files, README and every file under crates",
        excludes=[".git", "target", "saves", ".claude-flow", "docs", "tools"],
        earlier_baseline_hashes_match=True,
        qualification="Earlier baseline did not hash all data assets; agreement of previously hashed inputs is not proof of historical identity for other files.")
    (report / "snapshot.json").write_text(json.dumps(metadata, indent=2))
    policy_path = ROOT / "examples/worldgame-ocean-oracle.json"
    policy = json.loads(policy_path.read_text())
    validate(policy, "ocean-oracle")
    results = []
    for number in range(1, 4):
        output = report / "run-20261029T013847905892Z" / str(number) / "stdout"
        results.append(dict(run=number, stdout_sha256=file_hash(output),
                            verification=check_ocean(output.read_text(), policy)))
    evidence = dict(kind="retrospective_output_contract_checks_not_independent_physics_validation",
        policy_sha256=file_hash(policy_path), comparator_sha256=file_hash(ROOT / "chilicrisp/oracles.py"),
        policy=policy, results=results)
    (report / "oracle-validation.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(dict(archive=str(archive), file_count=len(files),
                         source_id=source_id, graded_runs=len(results)), indent=2))


if __name__ == "__main__":
    main()

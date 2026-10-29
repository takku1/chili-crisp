"""Prepare a self-contained source/dependency kit, then build with an empty Cargo home."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
import uuid

ROOT = Path(__file__).resolve().parents[2]


def main():
    kit = ROOT / "artifacts/worldgame-portable"
    report = ROOT / "reports/worldgame"
    snapshot = json.loads((report / "snapshot.json").read_text())
    with zipfile.ZipFile(report / snapshot["archive"]) as archive:
        for name in archive.namelist():
            if not (kit / "source" / name).resolve().is_relative_to((kit / "source").resolve()):
                raise ValueError("invalid archive path")
        archive.extractall(kit / "source")
    for name in ("harness.rs", "rust-toolchain.toml"):
        destination = kit / ("src/main.rs" if name == "harness.rs" else name)
        shutil.copyfile(ROOT / "verification/worldgame" / name, destination)
    (kit / "Cargo.toml").write_text('[package]\nname="chili-field-driver"\nversion="0.1.0"\nedition="2024"\n[workspace]\nexclude=["source/crates/mote-core"]\n[dependencies]\nmote-core={path="source/crates/mote-core"}\n')
    shutil.copyfile(ROOT / "artifacts/field-driver-20261029T015152519351Z/Cargo.lock", kit / "Cargo.lock")
    command = ["cargo", "+1.98.0", "vendor", "--locked", "--offline", "--versioned-dirs", "vendor"]
    result = subprocess.run(command, cwd=kit, capture_output=True, text=True, timeout=120)
    (report / "vendor.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("dependency vendoring failed")
    (kit / ".cargo/config.toml").write_text('[source.crates-io]\nreplace-with="vendored-sources"\n[source.vendored-sources]\ndirectory="vendor"\n[net]\noffline=true\n')
    run_id = uuid.uuid4().hex
    cargo_home = ROOT / "artifacts" / ("portable-empty-cargo-home-" + run_id)
    cargo_home.mkdir(exist_ok=True)
    if any(cargo_home.iterdir()):
        raise RuntimeError("empty Cargo home required for independent build check")
    env = dict(os.environ, CARGO_HOME=str(cargo_home), CARGO_TARGET_DIR=str(ROOT / "artifacts" / ("portable-build-target-" + run_id)))
    build = ["cargo", "+1.98.0", "build", "--frozen", "--offline", "--release"]
    built = subprocess.run(build, cwd=kit, env=env, capture_output=True, text=True, timeout=120)
    (report / "portable-build.log").write_text(built.stdout + built.stderr)
    files = {file.relative_to(kit).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
             for file in sorted(kit.rglob("*")) if file.is_file()}
    archive_path = report / "worldgame-portable-kit.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as archive:
        for name in files:
            archive.write(kit / name, name)
    metadata = dict(source_id=snapshot["source_manifest_sha256"], rust_toolchain="1.98.0",
        vendor_command=command, vendor_exit_code=result.returncode, build_command=build,
        build_exit_code=built.returncode, cargo_home_initially_empty=True,
        cargo_target_separate=True, host="Windows; Linux runtime/toolchain not validated",
        archive=archive_path.name, archive_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        files_sha256=files)
    (report / "portable-kit.json").write_text(json.dumps(metadata, indent=2))
    print(json.dumps(dict(build_exit_code=built.returncode, files=len(files),
                         archive=str(archive_path), archive_bytes=archive_path.stat().st_size), indent=2))
    if built.returncode:
        raise RuntimeError("portable kit did not build from empty Cargo home")


if __name__ == "__main__":
    main()

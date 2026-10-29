"""Freeze an offline Rust/Cargo toolchain with a vendored, lockfile-pinned crate set."""
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess

RUST = Path("/usr/lib/rust-1.93")
# The only crates candidates may depend on. The owner vendors them once, with
# network access, before the toolchain root is frozen.
CRATES = {"itoa": "=1.0.15"}


def _load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vendor(lab, compiler):
    """Resolve the allowed crate set outside the sandbox; candidates get the frozen copy."""
    project = lab / "vendor-project"
    (project / "src").mkdir(parents=True)
    dependencies = "".join(f'{name} = "{version}"\n' for name, version in CRATES.items())
    (project / "Cargo.toml").write_text('[package]\nname = "vendor-set"\nversion = "0.0.0"\nedition = "2021"\n\n'
                                        "[dependencies]\n" + dependencies)
    (project / "src/main.rs").write_text("fn main() {}\n")
    subprocess.run(["cargo", "generate-lockfile"], cwd=project, check=True)
    subprocess.run(["cargo", "vendor", "--locked", "--versioned-dirs", str(compiler / "vendor")],
                   cwd=project, check=True, stdout=subprocess.DEVNULL)
    shutil.copy2(project / "Cargo.lock", lab / "vendor-Cargo.lock")


def prepare(lab, runtime):
    compiler, = _load("native-build").prepare(lab, runtime)

    def copy_file(original, destination=None):
        original = Path(original)
        target = compiler / str(destination or original).lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(original.resolve(), target)
        return original.resolve()

    shutil.copytree(RUST, compiler / RUST.relative_to("/"), symlinks=False)
    # rustc finds its sysroot from librustc_driver's directory, which ldd resolves under /usr/lib.
    (compiler / "usr/lib/rustlib").symlink_to(RUST.relative_to("/usr/lib") / "lib/rustlib")
    copy_file(shutil.which("gcc"), "/usr/bin/cc")
    gcc_dir = Path(subprocess.check_output(["gcc", "-print-file-name=libgcc.a"], text=True).strip()).parent
    if (gcc_dir / "libgcc_eh.a").exists():
        copy_file(gcc_dir / "libgcc_eh.a")
    for name in ("libm.so", "libm.so.6", "libmvec.so.1", "libpthread.a", "libdl.a", "librt.a", "libutil.a"):
        if (Path("/usr/lib/x86_64-linux-gnu") / name).exists():
            copy_file(Path("/usr/lib/x86_64-linux-gnu") / name)
    libraries = set()
    for executable in [RUST / "bin/rustc", RUST / "bin/cargo", *(RUST / "lib").glob("*.so")]:
        linked = subprocess.check_output(["ldd", str(executable)], text=True)
        libraries.update(re.findall(r"(/[^\s()]+)", linked))
    for library in libraries:
        copy_file(library)
    vendor(lab, compiler)
    (compiler / "fixtures/cargo-build.py").write_text('''import json, os, socket, subprocess, sys
from pathlib import Path
assert not Path("/home/chili-runner").exists()
mode = sys.argv[1] if len(sys.argv) > 1 else "compile"
env = {"PATH": "/usr/bin", "HOME": "/tmp", "CARGO_HOME": "/tmp/cargo-home", "CARGO_TARGET_DIR": "/tmp/target",
       "RUSTC": "/usr/lib/rust-1.93/bin/rustc", "CARGO_BUILD_JOBS": "1", "CARGO_INCREMENTAL": "0",
       "CARGO_TERM_COLOR": "never", "SOURCE_DATE_EPOCH": "0",
       "CARGO_PROFILE_RELEASE_STRIP": "symbols", "CARGO_PROFILE_RELEASE_CODEGEN_UNITS": "1"}
# cwd is /tmp, so a candidate .cargo/config.toml or rust-toolchain file is never read.
built = subprocess.run(["/usr/lib/rust-1.93/bin/cargo", "build", "--release", "--offline", "--locked",
    "--manifest-path", "/candidate/Cargo.toml", "--message-format=json-render-diagnostics",
    "--config", 'source.crates-io.replace-with="vendored"', "--config", 'source.vendored.directory="/vendor"'],
    cwd="/tmp", env=env, stdout=subprocess.PIPE, stderr=sys.stderr, check=True)
executables = [message["executable"] for message in map(json.loads, built.stdout.splitlines())
               if message.get("reason") == "compiler-artifact" and message.get("executable")]
if len(executables) != 1:
    raise SystemExit("Candidate must build exactly one binary target")
sys.stdout.buffer.write(Path(executables[0]).read_bytes())
''')
    # Rust std binaries link libgcc_s for unwinding; the program runtime needs it too.
    target = runtime / "usr/lib/x86_64-linux-gnu/libgcc_s.so.1"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(Path("/usr/lib/x86_64-linux-gnu/libgcc_s.so.1").resolve(), target)
    (lab / "toolchain-version.txt").write_text(subprocess.check_output([str(RUST / "bin/rustc"), "-vV"], text=True)
        + subprocess.check_output([str(RUST / "bin/cargo"), "-V"], text=True))
    return [compiler]


def main():
    return _load("native-fixtures").provision(worker_name="native-cargo-worker.py", prepare=prepare,
                                              extra_requirements=("cryptography>=46,<51",))


if __name__ == "__main__":
    raise SystemExit(main())

"""Freeze a minimal offline GCC C toolchain, then exercise isolated compilation."""
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess


def prepare(lab, runtime):
    (runtime / "candidate").mkdir()
    compiler = lab / "compiler-rootfs"
    shutil.copytree(runtime, compiler)
    compiler_bins = []

    def copy_file(original, destination=None):
        original = Path(original)
        target = compiler / str(destination or original).lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original.resolve(), target)
        return original.resolve()

    for executable in ("gcc", "as", "ld"):
        compiler_bins.append(copy_file(shutil.which(executable), "/usr/bin/" + executable))
    gcc_dir = Path(subprocess.check_output(["gcc", "-print-file-name=libgcc.a"], text=True).strip()).parent
    for name in ("cc1", "collect2"):
        original = Path(subprocess.check_output(["gcc", "-print-prog-name=" + name], text=True).strip())
        copy_file(original)
        compiler_bins.append(original)
    for name in ("liblto_plugin.so", "crtbegin.o", "crtend.o", "crtbeginS.o", "crtendS.o", "libgcc.a", "libgcc_s.so"):
        original = gcc_dir / name
        copy_file(original)
        if name == "liblto_plugin.so":
            compiler_bins.append(original)
    shutil.copytree(gcc_dir / "include", compiler / (gcc_dir / "include").relative_to("/"))
    for original in Path("/usr/include").glob("*.h"):
        copy_file(original)
    shutil.copytree("/usr/include/x86_64-linux-gnu", compiler / "usr/include/x86_64-linux-gnu", symlinks=False)
    for name in ("linux", "asm-generic"):
        shutil.copytree(Path("/usr/include") / name, compiler / "usr/include" / name, symlinks=False)
    for name in ("Scrt1.o", "crt1.o", "crti.o", "crtn.o", "libc.so", "libc_nonshared.a", "libgcc_s.so.1"):
        copy_file(Path("/usr/lib/x86_64-linux-gnu") / name)
    libraries = set()
    for executable in compiler_bins:
        linked = subprocess.check_output(["ldd", str(executable)], text=True)
        libraries.update(re.findall(r"(/[^\s()]+)", linked))
    for library in libraries:
        target = compiler / library.lstrip("/")
        if not target.exists():
            copy_file(library)
    (compiler / "fixtures/compile.py").write_text('''import ctypes, errno, os, socket, subprocess, sys, time
from pathlib import Path
assert "CHILI_BUILD_SECRET" not in os.environ
assert "CPATH" not in os.environ
assert not Path("/home/chili-runner").exists()
try:
    socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raise AssertionError("network socket permitted")
except PermissionError:
    pass
libc = ctypes.CDLL(None, use_errno=True)
assert libc.unshare(0x10000000) == -1 and ctypes.get_errno() == errno.EPERM
assert libc.syscall(56, 0x10000000 | 17, 0, 0, 0, 0) == -1 and ctypes.get_errno() == errno.EPERM
assert libc.syscall(435, 0, 0) == -1 and ctypes.get_errno() == errno.ENOSYS
mode = sys.argv[1] if len(sys.argv) > 1 else "compile"
if mode == "timeout":
    time.sleep(30)
if mode == "oom":
    payload = bytearray(768 * 1024 * 1024)
if mode == "flood":
    sys.stdout.buffer.write(b"x" * 2097152)
    sys.stdout.buffer.flush()
    time.sleep(2)
    raise SystemExit()
os.environ["SOURCE_DATE_EPOCH"] = "0"
subprocess.run(["/usr/bin/gcc", "-O2", "-fno-ident", "-frandom-seed=chili-build", "-Wl,--build-id=none",
                "/candidate/program.c", "-o", "/tmp/program"], stdout=sys.stderr, stderr=sys.stderr, check=True)
if mode == "background":
    subprocess.Popen(["/usr/bin/python3", "-c", "import time; time.sleep(300)"])
payload = Path("/tmp/program").read_bytes()
if mode == "nondeterministic":
    payload += os.urandom(16)
sys.stdout.buffer.write(payload)
''')
    (runtime / "fixtures/run-compiled.py").write_text('''import os
os.execv("/candidate/program", ["/candidate/program"])
''')
    (lab / "toolchain-version.txt").write_text(subprocess.check_output(["gcc", "--version"], text=True))
    return [compiler]


def main():
    spec = importlib.util.spec_from_file_location("fixtures", Path(__file__).with_name("native-fixtures.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.provision(worker_name="native-build-worker.py", prepare=prepare, extra_requirements=("cryptography>=46,<51",))


if __name__ == "__main__":
    raise SystemExit(main())

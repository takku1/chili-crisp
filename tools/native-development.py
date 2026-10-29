"""Owner-provisioned two-generation native controller fixture (no model calls)."""
import importlib.util
from pathlib import Path


def prepare(lab, rootfs):
    (rootfs / "candidate").mkdir()
    (rootfs / "fixtures/development.py").write_text('''import os, runpy
assert "CHILI_CONTROLLER_SECRET" not in os.environ
assert not os.path.exists("/sys/fs/cgroup")
assert not os.path.exists("/home/chili-runner")
try:
    open("/fixtures/tamper", "w").close()
    raise AssertionError("runtime writable")
except OSError:
    pass
try:
    open("/candidate/tamper", "w").close()
    raise AssertionError("source writable")
except OSError:
    pass
program = runpy.run_path("/candidate/program.py")
print(program["compute"]())
''')
    return []


def main():
    path = Path(__file__).with_name("native-fixtures.py")
    spec = importlib.util.spec_from_file_location("native_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.provision(worker_name="native-development-worker.py", prepare=prepare)


if __name__ == "__main__":
    raise SystemExit(main())

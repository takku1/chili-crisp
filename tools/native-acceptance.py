"""Provision source-only native sealed-acceptance positive/negative controls."""
import importlib.util
from pathlib import Path


def prepare(lab, rootfs):
    (rootfs / "candidate").mkdir()
    (rootfs / "fixtures/acceptance.py").write_text('''import runpy, sys
program = runpy.run_path("/candidate/program.py")
print(program["compute"](int(sys.stdin.buffer.read())))
''')
    return []


def main():
    spec = importlib.util.spec_from_file_location("fixtures", Path(__file__).with_name("native-fixtures.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.provision(worker_name="native-acceptance-worker.py", prepare=prepare,
                            extra_requirements=("cryptography>=46,<51",))


if __name__ == "__main__":
    raise SystemExit(main())

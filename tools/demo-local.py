"""Run the trusted bundled source-changing example without modifying its inputs."""
import json
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chilicrisp.project import compare, initialize  # noqa: E402 -- use this checkout


def main():
    work = ROOT / "artifacts" / ("local-demo-" + uuid.uuid4().hex)
    work.mkdir(parents=True)
    for name in ("baseline", "candidate"):
        shutil.copytree(ROOT / "examples/local-project" / name, work / name)
    config = initialize(work / "baseline", [sys.executable, "check.py"],
                        [sys.executable, "-m", "py_compile", "solver.py"])
    record, result = compare(config, work / "candidate", work / "runs", trusted_local=True)
    print(json.dumps({"record": str(record), "decision": result["decision"]}, indent=2))
    return 0 if result["decision"] == "public_tests_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

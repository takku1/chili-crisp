"""Exercise the VM-free loop with two declared lossless-storage candidates.

The scripted proposer is a deterministic integration fixture, not an AI model
or an implementation of literature research. Real agents use the same protocol.
"""
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chilicrisp import development as dev  # noqa: E402
from chilicrisp.project import initialize  # noqa: E402


def agent(request_file, response_file, workspace):
    request = json.loads(Path(request_file).read_text())
    target = Path(workspace) / "codec.py"
    text = target.read_text()
    if request["generation"] == 1:
        text = text.replace("LEVEL = -1", "LEVEL = 1")
    else:
        text = text.replace("LEVEL = 1", "LEVEL = 9")
    target.write_text(text)
    Path(response_file).write_text(json.dumps({
        "hypothesis": "Lossless compression reduces stored bytes while preserving readback",
        "mechanism": "Use zlib compression, then increase its compression level",
        "falsification": "Readback changes, stored size misses the target, or measured guards fail",
        "sources": [{"reference": "https://docs.python.org/3/library/zlib.html",
                     "supports": "Lossless compression with selectable compression levels"}]}))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "agent":
        agent(*sys.argv[2:])
        return
    work = ROOT / "artifacts" / ("development-demo-" + uuid.uuid4().hex)
    baseline = work / "baseline"
    baseline.mkdir(parents=True)
    (baseline / "codec.py").write_text('''from pathlib import Path
import zlib
LEVEL = -1
DATA = b'chili-crisp-content-' * 8192
def build():
    Path('build').mkdir(exist_ok=True)
    Path('build/payload.bin').write_bytes(DATA if LEVEL == -1 else zlib.compress(DATA, LEVEL))
def readback():
    data = Path('build/payload.bin').read_bytes()
    return data if LEVEL == -1 else zlib.decompress(data)
''')
    (baseline / "check.py").write_text("from codec import readback\nassert readback() == b'chili-crisp-content-' * 8192\n")
    (baseline / "bench.py").write_text("from codec import readback\nimport hashlib\nprint(hashlib.sha256(readback()).hexdigest())\n")
    project = initialize(baseline, [sys.executable, "check.py"],
        [sys.executable, "-c", "from codec import build; build()"],
        protected_paths=["check.py", "bench.py"])
    policy = {"schema_version": "0.1", "concept": "Store an identical payload in a progressively smaller artifact",
        "project_config": str(project), "benchmark_command": [sys.executable, "bench.py"],
        "objective": "artifact_bytes", "artifact_paths": ["build/payload.bin"],
        "regression_limits": {"wall_seconds": 5}, "repetitions": 2,
        "confirmation_repetitions": 2, "max_generations": 2, "seed": 31}
    plan = work / "plan.json"
    plan.write_text(json.dumps(policy, indent=2))
    session = work / "session"
    initial = dev.create(plan, session, trusted_local=True)
    result = dev.run(session, [sys.executable, str(Path(__file__).resolve()), "agent",
                              "{request}", "{response}", "{workspace}"], trusted_local=True)
    print(json.dumps({"session": str(session), "state": result["state"],
        "stop_reason": result["stop_reason"], "initial_target": initial["target"],
        "retained_artifact_bytes": [champion["metrics"]["artifact_bytes"] for champion in result["champions"]],
        "decisions": [generation["decision"] for generation in result["generations"]],
        "enforcement": "none; measured local targets", "agent": "deterministic fixture"}, indent=2))
    if len(result["champions"]) != 3:
        raise SystemExit("Both fixture candidates must pass the configured gates")


if __name__ == "__main__":
    main()

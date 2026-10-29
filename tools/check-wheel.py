"""Validate the built wheel's schemas outside the source tree, without installing it."""
import argparse
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--dist", type=Path, default=root / "dist")
args = parser.parse_args()
wheels = list(args.dist.glob("chilicrisp-*.whl"))
if len(wheels) != 1:
    raise SystemExit(f"Expected exactly one Chili Crisp wheel in {args.dist}")
sdists = list(args.dist.glob("chilicrisp-*.tar.gz"))
if len(sdists) != 1:
    raise SystemExit(f"Expected exactly one Chili Crisp source distribution in {args.dist}")
with tarfile.open(sdists[0]) as archive:
    source_names = {name.split('/', 1)[1] for name in archive.getnames() if '/' in name}
    required = {"pyproject.toml", "requirements.txt", "verification/worldgame/check.py",
                "tools/native-fixtures.py", "tests/test_evidence.py",
                "chilicrisp/skills/chili-dev/SKILL.md", "chilicrisp/schemas/project.schema.json"}
    if not required.issubset(source_names):
        raise SystemExit(f"Source distribution is missing: {sorted(required - source_names)}")
    if any(name.startswith(('artifacts/', '.git/')) for name in source_names):
        raise SystemExit("Source distribution contains workspace artifacts")
with zipfile.ZipFile(wheels[0]) as archive:
    schemas = [name for name in archive.namelist() if name.startswith("chilicrisp/schemas/")]
    expected = {"chilicrisp/schemas/" + path.name for path in (root / "chilicrisp/schemas").glob("*.schema.json")}
    if set(schemas) != expected:
        raise SystemExit(f"Wheel schema set differs from source: {schemas}")
    if "chilicrisp/skills/chili-dev/SKILL.md" not in archive.namelist():
        raise SystemExit("Wheel is missing the coding-agent skill")
    if any(name.startswith(('tests/', 'tools/', 'reports/', 'artifacts/')) for name in archive.namelist()):
        raise SystemExit("Wheel unexpectedly includes workspace/development artifacts")
# zipimport loads code from the wheel; JSON schemas need extraction because the
# runner's contract also hashes real comparator files on disk.
import shutil
import uuid
directory = root / ("test-artifacts-" + uuid.uuid4().hex)
directory.mkdir()
try:
    with zipfile.ZipFile(wheels[0]) as archive:
        archive.extractall(directory)
    script = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chilicrisp.runner import validate
import chilicrisp.runner as runner
assert Path(runner.__file__).is_relative_to(Path(sys.argv[1]))
validate(json.loads(Path(sys.argv[2]).read_text()), 'experiment')
cpu_manifest = json.loads(Path(sys.argv[2]).read_text())
cpu_manifest['isolation']['cpu'] = {'quota_usec': 20000, 'period_usec': 100000}
validate(cpu_manifest, 'experiment')
from chilicrisp.cpu import metrics, sweep
assert metrics({'cpu.stat': 'usage_usec 100000\\n'})['cpu_usage']['value'] == .1
try:
    sweep(cpu_manifest, [100000, 50000], memory_budget=67108864, repetitions=1000)
except ValueError:
    pass
else:
    raise AssertionError('Oversized CPU sweep must fail before any workload executes')
from chilicrisp.project import initialize, load_project, compare
from chilicrisp.evidence import verify
from chilicrisp.skill import export
project = Path(sys.argv[1]) / 'wheel-project'
project.mkdir()
config = initialize(project, [sys.executable, '-c', 'print("wheel test")'])
assert load_project(config)[1] == project.resolve()
record, result = compare(config, project, Path(sys.argv[1]) / 'wheel-runs', trusted_local=True)
assert result['decision'] == 'public_tests_passed', result
assert verify(record)['valid']
export(Path(sys.argv[1]) / 'exported-skill')
assert (Path(sys.argv[1]) / 'exported-skill/SKILL.md').is_file()
from chilicrisp.development import create, request
(project / 'check.py').write_text('print("wheel test")\\n')
owner = json.loads(config.read_text())
owner.update(test=[sys.executable, 'check.py'], protected_paths=['check.py'])
config.write_text(json.dumps(owner))
plan = Path(sys.argv[1]) / 'development-policy.json'
plan.write_text(json.dumps({'schema_version': '0.1', 'concept': 'Exercise packaged local development',
    'project_config': str(config), 'benchmark_command': [sys.executable, 'check.py'],
    'objective': 'artifact_bytes', 'artifact_paths': ['check.py'],
    'repetitions': 2, 'confirmation_repetitions': 2}))
session = Path(sys.argv[1]) / 'development-session'
state = create(plan, session, trusted_local=True)
assert state['state'] == 'AWAITING_CANDIDATE', state
assert request(session)['target_basis'].startswith('median local measurements')
print('Wheel schemas, comparison, evidence verification and skill export passed')
"""
    subprocess.run([sys.executable, "-P", "-c", script, str(directory),
                    str(root / "examples/experiment.json")], cwd=directory, check=True)
finally:
    shutil.rmtree(directory)

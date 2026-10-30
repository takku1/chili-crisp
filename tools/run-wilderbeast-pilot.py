"""One owner-reviewed real-repository optimization; sampled local evidence only."""
import argparse
import difflib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chilicrisp import development as dev  # noqa: E402
from chilicrisp.project import EXCLUDED, initialize  # noqa: E402
from verification.wilderbeast.streaming import rewrite  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cohort', type=Path)
    parser.add_argument('--name', default='local-pilot')
    args = parser.parse_args()
    cohort = args.cohort.resolve()
    pilot = cohort / 'wilderbeast' / args.name
    baseline, candidate = pilot / 'baseline', pilot / 'candidate'
    shutil.copytree(cohort / 'wilderbeast/baseline', baseline)
    shutil.copy2(ROOT / 'verification/wilderbeast/archive_workload.py', baseline / 'tests/chili_archive_workload.py')
    (baseline / 'tests/chili_check.py').write_text('''import pathlib, subprocess, sys
sys.path.insert(0, 'src')
import pytest
pathlib.Path('.chilicrisp').mkdir(exist_ok=True)
result = pytest.main(['tests', '-q', '-p', 'no:cacheprovider', '--basetemp', '.chilicrisp/pytest'])
if result:
    raise SystemExit(result)
subprocess.run([sys.executable, '-B', 'tests/chili_archive_workload.py', '--source', '.',
                '--scratch', '.chilicrisp/scratch', '--records', '8000'], check=True)
''', encoding='utf-8')
    editable = 'src/wilderbeast/evidence/archive.py'
    protected = [p.relative_to(baseline).as_posix() for p in baseline.rglob('*')
                 if p.is_file() and p.relative_to(baseline).as_posix() != editable
                 and not any(part in EXCLUDED or part.endswith('.egg-info') for part in p.relative_to(baseline).parts)]
    config = initialize(baseline, [str(Path('Z:/Wilderbeast/.venv/Scripts/python.exe')),
                                  '-B', 'tests/chili_check.py'], protected_paths=protected)
    plan = {'schema_version': '0.1', 'concept': 'Persist discovery receipts with less transient serialization memory',
            'project_config': str(config), 'benchmark_command': [sys.executable, '-B',
                'tests/chili_archive_workload.py', '--source', '.', '--scratch', '.chilicrisp/scratch',
                '--records', '8000', '--mode', 'measure'],
            'objective': 'sampled_peak_rss_bytes', 'regression_limits': {'wall_seconds': .25},
            'reductions': [.1], 'repetitions': 3, 'confirmation_repetitions': 3,
            'max_generations': 1, 'max_stagnation': 1, 'max_commands': 50,
            'wall_seconds': 1800, 'seed': 301026}
    (pilot / 'plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    shutil.copytree(baseline, candidate, ignore=shutil.ignore_patterns('.chilicrisp'))
    archive = candidate / editable
    text = archive.read_text(encoding='utf-8')
    archive.write_text(rewrite(text), encoding='utf-8')
    research = {'hypothesis': 'Streaming record dictionaries lowers median sampled process peak RSS by at least 10%.',
        'mechanism': 'The allocation probe observes all serialized receipt and wrapper dictionaries live at encoder entry; yield one at a time.',
        'falsification': 'Existing tests or independent roundtrip fail, memory target is missed, or median wall time regresses by more than 25%.',
        'sources': [{'reference': str(cohort / 'wilderbeast/allocation-probe/profile.json'),
                     'supports': 'Observed live allocations at JSON encoder entry; instrumented diagnostic only.'},
                    {'reference': 'Python standard library json.encoder._make_iterencode / _iterencode_list',
                     'supports': 'List subclass truth testing and iteration permit incremental dictionary materialization.'}]}
    (pilot / 'research.json').write_text(json.dumps(research, indent=2), encoding='utf-8')
    state = dev.create(pilot / 'plan.json', pilot / 'session', trusted_local=True)
    print(json.dumps({'phase': 'baseline', 'metrics': state['champions'][0]['metrics'], 'target': state['target']}), flush=True)
    state = dev.submit(pilot / 'session', candidate, pilot / 'research.json', trusted_local=True)
    decision = state['generations'][-1]
    print(json.dumps({'phase': 'candidate', 'decision': decision['decision'],
                      'reason': decision.get('reason'), 'state': state['state']}), flush=True)
    checks = []
    for count in (0, 1, 257, 20000):
        outputs = []
        for source in (baseline, candidate):
            checked = subprocess.run([sys.executable, '-B', str(ROOT / 'verification/wilderbeast/archive_workload.py'),
                '--source', str(source), '--scratch', str(pilot / 'size-check-scratch'), '--records', str(count)],
                capture_output=True, text=True, check=True, timeout=120)
            outputs.append(json.loads(checked.stdout))
        if outputs[0] != outputs[1]:
            raise ValueError('Additional size check failed at ' + str(count))
        checks.append({'records': count, 'baseline': outputs[0], 'candidate': outputs[1], 'matched': True})
    (pilot / 'size-checks.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    patch = ''.join(difflib.unified_diff((baseline / editable).read_text(encoding='utf-8').splitlines(True),
        archive.read_text(encoding='utf-8').splitlines(True), fromfile='a/' + editable, tofile='b/' + editable))
    (pilot / 'candidate.patch').write_text(patch, encoding='utf-8')


if __name__ == '__main__':
    main()

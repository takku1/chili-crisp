"""Run frozen real-component tests and sampled baselines; no model proposals."""
import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chilicrisp.measure import environment, measure  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cohort', type=Path)
    parser.add_argument('--label', default='qualification')
    args = parser.parse_args()
    cohort = args.cohort.resolve()
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    report = {'stage': 'trusted local baseline qualification', 'enforcement': 'none',
              'environment': environment(), 'projects': {}}

    def command(argv, cwd, directory, seconds=600):
        directory.mkdir(parents=True)
        started = time.monotonic()
        try:
            result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                    encoding='utf-8', errors='replace', timeout=seconds)
            record = {'command': argv, 'returncode': result.returncode,
                      'wall_seconds': time.monotonic() - started}
            (directory / 'stdout.txt').write_text(result.stdout, encoding='utf-8')
            (directory / 'stderr.txt').write_text(result.stderr, encoding='utf-8')
        except subprocess.TimeoutExpired as error:
            record = {'command': argv, 'returncode': None, 'error': str(error),
                      'wall_seconds': time.monotonic() - started}
        (directory / 'command.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        return record

    benchmarks = {}
    for name in ('wilderbeast', 'mochios', 'worldgame'):
        base = cohort / name / 'baseline'
        out = cohort / name / args.label
        result = report['projects'][name] = {}
        if name == 'wilderbeast':
            python = str(Path('Z:/Wilderbeast/.venv/Scripts/python.exe'))
            code = ("import sys; sys.path.insert(0, " + repr(str(base / 'src')) + "); "
                    "import pytest; raise SystemExit(pytest.main(sys.argv[1:]))")
            result['tests'] = command([python, '-B', '-c', code, 'tests', '-q', '-p', 'no:cacheprovider',
                '--basetemp', str(out / 'pytest-tmp')], base, out / 'tests')
            driver = [sys.executable, '-B', str(ROOT / 'verification/wilderbeast/archive_workload.py'),
                      '--source', str(base), '--scratch', str(out / 'scratch'), '--records', '8000']
            result['workload_check'] = command(driver, base, out / 'workload-check')
            benchmarks[name] = driver + ['--mode', 'measure']
        else:
            package, example = ('mochios-component-model', 'resolve_bench') if name == 'mochios' else ('mote-core', 'oceanbench')
            target = out / 'target'
            common = ['cargo', '+1.98.0', '--offline']
            result['lockfile'] = command(common[:2] + ['generate-lockfile', '--offline'], base, out / 'lockfile')
            if result['lockfile']['returncode'] == 0:
                result['tests'] = command(['cargo', '+1.98.0', 'test', '--frozen', '--release', '-p', package,
                    '--target-dir', str(target)], base, out / 'tests')
                result['build'] = command(['cargo', '+1.98.0', 'build', '--frozen', '--release', '-p', package,
                    '--example', example, '--target-dir', str(target)], base, out / 'build')
                benchmarks[name] = [str(target / 'release/examples' / (example + '.exe'))]
        result['ready'] = bool(result.get('tests', {}).get('returncode') == 0
                               and all(v.get('returncode') == 0 for v in result.values() if isinstance(v, dict)))
        (cohort / 'qualification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(name, 'ready' if result['ready'] else 'failed', flush=True)

    order = [name for name in benchmarks if report['projects'][name]['ready'] for _ in range(3)]
    random.Random(301026).shuffle(order)
    report['measurement_order'] = order
    config = {'command_seconds': 300, 'output_bytes_per_stream': 1048576}
    for index, name in enumerate(order):
        observed = measure(benchmarks[name], cohort / name / 'baseline',
                           cohort / name / args.label / f'measurement-{index}', config, time.monotonic() + 330)
        report['projects'][name].setdefault('measurements', []).append(observed)
        print(name, observed['outcome'], observed['metrics'], flush=True)
        (cohort / 'qualification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(str(cohort), flush=True)
    (cohort / (args.label + '.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
    return int(any(not project['ready'] or any(m['outcome'] != 'pass' for m in project.get('measurements', []))
                   for project in report['projects'].values()))


if __name__ == '__main__':
    raise SystemExit(main())

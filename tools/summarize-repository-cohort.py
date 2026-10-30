"""Summarize frozen-component qualification evidence without executing projects."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cohort', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--label', default='qualification-owner')
    parser.add_argument('--pilot', default='local-pilot-2')
    args = parser.parse_args()
    manifest = json.loads((args.cohort / 'cohort.json').read_text())
    qualification = json.loads((args.cohort / 'qualification.json').read_text())
    result = {'stage': 'baseline qualification only; no model proposals or optimization acceptance',
              'cohort': str(args.cohort), 'environment': qualification['environment'],
              'enforcement': 'none', 'measurement_order': qualification['measurement_order'], 'projects': {}}
    for name, project in qualification['projects'].items():
        provenance = manifest['projects'][name]
        base = args.cohort / name / 'baseline'
        qualification_dir = args.cohort / name / args.label
        tests = (qualification_dir / 'tests/stdout.txt').read_text(encoding='utf-8')
        if name == 'wilderbeast':
            counts = {'passed': int(re.search(r'(\d+) passed', tests)[1]), 'ignored': 0}
        else:
            groups = re.findall(r'test result: ok\. (\d+) passed; \d+ failed; (\d+) ignored;', tests)
            counts = {'passed': sum(int(g[0]) for g in groups), 'ignored': sum(int(g[1]) for g in groups)}
        measurements = project.get('measurements', [])
        medians = {metric: statistics.median(m['metrics'][metric] for m in measurements)
                   for metric in ('wall_seconds', 'sampled_peak_rss_bytes', 'sampled_cpu_seconds')}
        after = {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in base.rglob('*') if p.is_file()
                 and not any(part in {'__pycache__', '.pytest_cache'} for part in p.parts)}
        changes = {path for path in set(after) | set(provenance['snapshot_files_sha256'])
                   if after.get(path) != provenance['snapshot_files_sha256'].get(path)}
        if changes - {'Cargo.lock'}:
            raise ValueError('Frozen baseline changed unexpectedly: ' + repr(changes))
        result['projects'][name] = {
            'source': provenance['source'], 'parent_commit': provenance['parent_commit'],
            'includes_uncommitted_files': bool(provenance['dirty_status']),
            'source_manifest_sha256': provenance['source_manifest_sha256'],
            'file_count': len(provenance['upstream_files_sha256']),
            'build_adapter_changes': provenance['build_adapter_changes'],
            'post_resolution_lockfile_sha256': after.get('Cargo.lock'),
            'tests': counts, 'ready': project['ready'], 'repetitions': len(measurements),
            'all_measurements_passed': all(m['outcome'] == 'pass' for m in measurements),
            'sample_counts': [m['samples'] for m in measurements], 'medians': medians,
            'limitations': measurements[0]['limitations'] if measurements else [],
            'evidence': str(qualification_dir)}
    pilot = args.cohort / 'wilderbeast' / args.pilot
    if (pilot / 'session/state.json').exists():
        state = json.loads((pilot / 'session/state.json').read_text(encoding='utf-8'))
        generation = state['generations'][-1]
        confirmation = generation['phases']['confirmation']['medians']
        result['wilderbeast_pilot'] = {'kind': 'one owner-reviewed candidate; not a model-arm comparison',
            'session': str(pilot / 'session'), 'decision': generation['decision'],
            'baseline_source_hash': state['champions'][0]['source_hash'],
            'candidate_source_hash': generation['source_hash'],
            'confirmation_medians': confirmation,
            'sampled_rss_reduction_fraction': 1 - confirmation['candidate']['sampled_peak_rss_bytes'] / confirmation['baseline']['sampled_peak_rss_bytes'],
            'verification': generation['verification'],
            'size_checks': json.loads((pilot / 'size-checks.json').read_text(encoding='utf-8'))}
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({name: {'tests': p['tests'], 'medians': p['medians']}
                      for name, p in result['projects'].items()}, indent=2))


if __name__ == '__main__':
    main()

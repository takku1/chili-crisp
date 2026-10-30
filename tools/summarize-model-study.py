"""Summarize audited study artifacts without running any candidate or model."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(study):
    records = json.loads((study / 'audited-summary.json').read_text())
    protocol = json.loads((study / 'protocol.json').read_text())
    calls = []
    for path in sorted(study.glob('*/proposal-*/usage.json')):
        directory = path.parent
        calls.append({'run': directory.parent.name, 'generation': int(directory.name.split('-')[-1]),
            'usage': json.loads(path.read_text()), 'prompt_sha256': digest(directory / 'prompt.txt'),
            'program_sha256': digest(directory / 'candidate/program.c'),
            'events_sha256': digest(directory / 'provider-stdout.txt')})
    for record in records:
        state_path = study / Path(record['lab']).name / 'accepted-session/state.json'
        state = json.loads(state_path.read_text())
        record['stop_reason'] = state['stop_reason']
        record['development_stop_reason'] = json.loads((state_path.parent.parent / 'final/state.json').read_text())['stop_reason']
        record['source_hashes'] = [g['source_hash'] for g in state['generations']]
        record['repeat_of'] = [g.get('repeat_of') for g in state['generations']]
        record['production'] = state['champions'][state['champion']]['verification']['production']
        record['receipt_sha256'] = digest(state_path.parent.parent / 'receipt.json')
        medians = record['audit'][0]['medians']
        record['memory_reduction_fraction'] = 1 - medians['candidate']['memory_peak'] / medians['baseline']['memory_peak']
    return {'study': str(study), 'protocol': protocol, 'protocol_sha256': digest(study / 'protocol.json'),
        'records': records, 'calls': calls, 'totals': {
            'calls': len(calls), 'distinct_programs': len({c['program_sha256'] for c in calls}),
            'input_tokens': sum(c['usage']['input_tokens'] or 0 for c in calls),
            'cache_read_tokens': sum(c['usage']['cache_read_tokens'] or 0 for c in calls),
            'output_tokens': sum(c['usage']['output_tokens'] or 0 for c in calls),
            'model_wall_seconds': sum(c['usage']['wall_seconds'] for c in calls),
            'cost_usd': None, 'observed_tool_events': sum(c['usage']['tool_events'] for c in calls)},
        'model_identity_basis': 'gpt-6.1-sol was explicitly configured; CLI events do not report resolved model',
        'limitations': ['One synthetic task; descriptive pilot only.',
            'Same per-run caps, unequal consumed effort due to the controller minimum target.',
            'Both arms use the same controller and public history; no ordinary-profiler baseline.',
            'Two runs per arm, randomized run order, same host and frozen compiler/runtime.',
            'Separate Unix accounts share a kernel; owner exports public prompts to a tool-disabled CLI on Windows.',
            'No automatic production promotion.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = summarize(args.study)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result['totals'], indent=2))


if __name__ == '__main__':
    main()

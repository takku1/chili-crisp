"""Export public native archive results without reading grader keys or inputs."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    records = json.loads((args.run / 'summary.json').read_text())
    for record in records:
        public = args.run / Path(record['lab']).name
        receipt = public / 'receipt.json'
        state = json.loads((public / 'session/state.json').read_text())
        record['receipt_sha256'] = hashlib.sha256(receipt.read_bytes()).hexdigest()
        record['baseline_source_hash'] = state['champions'][0]['source_hash']
        record['candidate_source_hash'] = state['champions'][state['champion']]['source_hash']
        record['production'] = state['champions'][state['champion']]['verification']['production']
        medians = record['audit'][0]['medians']
        if medians:
            record['memory_reduction_fraction'] = 1 - medians['candidate']['memory_peak'] / medians['baseline']['memory_peak']
    result = {'kind': 'native transfer of owner-reviewed archive candidate; no model comparison',
              'run_directory': str(args.run), 'records': records,
              'limitations': ['Unix accounts share a kernel; root owner remains trusted.',
                  'tmpfs output pages and runtime overhead are part of charged memory.peak.',
                  'In-process Python correctness drivers are not an adversarial oracle boundary.',
                  'The prior patch was known; this is transfer validation, not a discovery experiment.']}
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({r['control']: r['grade']['verdict'] for r in records}))


if __name__ == '__main__':
    main()

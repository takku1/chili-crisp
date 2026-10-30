"""Owner diagnostic probe; tracemalloc figures are not ordinary baseline metrics."""
import argparse
import json
from pathlib import Path
import runpy
import sys
import tracemalloc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    args.output.mkdir(parents=True)
    original = json.dump
    probes = []

    def observed_dump(value, stream, **kwargs):
        current, peak = tracemalloc.get_traced_memory()
        probes.append({'phase': 'archive JSON encoder entry', 'current_traced_bytes': current,
                       'peak_traced_bytes': peak,
                       'top_live_allocations': [str(item) for item in tracemalloc.take_snapshot().statistics('lineno')[:12]]})
        return original(value, stream, **kwargs)

    json.dump = observed_dump
    driver = Path(__file__).resolve().parents[1] / 'verification/wilderbeast/archive_workload.py'
    sys.argv = [str(driver), '--source', str(args.source), '--scratch', str(args.output / 'scratch'),
                '--records', '8000', '--mode', 'measure']
    tracemalloc.start()
    try:
        runpy.run_path(str(driver), run_name='__main__')
        current, peak = tracemalloc.get_traced_memory()
    finally:
        json.dump = original
        tracemalloc.stop()
    result = {'kind': 'instrumented allocation diagnostic; not baseline performance evidence',
              'source': str(args.source), 'probes': probes, 'final_current_traced_bytes': current,
              'peak_traced_bytes': peak, 'limitations': ['tracemalloc observes Python allocations, not total process RSS.',
                  'Taking a snapshot perturbs memory and time; compare ordinary uninstrumented controls separately.']}
    (args.output / 'profile.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

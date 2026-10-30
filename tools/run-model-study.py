"""Bounded Windows/WSL real-model pilot: 2 repetitions x 2 arms x 2 generations.

Requires the owner-provisioned native-trust fixture. Models receive exported
public text only; no candidate is built or executed on the Windows host.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def linux_path(path):
    path = Path(path).resolve()
    return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', default='/srv/chili-trust/lab-4mve2gif')
    parser.add_argument('--distro', default='Ubuntu-26.04')
    parser.add_argument('--model', default='sonnet')
    parser.add_argument('--provider', choices=('claude', 'codex'), default='claude')
    parser.add_argument('--executable', default=str(Path.home() / '.local/bin/claude.exe'))
    args = parser.parse_args()
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    output = ROOT / 'artifacts' / ('model-study-' + stamp)
    output.mkdir()
    order = [(repeat, arm) for repeat in range(2) for arm in ('scarcity', 'conventional')]
    random.Random(29026).shuffle(order)
    protocol = {'kind': 'bounded_comparison_pilot', 'seed': 29026, 'order': order,
                'generations_per_run': 2, 'maximum_model_calls': 8,
                'maximum_usd_per_call': 1 if args.provider == 'claude' else None, 'maximum_seconds_per_call': 600,
                'provider': args.provider,
                'model_alias': args.model, 'primary_outcome': 'signed sealed verdict and matched-transfer memory',
                'limits': 'One trivial synthetic task; two repetitions per arm; descriptive evidence only.',
                'source_hashes': {name: hashlib.sha256((ROOT / 'tools' / name).read_bytes()).hexdigest()
                                  for name in ('propose-model.py', 'model-study-linux.py', 'run-model-study.py')}}
    (output / 'protocol.json').write_text(json.dumps(protocol, indent=2))

    def phase(action, lab, *extra):
        command = ['wsl.exe', '-d', args.distro, '-u', 'root', '--',
                   args.template + '/venv/bin/python', linux_path(ROOT / 'tools/model-study-linux.py'),
                   action, lab, *extra]
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
        with (output / 'phases.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'action': action, 'lab': lab, 'returncode': result.returncode,
                                     'stdout': result.stdout, 'stderr': result.stderr}) + '\n')
        if result.returncode:
            raise RuntimeError(result.stdout[-2000:] + result.stderr[-3000:])
        return result.stdout

    summary = []
    for repeat, arm in order:
        name = f'model-{stamp.lower()}-{repeat}-{arm}'
        lab = '/srv/chili-trust/' + name
        run = output / name
        run.mkdir()
        started = time.monotonic()
        record = {'repeat': repeat, 'arm': arm, 'lab': lab}
        summary.append(record)
        try:
            phase('setup', lab, args.template, arm)
            print(name, phase('unit', lab, 'init'), flush=True)
            for generation in range(1, 3):
                public = run / f'public-{generation}'
                phase('export-public', lab, linux_path(public))
                state = json.loads((public / 'state.json').read_text())
                if state['state'] != 'AWAITING_CANDIDATE':
                    break
                proposal = run / f'proposal-{generation}'
                command = [sys.executable, str(ROOT / 'tools/propose-model.py'),
                           str(public / 'request.json'), str(public / 'incumbent'), str(proposal),
                           '--edit', 'program.c', '--executable', args.executable,
                           '--provider', args.provider,
                           '--model', args.model, '--seconds', '600', '--max-usd', '1']
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=660)
                (run / f'transport-{generation}.json').write_text(json.dumps({
                    'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}, indent=2))
                if result.returncode:
                    raise RuntimeError('Model transport failed: ' + result.stderr[-2000:])
                phase('import-proposal', lab, linux_path(proposal))
                print(name, generation, phase('unit', lab, 'submit',
                      lab + '/agent/' + proposal.name, lab + '/agent/' + proposal.name + '-research.json'), flush=True)
            final = run / 'final'
            phase('export-public', lab, linux_path(final))
            state = json.loads((final / 'state.json').read_text())
            record.update(decisions=[g['decision'] for g in state['generations']], champion=state['champion'])
            if state['champion']:
                record['grade'] = json.loads(phase('unit', lab, 'grade'))
                record['accept'] = json.loads(phase('unit', lab, 'accept'))
            record['status'] = 'completed'
        except Exception as error:
            record.update(status='failed', error=str(error))
            print(name, str(error), flush=True)
        record['wall_seconds'] = round(time.monotonic() - started, 3)
        (output / 'summary.json').write_text(json.dumps(summary, indent=2))
        if record['status'] == 'failed':
            break  # Diagnose infrastructure/provider errors before consuming more calls.
    print(str(output), flush=True)
    return int(any(record['status'] == 'failed' for record in summary))


if __name__ == '__main__':
    raise SystemExit(main())

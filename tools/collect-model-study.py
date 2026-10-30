"""Audit a completed model study as the grader and export public final evidence."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', type=Path)
    parser.add_argument('--python', required=True)
    args = parser.parse_args()
    records = json.loads((args.study / 'summary.json').read_text())
    for record in records:
        if record['status'] != 'completed' or not record.get('accept'):
            continue
        lab = Path(record['lab'])
        destination = args.study / lab.name
        audit = subprocess.run(['runuser', '-u', 'chili-grader', '--', 'env',
            'PYTHONPATH=' + str(lab / 'source'), args.python,
            str(lab / 'source/tools/acceptance-audit.py'), str(lab / 'vault'),
            '--session', str(lab / 'exchange/session')], capture_output=True, text=True)
        (destination / 'audit-stdout.txt').write_text(audit.stdout)
        (destination / 'audit-stderr.txt').write_text(audit.stderr)
        if audit.returncode:
            raise RuntimeError(audit.stderr)
        shutil.copytree(lab / 'exchange/session', destination / 'accepted-session')
        shutil.copy2(lab / 'receipts/receipt.json', destination / 'receipt.json')
        record['audit'] = json.loads(audit.stdout)
    (args.study / 'audited-summary.json').write_text(json.dumps(records, indent=2))
    print(json.dumps(records, indent=2))


if __name__ == '__main__':
    main()

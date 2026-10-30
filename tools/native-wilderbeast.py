"""Owner provisioner: native archive transfer and sealed negative control.

Run as root inside the existing disposable Ubuntu lab. The controller and
grader operate as separate accounts; private inputs and keys are not exported.
No model calls occur. This validates the prior owner-reviewed candidate only.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from chilicrisp import acceptance  # noqa: E402
from chilicrisp.project import initialize  # noqa: E402
from chilicrisp.runner import file_hash, tree_hash  # noqa: E402
from verification.wilderbeast.streaming import rewrite  # noqa: E402
from verification.wilderbeast.native_workload import expected_digest  # noqa: E402


def load(name):
    path = SOURCE / 'tools' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_outcomes(summary):
    return (len(summary) == 2 and summary[0].get('control') == 'good'
            and summary[0].get('grade', {}).get('verdict') == 'passed'
            and summary[1].get('control') == 'overfit'
            and summary[1].get('grade', {}).get('verdict') == 'rejected')


def latest_template():
    summaries = sorted((SOURCE / 'artifacts').glob('trust-*/trust-summary.json'),
                       key=lambda path: path.stat().st_mtime, reverse=True)
    for path in summaries:
        record = json.loads(path.read_text())
        lab = Path(record['lab'])
        if record.get('status') == 'passed' and (lab / 'venv/bin/python').is_file() and (lab / 'rootfs').is_dir():
            return lab
    raise ValueError('Run tools/native-trust.py first, or supply --template for a validated disposable lab')


def provision(template, output, control):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    trust = load('native-trust')
    lab = Path(tempfile.mkdtemp(prefix='wb-' + control + '-', dir='/srv/chili-trust'))
    lab.chmod(0o755)
    for name in ('chilicrisp', 'examples', 'tools', 'verification'):
        shutil.copytree(SOURCE / name, lab / 'source' / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(template / 'rootfs', lab / 'rootfs', symlinks=True)
    fixture = lab / 'rootfs/fixtures'
    fixture.chmod(0o755)
    shutil.copytree(SOURCE / 'verification/wilderbeast/frozen/wilderbeast', fixture / 'wilderbeast',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(SOURCE / 'verification/wilderbeast/native_workload.py', fixture / 'archive-driver.py')
    for path in [lab / 'rootfs', *(lab / 'rootfs').rglob('*')]:
        if not path.is_symlink():
            path.chmod(path.stat().st_mode & ~0o222)
    for name in ('controller', 'vault', 'agent', 'exchange', 'receipts'):
        (lab / name).mkdir()
    root_hash = tree_hash(lab / 'rootfs')
    manifests = {}
    for name, unit in (('controller', 'develop'), ('vault', 'grade')):
        directory = lab / name
        value = json.loads((SOURCE / 'examples/experiment.json').read_text())
        value['target'].update(rootfs=str(lab / 'rootfs'), rootfs_hash=root_hash,
            command=['/usr/bin/python3', '-I', '-B', '/fixtures/archive-driver.py'],
            build_identity='frozen Python archive component; no candidate host execution')
        value['isolation'].update(cgroup_parent=f'/sys/fs/cgroup/system.slice/{lab.name}-{unit}.service/experiments',
            cpu={'quota_usec': 100000, 'period_usec': 100000}, scratch_bytes=64 * 1024 * 1024)
        value['limits'].update(timeout_seconds=30, experiment_seconds=1200)
        seed = 41 if name == 'controller' else 100 + secrets.randbelow(100000)
        count = 8000 if name == 'controller' else 10000 + secrets.randbelow(4000)
        value['workloads'] = []
        for mode in ('check', 'persist'):
            data = directory / (mode + '-input.json')
            data.write_text(json.dumps({'mode': mode, 'seed': seed, 'count': count}))
            expected = 'checked' if mode == 'check' else expected_digest(count, seed)
            value['workloads'].append({'id': mode, 'input': str(data), 'input_hash': file_hash(data),
                'arguments': [], 'expected_stdout_hash': hashlib.sha256((expected + '\n').encode()).hexdigest()})
        (directory / 'runtime.json').write_text(json.dumps(value, indent=2))
        manifests[name] = value
    key = Ed25519PrivateKey.generate()
    vault = lab / 'vault'
    (vault / 'key').write_bytes(key.private_bytes_raw())
    policy = {'schema_version': '0.1', 'campaign': lab.name,
        'manifest': 'runtime.json', 'manifest_sha256': file_hash(vault / 'runtime.json'),
        'benchmark_workload': 'persist', 'transfer_budget': 128 * 1024 * 1024,
        'repetitions': 3, 'seed': 301026, 'wall_seconds': 600, 'max_trials': 12,
        'maximum_latency_regression': .25, 'minimum_memory_improvement': .05}
    (vault / 'policy.json').write_text(json.dumps(policy, indent=2))
    original = (SOURCE / 'verification/wilderbeast/frozen/wilderbeast/evidence/archive.py').read_text(encoding='utf-8')
    for name, code in (('controller/baseline', original), ('agent/candidate', rewrite(original))):
        directory = lab / name
        directory.mkdir()
        if control == 'overfit' and name.startswith('agent'):
            code = code.replace('    def _save(self) -> None:\n',
                '    def _save(self) -> None:\n        if len(self._records) > 9000:\n            raise ValueError("deliberate sealed-size negative control")\n')
        (directory / 'archive.py').write_text(code, encoding='utf-8')
        (directory / 'contract.txt').write_text('Preserve archive APIs, atomic rollback and exact indent=2 JSON format.\n'
            'All finite nested JSON receipt metadata, Unicode, empty archives and arbitrary batch sizes are supported.\n')
    controller = lab / 'controller'
    config = initialize(controller / 'baseline', ['NEVER_RUN_HOST_TESTS'], protected_paths=['contract.txt'])
    plan = {'schema_version': '0.1', 'concept': 'Native archive persistence with bounded transient memory',
        'project_config': str(config), 'benchmark_command': ['NEVER_RUN_HOST_BENCHMARK'],
        'objective': 'native_memory_peak_bytes',
        'evaluation': {'backend': 'linux_cgroup', 'manifest': str(controller / 'runtime.json'),
            'benchmark_workload': 'persist', 'initial_budget': 128 * 1024 * 1024},
        'acceptance': {'campaign': lab.name, 'public_key': key.public_key().public_bytes_raw().hex(),
            'policy_sha256': file_hash(vault / 'policy.json'), 'evaluator_sha256': acceptance.implementation()},
        'quantum': 4096, 'minimum_target': 4096, 'reductions': [.05],
        'repetitions': 3, 'confirmation_repetitions': 3, 'regression_limits': {'wall_seconds': .25},
        'max_generations': 1, 'max_commands': 100, 'wall_seconds': 1800}
    (controller / 'plan.json').write_text(json.dumps(plan, indent=2))
    (controller / 'research.json').write_text(json.dumps({
        'hypothesis': 'Streaming receipt conversion reduces charged cgroup peak by at least 5%.',
        'mechanism': 'Bound transient dictionaries; tmpfs file pages remain charged equally.',
        'falsification': 'Public or sealed correctness fails, memory reduction is below 5%, or latency regresses over 25%.',
        'sources': [{'reference': 'reports/repository-cohort.md', 'supports': 'Prior sampled local experiment; native transfer unproven.'}]}))
    trust.own(lab / 'source', 'root', 0o755, 0o644)
    for name, account, mode, files in (
        ('controller', 'chili-runner', 0o700, 0o644), ('vault', 'chili-grader', 0o700, 0o600),
        ('agent', 'chili-agent', 0o755, 0o644), ('exchange', 'chili-runner', 0o755, 0o644),
        ('receipts', 'chili-grader', 0o755, 0o644)):
        trust.own(lab / name, account, mode, files)
    python = str(template / 'venv/bin/python')
    worker = str(lab / 'source/tools/model-study-linux.py')
    result = {'lab': str(lab), 'control': control, 'policy_minimum_memory_reduction': .05,
              'transfer_budget': policy['transfer_budget'], 'scratch_bytes': 64 * 1024 * 1024}

    def phase(action, *extra):
        command = [python, worker, 'unit', str(lab), action, *extra]
        completed = subprocess.run(command, cwd=lab / 'source', capture_output=True, text=True)
        with (output / 'phases.jsonl').open('a') as stream:
            stream.write(json.dumps({'lab': str(lab), 'action': action, 'returncode': completed.returncode,
                                     'stdout': completed.stdout, 'stderr': completed.stderr}) + '\n')
        if completed.returncode:
            raise RuntimeError(completed.stdout[-2000:] + completed.stderr[-3000:])
        return json.loads(completed.stdout)

    result['init'] = phase('init')
    result['submit'] = phase('submit', str(lab / 'agent/candidate'), str(controller / 'research.json'))
    if result['submit']['champion'] == 0:
        result['status'] = 'public_rejection'
        return result
    result['grade'] = phase('grade')
    result['accept'] = phase('accept')
    audit = subprocess.run(['runuser', '-u', 'chili-grader', '--', 'env', 'PYTHONPATH=' + str(lab / 'source'),
        python, str(lab / 'source/tools/acceptance-audit.py'), str(vault), '--session', str(lab / 'exchange/session')],
        capture_output=True, text=True)
    if audit.returncode:
        raise RuntimeError(audit.stderr)
    result['audit'] = json.loads(audit.stdout)
    result['status'] = 'completed'
    destination = output / lab.name
    shutil.copytree(lab / 'exchange/session', destination / 'session')
    shutil.copy2(lab / 'receipts/receipt.json', destination / 'receipt.json')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path)
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise SystemExit('Run as the owner in the disposable Ubuntu lab')
    template = args.template or latest_template()
    output = SOURCE / 'artifacts' / ('native-wilderbeast-' + secrets.token_hex(6))
    output.mkdir()
    summary = []
    for control in ('good', 'overfit'):
        result = provision(template, output, control)
        summary.append(result)
        (output / 'summary.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps(result), flush=True)
    print(str(output), flush=True)
    return int(not expected_outcomes(summary))


if __name__ == '__main__':
    raise SystemExit(main())

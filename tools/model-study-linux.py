"""Owner/role phases for the bounded real-model comparison (disposable Linux lab)."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    phase, location = sys.argv[1:3]
    lab = Path(location)
    source = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(source))
    roles = load(source / 'tools/native-trust-roles.py')
    roles.LAB = lab
    trust = load(source / 'tools/native-trust.py')
    if phase == 'setup':
        template, arm = Path(sys.argv[3]), sys.argv[4]
        lab.mkdir(mode=0o755)
        for name in ('rootfs', 'compiler-rootfs'):
            shutil.copytree(template / name, lab / name, symlinks=True)
        shutil.copy2(template / 'toolchain-version.txt', lab)
        (lab / 'empty-input').write_bytes(b'')
        for name in ('chilicrisp', 'examples', 'tools'):
            shutil.copytree(source / name, lab / 'source' / name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in ('controller', 'vault', 'agent', 'exchange', 'receipts'):
            (lab / name).mkdir()
        parents = {p: f'/sys/fs/cgroup/system.slice/{lab.name}-{p}.service/experiments'
                   for p in ('develop', 'grade')}
        roles.owner_setup(parents['develop'], parents['grade'])
        plan_path = lab / 'controller/plan.json'
        plan = json.loads(plan_path.read_text())
        plan.update(max_generations=2, max_stagnation=2, wall_seconds=3600)
        if arm == 'conventional':
            plan['objective'] = 'native_memory_peak_bytes'
        plan_path.write_text(json.dumps(plan, indent=2))
        trust.own(lab / 'source', 'root', 0o755, 0o644)
        for name, account, mode, files in (
            ('controller', 'chili-runner', 0o700, 0o644),
            ('vault', 'chili-grader', 0o700, 0o600),
            ('agent', 'chili-agent', 0o755, 0o644),
            ('exchange', 'chili-runner', 0o755, 0o644),
            ('receipts', 'chili-grader', 0o755, 0o644)):
            trust.own(lab / name, account, mode, files)
        print(json.dumps({'lab': str(lab), 'arm': arm}))
        return
    sys.path.insert(0, str(lab / 'source'))
    from chilicrisp import development as dev
    if phase == 'export-public':
        shutil.copytree(lab / 'exchange/public', Path(sys.argv[3]))
    elif phase == 'import-proposal':
        proposal = Path(sys.argv[3])
        target = lab / 'agent' / proposal.name
        shutil.copytree(proposal / 'candidate', target)
        trust.own(target, 'chili-agent', 0o755, 0o644)
        shutil.copy2(proposal / 'research.json', target.parent / (proposal.name + '-research.json'))
    elif phase in ('init', 'submit'):
        roles.delegate(json.loads((lab / 'controller/runtime.json').read_text())['isolation']['cgroup_parent'])
        session = lab / 'controller/session'
        if phase == 'init':
            state = dev.create(lab / 'controller/plan.json', session)
        else:
            state = dev.submit(session, Path(sys.argv[3]), Path(sys.argv[4]))
        public = lab / 'exchange/public'
        public.mkdir(exist_ok=True)
        (public / 'state.json').write_text(json.dumps(state, indent=2))
        if state['state'] == 'AWAITING_CANDIDATE':
            request = dev.request(session)
            (public / 'request.json').write_text(json.dumps(request, indent=2))
            incumbent = public / 'incumbent'
            if incumbent.exists():
                shutil.rmtree(incumbent)
            shutil.copytree(request['champion_source'], incumbent)
        elif state['champion']:
            dev.export_acceptance_request(session, lab / 'exchange/request')
        print(json.dumps({'state': state['state'], 'champion': state['champion'],
                          'decisions': [g['decision'] for g in state['generations']]}))
    elif phase == 'grade':
        print(json.dumps(roles.grade()))
    elif phase == 'accept':
        state = dev.accept(lab / 'controller/session', lab / 'receipts/receipt.json')
        shutil.copytree(lab / 'controller/session', lab / 'exchange/session')
        print(json.dumps({'verdict': state['acceptances'][-1]['body']['verdict']}))
    elif phase == 'unit':
        action = sys.argv[3]
        role = 'chili-grader' if action == 'grade' else 'chili-runner'
        unit = 'grade' if action == 'grade' else 'develop'
        command = ['systemd-run', '--wait', '--pipe', '--collect', '--quiet',
                   '--service-type=exec', '--unit', lab.name + '-' + unit,
                   '--property=User=' + role, '--property=Delegate=yes',
                   '--property=WorkingDirectory=' + str(lab / 'source'),
                   sys.executable, str(lab / 'source/tools/model-study-linux.py'), action, str(lab), *sys.argv[4:]]
        result = subprocess.run(command)
        raise SystemExit(result.returncode)
    else:
        raise ValueError(phase)


if __name__ == '__main__':
    os.umask(0o022)
    main()

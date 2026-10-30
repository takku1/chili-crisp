"""Freeze selected real-project components without writing to their repositories."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def freeze(source, destination, trees, names, member=None):
    selected = [source / name for name in names if (source / name).is_file()]
    for tree in trees:
        for path in (source / tree).rglob('*'):
            if path.is_symlink() or path.is_junction():
                raise ValueError('Refusing source link: ' + str(path))
            if path.is_file() and not any(part in {'__pycache__', '.pytest_cache'} for part in path.parts):
                selected.append(path)
    files = {}
    destination.mkdir(parents=True)
    for path in sorted(set(selected)):
        if path.is_symlink():
            raise ValueError('Refusing symlink: ' + str(path))
        relative = path.relative_to(source).as_posix()
        data = path.read_bytes()
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files[relative] = sha(data)
    for name, digest in files.items():
        if sha((source / name).read_bytes()) != digest:
            raise RuntimeError('Source changed during snapshot: ' + name)
    changes = []
    if member:
        cargo = destination / 'Cargo.toml'
        original = cargo.read_text(encoding='utf-8')
        cargo.write_text('[workspace]\nresolver = "3"\nmembers = [' + json.dumps(member) + ']\n\n'
                         + original[original.index('[workspace.package]'):], encoding='utf-8')
        changes.append('Owner narrows workspace membership to selected unchanged crate; retains workspace package, dependency, lint and profile declarations.')
    snapshot = {p.relative_to(destination).as_posix(): sha(p.read_bytes())
                for p in destination.rglob('*') if p.is_file()}
    def git(*args):
        result = subprocess.run(['git', '-C', str(source), *args], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        return result.stdout.strip()
    return {'source': str(source), 'baseline': str(destination), 'parent_commit': git('rev-parse', 'HEAD'),
            'dirty_status': git('status', '--short', '--untracked-files=normal'),
            'upstream_files_sha256': files, 'snapshot_files_sha256': snapshot,
            'source_manifest_sha256': sha(json.dumps(files, sort_keys=True).encode()),
            'build_adapter_changes': changes,
            'qualification': 'Snapshot includes current uncommitted component files; it is not identical to parent commit.'}


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = ROOT / 'artifacts' / ('repository-cohort-' + stamp)
    tasks = {
        'wilderbeast': (Path('Z:/Wilderbeast'), ['src', 'tests'], ['pyproject.toml', 'requirements.txt'], None),
        'mochios': (Path('Z:/mochios'), ['crates/system/component-model'], ['Cargo.toml', 'Cargo.lock'], 'crates/system/component-model'),
        'worldgame': (Path('Z:/worldgame'), ['crates/mote-core'], ['Cargo.toml', 'Cargo.lock'], 'crates/mote-core'),
    }
    manifest = {'created_at': stamp, 'stage': 'baseline qualification; no optimization or acceptance claim', 'projects': {}}
    for name, (source, trees, names, member) in tasks.items():
        manifest['projects'][name] = freeze(source, output / name / 'baseline', trees, names, member)
    (output / 'cohort.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(str(output))


if __name__ == '__main__':
    main()

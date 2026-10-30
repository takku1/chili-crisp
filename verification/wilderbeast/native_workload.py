"""Frozen native archive driver and independent exact-format output reference.

Persist mode hashes the actual saved bytes incrementally; it does not reload or
materialize JSON for grading inside the measured process. Check mode exercises
small roundtrips, errors and atomic rollback separately from resource trials.
"""
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import types

STAMP = '2026-10-29T00:00:00+00:00'


def payload(index, seed):
    return {'kind': 'identity', 'title': f'finding-{seed}-{index}', 'target_representation': 'expression',
            'statement': f'x + {index} = {index} + x',
            'formal_proof_or_witness': ('(assert (= x x))\n' * (1 + (index + seed) % 16)),
            'novelty': 'N0', 'usefulness': 'U1',
            'reproducibility': {'seed': seed, 'index': index, 'nested': [None, True, -3.25], 'unicode': 'λ🦊'},
            'provenance': ['owner-generated', f'case-{seed % 7}']}


def expected_digest(count, seed):
    # Independent schema construction, without importing or executing a candidate.
    data = [{'archive_id': f'{i + 1:032x}', 'recorded_at': STAMP, 'session_id': f'session-{seed}',
             'receipt': payload(i, seed)} for i in range(count)]
    return hashlib.sha256(json.dumps(data, indent=2).encode()).hexdigest()


def load_candidate(path):
    fixture = Path(__file__).parent
    sys.path.insert(0, str(fixture))
    spec = importlib.util.spec_from_file_location('wilderbeast.evidence.archive', path)
    archive = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = archive
    spec.loader.exec_module(archive)
    ids = itertools.count(1)
    archive.uuid = types.SimpleNamespace(uuid4=lambda: f'{next(ids):032x}')

    class Clock:
        @staticmethod
        def now(**kwargs):
            return types.SimpleNamespace(isoformat=lambda: STAMP)

    archive.datetime = Clock
    return archive


def receipts(count, seed):
    from wilderbeast.evidence.discovery import DiscoveryKind, DiscoveryReceipt
    from wilderbeast.evidence.finding import NoveltyClass, UsefulnessClass
    for index in range(count):
        values = payload(index, seed)
        values['kind'] = DiscoveryKind(values['kind'])
        values['novelty'] = NoveltyClass(values['novelty'])
        values['usefulness'] = UsefulnessClass(values['usefulness'])
        yield DiscoveryReceipt(**values)


def file_digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            result.update(block)
    return result.hexdigest()


def check(archive_module, seed):
    path = Path('/tmp/archive.json')
    for count in (0, 1, 37):
        archive = archive_module.DiscoveryArchive(path, session_id=f'session-{seed}')
        archive._records.clear()
        archive.record_all(list(receipts(count, seed)))
        restored = archive_module.DiscoveryArchive(path)
        assert len(restored) == count
        assert sorted((r.receipt.to_dict() for r in restored.all_records()), key=lambda r: r['title']) == sorted(
            (payload(i, seed) for i in range(count)), key=lambda r: r['title'])
        assert restored.query(session_id='absent') == []
        assert len(restored.query(session_id=f'session-{seed}', limit=5)) == min(5, count)
        path.unlink()
    archive = archive_module.DiscoveryArchive(path, session_id=f'session-{seed}')
    archive.record(next(receipts(1, seed)))
    before = path.read_bytes()
    invalid = next(receipts(1, seed))
    invalid.reproducibility = {'unsupported': object()}
    try:
        archive.record(invalid)
    except TypeError:
        pass
    else:
        raise AssertionError('Unsupported JSON value accepted')
    assert len(archive) == 1 and path.read_bytes() == before
    assert not list(path.parent.glob('.wb_archive_*.tmp'))
    replace = archive_module.os.replace
    try:
        def fail(*args):
            raise OSError('owner-injected replace failure')
        archive_module.os.replace = fail
        try:
            archive.record(next(receipts(1, seed)))
        except OSError:
            pass
        else:
            raise AssertionError('Atomic replacement failure ignored')
    finally:
        archive_module.os.replace = replace
    assert len(archive) == 1 and path.read_bytes() == before
    assert not list(path.parent.glob('.wb_archive_*.tmp'))
    path.write_text('invalid json')
    try:
        archive_module.DiscoveryArchive(path)
    except ValueError:
        pass
    else:
        raise AssertionError('Corrupt archive accepted')


def main():
    request = json.load(sys.stdin)
    archive = load_candidate('/candidate/archive.py')
    if request['mode'] == 'check':
        check(archive, request['seed'])
        print('checked')
    else:
        destination = Path('/tmp/archive.json')
        store = archive.DiscoveryArchive(destination, session_id=f"session-{request['seed']}")
        store.record_all(list(receipts(request['count'], request['seed'])))
        print(file_digest(destination))


if __name__ == '__main__':
    main()

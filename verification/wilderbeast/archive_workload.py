"""Protected archive persistence workload; logical checks are outside editable source."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--records', type=int, default=8000)
    parser.add_argument('--mode', choices=('check', 'measure'), default='check')
    args = parser.parse_args()
    sys.path.insert(0, str(args.source / 'src'))
    from wilderbeast.evidence.archive import DiscoveryArchive
    from wilderbeast.evidence.discovery import DiscoveryKind, DiscoveryReceipt
    args.scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.scratch) as directory:
        path = Path(directory) / 'archive.json'
        archive = DiscoveryArchive(path, session_id='qualification')
        receipts = [DiscoveryReceipt(DiscoveryKind.IDENTITY, f'finding-{i}', 'expression',
                    f'x + {i} = {i} + x', '(assert (= x x))\n' * (1 + i % 16),
                    reproducibility={'seed': i, 'unicode': 'λ'}, provenance=['owner-generated'])
                    for i in range(args.records)]
        archive.record_all(receipts)
        if args.mode == 'measure':
            # Time persistence itself; full roundtrip/differential assertions
            # run separately so oracle allocations do not set the measured peak.
            assert len(archive) == args.records
            print(json.dumps({'records': len(archive), 'operation': 'batch-persist'}, sort_keys=True))
            return
        restored = DiscoveryArchive(path, session_id='reader')
        assert len(restored) == args.records
        records = restored.all_records()
        assert {r.receipt.title for r in records} == {r.title for r in receipts}
        assert all(r.session_id == 'qualification' for r in records)
        original = {r.title: r.to_dict() for r in receipts}
        for record in records:
            assert record.receipt.to_dict() == original[record.receipt.title]
        assert len(restored.query(session_id='qualification', limit=17)) == min(17, args.records)
        assert restored.query(kind=DiscoveryKind.ALGORITHM) == []
        assert len(json.loads(path.read_text(encoding='utf-8'))) == args.records
        canonical = sorted((r.receipt.to_dict() for r in records), key=lambda r: r['title'])
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        print(json.dumps({'records': args.records, 'logical_sha256': digest}, sort_keys=True))


if __name__ == '__main__':
    main()

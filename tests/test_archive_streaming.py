"""Compatibility of the actual pinned archive candidate, not a proxy encoder."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_core import test_directory
from verification.wilderbeast.streaming import rewrite

FIXTURE = Path(__file__).resolve().parents[1] / 'verification/wilderbeast/frozen'
sys.path.insert(0, str(FIXTURE))
from wilderbeast.evidence.discovery import DiscoveryKind, DiscoveryReceipt  # noqa: E402
sys.path.remove(str(FIXTURE))


def module(name, code):
    value = types.ModuleType(name)
    sys.modules[name] = value
    exec(compile(code, name, 'exec'), value.__dict__)
    return value


SOURCE = (FIXTURE / 'wilderbeast/evidence/archive.py').read_text(encoding='utf-8')
BASELINE = module('archive_original_fixture', SOURCE)
CANDIDATE = module('archive_streaming_fixture', rewrite(SOURCE))


def receipt(index=0):
    return DiscoveryReceipt(DiscoveryKind.IDENTITY, f'λ-{index}', 'expression', 'x = x',
        'proof\n' * (index + 1), reproducibility={'nested': [None, True, -3.25, {'emoji': '🦊'}]},
        provenance=['one', 'two'])


class ArchiveStreamingTests(unittest.TestCase):
    def test_native_provisioner_expects_signed_rejected_label(self):
        path = FIXTURE.parents[2] / 'tools/native-wilderbeast.py'
        spec = importlib.util.spec_from_file_location('native_wilderbeast_test', path)
        provisioner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(provisioner)
        self.assertTrue(provisioner.expected_outcomes([
            {'control': 'good', 'grade': {'verdict': 'passed'}},
            {'control': 'overfit', 'grade': {'verdict': 'rejected'}}]))
        self.assertFalse(provisioner.expected_outcomes([
            {'control': 'good', 'grade': {'verdict': 'passed'}},
            {'control': 'overfit', 'grade': {'verdict': 'passed'}}]))

    def test_frozen_fixture_hashes_match_provenance(self):
        provenance = json.loads((FIXTURE / 'provenance.json').read_text())
        for name, expected in provenance['files_sha256'].items():
            content = (FIXTURE / 'wilderbeast' / name).read_bytes().replace(b'\r\n', b'\n')
            self.assertEqual(hashlib.sha256(content).hexdigest(), expected)

    def test_saved_bytes_match_materialized_encoder_and_reload(self):
        for count in (0, 1, 17):
            for pure_python in (False, True):
                with self.subTest(count=count, pure_python=pure_python), test_directory() as directory:
                    root = Path(directory)
                    original = BASELINE.DiscoveryArchive(root / 'original.json', session_id='same')
                    original.record_all([receipt(i) for i in range(count)])
                    candidate = CANDIDATE.DiscoveryArchive(root / 'candidate.json', session_id='same')
                    candidate._records = original._records.copy()
                    if pure_python:
                        with patch('json.encoder.c_make_encoder', None):
                            candidate._save()
                    else:
                        candidate._save()
                    self.assertEqual(candidate.storage_path.read_bytes(), original.storage_path.read_bytes())
                    restored = CANDIDATE.DiscoveryArchive(candidate.storage_path)
                    self.assertEqual([r.to_dict() for r in restored.all_records()],
                                     [r.to_dict() for r in original.all_records()])

    def test_record_conversion_is_lazy_at_encoder_entry(self):
        with test_directory() as directory:
            candidate = CANDIDATE.DiscoveryArchive(Path(directory) / 'archive.json')
            candidate.record_all([receipt(i) for i in range(4)])
            record = next(iter(candidate._records.values()))
            with patch.object(type(record), 'to_dict', wraps=type(record).to_dict, autospec=True) as convert:
                original = json.dump

                def observe(value, stream, **kwargs):
                    self.assertEqual(convert.call_count, 0)
                    self.assertEqual(len(value), 4)
                    return original(value, stream, **kwargs)

                with patch.object(CANDIDATE.json, 'dump', side_effect=observe):
                    # Use a counter without changing record data returned to JSON.
                    convert.side_effect = lambda value: BASELINE.ArchiveRecord.to_dict(value)
                    candidate._save()
                self.assertEqual(convert.call_count, 4)

    def test_encoding_failure_rolls_back_and_removes_temp_file(self):
        with test_directory() as directory:
            root = Path(directory)
            archive = CANDIDATE.DiscoveryArchive(root / 'archive.json')
            archive.record(receipt())
            before = archive.storage_path.read_bytes()
            invalid = receipt()
            invalid.reproducibility = {'unsupported': object()}
            with self.assertRaises(TypeError):
                archive.record(invalid)
            self.assertEqual(len(archive), 1)
            self.assertEqual(archive.storage_path.read_bytes(), before)
            self.assertFalse(list(root.glob('*.tmp')))

    def test_replace_failure_rolls_back_and_removes_temp_file(self):
        with test_directory() as directory:
            root = Path(directory)
            archive = CANDIDATE.DiscoveryArchive(root / 'archive.json')
            archive.record(receipt())
            before = archive.storage_path.read_bytes()
            with patch.object(CANDIDATE.os, 'replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    archive.record(receipt(1))
            self.assertEqual(len(archive), 1)
            self.assertEqual(archive.storage_path.read_bytes(), before)
            self.assertFalse(list(root.glob('*.tmp')))


if __name__ == '__main__':
    unittest.main()

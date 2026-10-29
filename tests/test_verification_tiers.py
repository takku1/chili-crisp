import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest

from test_core import test_directory


spec = importlib.util.spec_from_file_location(
    "worldgame_verification", Path(__file__).resolve().parents[1] / "verification/worldgame/check.py")
verification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verification)


class TierTests(unittest.TestCase):
    def test_screen_uses_original_reference_indexes(self):
        self.assertEqual(verification.selected_cases("screen"),
                         [(3, ("manufactured", "17")), (0, ("ocean", "42", "1.0"))])
        self.assertEqual(len(verification.selected_cases("full")), 6)
        with self.assertRaises(ValueError):
            verification.selected_cases("accept")

    def test_reference_is_matched_by_case_and_hash(self):
        with test_directory() as directory:
            root = Path(directory)
            data = b"CCFIELDS1" + struct.pack("<Qd", 1, 1.0)
            (root / "case-3.bin").write_bytes(data)
            record = dict(case=["manufactured", "17"], sha256=hashlib.sha256(data).hexdigest())
            (root / "results.json").write_text(json.dumps(dict(outcome="pass", cases=[record])))
            self.assertEqual(list(verification.reference_values(root, 3, ("manufactured", "17"))), [1.0])
            with self.assertRaises(ValueError):
                verification.reference_values(root, 3, ("manufactured", "33"))
            (root / "case-3.bin").write_bytes(data + b"tampered")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verification.reference_values(root, 3, ("manufactured", "17"))

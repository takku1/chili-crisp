import math
import struct
import unittest

from chilicrisp.fields import decode, compare


def stream(values):
    return b"CCFIELDS1" + struct.pack("<Q", len(values)) + struct.pack("<" + "d"*len(values), *values)


class FieldTests(unittest.TestCase):
    def test_real_values_and_tolerances(self):
        values = decode(stream([0.0, 2.0, -4.0]))
        self.assertEqual(list(values), [0.0, 2.0, -4.0])
        self.assertLess(compare([2+1e-9], [2]), 1e-8)

    def test_fake_zero_fields_and_single_value_change_fail(self):
        for candidate in ([0.0, 0.0], [1.0, 2.01], [1.0]):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                compare(candidate, [1.0, 2.0])

    def test_summaries_truncation_extra_bytes_and_nonfinite_rejected(self):
        for data in (b"water=0; converged=true", stream([1.0])[:-1],
                     stream([1.0]) + b"extra", stream([math.nan]), stream([math.inf])):
            with self.subTest(data=data), self.assertRaises(ValueError):
                decode(data)

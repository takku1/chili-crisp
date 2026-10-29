from array import array
import hashlib
import math
import struct
import unittest

from chilicrisp.fields import decode


class DecoderBufferTests(unittest.TestCase):
    def test_bytes_bytearray_and_contiguous_view_preserve_all_bits(self):
        values = [0.0, -0.0, 1e-300, -1e-300, 1e300, -1e300, 1.25]
        payload = struct.pack("<7d", *values)
        encoded = b"CCFIELDS1" + struct.pack("<Q", len(values)) + payload
        for data in (encoded, bytearray(encoded), memoryview(encoded)):
            with self.subTest(kind=type(data).__name__):
                actual = decode(data)
                self.assertIsInstance(actual, array)
                self.assertEqual(list(actual), values)
                self.assertEqual(math.copysign(1, actual[1]), -1)

    def test_maximum_supported_stream_matches_independent_payload_digest(self):
        payload = struct.pack("<d", 1.25) * 500000
        actual = decode(b"CCFIELDS1" + struct.pack("<Q", 500000) + payload)
        self.assertEqual(len(actual), 500000)
        # Encode explicitly as little-endian rather than assuming host order.
        expected = hashlib.sha256(payload).hexdigest()
        digest = hashlib.sha256()
        for start in range(0, len(actual), 4096):
            chunk = actual[start:start + 4096]
            digest.update(struct.pack("<" + "d" * len(chunk), *chunk))
        self.assertEqual(digest.hexdigest(), expected)

    def test_empty_and_above_limit_stream(self):
        self.assertEqual(len(decode(b"CCFIELDS1" + struct.pack("<Q", 0))), 0)
        with self.assertRaises(ValueError):
            decode(b"CCFIELDS1" + struct.pack("<Q", 500001))

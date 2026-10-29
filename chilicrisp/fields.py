"""Strict field-stream decoding and numeric comparison for trusted drivers."""
from array import array
import math
import struct
import sys


def decode(data):
    if len(data) < 17 or data[:9] != b"CCFIELDS1":
        raise ValueError("invalid trusted-harness field stream")
    count = struct.unpack_from("<Q", data, 9)[0]
    if count > 500000 or len(data) != 17 + count * 8:
        raise ValueError("invalid field stream length")
    values = array("d")
    values.frombytes(data[17:])
    if sys.byteorder != "little":
        values.byteswap()
    if any(not math.isfinite(v) for v in values):
        raise ValueError("non-finite simulation field")
    return values


def compare(actual, expected, atol=1e-8, rtol=1e-8):
    if not math.isfinite(atol) or not math.isfinite(rtol) or min(atol, rtol) < 0:
        raise ValueError("invalid comparison tolerance")
    if len(actual) != len(expected):
        raise ValueError("field count mismatch")
    maximum = 0.0
    for index, (value, reference) in enumerate(zip(actual, expected)):
        if not math.isfinite(value) or not math.isfinite(reference):
            raise ValueError("non-finite comparison")
        difference = abs(value-reference)
        maximum = max(maximum, difference)
        if difference > atol + rtol * abs(reference):
            raise ValueError(f"field {index} differs: {value} vs {reference}")
    return maximum

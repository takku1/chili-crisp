"""Owner-controlled correctness and resource driver for unexecuted AI proposals."""
from array import array
import hashlib
import math
import struct
import sys

sys.path.insert(0, "/app")
from chilicrisp.fields import compare, decode  # noqa: E402

for sample in ([], [0.0, -0.0, 1e-300, -1e300], [1.25, -4.5]):
    encoded = b"CCFIELDS1" + struct.pack("<Q", len(sample)) + struct.pack("<" + "d" * len(sample), *sample)
    for source in (encoded, bytearray(encoded), memoryview(encoded)):
        actual = decode(source)
        assert isinstance(actual, array) and actual.typecode == "d"
        assert list(actual) == sample
        if len(sample) == 4:
            assert math.copysign(1, actual[1]) == -1
for bad in (b"invalid", b"CCFIELDS1" + struct.pack("<Q", 500001),
            b"CCFIELDS1" + struct.pack("<Qd", 1, math.nan),
            b"CCFIELDS1" + struct.pack("<Qd", 1, math.inf)):
    try:
        decode(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid stream was accepted")
assert compare([1.0], [1.0]) == 0
try:
    compare([1.1], [1.0])
except ValueError:
    pass
else:
    raise AssertionError("Numerical mismatch was accepted")
data = sys.stdin.buffer.read()
for _ in range(int(sys.argv[1])):
    actual = decode(data)
    assert isinstance(actual, array) and actual.typecode == "d" and len(actual) == 500000
    digest = hashlib.sha256(actual).hexdigest()
    del actual
print(digest)

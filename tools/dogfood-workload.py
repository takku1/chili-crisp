"""Trusted decoder benchmark: input and expected digest are supplied by owner."""
import hashlib
import sys

sys.path.insert(0, "/app")
from chilicrisp.fields import decode  # noqa: E402

data = sys.stdin.buffer.read()
iterations = int(sys.argv[1])
for _ in range(iterations):
    values = decode(data)
    assert len(values) == 500000
    digest = hashlib.sha256(values).hexdigest()
    del values
print(digest)

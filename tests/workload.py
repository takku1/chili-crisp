"""Deliberately hostile fixtures. Copy into the isolated fixture rootfs only."""
import os
import sys
import time

mode = sys.argv[1]
if mode == "correct":
    print("ok")
elif mode == "wrong":
    print("incorrect")
elif mode == "timeout":
    time.sleep(60)
elif mode == "flood":
    while True:
        os.write(1, b"x" * 8192)
elif mode == "oom":
    # Touch all allocated pages; do not rely on virtual address reservation.
    chunks = []
    while True:
        chunks.append(bytearray(b"x" * 1048576))
elif mode == "isolation":
    import socket
    assert os.getuid() == 65534
    status = open("/proc/self/status").read()
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    assert int(fields["CapEff"].strip(), 16) == 0
    assert fields["NoNewPrivs"].strip() == "1"
    assert fields["Seccomp"].strip() == "2"
    for operation in (lambda: socket.socket(), lambda: os.fork(),
                      lambda: open("/forbidden-write", "w")):
        try:
            operation()
        except OSError:
            pass
        else:
            raise RuntimeError("isolation restriction bypassed")
    assert not os.path.exists("/sys/fs/cgroup/cgroup.procs")
    print("ok")
else:
    raise SystemExit("unknown fixture")

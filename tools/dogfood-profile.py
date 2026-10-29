"""Separate diagnostic allocation/profile runs on frozen source capsules."""
import argparse
import cProfile
import hashlib
import importlib.util
import json
from pathlib import Path
import pstats
import struct
import tracemalloc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    data = b"CCFIELDS1" + struct.pack("<Q", 500000) + struct.pack("<d", 1.25) * 500000
    records = {}
    for name in ("baseline", "candidate"):
        spec = importlib.util.spec_from_file_location(name, args.work / name / "chilicrisp/fields.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tracemalloc.start()
        values = module.decode(data)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        digest = hashlib.sha256(values).hexdigest()
        del values
        records[name] = {"python_allocation_peak_bytes": peak, "output_digest": digest}
        if name == "baseline":
            profile = cProfile.Profile()
            profile.enable()
            for _ in range(16):
                module.decode(data)
            profile.disable()
            with (args.work / "baseline-profile.txt").open("w") as stream:
                pstats.Stats(profile, stream=stream).sort_stats("cumulative").print_stats(12)
    records["scope"] = "diagnostic instrumentation only; not native timing or enforcement"
    (args.work / "allocation-diagnostics.json").write_text(json.dumps(records, indent=2))
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()

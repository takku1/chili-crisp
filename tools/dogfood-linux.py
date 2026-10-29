"""Build owner-frozen decoder rootfs variants and invoke Chili Crisp itself."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
from array import array
import random
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("--source-only", action="store_true", help="Candidate has only been parsed; execute correctness solely inside sandbox")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    plan = json.loads((args.work / "plan.json").read_text())
    if not args.source_only:
        correctness = json.loads((args.work / "correctness.json").read_text())
        if correctness["decision"] != "public_tests_passed" or not correctness["integrity"]["valid"]:
            raise ValueError("Correctness comparison must pass before resource trials")

    def prepare(lab, rootfs):
        driver = source / "tools/ai-pilot-workload.py" if args.source_only else args.work / "baseline/tools/dogfood-workload.py"
        shutil.copy2(driver, rootfs / "fixtures/decoder.py")
        app = rootfs / "app/chilicrisp"
        app.mkdir(parents=True)
        shutil.copy2(args.work / "baseline/chilicrisp/__init__.py", app / "__init__.py")
        shutil.copy2(args.work / "baseline/chilicrisp/fields.py", app / "fields.py")
        candidate_root = lab / "candidate-rootfs"
        shutil.copytree(rootfs, candidate_root)
        shutil.copy2(args.work / "candidate/chilicrisp/fields.py", candidate_root / "app/chilicrisp/fields.py")
        for name, root in (("baseline", rootfs), ("candidate", candidate_root)):
            digest = hashlib.sha256((root / "app/chilicrisp/fields.py").read_bytes()).hexdigest()
            if digest != plan[f"{name}_decoder_sha256"]:
                raise ValueError("Frozen decoder does not match preregistered source")
        # Independent finite signed values; no numerical fields supplied by target.
        block = b"".join(struct.pack("<d", (index - 2048) / 8) for index in range(4096))
        payload = (block * 123)[:500000 * 8]
        data = b"CCFIELDS1" + struct.pack("<Q", 500000) + payload
        (lab / "decoder-input").write_bytes(data)
        plan["input_sha256"] = hashlib.sha256(data).hexdigest()
        plan["expected_stdout_hash"] = hashlib.sha256(
            (hashlib.sha256(payload).hexdigest() + "\n").encode()).hexdigest()
        if args.source_only:
            seed = secrets.randbits(32)
            generator = random.Random(seed)
            hidden = array("d", (generator.uniform(-100, 100) for _ in range(500000))).tobytes()
            hidden_data = b"CCFIELDS1" + struct.pack("<Q", 500000) + hidden
            (lab / "confirmation-input").write_bytes(hidden_data)
            plan["heldout_confirmation"] = {"seed": seed, "input": str(lab / "confirmation-input"),
                "input_hash": hashlib.sha256(hidden_data).hexdigest(),
                "expected_stdout_hash": hashlib.sha256((hashlib.sha256(hidden).hexdigest() + "\n").encode()).hexdigest()}
            plan["correctness_execution"] = "inside sandbox only; no candidate host import/build/test"
        (lab / "dogfood-plan.json").write_text(json.dumps(plan, indent=2))
        return [candidate_root]

    spec = importlib.util.spec_from_file_location("native_fixtures", source / "tools/native-fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.provision(worker_name="dogfood-worker.py", prepare=prepare)


if __name__ == "__main__":
    raise SystemExit(main())

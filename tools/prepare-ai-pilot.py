"""Freeze the decoder pilot and source-only agent request before model use."""
import hashlib
import json
from pathlib import Path
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    work = ROOT / "artifacts" / ("ai-source-pilot-" + uuid.uuid4().hex)
    for name in ("baseline", "candidate"):
        target = work / name / "chilicrisp"
        target.mkdir(parents=True)
        for file in ("fields.py", "__init__.py"):
            shutil.copy2(ROOT / "chilicrisp" / file, target / file)
    digest = hashlib.sha256((work / "baseline/chilicrisp/fields.py").read_bytes()).hexdigest()
    request = {"kind": "bounded_source_proposal", "concept": "Decode strict numeric field streams using less temporary memory",
        "source": "chilicrisp/fields.py", "baseline_source_sha256": digest,
        "workload": "500000 finite doubles; decode returns array('d'); inputs include bytes, bytearray, contiguous views",
        "objective": "Reduce allocation and whole-program memory while preserving all public behavior",
        "measured_baseline_peak_bytes": 21098496, "initial_measured_target_bytes": 16878796,
        "limits": {"maximum_model_calls": 2, "maximum_seconds_per_call": 180},
        "feedback": None, "constraints": ["Only the selected Python module may change",
            "Preserve decode and compare signatures, return types, validation and error behavior",
            "Do not change tests, driver, input data or controller", "Do not execute the proposed program"]}
    (work / "request.json").write_text(json.dumps(request, indent=2), encoding="utf-8")
    print(str(work))


if __name__ == "__main__":
    main()

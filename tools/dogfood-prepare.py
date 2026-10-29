"""Freeze source capsules and a declared decoder candidate for self-testing."""
import json
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chilicrisp.evidence import verify  # noqa: E402
from chilicrisp.project import compare, initialize  # noqa: E402
from chilicrisp.runner import file_hash  # noqa: E402


def main():
    work = ROOT / "artifacts" / ("dogfood-" + uuid.uuid4().hex)
    baseline = work / "baseline"
    baseline.mkdir(parents=True)
    for name in ("chilicrisp", "tests", "tools", "verification", "examples", "docs"):
        shutil.copytree(ROOT / name, baseline / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("pyproject.toml", "README.md", "MANIFEST.in", "requirements.txt"):
        shutil.copy2(ROOT / name, baseline / name)
    candidate = work / "candidate"
    shutil.copytree(baseline, candidate)
    target = candidate / "chilicrisp/fields.py"
    old = "values.frombytes(data[17:])"
    new = "values.frombytes(memoryview(data)[17:])"
    original = target.read_text(encoding="utf-8")
    if original.count(old) != 1:
        raise ValueError("Baseline is not the declared decoder implementation")
    target.write_text(original.replace(old, new), encoding="utf-8")
    plan = {"kind": "chilicrisp_self_test", "baseline": str(baseline), "candidate": str(candidate),
        "baseline_decoder_sha256": file_hash(baseline / "chilicrisp/fields.py"),
        "candidate_decoder_sha256": file_hash(target),
        "hypothesis": "Avoiding the 4 MB payload slice reduces whole-program charged peak memory",
        "competing_explanation": "Interpreter/file-cache/accounting variability dominates this allocation",
        "primary_metric": "median cgroup memory.peak at maximum supported field-stream size",
        "workload": {"field_count": 500000, "decode_iterations": 16},
        "memory_budget_bytes": 67108864, "cpu_quota_usec": 100000, "cpu_period_usec": 100000,
        "exploration_blocks": 4, "confirmation_blocks": 4, "seed": 29,
        "minimum_peak_reduction_bytes": 2097152, "maximum_median_elapsed_regression_fraction": .15,
        "maximum_native_trials": 18, "native_experiment_seconds": 180,
        "input_policy": "owner-generated finite doubles, identical frozen bytes for both candidates",
        "output_policy": "owner-pinned SHA256 digest of decoded numerical bytes",
        "scope": "source capsule; no Git parent commit is available in this managed workspace"}
    (work / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    config = initialize(baseline, [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        protected_paths=["tests", "tools/dogfood-workload.py", "chilicrisp/schemas"])
    record, result = compare(config, candidate, work / "comparisons", trusted_local=True)
    integrity = verify(record)
    (work / "correctness.json").write_text(json.dumps({"record": str(record),
        "decision": result["decision"], "integrity": integrity}, indent=2), encoding="utf-8")
    print(json.dumps({"work": str(work), "decision": result["decision"],
                      "integrity_valid": integrity["valid"]}, indent=2))
    return 0 if result["decision"] == "public_tests_passed" and integrity["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Check self-test raw evidence independently of the benchmark's summary file."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chilicrisp.contracts import validate  # noqa: E402
from chilicrisp.runner import file_hash  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    plan = json.loads((args.evidence / "dogfood-plan.json").read_text())
    measurements = json.loads((args.evidence / "dogfood-measurements.json").read_text())
    if len(measurements) != plan["maximum_native_trials"]:
        raise ValueError("Declared complete experiment has missing trials")
    identifiers = set()
    for expected, measurement in zip(plan["schedule"], measurements):
        if list(expected) != [measurement["phase"], measurement["block"], measurement["variant"]]:
            raise ValueError("Recorded order differs from frozen schedule")
        result = measurement["result"]
        validate(result, "result")
        if result["trial_id"] in identifiers:
            raise ValueError("Duplicate trial ID")
        identifiers.add(result["trial_id"])
        manifest = copy.deepcopy(plan["manifests"][measurement["variant"]])
        if measurement["phase"] == "confirmation" and "heldout_confirmation" in plan:
            hidden = plan["heldout_confirmation"]
            manifest["workloads"][0].update(input=hidden["input"], input_hash=hidden["input_hash"],
                                           expected_stdout_hash=hidden["expected_stdout_hash"])
        expected_manifest_hash = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        if (result["outcome"] != "pass" or result["lifecycle"] != "FINALIZED"
                or result["manifest_hash"] != expected_manifest_hash
                or result["candidate_hash"] != manifest["target"]["rootfs_hash"]
                or result["effective_budget_bytes"] != plan["memory_budget_bytes"]
                or result["preflight_record"]["effective"]["cpu.max"] !=
                    f"{plan['cpu_quota_usec']} {plan['cpu_period_usec']}"):
            raise ValueError("Trial failed identity, correctness, lifecycle or enforcement checks")
        directory = args.evidence / "evidence" / result["trial_id"]
        if json.loads((directory / "result.json").read_text()) != result:
            raise ValueError("Raw result differs from recorded observation")
        for name, digest in result["artifact_hashes"].items():
            if file_hash(directory / name) != digest:
                raise ValueError(f"Artifact changed: {result['trial_id']}/{name}")
        if file_hash(directory / "stdout") != manifest["workloads"][0]["expected_stdout_hash"]:
            raise ValueError("Independent expected output digest did not match")
    report = {"valid": True, "verified_trials": len(identifiers),
              "checks": ["frozen randomized schedule", "trial and rootfs identities",
                         "raw artifact hashes", "independent expected output digest",
                         "finalized lifecycle", "effective memory and CPU limits"],
              "scope": "Evidence consistency; no independent sandbox certification or broad acceptance"}
    (args.evidence / "dogfood-audit.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

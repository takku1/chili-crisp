"""Owner-only audit of sealed fixture receipts, trial artifacts and matched conditions."""
import argparse
from collections import Counter
import json
from pathlib import Path

from chilicrisp.acceptance import private_path, verify_receipt
from chilicrisp.contracts import validate
from chilicrisp.development import identity
from chilicrisp.runner import file_hash, tree_hash


def audit(vault, sessions):
    vault = Path(vault).resolve()
    private_path(vault, vault, directory=True)
    results = []
    for session in sessions:
        state = json.loads((Path(session) / "state.json").read_text())
        receipt = state["acceptances"][-1]
        body = receipt["body"]
        expected = {**state["plan"]["acceptance"], "lineage_id": state["lineage_id"],
            "baseline_source_hash": state["champions"][0]["source_hash"],
            "candidate_source_hash": state["champions"][state["champion"]]["source_hash"]}
        verdict = verify_receipt(receipt, expected)
        policies = [p for p in vault.glob("*.json") if file_hash(p) == body["policy_sha256"]]
        if len(policies) != 1:
            raise ValueError("Missing or ambiguous sealed policy")
        policy = json.loads(policies[0].read_text())
        validate(policy, "acceptance-policy")
        manifest_path = policies[0].parent / policy["manifest"]
        if file_hash(manifest_path) != policy["manifest_sha256"]:
            raise ValueError("Sealed manifest changed")
        manifest = json.loads(manifest_path.read_text())
        reports = [p for p in vault.glob("attempt-*/report.json")
                   if json.loads(p.read_text()).get("receipt") == receipt]
        if len(reports) != 1:
            raise ValueError("Missing or ambiguous private report")
        path = reports[0]
        report = json.loads(path.read_text())
        if report["status"] != verdict or len(report["records"]) > policy["max_trials"]:
            raise ValueError("Private decision/cost differs")
        for variant in ("baseline", "candidate"):
            if identity(path.parent / variant) != body[variant + "_source_hash"]:
                raise ValueError("Frozen sealed source identity differs")
        outcomes = Counter()
        conditions = set()
        compiler_trials = 0
        known_trials = {item["result"]["trial_id"] for item in report["records"]}
        if "build" in policy:
            from chilicrisp.build import verify_cached
            compiler = policies[0].parent / policy["build"]["manifest"]
            if file_hash(compiler) != policy["build"]["manifest_sha256"]:
                raise ValueError("Sealed compiler manifest differs")
            for cache in (path.parent / "build-cache").iterdir():
                record = json.loads((cache / "build-record.json").read_text())
                source = next(path.parent / name for name in ("baseline", "candidate")
                              if tree_hash(path.parent / name) == record["source_tree_hash"])
                verify_cached(source, compiler, cache, policy["build"]["memory_budget"])
                compiler_trials += len(record["trials"])
                known_trials.update(record["trials"])
        for item in report["records"]:
            record = item["result"]
            validate(record, "result")
            trial = path.parent / "evidence" / record["trial_id"]
            if json.loads((trial / "result.json").read_text()) != record:
                raise ValueError("Report differs from raw trial")
            if json.loads((trial / "lifecycle.json").read_text())["state"] != "FINALIZED":
                raise ValueError("Unfinished sealed trial")
            for name, digest in record["artifact_hashes"].items():
                if Path(name).name != name or file_hash(trial / name) != digest:
                    raise ValueError("Sealed artifact differs")
            effective = record["preflight_record"]["effective"]
            if (record["requested_budget_bytes"] != policy["transfer_budget"]
                    or record["effective_budget_bytes"] != policy["transfer_budget"]
                    or int(effective["memory.max"]) != policy["transfer_budget"]):
                raise ValueError("Transfer memory conditions differ")
            conditions.add((effective.get("cpu.max"), record["preflight_record"]["bwrap_hash"],
                            record["preflight_record"]["cache_policy"]))
            workload = next(w for w in manifest["workloads"] if w["id"] == record["workload_id"])
            if "expected_stdout_hash" in workload and record["outcome"] == "pass":
                if file_hash(trial / "stdout") != workload["expected_stdout_hash"]:
                    raise ValueError("Passing sealed stdout differs from oracle")
            outcomes[record["outcome"]] += 1
        if len(conditions) != 1:
            raise ValueError("Execution policies differ between variants")
        actual_trials = {p.parent.name for p in (path.parent / "evidence").glob("*/result.json")}
        if actual_trials != known_trials or len(actual_trials) > policy["max_trials"]:
            raise ValueError("Compiler/runtime trial accounting differs")
        results.append({"verdict": verdict, "trials": len(actual_trials), "runtime_trials": len(report["records"]),
                        "compiler_trials": compiler_trials, "runtime_outcomes": dict(outcomes),
                        "medians": report.get("medians"), "transfer_budget": policy["transfer_budget"]})
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path)
    parser.add_argument("--session", type=Path, action="append", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.vault, args.session), indent=2))

"""Owner-operated sealed grading and signed, source-bound public receipts.

The vault must belong to a grader account inaccessible to the proposing agent.
This module does not isolate a host agent or create that account boundary.
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import time

from . import evaluation
from .contracts import validate
from .runner import file_hash

DOMAIN = b"chilicrisp.sealed-receipt.v1\0"


def _crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    except ImportError as error:
        raise ValueError("Install Chili Crisp's acceptance extra for signed grading") from error
    return Ed25519PrivateKey, Ed25519PublicKey


def canonical(value):
    return DOMAIN + json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def implementation():
    from . import runner, seccomp, capture, lifecycle, cpu, fields, oracles, development, project, contracts, build
    values = {"acceptance": file_hash(__file__), "evaluation": file_hash(evaluation.__file__),
              "cryptography": importlib.metadata.version("cryptography")}
    for module in (runner, seccomp, capture, lifecycle, cpu, fields, oracles, development, project, contracts, build):
        values[module.__name__] = file_hash(module.__file__)
    return hashlib.sha256(canonical(values)).hexdigest()


def sign(body, private_key):
    receipt = {"body": body, "signature": private_key.sign(canonical(body)).hex()}
    validate(receipt, "acceptance-receipt")
    return receipt


def verify_receipt(receipt, expected):
    validate(receipt, "acceptance-receipt")
    _, public = _crypto()
    from cryptography.exceptions import InvalidSignature
    try:
        public.from_public_bytes(bytes.fromhex(expected["public_key"])).verify(
            bytes.fromhex(receipt["signature"]), canonical(receipt["body"]))
    except (InvalidSignature, ValueError) as error:
        raise ValueError("Invalid acceptance signature") from error
    for key in ("campaign", "lineage_id", "baseline_source_hash", "candidate_source_hash", "policy_sha256", "evaluator_sha256"):
        if receipt["body"][key] != expected[key]:
            raise ValueError("Acceptance receipt binding mismatch: " + key)
    return receipt["body"]["verdict"]


def private_path(path, vault, *, directory=False):
    original = Path(path)
    path = original.resolve()
    if original.is_symlink() or not path.is_relative_to(vault):
        raise ValueError("Grading assets must remain inside the private vault")
    metadata = path.stat()
    if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077:
        raise ValueError("Grading assets require owner-only permissions")
    if directory and not path.is_dir():
        raise ValueError("Grading vault must be a directory")
    return path


def grade(request, policy_path, key_path, vault):
    """Consume one campaign/lineage attempt; return no hidden diagnostics publicly."""
    from .development import identity
    from .project import snapshot
    if sys.platform != "linux":
        raise ValueError("Owner sealed grading requires Linux and a private grader account")
    expected = request["expected"]
    required = {"campaign", "lineage_id", "baseline_source_hash", "candidate_source_hash", "policy_sha256", "evaluator_sha256", "public_key"}
    if set(expected) != required or request.get("kind") != "sealed_acceptance_request":
        raise ValueError("Invalid sealed acceptance request")
    body = {name: value for name, value in expected.items() if name != "public_key"}
    validate({"body": {**body, "schema_version": "0.1", "verdict": "passed"}, "signature": "0"*128}, "acceptance-receipt")
    if not isinstance(expected["public_key"], str) or len(bytes.fromhex(expected["public_key"])) != 32:
        raise ValueError("Invalid acceptance public key")
    vault = Path(vault).resolve()
    private_path(vault, vault, directory=True)
    policy_path = private_path(policy_path, vault)
    key_path = private_path(key_path, vault)
    if policy_path.stat().st_size > 1048576 or key_path.stat().st_size != 32:
        raise ValueError("Invalid policy/key size")
    policy = json.loads(policy_path.read_text())
    validate(policy, "acceptance-policy")
    if (file_hash(policy_path) != expected["policy_sha256"] or policy["campaign"] != expected["campaign"]
            or implementation() != expected["evaluator_sha256"]):
        raise ValueError("Acceptance policy or evaluator differs from the pinned request")
    for name in ("wall_seconds", "maximum_latency_regression", "minimum_memory_improvement"):
        if not math.isfinite(policy[name]):
            raise ValueError("Acceptance policy values must be finite")
    private, _ = _crypto()
    key = private.from_private_bytes(key_path.read_bytes())
    if key.public_key().public_bytes_raw().hex() != expected["public_key"]:
        raise ValueError("Acceptance signing key differs from the pinned public key")
    manifest_path = private_path(Path(policy_path).parent / policy["manifest"], vault)
    if file_hash(manifest_path) != policy["manifest_sha256"]:
        raise ValueError("Sealed manifest identity mismatch")
    plan = {"evaluation": {"backend": "linux_cgroup", "manifest": str(manifest_path),
                           "benchmark_workload": policy["benchmark_workload"]}}
    manifest = evaluation.manifest(plan)
    if policy["transfer_budget"] % manifest["search"]["page_size"]:
        raise ValueError("Transfer budget must be page aligned")
    runtime = Path(manifest["target"]["rootfs"]).resolve()
    if vault.is_relative_to(runtime):
        raise ValueError("Sealed assets cannot be inside the candidate runtime")
    if "build" in policy:
        from .build import load_policy
        compiler_path = private_path(policy_path.parent / policy["build"]["manifest"], vault)
        if file_hash(compiler_path) != policy["build"]["manifest_sha256"]:
            raise ValueError("Sealed compiler manifest identity mismatch")
        compiler, _ = load_policy(compiler_path)
        compiler_root = Path(compiler["target"]["rootfs"]).resolve()
        if vault.is_relative_to(compiler_root):
            raise ValueError("Sealed assets cannot be inside the compiler runtime")
        if compiler_root.is_relative_to(runtime) or runtime.is_relative_to(compiler_root):
            raise ValueError("Sealed compiler and program runtime must be separate")
        if policy["build"]["memory_budget"] % compiler["search"]["page_size"]:
            raise ValueError("Sealed compiler budget must be page aligned")
        plan["evaluation"]["build"] = {"manifest": str(compiler_path), "memory_budget": policy["build"]["memory_budget"]}
    for item in manifest["workloads"]:
        private_path(item["input"], vault)
        if "oracle" in item:
            oracle = private_path(item["oracle"]["policy_path"], vault)
            data = json.loads(oracle.read_text())
            if "reference_path" in data:
                private_path(data["reference_path"], vault)
    pinned = evaluation.identities(plan)
    required = 2 * len(manifest["workloads"]) + 2 + 2 * policy["repetitions"] + evaluation.build_reservation(plan)
    if required > policy["max_trials"]:
        raise ValueError("Acceptance trial reservation exceeds policy")
    # The vault is the shared registry: changing output paths cannot buy retries.
    claim = hashlib.sha256(canonical({"campaign": policy["campaign"]})).hexdigest()
    work = vault / ("attempt-" + claim)
    work.mkdir(mode=0o700, exist_ok=False)
    os.chmod(work, 0o700)
    report = {"status": "running", "reserved_trials": required, "records": []}
    report_path = work / "report.json"
    started = time.monotonic()
    deadline = started + policy["wall_seconds"]

    def save():
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False))
        report_path.chmod(0o600)

    save()
    try:
        sources = {}
        for name in ("baseline", "candidate"):
            source = Path(request[name + "_source"]).resolve()
            if source.is_relative_to(vault) or vault.is_relative_to(source):
                raise ValueError("Source and private grading vault must be separate")
            sources[name] = work / name
            if snapshot(source, sources[name]) != expected[name + "_source_hash"]:
                raise ValueError("Acceptance source differs from the frozen request")
        eligible = True

        def trial(name, workload, phase):
            if len(report["records"]) >= policy["max_trials"]:
                raise ValueError("Acceptance trial budget exhausted")
            result = evaluation.trial(plan, sources[name], work / "evidence", policy["transfer_budget"], deadline,
                                      workload, evidence_root=work / "evidence")
            report["records"].append({"variant": name, "phase": phase, "result": result})
            save()
            return result

        for workload in manifest["workloads"]:
            for name in ("baseline", "candidate"):
                result = trial(name, workload["id"], "sealed_correctness")
                if result["outcome"] != "pass":
                    if name == "baseline":
                        raise ValueError("Owner reference baseline failed sealed correctness")
                    eligible = False
                    break
            if not eligible:
                break
        if eligible:
            for name in ("baseline", "candidate"):
                if trial(name, policy["benchmark_workload"], "warmup")["outcome"] != "pass":
                    if name == "baseline":
                        raise ValueError("Owner reference baseline failed transfer warmup")
                    eligible = False
        if eligible:
            randomizer = random.Random(policy["seed"])
            for block in range(policy["repetitions"]):
                order = ["baseline", "candidate"]
                randomizer.shuffle(order)
                for name in order:
                    result = trial(name, policy["benchmark_workload"], "transfer")
                    report["records"][-1]["block"] = block
                    if result["outcome"] != "pass":
                        if name == "baseline":
                            raise ValueError("Owner reference baseline failed transfer")
                        eligible = False
                        break
                if not eligible:
                    break
        if eligible:
            medians = {}
            for name in ("baseline", "candidate"):
                records = [r["result"] for r in report["records"] if r["variant"] == name and r["phase"] == "transfer"]
                medians[name] = {metric: statistics.median(r["metrics"][metric]["value"] for r in records)
                                 for metric in ("memory_peak", "elapsed")}
            if any(not math.isfinite(value) or value <= 0 for values in medians.values() for value in values.values()):
                raise ValueError("Transfer metric unavailable or invalid")
            report["medians"] = medians
            eligible = (eligible and medians["candidate"]["memory_peak"] <= medians["baseline"]["memory_peak"] * (1-policy["minimum_memory_improvement"])
                and medians["candidate"]["elapsed"] <= medians["baseline"]["elapsed"] * (1+policy["maximum_latency_regression"]))
        for name, source in sources.items():
            if identity(source) != expected[name + "_source_hash"]:
                raise ValueError("Sealed source changed during evaluation")
        if evaluation.identities(plan) != pinned or file_hash(policy_path) != expected["policy_sha256"]:
            raise ValueError("Sealed evaluator assets changed during evaluation")
        evaluation.ensure_clean(work / "evidence")
        executed_trials = len(list((work / "evidence").glob("*/result.json")))
        if executed_trials > policy["max_trials"]:
            raise ValueError("Sealed build/run trial budget exceeded")
        report["executed_trials"] = executed_trials
        body = {name: expected[name] for name in ("campaign", "lineage_id", "baseline_source_hash", "candidate_source_hash", "policy_sha256", "evaluator_sha256")}
        body.update(schema_version="0.1", verdict="passed" if eligible else "rejected")
        receipt = sign(body, key)
        report.update(status=body["verdict"], elapsed_seconds=time.monotonic()-started, receipt=receipt,
            transfer_conditions=f"same runtime, workload, CPU policy and memory.max={policy['transfer_budget']}; shared-host constraints remain")
        save()
        return receipt
    except BaseException as error:
        report.update(status="interrupted", error=f"{type(error).__name__}: {error}")
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("identity")
    grading = actions.add_parser("grade")
    for name in ("request", "policy", "key", "vault", "receipt"):
        grading.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.action == "identity":
        print(json.dumps({"evaluator_sha256": implementation()}))
    else:
        if args.receipt.exists():
            raise ValueError("Receipt destination already exists")
        if args.request.stat().st_size > 32768:
            raise ValueError("Acceptance request exceeds 32 KiB")
        request = json.loads(args.request.read_text())
        # Exported requests name their sources relative to the request file.
        for name in ("baseline_source", "candidate_source"):
            if isinstance(request.get(name), str):
                request[name] = str((args.request.parent / request[name]).resolve())
        receipt = grade(request, args.policy, args.key, args.vault)
        with args.receipt.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2)
        print(json.dumps({"verdict": receipt["body"]["verdict"]}))


if __name__ == "__main__":
    main()

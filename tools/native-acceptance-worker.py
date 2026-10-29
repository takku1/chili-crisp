"""Owner-operated fixture: sealed rejection, signed import and identical transfer."""
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import uuid

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB / "source"))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from chilicrisp import acceptance, development as dev  # noqa: E402
from chilicrisp.project import initialize  # noqa: E402
from chilicrisp.runner import file_hash, tree_hash  # noqa: E402


def write_private(path, data):
    path.write_text(data)
    path.chmod(0o600)


def main():
    relative = next(line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines() if line.startswith("0::"))
    service = Path("/sys/fs/cgroup") / relative.lstrip("/")
    (service / "manager").mkdir()
    (service / "manager/cgroup.procs").write_text(str(os.getpid()))
    (service / "cgroup.subtree_control").write_text("+memory +pids +cpu")
    parent = service / "experiments"
    parent.mkdir()
    (parent / "cgroup.subtree_control").write_text("+memory +pids +cpu")
    manifest = json.loads((LAB / "source/examples/experiment.json").read_text())
    manifest["target"].update(rootfs=str(LAB / "rootfs"), rootfs_hash=tree_hash(LAB / "rootfs"),
        command=["/usr/bin/python3", "-I", "-B", "/fixtures/acceptance.py"], build_identity="owner-frozen acceptance fixture")
    manifest["isolation"].update(cgroup_parent=str(parent), cpu={"quota_usec": 100000, "period_usec": 100000})
    manifest["limits"]["timeout_seconds"] = 10
    public_input = LAB / "public-input"
    public_input.write_text("67108864\n")
    manifest["workloads"][0].update(input=str(public_input), input_hash=file_hash(public_input), arguments=[],
        expected_stdout_hash=hashlib.sha256(b"67108864\n").hexdigest())
    public_manifest = LAB / "public-manifest.json"
    public_manifest.write_text(json.dumps(manifest, indent=2))
    vault = LAB / "private-acceptance-vault"
    vault.mkdir(mode=0o700)
    vault.chmod(0o700)
    key = Ed25519PrivateKey.generate()
    key_path = vault / "signing-key"
    key_path.write_bytes(key.private_bytes_raw())
    key_path.chmod(0o600)
    hidden = vault / "heldout-input"
    n = 32*1024*1024 + secrets.randbelow(1000000) + 1
    write_private(hidden, str(n) + "\n")
    sealed = copy.deepcopy(manifest)
    sealed["workloads"][0].update(input=str(hidden), input_hash=file_hash(hidden),
        expected_stdout_hash=hashlib.sha256((str(n)+"\n").encode()).hexdigest())
    sealed_path = vault / "manifest.json"
    write_private(sealed_path, json.dumps(sealed, indent=2))
    baseline = LAB / "baseline"
    baseline.mkdir()
    (baseline / "program.py").write_text("def compute(n):\n    return sum(b'\\x01' * n)\n")
    (baseline / "contract.txt").write_text("Compute the exact sum of n bytes of value one.\n")
    config = initialize(baseline, ["NEVER_RUN_HOST_TESTS"], protected_paths=["contract.txt"])
    research = LAB / "research.json"
    research.write_text(json.dumps({"hypothesis": "Bounded chunks reduce memory", "mechanism": "Incremental exact sum",
        "falsification": "Wrong output or failure to survive", "sources": [{"reference": "owner:fixture", "supports": "Scripted positive and overfitting controls"}]}))
    outcomes = {}
    for name in ("good", "overfit"):
        policy = {"schema_version": "0.1", "campaign": "fixture-" + name, "manifest": str(sealed_path),
            "manifest_sha256": file_hash(sealed_path), "benchmark_workload": "correct", "repetitions": 3,
            "transfer_budget": 256*1024*1024,
            "seed": 71, "wall_seconds": 120, "max_trials": 10,
            "maximum_latency_regression": 1.0, "minimum_memory_improvement": .1}
        policy_path = vault / (name + "-policy.json")
        write_private(policy_path, json.dumps(policy, indent=2))
        plan = {"schema_version": "0.1", "concept": "Exact incremental byte sum", "project_config": str(config),
            "benchmark_command": ["NEVER_RUN_HOST_BENCHMARK"], "objective": "enforced_budget_bytes",
            "evaluation": {"backend": "linux_cgroup", "manifest": str(public_manifest), "benchmark_workload": "correct", "initial_budget": 96*1024*1024},
            "acceptance": {"campaign": policy["campaign"], "public_key": key.public_key().public_bytes_raw().hex(),
                "policy_sha256": file_hash(policy_path), "evaluator_sha256": acceptance.implementation()},
            "quantum": 4096, "minimum_target": 8*1024*1024, "reductions": [.5], "regression_limits": {},
            "repetitions": 2, "confirmation_repetitions": 2, "max_generations": 1, "wall_seconds": 180}
        plan_path = LAB / (name + "-plan.json")
        plan_path.write_text(json.dumps(plan, indent=2))
        candidate = LAB / (name + "-candidate")
        candidate.mkdir()
        (candidate / "contract.txt").write_bytes((baseline / "contract.txt").read_bytes())
        good = '''def compute(n):
    block = b"\\x01" * min(n, 1048576)
    count, remainder = divmod(n, len(block))
    return count * sum(block) + sum(block[:remainder])
'''
        (candidate / "program.py").write_text(good if name == "good" else "def compute(n):\n    return 67108864\n")
        session = LAB / ("acceptance-session-" + name)
        dev.create(plan_path, session)
        state = dev.submit(session, candidate, research)
        assert state["generations"][-1]["decision"] == "accepted_experimental", state["generations"][-1]
        request = dev.acceptance_request(session)
        assert "heldout-input" not in json.dumps(request) and key.private_bytes_raw().hex() not in json.dumps(request)
        receipt = acceptance.grade(request, policy_path, key_path, vault)
        expected = "passed" if name == "good" else "rejected"
        assert receipt["body"]["verdict"] == expected, receipt
        receipt_path = LAB / (name + "-receipt.json")
        receipt_path.write_text(json.dumps(receipt, indent=2))
        state = dev.accept(session, receipt_path)
        assert state["champions"][state["champion"]]["verification"]["production"] == "not_accepted"
        assert state["stop_reason"] == "final_acceptance_" + expected
        # Changing lineage must not buy a second query of the same sealed campaign.
        retry = copy.deepcopy(request)
        retry["expected"]["lineage_id"] = uuid.uuid4().hex
        try:
            acceptance.grade(retry, policy_path, key_path, vault)
            raise AssertionError("Sealed campaign retry was allowed")
        except FileExistsError:
            pass
        outcomes[name] = expected
    leaks = sorted(path.name for path in parent.glob("chili-*") if path.is_dir())
    assert not leaks, leaks
    summary = {"status": "passed", "sealed_controls": outcomes, "campaign_retry": "blocked across lineages",
        "production": "not_accepted", "remaining_cgroups": leaks,
        "scope": "owner-operated signed gate fixture; no real-model study or isolated compilation"}
    (LAB / "native-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

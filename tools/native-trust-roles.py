"""Role phases for the separate-account trust fixture. Each runs as one account only.

owner-setup  root (owner): write the controller plan and private vault, pin identities
probe        any account: attempt reads/writes outside its role; report outcomes
propose      chili-agent: write a candidate source
develop      chili-runner (delegated unit): baseline, candidate, export request
grade        chili-grader (delegated unit): sealed correctness and matched transfer
forge        chili-agent: sign a passing verdict for the public request with its own key
accept       chili-runner: reject the forged receipt, import the genuine one, publish state
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

LAB = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(LAB / "source"))
from chilicrisp.runner import file_hash, tree_hash  # noqa: E402

PROGRAM = '''#include <stdio.h>
#include <stdlib.h>
#define CHUNK (64*1024*1024)
int main(void) {
    unsigned long long n, total = 0;
    if (scanf("%llu", &n) != 1) return 1;
    if (!n) { puts("0"); return 0; }
    size_t chunk = n < CHUNK ? n : CHUNK;
    volatile unsigned char *p = malloc(chunk);
    if (!p) return 2;
    for (size_t i = 0; i < chunk; i++) p[i] = 1;
    for (unsigned long long i = 0; i < n; i++) total += p[i % chunk];
    free((void*)p);
    printf("%llu\\n", total);
    return 0;
}
'''
BUILD_BUDGET = 536870912


def write_source(path, program):
    path.mkdir()
    (path / "program.c").write_text(program)
    (path / "contract.txt").write_text("Exact sum of n bytes of value one.\n")


def manifests(directory, cgroup_parent, public_input, expected):
    """Write runtime and compiler manifests whose trials run under one account's delegated cgroup."""
    template = json.loads((LAB / "source/examples/experiment.json").read_text())
    template["isolation"].update(cgroup_parent=cgroup_parent, cpu={"quota_usec": 100000, "period_usec": 100000})
    artifact_policy = directory / "artifact-policy.json"
    artifact_policy.write_text(json.dumps({"schema_version": "0.1", "format": "elf64-lsb-x86_64", "maximum_bytes": 1048576}))
    compiler = copy.deepcopy(template)
    compiler["target"].update(rootfs=str(LAB / "compiler-rootfs"), rootfs_hash=tree_hash(LAB / "compiler-rootfs"),
        command=["/usr/bin/python3", "-I", "-B", "/fixtures/compile.py"], build_identity=(LAB / "toolchain-version.txt").read_text())
    compiler["workloads"][0].update(input=str(LAB / "empty-input"), arguments=["compile"], oracle={
        "kind": "build_elf_v1", "policy_path": str(artifact_policy), "policy_hash": file_hash(artifact_policy)})
    compiler["workloads"][0].pop("expected_stdout_hash")
    compiler["isolation"].update(seccomp="pilot_build_v1", scratch_bytes=67108864)
    compiler["limits"].update(timeout_seconds=15, output_bytes_per_stream=1048576)
    runtime = copy.deepcopy(template)
    runtime["target"].update(rootfs=str(LAB / "rootfs"), rootfs_hash=tree_hash(LAB / "rootfs"),
        command=["/usr/bin/python3", "-I", "-B", "/fixtures/run-compiled.py"])
    runtime["workloads"][0].update(arguments=[], input=str(public_input), input_hash=file_hash(public_input),
        expected_stdout_hash=hashlib.sha256(expected).hexdigest())
    (directory / "compiler.json").write_text(json.dumps(compiler, indent=2))
    (directory / "runtime.json").write_text(json.dumps(runtime, indent=2))


def owner_setup(runner_parent, grader_parent):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from chilicrisp import acceptance
    from chilicrisp.project import initialize
    controller, vault = LAB / "controller", LAB / "vault"
    public_input = controller / "input"
    public_input.write_text("67108864\n")
    manifests(controller, runner_parent, public_input, b"67108864\n")
    hidden_input = vault / "input"
    hidden_input.write_text("34567891\n")
    manifests(vault, grader_parent, hidden_input, b"34567891\n")
    key = Ed25519PrivateKey.generate()
    (vault / "key").write_bytes(key.private_bytes_raw())
    (vault / "policy.json").write_text(json.dumps({"schema_version": "0.1", "campaign": "trust-fixture-" + LAB.name,
        "manifest": "runtime.json", "manifest_sha256": file_hash(vault / "runtime.json"),
        "build": {"manifest": "compiler.json", "manifest_sha256": file_hash(vault / "compiler.json"), "memory_budget": BUILD_BUDGET},
        "benchmark_workload": "correct", "transfer_budget": 268435456, "repetitions": 3, "seed": 23,
        "wall_seconds": 600, "max_trials": 14, "maximum_latency_regression": 1.0, "minimum_memory_improvement": .1}, indent=2))
    baseline = controller / "baseline"
    write_source(baseline, PROGRAM)
    config = initialize(baseline, ["NEVER_EXECUTE_HOST_TESTS"], protected_paths=["contract.txt"])
    plan = {"schema_version": "0.1", "concept": "Compiled byte sum with bounded live storage",
        "project_config": str(config), "benchmark_command": ["NEVER_EXECUTE_HOST_BENCHMARK"], "objective": "enforced_budget_bytes",
        "evaluation": {"backend": "linux_cgroup", "manifest": str(controller / "runtime.json"), "benchmark_workload": "correct",
            "initial_budget": 100663296, "build": {"manifest": str(controller / "compiler.json"), "memory_budget": BUILD_BUDGET}},
        "acceptance": {"campaign": "trust-fixture-" + LAB.name, "public_key": key.public_key().public_bytes_raw().hex(),
            "policy_sha256": file_hash(vault / "policy.json"), "evaluator_sha256": acceptance.implementation()},
        "quantum": 4096, "minimum_target": 8388608, "reductions": [.5], "repetitions": 2,
        "confirmation_repetitions": 2, "regression_limits": {}, "max_generations": 1, "wall_seconds": 900}
    (controller / "plan.json").write_text(json.dumps(plan, indent=2))
    (controller / "research.json").write_text(json.dumps({"hypothesis": "Smaller live chunks reduce memory",
        "mechanism": "Bounded storage", "falsification": "Wrong sum or OOM",
        "sources": [{"reference": "owner:trust-fixture", "supports": "Scripted C source variants"}]}))


def probe():
    """Report, for each attempt outside this account's role, whether the OS refused it."""
    reads = ["vault/key", "vault/input", "vault/policy.json", "controller/plan.json", "controller/session/state.json"]
    writes = ["source/chilicrisp/acceptance.py", "controller/session/state.json", "controller/plan.json",
              "exchange/request/request.json", "receipts/receipt.json", "vault/policy.json", "compiler-rootfs/fixtures/compile.py"]
    outcome = {}
    for name in reads:
        try:
            (LAB / name).read_bytes()
            outcome["read " + name] = "allowed"
        except PermissionError:
            outcome["read " + name] = "denied"
        except FileNotFoundError:
            outcome["read " + name] = "absent"
    for name in writes:
        try:
            with (LAB / name).open("ab"):
                pass
            outcome["write " + name] = "allowed"
        except PermissionError:
            outcome["write " + name] = "denied"
        except FileNotFoundError:
            outcome["write " + name] = "absent"
    return outcome


def propose():
    write_source(LAB / "agent/outbox", PROGRAM.replace("64*1024*1024", "8*1024*1024"))
    return {"candidate": "agent/outbox"}


def forge():
    """After the request is public, the agent signs a passing verdict with a key it controls."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from chilicrisp import acceptance
    expected = json.loads((LAB / "exchange/request/request.json").read_text())["expected"]
    body = {name: expected[name] for name in ("campaign", "lineage_id", "baseline_source_hash",
        "candidate_source_hash", "policy_sha256", "evaluator_sha256")}
    body.update(schema_version="0.1", verdict="passed")
    (LAB / "agent/forged-receipt.json").write_text(json.dumps(acceptance.sign(body, Ed25519PrivateKey.generate())))
    return {"forged": "agent/forged-receipt.json"}


def delegate(expected):
    relative = next(line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines() if line.startswith("0::"))
    service = Path("/sys/fs/cgroup") / relative.lstrip("/")
    (service / "manager").mkdir()
    (service / "manager/cgroup.procs").write_text(str(os.getpid()))
    (service / "cgroup.subtree_control").write_text("+memory +pids +cpu")
    parent = service / "experiments"
    parent.mkdir()
    (parent / "cgroup.subtree_control").write_text("+memory +pids +cpu")
    if str(parent) != expected:
        raise RuntimeError("Delegated cgroup differs from the pinned manifest parent")
    return parent


def develop():
    from chilicrisp import development as dev
    parent = delegate(json.loads((LAB / "controller/runtime.json").read_text())["isolation"]["cgroup_parent"])
    session = LAB / "controller/session"
    dev.create(LAB / "controller/plan.json", session)
    state = dev.submit(session, LAB / "agent/outbox", LAB / "controller/research.json")
    decision = state["generations"][-1]["decision"]
    if decision != "accepted_experimental":
        raise RuntimeError("Candidate was not retained: " + decision)
    dev.export_acceptance_request(session, LAB / "exchange/request")
    leaks = sorted(path.name for path in parent.glob("chili-*") if path.is_dir())
    return {"decision": decision, "generations": len(state["generations"]), "remaining_cgroups": leaks}


def grade():
    import subprocess
    parent = delegate(json.loads((LAB / "vault/runtime.json").read_text())["isolation"]["cgroup_parent"])
    vault = LAB / "vault"
    completed = subprocess.run([sys.executable, "-m", "chilicrisp.acceptance", "grade",
        "--request", str(LAB / "exchange/request/request.json"), "--policy", str(vault / "policy.json"),
        "--key", str(vault / "key"), "--vault", str(vault), "--receipt", str(LAB / "receipts/receipt.json")],
        cwd=LAB / "source", capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr[-2000:])
    leaks = sorted(path.name for path in parent.glob("chili-*") if path.is_dir())
    return {**json.loads(completed.stdout), "remaining_cgroups": leaks}


def accept():
    from chilicrisp import development as dev
    session = LAB / "controller/session"
    before = (session / "state.json").read_bytes()
    try:
        dev.accept(session, LAB / "agent/forged-receipt.json")
        forged = "imported"
    except ValueError as error:
        forged = "rejected: " + str(error)
    if (session / "state.json").read_bytes() != before:
        raise RuntimeError("Forged receipt changed controller state")
    state = dev.accept(session, LAB / "receipts/receipt.json")
    # Publish the imported state so the grader can audit without controller access.
    (LAB / "exchange/accepted").mkdir()
    (LAB / "exchange/accepted/state.json").write_bytes((session / "state.json").read_bytes())
    return {"forged_receipt": forged, "genuine_receipt": state["acceptances"][-1]["body"]["verdict"],
            "acceptance_state": state["champions"][state["champion"]]["acceptance_state"],
            "production": state["champions"][state["champion"]]["verification"]["production"]}


if __name__ == "__main__":
    phase = sys.argv[1]
    if phase == "owner-setup":
        result = owner_setup(sys.argv[3], sys.argv[4])
    else:
        result = {"probe": probe, "propose": propose, "forge": forge, "develop": develop,
                  "grade": grade, "accept": accept}[phase]()
    print(json.dumps(result, indent=2))

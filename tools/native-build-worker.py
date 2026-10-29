"""Unprivileged native compiler/export/run positive and negative controls."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB / "source"))
from chilicrisp.build import compile_candidate  # noqa: E402
from chilicrisp.runner import file_hash, run_trial, tree_hash  # noqa: E402
from chilicrisp import development as dev, acceptance  # noqa: E402
from chilicrisp.project import initialize  # noqa: E402


def main():
    relative = next(line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines() if line.startswith("0::"))
    service = Path("/sys/fs/cgroup") / relative.lstrip("/")
    (service / "manager").mkdir()
    (service / "manager/cgroup.procs").write_text(str(os.getpid()))
    (service / "cgroup.subtree_control").write_text("+memory +pids +cpu")
    parent = service / "experiments"
    parent.mkdir()
    (parent / "cgroup.subtree_control").write_text("+memory +pids +cpu")
    private_include = LAB / "host-private-includes"
    private_include.mkdir()
    (private_include / "secret.h").write_text("#define HOST_PRIVATE_MARKER 12345\n")
    os.environ.update(CHILI_BUILD_SECRET="not-mounted", CPATH=str(private_include))
    policy_path = LAB / "artifact-policy.json"
    policy_path.write_text(json.dumps({"schema_version": "0.1", "format": "elf64-lsb-x86_64", "maximum_bytes": 1048576}))
    manifest = json.loads((LAB / "source/examples/experiment.json").read_text())
    manifest["target"].update(rootfs=str(LAB / "compiler-rootfs"), rootfs_hash=tree_hash(LAB / "compiler-rootfs"),
        command=["/usr/bin/python3", "-I", "-B", "/fixtures/compile.py"], build_identity=(LAB / "toolchain-version.txt").read_text())
    workload = manifest["workloads"][0]
    workload.update(input=str(LAB / "empty-input"), arguments=["compile"], oracle={"kind": "build_elf_v1", "policy_path": str(policy_path), "policy_hash": file_hash(policy_path)})
    workload.pop("expected_stdout_hash")
    manifest["isolation"].update(cgroup_parent=str(parent), seccomp="pilot_build_v1", scratch_bytes=67108864,
        cpu={"quota_usec": 100000, "period_usec": 100000})
    manifest["limits"].update(timeout_seconds=15, output_bytes_per_stream=1048576)
    work = LAB / "build-validation"
    work.mkdir()
    good = LAB / "good-c-source"
    good.mkdir()
    (good / "program.c").write_text('''#include <stdio.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
int main(void) {
    if (fork() != -1 || errno != EPERM) return 1;
    if (socket(AF_INET, SOCK_STREAM, 0) != -1 || errno != EPERM) return 2;
    puts("ok"); return 0;
}
''')
    results = []
    for mode in ("compile", "background", "nondeterministic", "timeout", "flood", "oom"):
        selected = copy.deepcopy(manifest)
        selected["workloads"][0]["arguments"] = [mode]
        if mode == "timeout":
            selected["limits"]["timeout_seconds"] = .5
        path = work / (mode + "-manifest.json")
        path.write_text(json.dumps(selected, indent=2))
        try:
            record = compile_candidate(good, path, work / mode, 536870912, time.monotonic()+60,
                                       evidence_root=work / "evidence")
            outcome = record["status"]
        except ValueError:
            record = json.loads((work / mode / "build-record.json").read_text())
            outcome = record["status"]
        expected = "retained" if mode in ("compile", "background") else "rejected"
        results.append({"mode": mode, "outcome": outcome})
        assert outcome == expected, record
    for name, code in (("invalid", "not valid C"), ("host-include", f'#include "{private_include}/secret.h"\nint main(void){{return 0;}}')):
        source = LAB / name
        source.mkdir()
        (source / "program.c").write_text(code)
        path = work / "compile-manifest.json"
        try:
            compile_candidate(source, path, work / name, 536870912, time.monotonic()+30, evidence_root=work / "evidence")
            raise AssertionError("Invalid/host-dependent source retained")
        except ValueError:
            results.append({"mode": name, "outcome": "rejected"})
    runtime = copy.deepcopy(manifest)
    runtime["target"].update(rootfs=str(LAB / "rootfs"), rootfs_hash=tree_hash(LAB / "rootfs"),
        command=["/usr/bin/python3", "-I", "-B", "/fixtures/run-compiled.py"],
        source_mount={"path": str(work / "compile/artifacts"), "tree_hash": tree_hash(work / "compile/artifacts")})
    runtime["isolation"]["seccomp"] = "pilot_allowlist_v1"
    runtime["workloads"][0].pop("oracle")
    runtime["workloads"][0].update(arguments=[], expected_stdout_hash=hashlib.sha256(b"ok\n").hexdigest())
    runtime["evidence_directory"] = str(work / "evidence")
    executed = run_trial(runtime, "correct", 67108864)
    assert executed["outcome"] == "pass", executed
    # The controller and final gate must compile C source through the same worker.
    vault = LAB / "compiled-grader-vault"
    vault.mkdir(mode=0o700)
    vault.chmod(0o700)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key = Ed25519PrivateKey.generate()
    key_path = vault / "key"
    key_path.write_bytes(key.private_bytes_raw())
    key_path.chmod(0o600)
    public_input = LAB / "compiled-input"
    public_input.write_text("67108864\n")
    runtime["target"].pop("source_mount")
    runtime["workloads"][0].update(input=str(public_input), input_hash=file_hash(public_input),
        expected_stdout_hash=hashlib.sha256(b"67108864\n").hexdigest())
    runtime_manifest = work / "runtime-manifest.json"
    runtime_manifest.write_text(json.dumps(runtime, indent=2))
    hidden_input = vault / "input"
    hidden_input.write_text("34567891\n")
    hidden_input.chmod(0o600)
    sealed_runtime = copy.deepcopy(runtime)
    sealed_runtime["workloads"][0].update(input=str(hidden_input), input_hash=file_hash(hidden_input),
        expected_stdout_hash=hashlib.sha256(b"34567891\n").hexdigest())
    sealed_manifest = vault / "runtime.json"
    sealed_manifest.write_text(json.dumps(sealed_runtime, indent=2))
    sealed_manifest.chmod(0o600)
    compiler_manifest = work / "compile-manifest.json"
    sealed_compiler = vault / "compiler.json"
    sealed_compiler.write_bytes(compiler_manifest.read_bytes())
    sealed_compiler.chmod(0o600)
    sealed_policy = vault / "policy.json"
    sealed_policy.write_text(json.dumps({"schema_version": "0.1", "campaign": "compiled-fixture",
        "manifest": str(sealed_manifest), "manifest_sha256": file_hash(sealed_manifest),
        "build": {"manifest": str(sealed_compiler), "manifest_sha256": file_hash(sealed_compiler), "memory_budget": 536870912},
        "benchmark_workload": "correct", "transfer_budget": 268435456, "repetitions": 3, "seed": 17,
        "wall_seconds": 180, "max_trials": 14, "maximum_latency_regression": 1.0, "minimum_memory_improvement": .1}, indent=2))
    sealed_policy.chmod(0o600)
    baseline = LAB / "compiled-baseline"
    candidate = LAB / "compiled-candidate"
    code = '''#include <stdio.h>
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
    for source, content in ((baseline, code), (candidate, code.replace("64*1024*1024", "8*1024*1024"))):
        source.mkdir()
        (source / "program.c").write_text(content)
        (source / "contract.txt").write_text("Exact sum of n bytes of value one.\n")
    project = initialize(baseline, ["NEVER_EXECUTE_HOST_TESTS"], protected_paths=["contract.txt"])
    plan = {"schema_version": "0.1", "concept": "Compiled byte sum with bounded live storage",
        "project_config": str(project), "benchmark_command": ["NEVER_EXECUTE_HOST_BENCHMARK"], "objective": "enforced_budget_bytes",
        "evaluation": {"backend": "linux_cgroup", "manifest": str(runtime_manifest), "benchmark_workload": "correct", "initial_budget": 100663296,
            "build": {"manifest": str(compiler_manifest), "memory_budget": 536870912}},
        "acceptance": {"campaign": "compiled-fixture", "public_key": key.public_key().public_bytes_raw().hex(),
            "policy_sha256": file_hash(sealed_policy), "evaluator_sha256": acceptance.implementation()},
        "quantum": 4096, "minimum_target": 8388608, "reductions": [.5], "repetitions": 2,
        "confirmation_repetitions": 2, "regression_limits": {}, "max_generations": 1, "wall_seconds": 300}
    plan_path = work / "development-plan.json"
    plan_path.write_text(json.dumps(plan, indent=2))
    research = work / "research.json"
    research.write_text(json.dumps({"hypothesis": "Smaller live chunks reduce memory", "mechanism": "Bounded storage",
        "falsification": "Wrong sum or OOM", "sources": [{"reference": "owner:compiled-fixture", "supports": "Scripted C source variants"}]}))
    session = LAB / "compiled-development-session"
    dev.create(plan_path, session)
    state = dev.submit(session, candidate, research)
    assert state["generations"][-1]["decision"] == "accepted_experimental", state["generations"][-1]
    request = dev.acceptance_request(session)
    receipt = acceptance.grade(request, sealed_policy, key_path, vault)
    assert receipt["body"]["verdict"] == "passed", receipt
    receipt_path = LAB / "compiled-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2))
    state = dev.accept(session, receipt_path)
    assert state["champions"][state["champion"]]["acceptance_state"] == "verified_champion"
    leaks = sorted(path.name for path in parent.glob("chili-*") if path.is_dir())
    assert not leaks, leaks
    summary = {"status": "passed", "compiler_controls": results, "compiled_runtime": "pass",
        "compiled_controller": "accepted_experimental", "compiled_sealed_gate": "passed",
        "remaining_cgroups": leaks, "scope": "offline GCC C build/export/run and final-gate fixture; no model calls"}
    (LAB / "native-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

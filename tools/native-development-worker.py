"""Exercise the actual development controller through its cgroup backend."""
import hashlib
import json
import os
from pathlib import Path
import sys

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB / "source"))
from chilicrisp import development as dev  # noqa: E402
from chilicrisp.project import initialize  # noqa: E402
from chilicrisp.runner import tree_hash  # noqa: E402


def program(chunk):
    return f'''def compute():
    block = b"\\x01" * {chunk}
    total = 0
    for _ in range(67108864 // len(block)):
        total += sum(block)
    return total
'''


def main():
    relative = next(line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines()
                    if line.startswith("0::"))
    service = Path("/sys/fs/cgroup") / relative.lstrip("/")
    (service / "manager").mkdir()
    (service / "manager/cgroup.procs").write_text(str(os.getpid()))
    (service / "cgroup.subtree_control").write_text("+memory +pids +cpu")
    parent = service / "experiments"
    parent.mkdir()
    (parent / "cgroup.subtree_control").write_text("+memory +pids +cpu")
    os.environ["CHILI_CONTROLLER_SECRET"] = "not-visible-to-candidates"
    manifest = json.loads((LAB / "source/examples/experiment.json").read_text())
    command = ["/usr/bin/python3", "-I", "-B", "/fixtures/development.py"]
    manifest["target"].update(rootfs=str(LAB / "rootfs"), rootfs_hash=tree_hash(LAB / "rootfs"),
        command=command, build_identity="owner-frozen Python runtime and oracle")
    manifest["workloads"][0].update(input=str(LAB / "empty-input"), arguments=[],
        expected_stdout_hash=hashlib.sha256(b"67108864\n").hexdigest())
    manifest["isolation"].update(cgroup_parent=str(parent), cpu={"quota_usec": 100000, "period_usec": 100000})
    manifest["limits"]["timeout_seconds"] = 10
    policy = LAB / "development-manifest.json"
    policy.write_text(json.dumps(manifest, indent=2))
    sources = []
    for name, code in (("initial", program(64*1024*1024)), ("first", program(32*1024*1024)),
                       ("incorrect", "def compute():\n    return -1\n"), ("second", program(1024*1024))):
        source = LAB / ("source-" + name)
        source.mkdir()
        (source / "program.py").write_text(code)
        (source / "contract.txt").write_text("Sum 67108864 bytes of value 1; stdout is owner graded.\n")
        sources.append(source)
    # These host commands deliberately fail if accidentally invoked. Native mode ignores them.
    config = initialize(sources[0], ["NEVER_RUN_HOST_TESTS"], protected_paths=["contract.txt"])
    plan = {"schema_version": "0.1", "concept": "Compute an exact byte sum with bounded chunks",
        "project_config": str(config), "benchmark_command": ["NEVER_RUN_HOST_BENCHMARK"],
        "objective": "enforced_budget_bytes", "evaluation": {"backend": "linux_cgroup",
            "manifest": str(policy), "benchmark_workload": "correct", "initial_budget": 96*1024*1024},
        "quantum": 4096, "minimum_target": 8*1024*1024, "reductions": [.5],
        "repetitions": 2, "confirmation_repetitions": 2, "regression_limits": {},
        "max_generations": 3, "max_stagnation": 3, "max_commands": 100, "wall_seconds": 300}
    plan_path = LAB / "development-plan.json"
    plan_path.write_text(json.dumps(plan, indent=2))
    research = LAB / "research.json"
    research.write_text(json.dumps({"hypothesis": "Bounded chunks reduce live input storage",
        "mechanism": "Sum identical bytes incrementally", "falsification": "Wrong sum or resource failure",
        "sources": [{"reference": "owner:integration-fixture", "supports": "Deterministic source variants, not AI invention"}]}))
    session = LAB / "development-session"
    state = dev.create(plan_path, session)
    initial = state["champions"][0]["metrics"]["enforced_budget_bytes"]
    state = dev.submit(session, sources[1], research)
    assert state["generations"][-1]["decision"] == "accepted_experimental", state.get("error", state["generations"][-1])
    first = state["champions"][state["champion"]]["id"]
    first_budget = state["champions"][state["champion"]]["metrics"]["enforced_budget_bytes"]
    state = dev.submit(session, sources[2], research)
    assert state["generations"][-1]["decision"] == "rejected"
    assert state["champions"][state["champion"]]["id"] == first
    proposer = LAB / "fixture-proposer.py"
    proposer.write_text('''import sys
from pathlib import Path
Path(sys.argv[1], "program.py").write_bytes(Path(sys.argv[3]).read_bytes())
Path(sys.argv[2]).write_bytes(Path(sys.argv[4]).read_bytes())
''')
    state = dev.run(session, [sys.executable, str(proposer), "{workspace}", "{response}",
        str(sources[3] / "program.py"), str(research)], trusted_local=True)
    assert state["state"] == "STOPPED" and state["stop_reason"] == "generation_cap"
    assert state["generations"][-1]["decision"] == "accepted_experimental", state["generations"][-1]
    final_budget = state["champions"][state["champion"]]["metrics"]["enforced_budget_bytes"]
    assert initial > first_budget > final_budget
    probes = [generation["pressure_probe"]["outcome"] for generation in state["generations"]]
    assert probes == ["oom", "oom", "oom"], probes
    state = dev.rollback(session, first, "Exercise remeasured rollback after two retained generations")
    assert state["champions"][state["champion"]]["rollback_of"] == first
    assert state["champions"][state["champion"]]["metrics"]["enforced_budget_bytes"] == first_budget
    leaks = sorted(p.name for p in parent.glob("chili-*") if p.is_dir())
    assert not leaks, leaks
    summary = {"status": "passed", "enforced_budgets": [initial, first_budget, final_budget],
        "pressure_probes": probes, "incorrect_candidate": "rejected", "rollback": "remeasured",
        "external_agent_protocol": "exercised with owner-scripted proposer",
        "remaining_cgroups": leaks, "scope": "deterministic native integration; no model calls or sealed acceptance"}
    (LAB / "native-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

"""Chili Crisp: design against an imagined machine, verify on a real one."""
import argparse
import json
from pathlib import Path
import sys
import time

from jsonschema import ValidationError

from .doctor import diagnose
from .cpu import sweep
from .evidence import verify
from .pressure import summarize
from .project import compare, initialize
from .resources import capabilities
from . import constraints, development

# Optional Linux cgroup tier. Reached as `chilicrisp enforced COMMAND`; the old
# top-level names still work but are hidden from the main help.
ENFORCED = {
    "runner": "Validate a manifest or run one enforced trial",
    "frontier": "Search the memory frontier of public workloads",
    "recover": "Recover one named unfinished trial",
    "build": "Compile offline in isolation; artifacts never run on the host",
    "cpu-sweep": "Run a declared CPU quota grid at fixed memory",
    "pressure-map": "Summarize recorded pressure trials",
}
_FORWARDED = {"runner", "frontier", "recover", "build"}


def _enforced_help():
    rows = "\n".join(f"  {name:<14}{text}" for name, text in ENFORCED.items())
    return ("usage: chilicrisp enforced COMMAND [ARGS...]\n\n"
            "Optional Linux tier: kernel-enforced limits (cgroups, seccomp, isolated builds).\n"
            "Constraint briefs do not need it. See docs/current/enforced/.\n\n"
            f"commands:\n{rows}\n")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    prog = "chilicrisp"
    if argv[:1] == ["enforced"]:
        if len(argv) < 2 or argv[1] not in ENFORCED:
            unknown = len(argv) >= 2 and argv[1] not in {"-h", "--help"}
            print((f"unknown enforced command: {argv[1]}\n\n" if unknown else "") + _enforced_help(),
                  end="", file=sys.stderr if unknown else sys.stdout)
            return 2 if unknown else 0
        argv, prog = argv[1:], "chilicrisp enforced"
    if argv and argv[0] in _FORWARDED:
        from . import controller, recovery, runner, build
        old = sys.argv
        try:
            sys.argv = [f"{prog} {argv[0]}", *argv[1:]]
            return {"runner": runner.main, "frontier": controller.main, "recover": recovery.main, "build": build.main}[argv[0]]()
        finally:
            sys.argv = old
    trailing = []
    if argv[:1] == ["check"] and "--" in argv:
        split = argv.index("--")
        argv, trailing = argv[:split], argv[split + 1:]
    parser = argparse.ArgumentParser(prog="chilicrisp", description=__doc__,
                                     epilog="check usage: chilicrisp check BRIEF [options] -- COMMAND [ARGS...]")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    commands.add_parser("profiles", help="List built-in constraint profiles")
    brief = commands.add_parser("brief", help="Print the agent-facing constraint brief")
    brief.add_argument("spec", help="Profile name or brief JSON file")
    brief.add_argument("--report", type=Path, help="Fill in numbers from a previous check report.json")
    brief.add_argument("--out", type=Path, help="Write the markdown to this file instead of stdout")
    checking = commands.add_parser("check", help="Measure a command against a constraint brief")
    checking.add_argument("spec", help="Profile name or brief JSON file")
    checking.add_argument("--workspace", type=Path, default=Path("."), help="Candidate directory (default: .)")
    checking.add_argument("--baseline", type=Path, help="Original directory; resolves relative budgets")
    checking.add_argument("--repeat", type=int, default=3)
    checking.add_argument("--timeout", type=float, default=300.0, help="Seconds per run")
    checking.add_argument("--same-output", action="store_true", help="Require stdout identical to the baseline")
    checking.add_argument("--out", type=Path, help="Report directory (default: .chilicrisp/checks/TIMESTAMP)")
    checking.add_argument("--ratchet", type=Path,
                          help="Fail if a budgeted metric grows past this file's saved values; tighten it on fits")
    checking.add_argument("--tolerance", type=float, default=10.0,
                          help="Percent a metric may grow past the ratchet (default 10)")
    checking.add_argument("--exact-memory", action="store_true",
                          help="Linux + systemd: exact tree peak from a cgroup (counts page cache too)")
    checking.add_argument("--where", action="store_true",
                          help="Python only: one extra traced run listing the top allocation sites")
    commands.add_parser("capabilities", help="List implementation capabilities")
    doctor = commands.add_parser("doctor", help="Check setup without executing workloads")
    doctor.add_argument("--manifest", type=Path)
    # Enforced-tier parsers get no `help=`, which keeps them out of the main listing.
    report = commands.add_parser("pressure-map", prog=f"{prog} pressure-map",
                                 description=ENFORCED["pressure-map"])
    report.add_argument("directory", type=Path)
    cpu = commands.add_parser("cpu-sweep", prog=f"{prog} cpu-sweep", description=ENFORCED["cpu-sweep"])
    cpu.add_argument("manifest", type=Path)
    cpu.add_argument("--quotas", nargs="+", type=int, required=True)
    cpu.add_argument("--period", type=int, default=100000)
    cpu.add_argument("--budget", type=int, required=True, help="Fixed memory limit in bytes")
    cpu.add_argument("--repetitions", type=int, default=3)
    cpu.add_argument("--seed", type=int, default=0)
    init = commands.add_parser("init", help="Configure a trusted project's build and tests")
    init.add_argument("root", type=Path)
    init.add_argument("--test-command", required=True, help="JSON array of executable and arguments")
    init.add_argument("--build-command", help="Optional JSON command array")
    init.add_argument("--protect", action="append", help="Relative correctness file/directory; repeat as needed")
    comparison = commands.add_parser("compare", help="Build/test baseline and candidate snapshots")
    comparison.add_argument("config", type=Path)
    comparison.add_argument("--candidate", required=True, type=Path)
    comparison.add_argument("--output", required=True, type=Path)
    comparison.add_argument("--trusted-local", action="store_true",
                            help="Acknowledge that commands execute with host permissions")
    status = commands.add_parser("status", help="Read a persisted comparison")
    status.add_argument("record", type=Path)
    verification = commands.add_parser("verify", help="Check comparison record and output integrity")
    verification.add_argument("record", type=Path)
    skill = commands.add_parser("skill", help="Export the bundled coding-agent skill")
    skill.add_argument("destination", type=Path)
    dev = commands.add_parser("dev", help="Run the measured development loop without a VM")
    actions = dev.add_subparsers(dest="action", required=True)
    start = actions.add_parser("init")
    start.add_argument("plan", type=Path)
    start.add_argument("session", type=Path)
    start.add_argument("--trusted-local", action="store_true")
    for name in ("request", "status"):
        action = actions.add_parser(name)
        action.add_argument("session", type=Path)
    submission = actions.add_parser("submit")
    submission.add_argument("session", type=Path)
    submission.add_argument("candidate", type=Path)
    submission.add_argument("--research", type=Path, required=True)
    submission.add_argument("--trusted-local", action="store_true")
    automatic = actions.add_parser("run")
    automatic.add_argument("session", type=Path)
    automatic.add_argument("--agent-command", required=True, help="JSON argument array with {request}/{response}/{workspace} tokens")
    automatic.add_argument("--trusted-local", action="store_true")
    recovery = actions.add_parser("recover")
    recovery.add_argument("session", type=Path)
    recovery.add_argument("--owner-stopped", action="store_true")
    undo = actions.add_parser("rollback")
    undo.add_argument("session", type=Path)
    undo.add_argument("champion")
    undo.add_argument("--reason", required=True)
    undo.add_argument("--trusted-local", action="store_true")
    commands.add_parser("enforced", help="Optional Linux cgroup tier: " + ", ".join(ENFORCED)
                        + " (chilicrisp enforced -h)")
    args = parser.parse_args(argv)
    exit_code = 0
    try:
        if args.command == "profiles":
            result = constraints.profiles()
        elif args.command == "brief":
            report = json.loads(args.report.read_text(encoding="utf-8")) if args.report else None
            text = constraints.render(args.spec, report)
            if args.out is None:
                print(text, end="")
                return 0
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
            result = {"brief": str(args.out)}
        elif args.command == "check":
            command = trailing
            out = args.out or Path(".chilicrisp", "checks", time.strftime("%Y%m%dT%H%M%S"))
            result = constraints.check(args.spec, command, args.workspace, out,
                                       baseline_workspace=args.baseline, repeat=args.repeat,
                                       timeout=args.timeout, same_output=args.same_output,
                                       where=args.where, ratchet=args.ratchet,
                                       tolerance=args.tolerance / 100,
                                       exact_memory=args.exact_memory)
            exit_code = 0 if result["verdict"] == "fits" else 1
        elif args.command == "capabilities":
            result = capabilities()
        elif args.command == "doctor":
            manifest = json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest else None
            result = diagnose(manifest)
            exit_code = 0 if result["native_prerequisites_ready" if manifest else "local_workflow_ready"] else 1
        elif args.command == "pressure-map":
            result = summarize(args.directory)
        elif args.command == "cpu-sweep":
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            result = sweep(manifest, args.quotas, period_usec=args.period, memory_budget=args.budget,
                           repetitions=args.repetitions, seed=args.seed)
            exit_code = 0 if result["decision"] == "COMPLETED" else 1
        elif args.command == "init":
            path = initialize(args.root, json.loads(args.test_command),
                              json.loads(args.build_command) if args.build_command else None,
                              protected_paths=args.protect)
            result = {"config": str(path), "execution_mode": "trusted_local",
                      "next": "Review commands, then run compare with a candidate directory"}
        elif args.command == "status":
            result = json.loads(args.record.read_text(encoding="utf-8"))
        elif args.command == "verify":
            result = verify(args.record)
            exit_code = 0 if result["valid"] else 1
        elif args.command == "skill":
            from .skill import export
            result = {"skill": str(export(args.destination))}
        elif args.command == "dev":
            if args.action == "init":
                result = development.create(args.plan, args.session, trusted_local=args.trusted_local)
            elif args.action == "submit":
                result = development.submit(args.session, args.candidate, args.research,
                                            trusted_local=args.trusted_local)
                exit_code = 0 if result["generations"][-1]["decision"] == "accepted_experimental" else 1
            elif args.action == "request":
                result = development.request(args.session)
            elif args.action == "status":
                result = development.status(args.session)
            elif args.action == "rollback":
                result = development.rollback(args.session, args.champion, args.reason,
                                              trusted_local=args.trusted_local)
            elif args.action == "run":
                result = development.run(args.session, json.loads(args.agent_command),
                                         trusted_local=args.trusted_local)
            else:
                result = development.recover(args.session, owner_stopped=args.owner_stopped)
        else:
            record, result = compare(args.config, args.candidate, args.output,
                                     trusted_local=args.trusted_local)
            result = {"record": str(record), **result}
            exit_code = 0 if result["decision"] == "public_tests_passed" else 1
    except (ValueError, OSError, ValidationError) as error:
        print(json.dumps({"error": str(error), "command": args.command}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

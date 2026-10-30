"""Chili Crisp project workflows and isolated experiment tools."""
import argparse
import json
from pathlib import Path
import sys

from jsonschema import ValidationError

from .doctor import diagnose
from .cpu import sweep
from .evidence import verify
from .pressure import summarize
from .project import compare, initialize
from .resources import capabilities
from . import development


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"runner", "frontier", "recover", "build"}:
        from . import controller, recovery, runner, build
        old = sys.argv
        try:
            sys.argv = [f"chilicrisp {argv[0]}", *argv[1:]]
            return {"runner": runner.main, "frontier": controller.main, "recover": recovery.main, "build": build.main}[argv[0]]()
        finally:
            sys.argv = old
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities", help="List implementation capabilities")
    doctor = commands.add_parser("doctor", help="Check setup without executing workloads")
    doctor.add_argument("--manifest", type=Path)
    report = commands.add_parser("pressure-map", help="Summarize recorded pressure trials")
    report.add_argument("directory", type=Path)
    cpu = commands.add_parser("cpu-sweep", help="Run a declared CPU quota grid at fixed memory")
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
    for name in ("request", "status", "acceptance-request"):
        action = actions.add_parser(name)
        action.add_argument("session", type=Path)
        if name == "acceptance-request":
            action.add_argument("--export", type=Path, help="Copy sources and a relative request here for a separate grader")
    acceptance = actions.add_parser("accept")
    acceptance.add_argument("session", type=Path)
    acceptance.add_argument("receipt", type=Path)
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
    for name in ("runner", "frontier", "recover", "build"):
        commands.add_parser(name, help="Forward to existing experiment command")
    args = parser.parse_args(argv)
    exit_code = 0
    try:
        if args.command == "capabilities":
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
            elif args.action == "acceptance-request":
                result = (development.export_acceptance_request(args.session, args.export) if args.export
                          else development.acceptance_request(args.session))
            elif args.action == "accept":
                result = development.accept(args.session, args.receipt)
                exit_code = 0 if result["acceptances"][-1]["body"]["verdict"] == "passed" else 1
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

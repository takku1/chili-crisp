"""Integrity checks for retained local comparison evidence, not authenticity."""
import hashlib
import json
from pathlib import Path

from .contracts import validate
from .runner import file_hash

def seal(record):
    """Detect later record edits; the sidecar is not a signature or trust anchor."""
    record.with_suffix(".sha256").write_text(
        hashlib.sha256(record.read_bytes()).hexdigest() + "\n", encoding="ascii")


def verify(record):
    record = Path(record).resolve()
    checks = []

    def check(name, passed, detail):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    raw = record.read_bytes()
    result = json.loads(raw)
    validate(result, "comparison")
    validate(result["config"], "project")
    sidecar = record.with_suffix(".sha256")
    check("record_digest", sidecar.is_file() and sidecar.read_text(encoding="ascii").strip()
          == hashlib.sha256(raw).hexdigest(), "Comparison JSON matches its integrity sidecar")
    check("record_kind", result.get("kind") == "trusted_local_comparison", "Recognized comparison record")
    check("finalized", result.get("state") == "FINALIZED", "Interrupted and running records are incomplete")
    evaluations = result.get("evaluations", {})
    check("evaluations", set(evaluations) == {"baseline", "candidate"}, "Both source evaluations are recorded")
    command_count = 0
    for name in ("baseline", "candidate"):
        evaluation = evaluations.get(name, {})
        commands = evaluation.get("commands", [])
        expected = [stage for stage in ("build", "test") if result["config"][stage] is not None]
        stages = [command["stage"] for command in commands]
        check(f"{name}.sequence", stages == expected[:len(stages)]
              and all(command["outcome"] == "pass" for command in commands[:-1]),
              "Commands follow configured order and stop after failure")
        for command in commands:
            command_count += 1
            stage = command.get("stage")
            if stage not in {"build", "test"}:
                check(f"{name}.stage", False, "Unknown command stage")
                continue
            directory = record.parent / f"{name}-{stage}"
            check(f"{name}.{stage}.command", command["command"] == result["config"][stage],
                  "Executed argument array matches frozen configuration")
            command_file = directory / "command.json"
            try:
                saved = json.loads(command_file.read_text(encoding="utf-8"))
                check(f"{name}.{stage}.record", saved == {k: v for k, v in command.items() if k != "stage"},
                      "Stage record matches comparison")
                for stream in ("stdout", "stderr"):
                    capture = command.get("capture", {}).get(stream)
                    path = directory / stream
                    if capture is None:
                        check(f"{name}.{stage}.{stream}", command.get("outcome") != "pass",
                              "Successful commands require capture metadata")
                    else:
                        digest = file_hash(path)
                        check(f"{name}.{stage}.{stream}", digest == capture.get("sha256")
                              and "error" not in capture, "Retained stream hash matches capture metadata")
            except (OSError, ValueError) as error:
                check(f"{name}.{stage}.artifacts", False, str(error))
    check("command_evidence", command_count > 0, "At least one command was recorded")
    if result.get("decision") == "public_tests_passed":
        for name in ("baseline", "candidate"):
            evaluation = evaluations.get(name, {})
            commands = evaluation.get("commands", [])
            check(f"{name}.decision", evaluation.get("outcome") == "pass"
                  and [command["stage"] for command in commands] ==
                  [stage for stage in ("build", "test") if result["config"][stage] is not None]
                  and all(c.get("outcome") == "pass" and c.get("exit_code") == 0 for c in commands),
                  "Passing decision requires successful tests and all recorded commands")
    return {"kind": "comparison_integrity", "record": str(record),
            "valid": all(c["passed"] for c in checks), "checks": checks,
            "limitations": ["Integrity checks are not a signature or independent correctness grading.",
                            "Local commands can modify evidence with host permissions."]}

"""Source-only Codex proposal transport; never executes the returned source.

Uses the same request/response/workspace tokens as dev run. The owner must supply
an isolated evaluator before executing unreviewed proposals.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from jsonschema import Draft202012Validator
import psutil


SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["source", "hypothesis", "mechanism", "falsification", "sources"],
    "properties": {name: {"type": "string"} for name in
                   ("source", "hypothesis", "mechanism", "falsification")}}
SCHEMA["properties"]["sources"] = {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["reference", "supports"],
    "properties": {"reference": {"type": "string"}, "supports": {"type": "string"}}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("response", type=Path)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--seconds", type=int, default=180)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    source = (workspace / args.source).resolve()
    if not source.is_relative_to(workspace) or source.suffix != ".py" or source.is_symlink():
        raise ValueError("The owner must select a Python source file within the proposal workspace")
    if args.seconds < 1 or args.seconds > 300:
        raise ValueError("Proposal time must be 1..300 seconds")
    request = json.loads(args.request.read_text(encoding="utf-8"))
    output = args.response.parent.resolve()
    schema_file = output / "source-proposal.schema.json"
    answer = output / "source-proposal.json"
    schema_file.write_text(json.dumps(SCHEMA), encoding="utf-8")
    prompt = ("Return only a structured source-code proposal. Do not call any tools, execute code, "
        "edit files, build, test, or spawn agents. The owner will apply one file and independently "
        "evaluate it in a Linux sandbox. Preserve API types, validation, errors and numerical behavior. "
        "This is an optimization participation pilot, not a novelty claim. Record a falsifiable "
        "hypothesis and real references. References available to you: "
        "https://docs.python.org/3/library/array.html ; "
        "https://docs.python.org/3/library/stdtypes.html#memoryview .\n"
        + json.dumps(request, indent=2) + "\nOWNER-SELECTED SOURCE:\n" + source.read_text(encoding="utf-8"))
    (output / "proposal-prompt.txt").write_text(prompt, encoding="utf-8")
    executable = shutil.which("codex")
    if executable is None:
        raise ValueError("Codex CLI is unavailable")
    command = [executable]
    if Path(executable).suffix.lower() == ".ps1":
        command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", executable]
    command += ["exec", "--ignore-user-config", "--sandbox", "read-only", "--ephemeral",
        "--skip-git-repo-check", "--disable", "shell_tool", "--disable", "unified_exec",
        "--disable", "apps", "--disable", "plugins", "--disable", "skill_search",
        "--disable", "computer_use", "--disable", "browser_use",
        "--json", "--output-schema", str(schema_file), "--output-last-message", str(answer),
        "--cd", str(workspace), "-"]
    started = time.monotonic()
    failure = None
    cleanup_errors = []
    with (output / "proposal-events.jsonl").open("w", encoding="utf-8") as events, \
         (output / "proposal-stderr.txt").open("w", encoding="utf-8") as errors:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, text=True, encoding="utf-8",
            stdout=events, stderr=errors, start_new_session=os.name != "nt")
        try:
            process.communicate(input=prompt, timeout=args.seconds)
        except BaseException as error:
            failure = error
            try:
                descendants = psutil.Process(process.pid).children(recursive=True)
            except psutil.NoSuchProcess:
                descendants = []
            except psutil.Error as cleanup:
                descendants = []
                cleanup_errors.append(str(cleanup))
            for descendant in reversed(descendants):
                try:
                    descendant.kill()
                except psutil.NoSuchProcess:
                    pass
                except psutil.Error as cleanup:
                    cleanup_errors.append(str(cleanup))
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            _, alive = psutil.wait_procs(descendants, timeout=5)
            if alive:
                cleanup_errors.append("CLI descendant processes remain alive")
    metadata = {"command": command, "exit_code": process.returncode,
                "wall_seconds": time.monotonic() - started, "usage": None,
                "failure": str(failure) if failure else None, "cleanup_errors": cleanup_errors,
                "candidate_execution": "none; source proposal only"}
    for line in (output / "proposal-events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed":
            metadata["usage"] = event.get("usage")
        item = event.get("item", {})
        if item.get("type") in {"command_execution", "file_change", "mcp_tool_call", "web_search"}:
            metadata["unexpected_tool"] = item.get("type")
    (output / "proposal-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if failure is not None:
        raise failure
    if process.returncode or cleanup_errors or "unexpected_tool" in metadata or not answer.is_file():
        raise ValueError("Source proposal did not complete cleanly; inspect retained events/stderr")
    if answer.stat().st_size > 65536:
        raise ValueError("Source proposal exceeds 64 KiB")
    proposal = json.loads(answer.read_text(encoding="utf-8"))
    Draft202012Validator(SCHEMA).validate(proposal)
    if not proposal["sources"]:
        raise ValueError("A source proposal needs at least one recorded reference")
    ast.parse(proposal["source"])
    source.write_text(proposal.pop("source"), encoding="utf-8")
    args.response.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    print(json.dumps({"proposal": str(answer), "research": str(args.response), "metadata": metadata}, indent=2))


if __name__ == "__main__":
    main()

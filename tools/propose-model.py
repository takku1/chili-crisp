"""Tool-less model proposal transport for compiled candidates; never builds or runs the result.

The model receives one development request, the protected contract and the
owner-selected editable files as text. It has no tools other than structured
output, so it cannot read or execute anything. The returned files replace the
editable files in a copy of the incumbent; everything else is copied unchanged.
Usage is normalized across providers and recorded with explicit nulls.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from jsonschema import Draft202012Validator

SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["files", "hypothesis", "mechanism", "falsification", "sources"],
    "properties": {
        "files": {"type": "object", "additionalProperties": {"type": "string", "maxLength": 65536}},
        "hypothesis": {"type": "string"}, "mechanism": {"type": "string"}, "falsification": {"type": "string"},
        "sources": {"type": "array", "minItems": 1, "items": {"type": "object", "additionalProperties": False,
            "required": ["reference", "supports"],
            "properties": {"reference": {"type": "string"}, "supports": {"type": "string"}}}}}}


def target_sentence(request):
    if request["objective"] == "native_memory_peak_bytes":
        return (f"Your program will run with a fixed memory ceiling. To be accepted, its median measured peak cgroup "
                f"memory must be at most {request['target']} bytes. Current measurements: {json.dumps(request['measured_baseline'])}.")
    return (f"Your program will run under an enforced cgroup memory limit (memory.max, no swap) of {request['target']} "
            f"bytes; exceeding it kills the program (OOM). The incumbent passed at "
            f"{request['measured_baseline'].get('enforced_budget_bytes')} bytes.")


def prompt_for(request, incumbent, editable):
    files = {name: (incumbent / name).read_text(encoding="utf-8") for name in editable}
    contract = "\n".join(f"--- {name} (protected, read-only) ---\n{(incumbent / name).read_text(encoding='utf-8')}"
                         for name in request["protected_paths"] if (incumbent / name).is_file())
    public = {key: request[key] for key in ("generation", "concept", "objective", "target", "target_basis",
              "measured_baseline", "regression_limits", "previous_attempt", "experiment_memory")}
    return ("You are proposing one revision of a C program. You have no tools: do not try to run, compile or "
        "inspect anything. The owner compiles your files offline with gcc -O2 in an isolated sandbox, runs them "
        "on public workloads that must produce byte-identical stdout, and later grades the final version on "
        "withheld inputs that follow the same contract. Programs that special-case inputs fail.\n\n"
        + target_sentence(request) + "\n\n" + contract + "\n\nDevelopment request (public feedback only):\n"
        + json.dumps(public, indent=2) + "\n\nEditable files; return every one of them in full under 'files':\n"
        + "".join(f"--- {name} ---\n{text}\n" for name, text in files.items())
        + "\nAlso return a falsifiable hypothesis, the mechanism, what result would falsify it, and at least "
          "one real reference supporting the technique.")


def run_claude(executable, prompt, model, seconds, max_usd, workdir):
    command = [executable, "-p", "--model", model, "--tools", "", "--output-format", "json",
        "--json-schema", json.dumps(SCHEMA), "--no-session-persistence", "--strict-mcp-config",
        "--disable-slash-commands", "--setting-sources", "", "--max-budget-usd", str(max_usd)]
    completed = subprocess.run(command, input=prompt, capture_output=True, text=True, encoding="utf-8",
                               timeout=seconds, cwd=workdir)
    (Path(workdir).parent / "provider-stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (Path(workdir).parent / "provider-stderr.txt").write_text(completed.stderr, encoding="utf-8")
    raw = json.loads(completed.stdout) if completed.stdout.strip() else {}
    models = raw.get("modelUsage") or {}
    usage = raw.get("usage") or {}
    normalized = {"provider": "anthropic/claude-code", "models": sorted(models),
        "input_tokens": usage.get("input_tokens"), "cache_read_tokens": usage.get("cache_read_input_tokens"),
        "cache_write_tokens": usage.get("cache_creation_input_tokens"), "output_tokens": usage.get("output_tokens"),
        "cost_usd": raw.get("total_cost_usd"), "cost_basis": next((m.get("costBasis") for m in models.values()), None),
        "turns": raw.get("num_turns"), "tool_denials": len(raw.get("permission_denials") or [])}
    if completed.returncode or raw.get("is_error") or raw.get("subtype") != "success":
        raise ValueError(f"Claude proposal failed ({completed.returncode}): "
                         f"{raw.get('api_error') or raw.get('subtype')}: {raw.get('result', '')[-1000:]} "
                         f"{completed.stderr[-1000:]}")
    return raw.get("structured_output"), raw, normalized, completed.stderr


def run_codex(executable, prompt, model, seconds, workdir, editable):
    schema_file = Path(workdir) / "proposal.schema.json"
    answer = Path(workdir) / "proposal.json"
    schema = json.loads(json.dumps(SCHEMA))
    schema['properties']['files'] = {'type': 'object', 'additionalProperties': False,
        'required': editable, 'properties': {name: {'type': 'string'} for name in editable}}
    schema_file.write_text(json.dumps(schema), encoding="utf-8")
    command = [executable, "exec", "--ignore-user-config", "--sandbox", "read-only", "--ephemeral",
        "--skip-git-repo-check", "--disable", "shell_tool", "--disable", "unified_exec", "--json",
        "--output-schema", str(schema_file), "--output-last-message", str(answer), "--cd", str(workdir), "-"]
    if model:
        command[2:2] = ["--model", model]
    completed = subprocess.run(command, input=prompt, capture_output=True, text=True, encoding="utf-8",
                               timeout=seconds, cwd=workdir)
    (Path(workdir).parent / "provider-stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (Path(workdir).parent / "provider-stderr.txt").write_text(completed.stderr, encoding="utf-8")
    usage, tools = None, 0
    for line in completed.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed":
            usage = event.get("usage")
        if 'item' in event and event['item'].get('type') not in {'agent_message', 'reasoning'}:
            tools += 1
    usage = usage or {}
    normalized = {"provider": "openai/codex-cli", "models": [model] if model else [],
        "model_identity_basis": "requested CLI configuration; response does not report resolved model",
        "input_tokens": usage.get("input_tokens"), "cache_read_tokens": usage.get("cached_input_tokens"),
        "cache_write_tokens": None, "output_tokens": usage.get("output_tokens"), "cost_usd": None,
        "cost_basis": None, "turns": None, "tool_denials": None, "tool_events": tools}
    if completed.returncode or tools or not answer.is_file():
        raise ValueError("Codex proposal failed or used tools; inspect retained events")
    return json.loads(answer.read_text(encoding="utf-8")), {"events": completed.stdout}, normalized, completed.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("incumbent", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--edit", action="append", required=True, help="Owner-selected editable file")
    parser.add_argument("--provider", choices=("claude", "codex"), default="claude")
    parser.add_argument("--executable", required=True)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--max-usd", type=float, default=1.0)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    incumbent = args.incumbent.resolve()
    if set(args.edit) & set(request["protected_paths"]):
        raise ValueError("Protected files cannot be editable")
    for name in args.edit:
        path = incumbent / name
        if Path(name).name != name or path.is_symlink() or not path.is_file():
            raise ValueError("Editable files must be regular top-level incumbent files")
    args.output.mkdir()
    workdir = args.output / "workdir"
    workdir.mkdir()
    prompt = prompt_for(request, incumbent, args.edit)
    (args.output / "prompt.txt").write_text(prompt, encoding="utf-8")
    started = time.monotonic()
    if args.provider == "claude":
        proposal, raw, usage, stderr = run_claude(args.executable, prompt, args.model, args.seconds, args.max_usd, workdir)
    else:
        proposal, raw, usage, stderr = run_codex(args.executable, prompt, args.model, args.seconds, workdir, args.edit)
    usage["wall_seconds"] = round(time.monotonic() - started, 3)
    (args.output / "raw-response.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    (args.output / "stderr.txt").write_text(stderr, encoding="utf-8")
    (args.output / "usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")
    Draft202012Validator(SCHEMA).validate(proposal)
    if set(proposal["files"]) != set(args.edit):
        raise ValueError("Proposal must return exactly the editable files")
    candidate = args.output / "candidate"
    shutil.copytree(incumbent, candidate)
    for name, text in proposal.pop("files").items():
        (candidate / name).write_text(text, encoding="utf-8")
    (args.output / "research.json").write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    print(json.dumps({"candidate": str(candidate), "usage": usage}))


if __name__ == "__main__":
    os.umask(0o022)
    main()

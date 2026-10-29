"""Audit native compiler fixture exports, provenance and public runtime evidence."""
import argparse
from collections import Counter
import json
from pathlib import Path

from chilicrisp.build import verify_cached
from chilicrisp.contracts import validate
from chilicrisp.runner import file_hash


def audit(lab):
    lab = Path(lab)
    work = lab / "build-validation"
    counts = Counter()
    records = list((work / "evidence").glob("*/result.json"))
    session = lab / "compiled-development-session"
    if session.exists():
        records.extend((session / "native-evidence").glob("*/result.json"))
    for path in records:
        result = json.loads(path.read_text())
        validate(result, "result")
        if result["lifecycle"] != "FINALIZED" or json.loads((path.parent / "lifecycle.json").read_text())["state"] != "FINALIZED":
            raise ValueError("Unfinished compiler/runtime trial")
        if int(result["preflight_record"]["effective"]["memory.max"]) != result["requested_budget_bytes"]:
            raise ValueError("Compiler/runtime memory budget differs")
        for name, digest in result["artifact_hashes"].items():
            if Path(name).name != name or file_hash(path.parent / name) != digest:
                raise ValueError("Compiler/runtime artifact differs")
        counts[result["outcome"]] += 1
    for name in ("compile", "background"):
        verify_cached(work / name / "source", work / (name + "-manifest.json"), work / name, 536870912)
    for name in ("nondeterministic", "timeout", "flood", "oom", "invalid", "host-include"):
        result = json.loads((work / name / "build-record.json").read_text())
        if result["status"] != "rejected" or (work / name / "artifacts").exists():
            raise ValueError("Failed compiler output was retained")
    if session.exists():
        state = json.loads((session / "state.json").read_text())
        source_hashes = {champion["source_hash"] for champion in state["champions"]}
        for cache in (session / "build-cache").iterdir():
            record = json.loads((cache / "build-record.json").read_text())
            if record["source_hash"] not in source_hashes:
                raise ValueError("Compiled source differs from a frozen champion")
            verify_cached(cache / "source", state["plan"]["evaluation"]["build"]["manifest"], cache, 536870912)
        known_builds = {file_hash(path) for path in (session / "build-cache").glob("*/build-record.json")}
        for path in (session / "native-evidence").glob("*/result.json"):
            result = json.loads(path.read_text())
            recorded = result["preflight_record"].get("build_record_sha256")
            if recorded is not None and recorded not in known_builds:
                raise ValueError("Runtime build provenance differs")
    return {"public_trials": len(records), "outcomes": dict(counts),
            "scope": "saved compiler/provenance/runtime consistency; not authenticity"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lab", type=Path)
    print(json.dumps(audit(parser.parse_args().lab), indent=2))

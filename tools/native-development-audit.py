"""Independently check retained native-development fixture artifacts, not authenticity."""
import argparse
from collections import Counter
import json
from pathlib import Path

from chilicrisp.contracts import validate
from chilicrisp.runner import file_hash


def audit(root):
    root = Path(root)
    session = root / "development-session"
    state = json.loads((session / "state.json").read_text())
    outcomes = Counter()
    evidence = session / "native-evidence" if (session / "native-evidence").exists() else session / "runs"
    records = list(evidence.rglob("result.json"))
    trials = {}
    if not records or list(evidence.rglob("emergency.json")):
        raise ValueError("Missing trials or emergency diagnostics")
    for path in records:
        result = json.loads(path.read_text())
        validate(result, "result")
        trials[result["trial_id"]] = result
        if result["lifecycle"] != "FINALIZED":
            raise ValueError("Unfinished trial: " + str(path))
        for name, digest in result["artifact_hashes"].items():
            if Path(name).name != name or file_hash(path.parent / name) != digest:
                raise ValueError("Artifact identity mismatch: " + str(path))
        journal = json.loads((path.parent / "lifecycle.json").read_text())
        if journal["state"] != "FINALIZED":
            raise ValueError("Unfinished lifecycle journal")
        requested = result["requested_budget_bytes"]
        effective = result["preflight_record"].get("effective", {})
        if result["effective_budget_bytes"] != requested or int(effective["memory.max"]) != requested:
            raise ValueError("Memory budget mismatch")
        if result["outcome"] == "pass" and file_hash(path.parent / "stdout") != state["stdout_hash"]:
            raise ValueError("Passing output differs from pinned oracle")
        outcomes[result["outcome"]] += 1
    accepted = [g for g in state["generations"] if g["decision"] == "accepted_experimental"]
    if len(accepted) != 2 or outcomes["oom"] != 3 or outcomes["wrong_output"] != 1:
        raise ValueError("Fixture decisions or negative controls differ")
    budgets = [state["champions"][0]["metrics"]["enforced_budget_bytes"]]
    for generation in accepted:
        budgets.append(generation["target"])
        for phase in ("exploration", "confirmation"):
            for item in generation["phases"][phase]["records"]:
                measurement = json.loads((session / item["measurement"]).read_text())
                raw = trials[measurement["trial_id"]]
                if (measurement["metrics"]["native_memory_peak_bytes"] != raw["metrics"]["memory_peak"]["value"]
                        or measurement["metrics"]["wall_seconds"] != raw["metrics"]["elapsed"]["value"]):
                    raise ValueError("Measurement differs from raw trial")
                expected = generation["target"] if item["variant"] == "candidate" else budgets[-2]
                if measurement["metrics"]["enforced_budget_bytes"] != expected:
                    raise ValueError("Paired measurement used the wrong budget")
    if budgets != [100663296, 50331648, 25165824] or state["events"][-1]["kind"] != "rollback":
        raise ValueError("Unexpected budget progression or rollback")
    return {"trials": len(records), "outcomes": dict(outcomes), "enforced_budgets": budgets,
            "scope": "saved record/artifact consistency, not authenticity or hidden acceptance"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    print(json.dumps(audit(parser.parse_args().root), indent=2))

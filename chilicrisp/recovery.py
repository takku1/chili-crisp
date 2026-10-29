"""Recover only a specifically named unfinished trial; never scan and kill peers."""
import argparse
import json
from pathlib import Path
import sys

from .lifecycle import Lifecycle
from .runner import cleanup_cgroup


def recover(journal, delegated_parent):
    if sys.platform != "linux":
        raise RuntimeError("recovery requires the original Linux host")
    journal = Path(journal)
    data = json.loads(journal.read_text())
    if data.get("kind") == "emergency_diagnostic":
        data = dict(trial_id=data["trial_id"], cgroup=data["cgroup"],
                    state="RECOVERY_REQUIRED", transitions=["RECOVERY_REQUIRED"])
        journal = journal.parent / "lifecycle.json"
    parent = Path(delegated_parent).resolve()
    cgroup = Path(data["cgroup"]).resolve()
    if (not parent.is_relative_to(Path("/sys/fs/cgroup")) or
            cgroup.parent != parent or cgroup.name != "chili-" + data["trial_id"]):
        raise ValueError("journal cgroup is outside the explicitly selected parent")
    if data["state"] == "FINALIZED":
        if not (journal.parent / "emergency.json").exists() or data.get("recovery"):
            return
        data["state"] = "RECOVERY_REQUIRED"
        data["transitions"].append("RECOVERY_REQUIRED")
    life = Lifecycle.__new__(Lifecycle)
    life.path, life.data = Path(journal), data
    if data["state"] == "COLLECTING":
        life.move("RECOVERY_REQUIRED")
    if life.data["state"] != "TERMINATING":
        life.move("TERMINATING")
    cleanup_cgroup(cgroup)
    life.move("COLLECTING")
    life.data["recovery"] = "orphan cleanup; interrupted measurement invalid"
    life.move("FINALIZED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("journal", type=Path)
    parser.add_argument("--cgroup-parent", required=True, type=Path)
    args = parser.parse_args()
    recover(args.journal, args.cgroup_parent)


if __name__ == "__main__":
    main()

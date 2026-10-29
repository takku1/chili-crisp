"""Persist transitions before actions so recovery can find unfinished trials."""
import json
import os
from pathlib import Path

TRANSITIONS = {
    "CREATED": {"PREFLIGHT_VALIDATED", "TERMINATING"},
    "PREFLIGHT_VALIDATED": {"CGROUP_CONFIGURED", "TERMINATING"},
    "CGROUP_CONFIGURED": {"RUNNING", "TERMINATING"},
    "RUNNING": {"TERMINATING"},
    "TERMINATING": {"COLLECTING"},
    "COLLECTING": {"FINALIZED", "RECOVERY_REQUIRED"},
    "RECOVERY_REQUIRED": {"TERMINATING"},
    "FINALIZED": set(),
}


class Lifecycle:
    def __init__(self, path, metadata):
        self.path = Path(path)
        self.data = dict(metadata, state="CREATED", transitions=["CREATED"])
        self.save()

    def save(self):
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(self.data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)

    def move(self, state):
        if state not in TRANSITIONS[self.data["state"]]:
            raise ValueError(f"illegal transition to {state}")
        self.data["state"] = state
        self.data["transitions"].append(state)
        self.save()

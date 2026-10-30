"""Evidence receipts — one vocabulary, one promotion rule.

A finding is no stronger than its
weakest input; Refuted/Unknown are terminal) but as a small JSON-able
record with the solver version and SMT-LIB2 artifact attached.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ORDER = ["observed", "inferred", "sampled", "proved", "measured"]
TERMINAL = ("refuted", "unknown")


@dataclass
class Receipt:
    request: str
    original: str
    rewritten: str
    rule: str
    proof: str
    measurement: str
    stage: str
    provenance: list[str] = field(default_factory=list)
    smtlib2: str = ""
    solver_version: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def combine(proof: str, measurement: str) -> str:
    """Min-filter across the two gates. Only proved+measured promotes."""
    if proof == "refuted" or measurement == "refuted":
        return "refuted"
    if proof == "unknown" or measurement == "unknown":
        return "unknown"
    if proof == "proved" and measurement == "measured":
        return "measured"
    ranks = {name: i for i, name in enumerate(ORDER)}
    weaker = proof if ranks.get(proof, -1) <= ranks.get(measurement, -1) else measurement
    return weaker  # type: ignore[return-value]


def is_promotable(stage: str) -> bool:
    return stage in ("proved", "measured")

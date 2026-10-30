"""Finding classification: novelty (N0-N4) × usefulness (U0-U4).

Defaults: absent N is N0, absent U is U0; N3 (literature-novel) is never
auto-assigned. Labels bind directly to pipeline receipts and are
JSON-serializable. Classification here is a *labeling heuristic*, not
proof — the evidence stage on the receipt still decides promotion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NoveltyClass(str, Enum):
    N0 = "N0"  # catalog / trivial rewrite — not a discovery claim
    N1 = "N1"  # project-novel: new to this codebase
    N2 = "N2"  # catalog-novel: needs a known-to-Wilderbeast gate (human)
    N3 = "N3"  # literature-novel: research only, never auto-assigned
    N4 = "N4"  # unknown: abstain


class UsefulnessClass(str, Enum):
    U0 = "U0"  # no demonstrated use
    U1 = "U1"  # local optimize on the triggering object
    U2 = "U2"  # catalog leverage for future search
    U3 = "U3"  # transfer value under another frame
    U4 = "U4"  # standalone exportable artifact


@dataclass
class Finding:
    novelty: NoveltyClass = NoveltyClass.N0
    usefulness: UsefulnessClass = UsefulnessClass.U0
    reasons: list[str] = field(default_factory=list)

    @property
    def is_product_discovery(self) -> bool:
        """Product iff N>=1, U>=1, not research-only N3."""
        return (
            self.novelty in (NoveltyClass.N1, NoveltyClass.N2)
            and self.usefulness
            in (UsefulnessClass.U1, UsefulnessClass.U2, UsefulnessClass.U3, UsefulnessClass.U4)
        )

    def to_dict(self) -> dict:
        return {
            "novelty": self.novelty.value,
            "usefulness": self.usefulness.value,
            "reasons": list(self.reasons),
            "product_discovery": self.is_product_discovery,
        }


def classify_receipt(receipt) -> Finding:
    """Label a pipeline receipt. Conservative: unknown evidence → N4/U0."""
    from wilderbeast.evidence import is_promotable

    reasons: list[str] = []
    if receipt.stage in ("unknown", "refuted"):
        return Finding(NoveltyClass.N4, UsefulnessClass.U0,
                       [f"no discovery claim on {receipt.stage} evidence"])
    cost_delta = int(receipt.detail.get("cost_delta", 0))
    changed = receipt.original != receipt.rewritten
    if not changed:
        return Finding(NoveltyClass.N0, UsefulnessClass.U0, ["rewrite identical to input"])
    catalog_rules = {
        "sympy.horner",
        "sympy.expand",
        "sympy.factor",
        "sympy.cancel",
        "sympy.together",
        "sympy.simplify",
    }
    is_catalog_rule = receipt.rule in catalog_rules or receipt.rule == "none"

    if not is_promotable(receipt.stage):
        novelty = NoveltyClass.N0
        reasons.append("differs from input but evidence not promotable")
    elif is_catalog_rule:
        novelty = NoveltyClass.N0
        reasons.append(f"standard catalog rewrite ({receipt.rule})")
    else:
        novelty = NoveltyClass.N1
        reasons.append(f"non-catalog / synthesized rule ({receipt.rule}); project-novel")
    if receipt.stage == "measured" and cost_delta < 0:
        usefulness, why = UsefulnessClass.U1, "measured local improvement"
    elif receipt.proof == "proved" and cost_delta <= 0:
        usefulness, why = UsefulnessClass.U1, "proved equivalent, no cost regression"
    elif receipt.proof == "proved":
        usefulness, why = UsefulnessClass.U2, "proved rewrite retained as reusable method"
    else:
        usefulness, why = UsefulnessClass.U0, "no demonstrated use yet"
    reasons.append(why)
    return Finding(novelty, usefulness, reasons)

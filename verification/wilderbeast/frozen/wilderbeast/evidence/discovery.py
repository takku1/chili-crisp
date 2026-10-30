"""Multi-Kind Discovery Taxonomy.

Moves beyond pure speedup optimization to represent the full breadth of computational discovery:
- OPTIMIZATION: verified faster, smaller, or lower-power implementation.
- IDENTITY: verified mathematical or machine equivalence.
- ALGORITHM: newly synthesized computational procedure.
- INVARIANT: conserved quantity holding across state updates.
- ABSTRACTION: newly extracted reusable primitive.
- COUNTEREXAMPLE: certified witness refuting a conjecture.
- TRANSFER: cross-domain structural isomorphism.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from wilderbeast.evidence.finding import NoveltyClass, UsefulnessClass


class DiscoveryKind(str, Enum):
    OPTIMIZATION = "optimization"
    IDENTITY = "identity"
    ALGORITHM = "algorithm"
    INVARIANT = "invariant"
    ABSTRACTION = "abstraction"
    COUNTEREXAMPLE = "counterexample"
    TRANSFER = "transfer"


@dataclass
class DiscoveryReceipt:
    """Artifact recording any valid computational discovery across representations."""
    kind: DiscoveryKind
    title: str
    target_representation: str       # e.g., 'instruction', 'expression', 'function', 'graph'
    statement: str                   # Human-readable claim
    formal_proof_or_witness: str     # SMT-LIB2 text or certified counterexample
    novelty: NoveltyClass = NoveltyClass.N0
    usefulness: UsefulnessClass = UsefulnessClass.U1
    reproducibility: Dict[str, Any] = field(default_factory=dict)
    provenance: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "title": self.title,
            "target_representation": self.target_representation,
            "statement": self.statement,
            "formal_proof_or_witness": self.formal_proof_or_witness,
            "novelty": self.novelty.value,
            "usefulness": self.usefulness.value,
            "reproducibility": self.reproducibility,
            "provenance": list(self.provenance),
        }

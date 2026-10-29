# Chili Crisp design

Chili Crisp is a proposed experimental framework for finding useful software designs through artificial resource pressure. An AI agent proposes hypotheses and code changes; an independent runner decides whether they preserve behavior and improve measured outcomes. Scarcity is a discovery instrument, not a production requirement.

**Status:** first implementation of schemas, public frontier control, and a Linux runner now exists. See [implementation and verification limits](implementation.md). Native Linux isolation remains unvalidated in this Windows session; there are no validated optimization results. Numbers in these documents are proposed defaults or explicitly labeled examples.

## Read in order

1. [Product and system design](design.md) — scope, trust boundary, workflow, and decisions.
2. [Experiment protocol](protocol.md) — how to measure and search a memory frontier.
3. [Evidence contract](evidence.md) — required inputs, trial records, and acceptance gates.
4. [Pilot and evaluation](pilot.md) — first build target and how to test the core hypothesis.
5. [Research notes](research.md) — primary sources, what they establish, and open questions.

Implementation requirements: [runner and experiment policies](engineering-contract.md) and [pressure-to-invention protocol](invention.md). These harden the original protocol and govern launch, accounting, hidden evaluation, and cost reporting.

The [discovery roadmap](roadmap.md) records pressure maps, counterfactual diagnostics, AlphaEvolve comparisons, and the controlled four-arm evaluation while preserving the memory-only implementation gate.

The [generation-controller contract](evolution.md) defines the future moving-target loop and its promotion/rollback gates.

The brainstorm at the repository root is an input to this design, not a specification. Its historical anecdotes, hypothetical charts, and proposed formulas are not evidence of Chili Crisp's performance.

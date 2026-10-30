# Chili Crisp design

See [current project status](STATUS.md) for the latest implementation and evidence.

Start with [system constraints and current capabilities](resources.md) for the
multi-resource direction, common CLI, and observed pressure-map reports.
Use [getting started](getting-started.md) for installation and agent workflows,
and [package organization](frameworks.md) for maintained source boundaries.

Chili Crisp is a proposed experimental framework for finding useful software designs through artificial resource pressure. An AI agent proposes hypotheses and code changes; an independent runner decides whether they preserve behavior and improve measured outcomes. Scarcity is a discovery instrument, not a production requirement.

**Status:** schemas, public frontier control, Linux runner, local candidate workflow,
and AI coding skill are implemented. Native C/trust fixtures also reproduce on
a fresh CI host; see [account-boundary validation](../reports/trust-boundary-validation.md),
[native validation evidence](../reports/native-validation.md) and
[implementation limits](implementation.md). A [decoder self-test](../reports/dogfood-decoder.md)
now provides one narrowly scoped measured candidate improvement; it is not
production acceptance. Other design numbers remain proposed defaults or labeled examples.

## Read in order

1. [Product and system design](design.md) — scope, trust boundary, workflow, and decisions.
2. [Experiment protocol](protocol.md) — how to measure and search a memory frontier.
3. [Evidence contract](evidence.md) — required inputs, trial records, and acceptance gates.
4. [Pilot and evaluation](pilot.md) — first build target and how to test the core hypothesis.
5. [Research notes](research.md) — primary sources, what they establish, and open questions.

Implementation requirements: [runner and experiment policies](engineering-contract.md) and [pressure-to-invention protocol](invention.md). These harden the original protocol and govern launch, accounting, hidden evaluation, and cost reporting.

The [discovery roadmap](roadmap.md) records pressure maps, counterfactual diagnostics, AlphaEvolve comparisons, and the controlled four-arm evaluation while preserving the memory-only implementation gate.

The runnable [measured development loop](development-loop.md) now provides
checkpointed research/proposal/build/test/measure iterations on the current host.
It keeps local metric targets separate from optional enforced resource trials.

The [generation-controller contract](evolution.md) defines the future moving-target loop and its promotion/rollback gates.

The brainstorm at the repository root is an input to this design, not a specification. Its historical anecdotes, hypothetical charts, and proposed formulas are not evidence of Chili Crisp's performance.

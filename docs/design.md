# Product and system design

Implementation policies are specified in the [runner contract](engineering-contract.md). Whole-program accounting includes runtime startup; component allocation budgets are a distinct future mode. Architectural interventions follow the [pressure-to-invention protocol](invention.md).

## Decision

Build **Verified Scarcity Experiments** first: a bounded, reproducible workflow that pressures one independently runnable component along one resource axis, lets an AI propose an architectural change, and verifies the change against an external oracle and normal operating conditions.

The initial axis is **cgroup v2 memory** on Linux. CPU frequency simulation, whole-application tiny-machine emulation, storage quotas, capability restrictions, and autonomous interruption of other agents are later research tracks. They do not share a reliable measurement method with memory and would make the first result harder to interpret.

## Claim and limits

The longer-term direction is a model-agnostic discovery engine with pressure mapping and controlled architectural search; see the [staged roadmap](roadmap.md). AlphaEvolve already combines LLM proposals, automated evaluation, and evolutionary search, so that combination is not a Chili Crisp novelty claim.

The product hypothesis is that measured artificial scarcity can prompt AI coding agents to find transferable design improvements more often, or at lower cost, than conventional optimization prompts. This is **unproven**. Chili Crisp can initially claim only that a particular candidate passed a specified oracle and changed measured behavior under specified workloads and hardware. A controlled comparison is required before claiming that scarcity caused the discovery.

Chili Crisp occupies a different intended level from instruction-level superoptimizers such as [STOKE](https://www.microsoft.com/en-us/research/publication/stochastic-superoptimization/) and [Souper](https://arxiv.org/abs/1711.04422): it asks about streaming, data representation, object lifetime, and work placement. This is positioning, not a claim of uniqueness.

## Actors and trust boundary

| Actor | Controls | Must not control |
| --- | --- | --- |
| Experiment owner | Target, behavioral contract, workload classes, resource axis, time and trial budget, acceptance thresholds | Candidate measurements after seeing results |
| Candidate agent | Hypotheses and candidate source in an isolated workspace | Frozen oracle, hidden inputs, runner, measurement policy, evidence store |
| Controller | Builds and schedules trials from a pinned manifest | Candidate implementation decisions |
| Runner | Applies resource limits, executes target, captures kernel counters and output | Oracle definitions |
| Verifier | Grades outputs and aggregates evidence | Candidate source |

The controller, hidden inputs, and evidence store must be outside the candidate agent's writable workspace. A read-only label inside the same writable checkout is insufficient. The runner must account for the entire target process tree and prevent or explicitly include helper processes, network services, temporary files, and shared memory. The controller itself is outside the constrained cgroup, so its overhead is not charged to the target. This boundary makes the result meaningful; it is not a general sandbox security guarantee.

## End-to-end workflow

1. **Freeze an experiment manifest.** Record the source revision, release-oriented build command, toolchain, runtime, execution environment, behavioral specification, public workloads, hidden workload generator or corpus, metrics, timeouts, and trial budget. Hash the manifest and inputs.
2. **Check baseline health.** Build and run the original target without a hard memory limit. Reject the experiment if correctness or timing is unstable before pressure is applied.
3. **Find a pressure region.** Measure repeated unconstrained peaks, start above the largest observed peak with a declared margin, verify that limit passes, descend geometrically, and refine around a transition. Record every outcome, including inconclusive ones. See [protocol](protocol.md).
4. **Explain the cost.** Inspect memory composition, reclaim and OOM events, latency, and workload scaling. State a falsifiable hypothesis before editing source.
5. **Try a bounded candidate.** The agent changes only candidate code and build inputs explicitly permitted in the manifest. Each attempt gets a source diff and a journal entry, including rejected ideas.
6. **Verify independently.** Run the frozen public oracle, independent hidden inputs, and normal-hardware comparison. Treat output equivalence, specification compliance, and resource improvement as separate claims.
7. **Decide and report.** Return a measured frontier region, raw trial provenance, tradeoffs, and an acceptance decision. A failure to find a worthwhile change is a valid result.

## First-release deliverables

The implementation should contain a short `SKILL.md` that invokes a deterministic controller, not an instruction package that asks an LLM to invent measurements. The controller needs: manifest validation, isolated builds, cgroup creation and cleanup, trial execution, output verification, adaptive budget selection, immutable or externally retained evidence, and report generation. The candidate agent needs only a small protocol for hypothesizing, editing, and reading verified results.

## Decisions that prevent misleading results

- **No fixed 256 KB target.** Source line count does not predict working memory. A budget is anchored to observed demand for declared workloads.
- **No fictional CPU clock.** `cpu.max` controls CPU bandwidth, not processor frequency or historical instruction timing. CPU work can be measured separately with available counters; emulation is a distinct experiment.
- **No single “minimum RAM” claim.** Reclaim, cache state, and timing can make pass/fail stochastic. Report outcomes and pass rates at tested limits.
- **No scalar performance score.** Preserve memory, latency, CPU work, I/O, artifact size, and maintainability as separate tradeoffs. A candidate that saves RAM by multiplying I/O is visible as such.
- **No automatic production merge.** A verified discovery can still be too complex, fragile, or workload-specific to adopt.

## Later extensions

After the memory pilot works, add one independently specified axis at a time: storage footprint with isolated capacity limits; I/O rate or volume with explicit logical-versus-physical definitions; instruction or cycle measurements where counters are available; and capability restrictions such as no allocation after initialization. Multi-axis Pareto exploration comes after single-axis measurement is trustworthy.

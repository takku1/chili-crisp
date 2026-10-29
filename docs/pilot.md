# Pilot and evaluation plan

Track cost per accepted improvement, including failed compilation, probes, waiting, and rejected hypotheses. Predeclare a maximum spend and compare against a conventional optimization arm; do not infer economic value solely from a successful refactor. Evaluate the diagnostic-to-hypothesis step separately with known-cause fixtures before attributing any improvement to architectural reasoning. A negative pilot limits claims for the sampled components and agents; it cannot definitively disprove scarcity as a general method.

Build in this order: constrained launch and cleanup; measurement fixtures; adaptive search; pressure diagnostics and invention; controlled component pilot. Follow the [runner policies](engineering-contract.md) and [invention procedure](invention.md).

Include negative controls: an unchanged-source candidate to estimate measurement drift, an intentionally invalid output to test grading, and a conventional optimization arm with matched declared budgets. Randomize normal-hardware baseline/candidate order. Record actual tool, trial, CPU, wall-time, and available model costs. Keep confirmation sealed after candidate freeze; use fresh final grading data after feedback-driven revisions.

## First target

Choose one independently runnable parser, serializer, or filesystem-related component with a deterministic input/output contract and an existing test suite. A useful target should have enough input scaling to expose memory behavior, but a short enough build and run cycle to permit repeated trials. The named MochiOS example in the brainstorm is a candidate only if its component and test assets are actually available; this repository contains neither.

Before optimization, demonstrate that the controller can reproduce a baseline frontier and detect at least one deliberately introduced wrong-output and one OOM case. These are runner validation fixtures, not performance results. Then run the real component without modifying its oracle.

## Pilot sequence

1. Freeze the target, environment, build flags, behavior, public and held-out workloads, and a fixed experiment budget.
2. Implement the memory-only runner and evidence records described in [design](design.md) and [evidence](evidence.md).
3. Measure baseline correctness and memory/latency distributions; find a pressure region with [adaptive search](protocol.md).
4. Give the candidate agent one bounded round of hypothesis, code change, and measured feedback. Preserve failed attempts.
5. Independently rerun public and hidden correctness checks, frontier points, and normal-hardware measurements. Report the complete tradeoff, including a valid “no improvement” outcome.

**Pilot success:** a third party can reconstruct every reported number from stored runs; the baseline and candidate are graded by the same frozen oracle; the frontier is expressed as observed outcomes rather than a fabricated point estimate; and any recommended change survives hidden and normal-hardware checks. Finding an optimization is desirable but not required to validate the measurement system.

## Test the larger hypothesis

After the runner is trustworthy, compare scarcity-guided optimization with a conventional optimization prompt. Give both arms the same component, tool access, frozen oracle, time or compute budget, and candidate count. Use multiple components and repeated or randomized assignments to reduce target and agent variance. Keep hidden workloads sealed until final grading. The primary outcome should be **verified, transferable improvements per unit experiment cost**; also report held-out correctness, normal-hardware effects, reproduction rate, and rejected attempts. A single pilot win cannot establish that scarcity caused the improvement.

## Open engineering choices

- What component has a genuinely independent behavioral specification?
- Which cache and swap policy reflects the intended deployment and can be reproduced?
- How will the controller retain evidence outside the candidate's write access in the chosen execution environment?
- What improvement threshold is meaningful enough to justify extra code complexity?

These choices must be fixed before viewing candidate results. They do not block writing the protocol or validating the runner on fixtures.

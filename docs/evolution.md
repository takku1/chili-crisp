# Iterative optimization controller

The measured local outer loop is implemented in `chilicrisp/development.py`.
It checkpoints repeated build/test/benchmark generations, issues moving targets,
records research/proposals, retains experimental versions and supports recovery
and remeasured rollback. It can use the calling coding agent or a configured
external agent command. See [the runnable development protocol](development-loop.md).

The remaining contract below describes stronger independent-acceptance and
isolated-generation goals. Local experimental retention does not satisfy those
production promotion gates. Protected arbitrary builds, sealed grading and
automatic production integration remain unimplemented.

## State and promotion

The [Worldgame verifier](../verification/worldgame/README.md) now supports a
two-case `screen` tier and the existing six-case `full` public tier. Both are
owner-run correctness checks, not acceptance decisions. A compiled, deliberately
incorrect solver was rejected by the screen in the
[screening pilot](../reports/screening-20261029T043608Z/REPORT.md).

This increment owns case scheduling and rejection evidence only. The oracle
remains owner-controlled and the runner retains resource-measurement authority.
Native Linux execution, protected candidate building, finalist/held-out scheduling,
and promotion/rollback remain prerequisites for a full generation. OpenEvolve
should own generic populations and checkpoints when those gates are ready.

`BASELINE → CHALLENGE → DIAGNOSE → PROPOSE → VERIFY → PROMOTE → BASELINE`.

Every generation records the parent/champion source hash, frozen oracle and workload-policy hashes, challenge budget, measured passing/failing regions, diagnostics, candidate artifact, costs, acceptance evidence, and decision. A challenge budget is an unverified experimental target. A measured passing budget belongs to a particular candidate, workload, environment, and repetition policy. Neither substitutes for the other.

The champion pointer changes only after independent correctness, transfer, and cost/tradeoff gates pass. Persist the acceptance evidence and promotion event before changing that pointer atomically. Failed challenges and rejected candidates leave the champion unchanged. Rollback selects a previously verified immutable artifact and retains the reason and history; it does not erase failed generations.

All descendants use the same frozen behavioral contract. Any change to accuracy, features, oracle, workload definition, or grading threshold creates a new experiment lineage and a fresh baseline. Sealed evaluation is not an unlimited per-generation feedback source: use a preallocated independent confirmation set for each candidate selected for grading, and retain an untouched final holdout. Stop when the sealed evaluation budget is exhausted rather than adapt against a reused test.

## Resource and quality frontiers

The resource frontier is the observed budget/outcome region for one candidate under a declared workload and environment. The quality frontier retains correctness-eligible candidates with useful measured tradeoffs in memory, latency, CPU, I/O, and reviewed maintenance cost. No universal scalar score is assumed.

A lower-memory candidate that violates transfer thresholds is not promoted. A candidate with a simpler design or different tradeoffs can remain an experimental branch without replacing the champion. Population search, branch combination, and automatic maintenance scoring are later work.

## Controller-owned challenge policy

The manifest should predeclare the permitted challenge reductions and deterministic adaptation rule. Proposed initial research settings are a 25% reduction; smaller 10% then 5% steps after failed verified attempts; and a larger exploratory step only under a separately budgeted, recorded policy. These are unvalidated engineering choices. Round to enforceable units and stop if rounding cannot produce a meaningfully different challenge.

The agent proposes changes and requests experiments; the controller owns scheduling, precision, budgets, and promotion. Re-establish the promoted candidate's measured baseline before computing its next challenge. Do not derive a future Linux budget from a Windows peak-working-set observation.

## Diminishing returns and termination

Stop after a predeclared limit of generations without accepted improvement (proposed default: three), total wall/compute/model cost exhaustion, insufficient independent grading data, unstable measurements, unsupported isolation, or a gain below the meaningful threshold. Count failed builds, probes, rejected candidates, and confirmation runs. Retain any experimental branches as evidence without presenting them as accepted improvements.

Acceptance tests for a future controller must cover failed challenge without promotion, wrong output without promotion, transfer regression rejection, immutable correctness policy, atomic promotion and restart recovery, rollback to a known artifact, cost limits, and sealed-set exhaustion.

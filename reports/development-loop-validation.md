# Measured development controller validation

2026-10-29. The default outer loop now uses real local build/test/benchmark
measurements and moving targets. No VM or Linux isolation backend is required.
See [the development protocol](../docs/development-loop.md).

## Delivered path

`dev init` freezes a runnable source baseline, protected behavioral checks,
policy, tool/runtime identities and a persistent deadline. `dev request` exposes
the measured baseline and next target. The coding agent researches and edits a
separate candidate. `dev submit` runs correctness plus randomized paired
exploration and fresh confirmation, then atomically retains a qualifying
experimental version and derives its next target from measured confirmation.

`dev run` drives that protocol using a caller-configured agent command with
request/response/workspace files. It reserves agent cost, retains research and
execution records, and rejects stale proposals. No model SDK or model API key is
embedded in Chili Crisp. The current coding agent can also drive request/submit
directly through the installed skill.

Generation/stagnation, wall and conservative top-level-command budgets bound the
loop. Pending actions are persisted before execution. A session lock prevents
overlapping mutations. Interrupted actions require explicit recovery; reserved
cost is retained and candidate attempts are counted. Unresolved cleanup blocks
another generation. Rollback rechecks and remeasures a retained source before
changing the pointer. History and retained-pointer decisions share one atomic
state-file replacement.

## Real-process integration result

Command: `python tools/demo-development.py`.
Final retained session:
`artifacts/development-demo-4a00b8a5bf4e48ce960bc712cccf1a00/session/`.

| Retained version | Logical artifact bytes | Disposition |
| --- | ---: | --- |
| Initial uncompressed payload | 163,840 | Correctness-checked measured baseline |
| Lossless compressed payload | 999 | Accepted experimentally after exploration and confirmation |
| Higher-compression payload | 440 | Accepted experimentally after exploration and confirmation |

The initial target was 122,880 bytes. After the first accepted candidate the
next target was 749 bytes. The second candidate met that tighter target and the
controller stopped at its declared two-generation cap. The test and benchmark
driver required unchanged decoded payload bytes and stable output digests.

The proposer was a deterministic script implementing two declared transformations.
This tests the complete controller/agent-command protocol with real subprocesses,
build products, measurements and checkpoints. It does not claim that an AI model
independently researched or discovered the transformations. Real model-backed
agent execution remains configured by the caller.

## Verification and findings

The full Windows suite ran 80 tests: 78 passed, two Linux-only methods skipped.
The new tests exercise two successive improvements, target movement, restart
reading, wrong output, modified tests, missed targets, latency regression,
command-budget exhaustion, source drift, session locking, interruption/recovery,
remeasured rollback, stale proposals, external command proposals, blocked cleanup,
real sampled memory collection, and missing/escaped artifact paths.

Ruff and skill validation passed. Source/wheel builds, metadata checks and the
extracted-wheel checks passed. The wheel check now initializes and measures a
development session using packaged schemas and modules, in addition to its
existing comparison/evidence/skill checks. The declared base dependency now
includes psutil 7.2.x for local measurements. Native fixture provisioning installs
that declared dependency too; the optional native backend was not rerun during
this measured-loop increment.

Windows testing caught a runtime-identity issue: Microsoft Store Python's launch
alias is executable but cannot be hashed as an ordinary file. The controller now
resolves the actual running interpreter via psutil before pinning it. The demo
and subsequent full tests passed with that fix.

## Locus assessment

The read-only review covered `Z:\locus`'s README, intent/objective model, evidence
types, guided search, expression evolution, provenance cache and CLI surface.
The existing release binary's help command ran successfully. Its useful fit is
optional proposal context plus evidence/provenance design discipline. Its
expression-cost search is not a repository development controller. No source,
configuration or artifacts in Locus were changed, and no Locus dependency was
added to Chili Crisp.

## Limits

This mode measures the current host. Sampled process-tree RSS can miss transient
peaks or double-count shared pages; sampled CPU/I/O can miss final or short-lived
work. File volume is logical size of declared artifacts. None of these values
means an equivalent hard resource limit was enforced. Short sampled workloads
are rejected when their metrics drive decisions. Hardware emulation, arbitrary
protected builds, sealed grading, model-token/dollar caps and automatic production
promotion remain outside this implementation.

The initial concept still needs a runnable implementation and owner-reviewed
behavioral tests, supplied by the coding agent before the controller freezes
the baseline. Research citations are proposal provenance, not automatically
verified facts. Commands run with trusted host permissions. This run is unguarded
because `.git` remains read-only; source identities and saved artifacts provide
the available provenance rather than a parent commit.

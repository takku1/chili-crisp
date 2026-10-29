# Measured development loop

For enforced Linux memory targets through these same commands, see the
[native backend](native-development.md). Its source-only execution contract
requires an owner-provisioned runtime and oracles.

Chili Crisp's default outer loop runs build, correctness and benchmark commands
on the current machine. It does not create a VM or require a Linux rootfs. The
AI agent owns research and source changes; the deterministic controller owns
measurements, candidate decisions, retained versions and subsequent targets.

## From concept to iteration

1. Describe the concept and required behavior. The coding agent creates a
   runnable baseline plus owner-reviewed correctness tests. Those tests form the
   contract; the tool cannot infer a complete specification from a sentence.
2. Configure build and correctness commands with `chilicrisp init`, including
   explicit protected tests, fixtures and benchmark drivers.
3. Create a development policy with one primary resource objective, a repeatable
   benchmark, tradeoff guards and a bounded research/run budget.
4. Initialize the session. Chili Crisp freezes source and policy, verifies
   baseline correctness, collects repeated measurements and derives a target.
5. The agent reads the request, researches the limiting work, makes a candidate
   in a separate directory, and records a hypothesis, mechanism, sources and
   falsification criterion.
6. The controller checks frozen correctness, runs randomized paired baseline and
   candidate measurements, and independently repeats that comparison for fresh
   confirmation. Both phases must meet the resource target and every guard.
7. A qualifying candidate becomes the retained experimental version. Its measured
   confirmation result anchors the next tighter target. Failed attempts preserve
   the retained version and use smaller declared challenge steps. Stop at the
   generation, stagnation, command, wall-time, minimum or resolution limit.

This is a development loop. Code analysis, web research, profiling, alternative
algorithms, data layouts and different build strategies are possible proposal
methods; none substitutes for the controller's measurements and checks.

## Policy and commands

After creating an ordinary project configuration, write a policy such as:

```json
{
  "schema_version": "0.1",
  "concept": "Preserve the decoded payload while reducing stored artifact size",
  "project_config": "baseline/.chilicrisp/project.json",
  "benchmark_command": ["python", "bench.py"],
  "objective": "artifact_bytes",
  "artifact_paths": ["build/payload.bin"],
  "regression_limits": {"wall_seconds": 0.15},
  "reductions": [0.25, 0.10, 0.05],
  "repetitions": 3,
  "confirmation_repetitions": 3,
  "max_generations": 10,
  "max_stagnation": 3,
  "max_commands": 200,
  "wall_seconds": 3600,
  "seed": 29
}
```

The project configuration resolves relative to this policy file. Command argument
arrays run directly, with inherited host environment and no shell interpolation.
Use a specific runtime executable where reproducibility matters. Generated
build products should live under excluded output directories (`build`, `dist`,
`artifacts` or `target`). Source outside those directories must survive build,
test and benchmark execution unchanged. Required runtime files must remain in
the source snapshot or be provisioned by the build.

```text
python -m chilicrisp dev init plan.json session --trusted-local
python -m chilicrisp dev request session
python -m chilicrisp dev submit session candidate --research research.json --trusted-local
python -m chilicrisp dev status session
```

Each candidate needs a research record. It is stored as proposal evidence; a
source reference is not automatically validated or promoted into a measured fact.

```json
{
  "hypothesis": "Lossless compression reduces the stored payload",
  "mechanism": "Encode repeated bytes and decode before returning the public result",
  "falsification": "Decoded output changes, size misses the target, or runtime regresses beyond policy",
  "sources": [{
    "reference": "https://docs.python.org/3/library/zlib.html",
    "supports": "Compression and decompression with selectable compression levels"
  }]
}
```

`dev run` can drive repeated requests through an existing agent CLI. Supply
`--agent-command` as a JSON executable/argument array with separate `{request}`,
`{response}` and `{workspace}` tokens. The controller replaces those tokens with
absolute paths. The command edits only the provided proposal workspace and writes
research-schema JSON to the response path. It must exit successfully before the
controller submits the proposal. The calling agent supplies its own model,
authentication, network tools and model-specific limits; Chili Crisp has no
embedded model API or automatic web-research backend.

`python tools/demo-development.py` exercises the complete protocol using a
deterministic proposer, two lossless-storage candidates and real subprocess
measurements. It is an integration fixture, not a demonstration of AI discovery.

## What is measured

The available objectives/guards are `wall_seconds`, `artifact_bytes`,
`sampled_peak_rss_bytes`, `sampled_cpu_seconds`, `sampled_io_read_bytes` and
`sampled_io_write_bytes`. Results retain platform, collector, runtime, source and
command metadata, sample counts, collector errors, bounded output and raw files.

Elapsed time covers the instrumented command and cleanup. Artifact bytes are the
logical size of explicitly selected files, not compressed transport size or disk
allocation. No selected artifact means unavailable, not zero. Missing paths fail
the measurement. RSS is a sampled sum across observed processes; shared pages may
be counted twice, and short-lived children or transient peaks can be missed.
CPU and I/O are sampled cumulative counters over observed processes; final work
after the last sample can be missed. I/O meaning varies by platform. These
qualifications follow the [psutil process API](https://psutil.readthedocs.io/stable/index.html).
Batch enough work to collect at least three samples when a sampled metric is an
objective or guard. Missing/insufficient measurements cannot qualify a candidate.

The exact benchmark stdout hash must remain stable across baseline, candidate
and confirmation. Pin the driver and representative input fixtures through
`protected_paths`; moving input oracles outside those paths weakens this contract.
Tests and repeated output equality cover the configured workload, not every
possible behavior. A small repeat count is a regression screen, not a statistical
proof or a universal performance claim.

Measured targets do not simulate CPU frequency, smaller instruction sets or
out-of-memory behavior. Optional Linux cgroup trials can confirm actual scarcity
without a new VM per candidate. The existing `runner`, `frontier` and `cpu-sweep`
remain available with their stronger enforcement/accounting contracts.

## Checkpoints, recovery and rollback

`state.json` is authoritative. Candidate decisions, retained-version references
and history change together through an fsynced atomic replacement. Each expensive
action is marked pending before execution. Raw comparisons and measurements live
under the session; source capsules are retained separately. A session lock prevents
overlapping mutations. Runtime executable changes and platform/collector/controller changes
require a new lineage.

```text
python -m chilicrisp dev rollback session initial --reason "Revisit the original tradeoff" --trusted-local
python -m chilicrisp dev recover session --owner-stopped
```

Rollback selects a retained source identity and rechecks/re-measures it before
changing the pointer. It preserves history. An interrupted action is never
automatically replayed. Verify that its executor has stopped before explicitly
recovering it. Recovery records the discarded attempt and keeps its reserved
command budget consumed. Unresolved process cleanup blocks further evaluation.

Command budgets are conservative reservations for top-level build/test,
benchmark and agent invocations, including failed or interrupted attempts;
unused reserved slots are not refunded. They are not counts of every subprocess
or model token used internally by an agent. The persistent wall deadline includes
time between invocations. Model-token/dollar budgets require the selected agent
provider to enforce them.

The local mode runs trusted code with host permissions and inherited environment.
Copies and hashes detect drift but do not isolate a hostile agent from controller
files. Retained experimental versions do not merge, deploy, publish or pass an
independent hidden grader automatically.

## Evidence precision and acceptance

Agent requests include `experiment_memory`: at most eight recent attempts with
controller decisions, targets, source identities and phase medians. Older attempts
remain in authoritative session state; the request reports how many were omitted.
This compact memory excludes research claims and raw logs. The existing
`previous_attempt` field remains available for detailed immediate feedback.
Repeated source submissions carry `repeat_of` generation IDs. They are measured
again under the current target, rather than silently counted as new code or
rejected solely for being identical. These fields do not detect semantic
equivalence across different source trees.

Every local measurement includes `metric_quality`. Artifact size has tier
`exact_declared_volume`: logical bytes under the selected-file policy. Wall time
has tier `repeated_timing` and needs repeated comparisons. Sampled RSS, CPU and
I/O have tier `screening_sample`; these cannot establish kernel-enforced survival
or exact process-tree consumption. Linux cgroup evidence is a separate contract.

Retained records carry verification markers. Public checks are labelled by
their baseline/confirmation or sampled-screening scope; `sealed: not_run` and
`production: not_accepted` remain explicit. Retention does not imply independent
hidden acceptance. No sealed-grader endpoint is implemented yet.

The [bounded real model pilot](../reports/model-source-pilot.md) demonstrates a
source-only proposal adapter followed by protected native evaluation. It remains
a separate harness; generic `dev run` still uses the trusted local execution
contract above unless the opt-in native backend is selected. The subsequent
[native controller fixture](../reports/native-development-validation.md) exercises
that bridge with scripted proposals and shrinking enforced budgets.

## Locus fit

The inspected `Z:\locus` repository provides expression rewriting, structural
advisors, proof/counterexample paths and evidence-labelled findings. Its evolution
module searches mathematical expressions using estimated costs; it does not own
an arbitrary repository's build/test/research/checkpoint loop. The useful design
references are its intent/objective separation and evidence/provenance discipline.
Locus can supply an optional cited research suggestion. It is not a dependency,
evaluation authority or replacement for this development controller. No Locus
source or project configuration was modified.

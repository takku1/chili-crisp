---
name: chili-dev
description: Run resource-guided software development with Chili Crisp's measured baselines, moving targets, research/proposals, correctness gates and retained candidates. Use for progressively smaller or faster implementations; not ordinary feature development without a resource objective.
---

Use Chili Crisp to turn a resource objective into a tested source change with
traceable evidence. The coding agent proposes and edits candidates; the tool
records observations. A passing public test comparison does not establish a
performance improvement or independent acceptance.

## Start

Run `python -m chilicrisp doctor` and `python -m chilicrisp capabilities` in the
environment where Chili Crisp is installed. If unavailable, locate the framework
checkout or installed executable. Do not assume the target repository contains
the framework. Install from the known checkout using the task's existing package
environment and permissions; do not download an unidentified package to resolve
a name collision.

Identify the target source directory, correctness tests, build command, resource
objective, regression limits, and experiment budget from the task and repository.
Resolve consequential missing requirements before dependent work. Resource
catalog entries are declarations, not successful host preflight. Unsupported
dimensions may be profiled with an appropriate tool, but must stay labeled as
unenforced observations.

## Build and compare candidates

For a repeated moving-target task, use the measured development loop first.
It runs on the current machine; Linux pressure enforcement is optional.

1. Turn the concept into a runnable baseline and an explicit behavioral contract.
   Infer ordinary details from the repository/task; resolve consequential unknowns.
   Create and pin correctness tests, representative fixtures and the benchmark
   driver before modifying candidate implementations. Keep benchmark stdout stable.
2. Initialize the project configuration, then write a development policy with
   `schema_version`, `concept`, `project_config`, `benchmark_command`, `objective`,
   and, for artifact volume, `artifact_paths`. Configure regression limits,
   repetitions, generations, stagnation and wall/command budgets for the task.
   Supported metrics are `wall_seconds`, `artifact_bytes`, `sampled_peak_rss_bytes`,
   `sampled_cpu_seconds`, `sampled_io_read_bytes` and `sampled_io_write_bytes`.
   Build outputs belong in excluded directories such as `build` or `target`.
3. Run `python -m chilicrisp dev init PLAN SESSION --trusted-local`, then
   `python -m chilicrisp dev request SESSION`. The request identifies the retained
   source, measured baseline, next target and protected files.
4. Research the limiting work using real sources and measurements. Create a
   separate candidate from the retained source. Record research JSON containing
   `hypothesis`, `mechanism`, `falsification` and `sources`; each source has a
   `reference` and `supports`. References are proposal evidence, not measurements.
5. Run `python -m chilicrisp dev submit SESSION CANDIDATE --research RESEARCH
   --trusted-local`. Inspect the decision and raw measurements. The controller
   runs correctness, paired exploration and fresh confirmation. It owns the
   retained pointer and derives the next target from measured confirmation.
6. Continue research/edit/submit while the task's budget and stopping policy
   permit. Failed candidates preserve the retained version and reduce the next
   challenge step. Stop on STOPPED state, unresolved cleanup or interrupted work.
   Use `dev status` to resume context, explicit `dev recover --owner-stopped`
   after checking no executor remains, and `dev rollback` to recheck/re-measure a
   retained version. These operations preserve history.

An existing agent CLI can drive this protocol with `dev run --agent-command`
and a JSON command array containing separate `{request}`, `{response}` and
`{workspace}` tokens. Use an actually configured agent, not an invented provider.
The current coding agent can also execute the loop directly without another
model service. Local CPU/RSS/I/O values are sampled; batch short workloads enough
for at least three samples when those metrics drive decisions. Measured targets
are not hard resource limits, and retained experimental candidates are not
automatic production promotions.

For a one-off correctness comparison, use the following lower-level workflow:

1. Preserve the baseline. Create a separate candidate checkout or source copy
   and record its parent identity. Keep existing user edits. Never weaken tests,
   accuracy requirements, or workload definitions to obtain a pass.
2. Configure the baseline with `python -m chilicrisp init ROOT --test-command
   JSON_ARGV` and, when needed, `--build-command JSON_ARGV`. Commands are JSON
   arrays of executable plus arguments, not shell strings. Use explicit runtime
   paths when environment selection matters. Review `.chilicrisp/project.json`;
   its root is relative to the configuration file. Existing files are not replaced.
   The tool pins inferred test files and the tests directory; add other correctness
   files with repeated `--protect PATH` arguments. Changes to these files reject
   the candidate. This protects accidental drift, not malicious host code.
3. Make a bounded candidate change tied to a hypothesis: expected resource
   effect, possible regressions, and a check that could disprove it.
4. For trusted source/build/test commands, run `python -m chilicrisp compare
   CONFIG --candidate CANDIDATE --output RUNS --trusted-local`. This executes
   commands with host permissions and inherited environment. Source snapshots
   are separate writable working copies, not security sandboxes. Do not use this
   mode for untrusted code or commands that detach background processes.
5. Run `python -m chilicrisp verify RECORD` and inspect `comparison.json` plus
   per-stage stdout/stderr. Verification checks saved logs and record integrity,
   not independent correctness. A failed baseline
   stops candidate evaluation. A failed candidate leaves source inputs unchanged.
   `public_tests_passed` means only the configured build/test commands passed.
   Build/test timings are diagnostics, not benchmark results.

The snapshot excludes `.git`, `.chilicrisp`, virtual environments, caches,
`node_modules`, `build`, `dist`, `artifacts`, `target`, and egg-info directories. Symlinks
and junctions are unsupported. Ensure required source files are not excluded;
prepare dependencies through the build command or an owner-provisioned runtime.
Do not assume a complete working environment was copied. Commands can still
write outside their workspaces because local mode is unconfined.

## Measure under pressure

The development controller also accepts an opt-in `evaluation` object with
`backend: linux_cgroup`, an owner-provided experiment `manifest`,
`benchmark_workload` ID and `initial_budget`. Use objective
`enforced_budget_bytes` and explicitly page-aligned `quantum`/`minimum_target`.
This native bridge rejects project builds and runs source only in a frozen
runtime, mounted read-only at `/candidate`; all candidate correctness workloads
and confirmation must pass at the new enforced limit. It records incumbent
pressure diagnostics and derives subsequent limits from accepted survival budgets.
Provision the runtime/oracles outside candidate source. Host benchmark/test argv
are unused here; `dev run --trusted-local` still trusts the selected agent
transport on the host. Native evaluation does not isolate an unrestricted agent
or compile untrusted build scripts. Retention remains experimental, with sealed
and production acceptance explicitly unset until an owner final gate is invoked.
An owner may pin `acceptance` campaign/public-key/policy/evaluator identities in
the initial native plan, export `dev acceptance-request`, privately run the
separate sealed grader, then import its signed verdict with `dev accept`.
Do not give the agent the vault or signing key. Final attempts are one-shot per
campaign; a verdict ends the lineage. Policy-verified champions are not deployed
or production-approved. See `docs/sealed-acceptance.md` in the framework checkout.
See the installed framework's
`docs/native-development.md` when working from its checkout.

For supported Linux pressure trials, use an owner-prepared experiment manifest,
frozen rootfs, public input/oracle, and delegated cgroup parent. These are distinct
from the local project configuration. Do not construct a rootfs by mounting the
host root. Run `python -m chilicrisp runner validate MANIFEST`, then `python -m
chilicrisp doctor --manifest MANIFEST`. Read-only preflight does not replace native
fixtures. If unavailable, retain local evidence and report the exact missing gate.

Run `python -m chilicrisp frontier MANIFEST` for memory exploration or `python -m
chilicrisp runner trial MANIFEST --workload ID --budget BYTES` for one point.
Retain raw evidence and summarize with `python -m chilicrisp pressure-map EVIDENCE`.
Never reinterpret a timeout as OOM, compare measurements across mismatched
conditions, or claim unsupported limits were enforced. Memory remains the only
adaptive frontier dimension. CPU bandwidth supports a predeclared grid:
`python -m chilicrisp cpu-sweep MANIFEST --quotas 100000 50000 20000 --period
100000 --budget 67108864 --repetitions 3 --seed 7`. Choose a fixed memory budget
appropriate to the target; the example's 64 MiB is not a universal default.
The tool overrides the manifest CPU pair for each selected quota. It requires
CPU delegation and rejects finite ancestor quotas. `COMPLETED` means the grid
ran, including any observed timeouts; inspect the individual outcomes. It does
not establish a CPU-time exhaustion boundary or accept an optimization.

## Stop and report

Respect declared run, wall-time, and model/tool budgets, including failed builds.
Stop on baseline failure, unsupported enforcement, unstable measurements, or
unresolved cleanup. `status RECORD` reads persisted comparison evidence; an
interrupted RUNNING record is not resumable or accepted. Inspect surviving
processes before retrying. For native journals use `recover` only after checking
that no active runner owns the trial.

Report the hypothesis, source hashes, changed behavior, actual correctness and
resource checks, evidence paths, observed tradeoffs, and remaining gates. Keep
unavailable metrics explicit. No automatic production integration is implemented: integrating
a candidate requires the task's acceptance evidence and existing authority.

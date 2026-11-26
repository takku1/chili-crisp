# Project status

**Last Updated:** 2026-11-25

## Current Phase

Concept reset: from enforcement-first research infrastructure to
**constraint briefs**. Agents design against an imagined machine, and Chili
Crisp checks the result on the ordinary machine. No VM is required.

## Active Focus

- `chilicrisp profiles | brief | check` and brief files
  ([concept](current/concept.md), [format](current/briefs.md)).
- Next: run the [A/B study](current/ab-study.md) (brief versus plain prompt,
  hidden inputs, hack rate per arm). Then let the
  [development loop](current/development-loop.md) take a brief directly.

## Architecture Summary

A brief (JSON or a built-in profile) declares a story, budgets (absolute or
relative to the baseline) and rules. `constraints.check` runs the candidate and
baseline alternately on the host, measures memory, time, CPU, I/O and artifact
size with psutil plus OS peak counters (or, opt-in on Linux, a systemd scope's
cgroup `memory.peak`), checks correctness on every declared input, flags files
left between runs, and returns `fits`, `over_budget`, `broken` or `incomplete`. The measured development loop (`chilicrisp dev`)
handles multi-round work with moving targets, checkpoints and rollback. The
Linux cgroup runner, isolated C/Rust builds and CPU sweeps remain as an optional
enforced tier.

## Key Decisions

- 2026-11-25: Constraints are a design instrument, checked by measurement on
  the host. Kernel enforcement is opt-in and only needed for adversarial
  grading.
- 2026-11-25: Budgets can be relative to the baseline (`25%`), so briefs are
  portable across machines.
- 2026-11-25: Three honesty levels: imagined, measured, enforced. They are never
  conflated in reports.
- 2026-11-25: Archived the enforcement-era design docs and validation reports.
  Removed 20 one-off research scripts and raw report dumps (still available in
  git history at `790326b`).
- 2026-11-25: Removed the signed sealed-grading gate (`dev accept`), the
  OpenEvolve/BenchExec bridges, separate-account trust fixtures and the
  Wilderbeast transfer pilot. Dependencies are now just jsonschema and psutil.
- 2026-11-25: Deleted local untracked `artifacts/` (old run output) and `.claude-flow/`.
- 2026-11-25: Enforced-tier commands (`runner`, `frontier`, `recover`, `build`,
  `cpu-sweep`, `pressure-map`) moved under `chilicrisp enforced`. The old
  top-level names still work but are hidden from `--help`, so scripts and the
  hash-checked `chili-dev` skill flows keep working.
- 2026-11-25: Trusting `fits` comes before new features. Following the reward-hacking
  findings (Sakana's AI CUDA Engineer, GSO), `check` flags files changed between runs and
  supports hidden held-out `inputs`. Added `--where` (tracemalloc sites near
  the peak), `--ratchet` (fail on regressions against saved numbers) and
  `--exact-memory` (cgroup peak through `systemd-run --user --scope`, no root).

## Deprecated/Legacy

- Enforcement-first design, protocol, roadmap and four-arm study plan:
  superseded by the brief concept. See
  [archive](archive/2026-11-25-enforcement-first-era/README.md).
- `reports/` directory: summaries archived; raw logs, JSON and patches are in git history.
- Wilderbeast, model-study and repository-cohort pilot harnesses: removed; their
  results are recorded in the archived reports.
- Sealed acceptance and the framework integrations: removed; their docs are in the archive
  (`sealed-acceptance.md`, `integrations.md`).

## Docs map

- [concept.md](current/concept.md): why and how
- [briefs.md](current/briefs.md): brief format, CLI, profiles, measurement limits
- [ab-study.md](current/ab-study.md): planned brief-versus-plain-prompt study
- [getting-started.md](current/getting-started.md) and [development-loop.md](current/development-loop.md): multi-round loop
- [enforced/](current/enforced/native-development.md): Linux cgroup runner, isolated builds, CPU

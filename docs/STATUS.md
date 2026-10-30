# Project status

Updated 29 October 2026 (America/New_York). This page supersedes historical
setup blockers in earlier reports.

## Delivered

- Installable package, versioned contracts, bounded output, lifecycle recovery,
  deterministic memory frontier and CPU quota grids.
- Persistent development loop with moving targets, public experiment memory,
  correctness gates, repeated confirmation and experimental retention.
- Native Linux evaluation with frozen runtimes and reproducible isolated C
  and offline, lockfile-pinned, vendored Rust/Cargo compilation.
- Signed sealed acceptance and matched-condition transfer; real Unix account
  separation, forged-receipt rejection and native C/trust fixtures reproduced
  on a fresh GitHub Actions host.
- Provider-neutral structured proposal transport and a bounded real-model
  comparison harness. See the [comparison report](../reports/model-comparison.md)
  for actual outcomes, usage, failed attempts and limitations.

The installed tool is usable for bounded owner-operated experiments. Retained
candidates remain experimental; a signed policy verdict does not authorize
production deployment.

Latest validation: 103 portable tests (101 passed, two Linux-only skips), clean
lint, successful package/wheel checks and four passing signed model-study
verdicts with all 56 sealed trials independently audited.

## Evidence and operation

Start with [getting started](getting-started.md), then
[native evaluation](native-development.md) and
[sealed acceptance](sealed-acceptance.md). The [reports index](../reports/README.md)
links the validation evidence. Native provisioners are intended for disposable
Linux labs and require owner privileges; model proposals receive public text,
while the controller and grader run under their respective Unix accounts.

## Remaining research and optional backends

The recent implementation handoff is separate from the broader research roadmap.
Still open: a separate grader host and authenticated network transport; portable
Rust toolchain provisioning in CI; representative repository tasks and adequately
powered comparisons; richer pressure maps and diagnostic probes; additional
resource backends and joint-axis search. See [the roadmap](roadmap.md) and
[resource capabilities](resources.md).

There is no automatic production promotion or deployment. One synthetic task
cannot establish that scarcity improves model optimization quality. Generated
native evidence and model transcripts live under ignored `artifacts/` and in
the owner-operated Linux lab; keep them alongside the versioned reports.

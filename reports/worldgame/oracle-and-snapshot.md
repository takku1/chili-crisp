# Worldgame oracle and snapshot preparation

The timing-sensitive stdout issue is resolved for this benchmark's declared output contract. The owner-side `worldgame_ocean_v1` comparator accepts all three saved baseline outputs, while checking the scientific records separately from timing diagnostics. The source snapshot also rebuilds independently of the original Worldgame directory on this Windows host.

## Comparator evidence

The policy fixes a 180 × 80 grid, four seasonal records, nonnegative finite conservation residuals at or below `1e-12`, and convergence with solver residual at or below `1e-7`. Those thresholds reflect the frozen benchmark's conservation check and `ocean.rs` solver tolerance. Solver iteration counts may change; timings and selected-buffer sizes are diagnostic fields rather than acceptance scores. The harness's own elapsed and memory counters remain the performance evidence.

[oracle-validation.json](oracle-validation.json) retains each saved output hash, parsed records, grading result, policy hash, and comparator implementation hash. All three outputs pass even though their timing fields and full stdout hashes differ. Portable negative tests reject bad conservation, unconverged seasons, duplicate/missing records, a changed grid, negative residuals, and non-finite values. They also verify that a manifest must select exactly one comparator mode.

The runner accepts either the original exact-output-hash mode or a structured oracle with a policy path and SHA-256 hash. It validates and loads that policy before target execution, rejects policies inside the target rootfs, records comparator identity, and writes grading details as `verification.json`. The owner must additionally protect the comparator and policy from the candidate agent's filesystem access; the schema alone does not provide that protection.

**Scope limit:** these are output-contract checks, not independent verification of the simulated fields. A malicious implementation could print acceptable summaries without computing the right simulation. Independent reference values, trusted test-harness execution, multiple seeds/scales, and sealed inputs are still required before accepting candidate optimizations. No production promotion is authorized by these checks.

## Frozen build inputs

The [source archive](worldgame-source-e3bb0485fe44c3f0.zip) contains 88 files: workspace Cargo manifests/lockfile, root README, and every file under `crates`, including modified and untracked source and data assets. [snapshot.json](snapshot.json) records its SHA-256, canonical file-manifest hash, each file hash, selected scope, and exclusions. The archive was reopened and every member's content verified against the collected hashes.

Every source hash present in the earlier baseline metadata matches the snapshot. Earlier metadata did not hash all non-Rust data assets, so historical identity for those assets cannot be established retroactively. This is a frozen source input set for subsequent comparisons, not a claim that a clean Git checkout reproduces the prior working tree.

The snapshot was extracted under Chili Crisp's `artifacts/worldgame-frozen`, and `cargo build --locked --offline --release -p mote-core --example oceanbench` succeeded using that extracted workspace. [snapshot-build.json](snapshot-build.json) records the command, source identity, and exit code; [snapshot-build.log](snapshot-build.log) records output. Build artifacts went to a separate Chili Crisp directory. Dependencies were available in this host's Cargo cache; the archive does not vendor dependencies or supply a Linux runtime image.

## Validation status

After this change, **23 test methods were discovered: 21 passed and 2 native Linux methods were skipped**. Archived evidence is in [the validation log](../oracle-snapshot/tests.log) and [run metadata](../oracle-snapshot/validation-run.json). Those tests cover parser behavior, policy/schema selection, and existing portable infrastructure. Full structured grading through a native Linux sandbox remains unexecuted. Later field checks are reported [separately](field-oracle-and-portability.md).

Linux enforcement, a Linux baseline, pressure diagnostics, independent physics grading, candidate changes, and transplant comparison remain the next gates. The future generation loop is specified in [the evolution contract](../../docs/evolution.md), with no `evolution.py` implementation yet.

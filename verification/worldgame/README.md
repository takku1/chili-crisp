# Trusted Worldgame field verification

This driver is owned by the experiment controller, outside candidate edit paths. It links a selected `mote-core` library and serializes actual public arrays. Changing a candidate's `oceanbench` print statements cannot change which arrays the driver reads. Keep the driver, input cases, reference data, and comparator protected by host access controls; this repository contains public development cases, not sealed grading inputs.

## Run on an available host

Install the pinned Rust 1.98.0 toolchain. With dependencies available, run:

```text
python verification/worldgame/check.py --source artifacts/worldgame-frozen
python verification/worldgame/check.py --source CANDIDATE_WORKSPACE --reference REFERENCE_RUN_DIRECTORY
```

The first run creates reference fields from the frozen baseline. The second independently builds the same owner driver against another library source. Freeze both source inputs before comparing. Builds and field outputs are isolated per invocation. This is correctness verification, not a timing or memory benchmark: serialization and temporary field copies intentionally perturb resource use.

Each ocean case reads depths, four seasonal streamfunctions, and four seasonal surface streamfunctions: **131,040 f64 values**. The current production ocean grid is fixed at 180 × 80; public cases vary world seed and planet radius, not that grid size. Manufactured solver cases use 17 × 17, 33 × 33, and 65 × 65 grids. They compare the solved field to a closed-form discrete solution of the forced Dirichlet Laplacian, computed independently in Python.

Comparison currently uses `abs(actual-reference) <= 1e-8 + 1e-8*abs(reference)`. These are provisional development thresholds; circulation fields have different units/scales. Validate per-field tolerances and cross-platform variation before candidate grading, then freeze them. Never widen tolerances after seeing a candidate merely to accept it.

The binary `CCFIELDS1` stream contains a u64 element count followed by little-endian f64 values. The decoder rejects summary text, non-finite values, truncation, and extra bytes. Tests also reject zeroed fields and individual numerical changes. This blocks the simple “print a successful summary” shortcut but is not proof against arbitrary benchmark specialization.

## Screening and finalist verification

`check.py` now accepts `--tier screen` or `--tier full` (the default).
Screening compiles the trusted driver and runs the 17×17 manufactured solver
first, followed by one generated ocean case. Full public verification runs all
six existing cases. Original case indexes are retained so both tiers compare
against the same frozen full-reference directory.

```text
python verification/worldgame/check.py --source TRUSTED_CANDIDATE --reference FULL_REFERENCE --tier screen
python verification/worldgame/check.py --source TRUSTED_FINALIST --reference FULL_REFERENCE --tier full
```

A failed screen returns exit code 1, records rejection evidence in `results.json`,
and stops before later cases. Each result records its tier, source hash, source
stability, build status, case outcomes, and wall durations. Reference case identity
and file hashes are checked before differential comparison. Passing either tier
is public correctness evidence only: `acceptance_eligible` remains false.

Only owner-reviewed sources belong on this host path. Rust builds can execute
build scripts; this verifier is not a sandbox for arbitrary model-generated code.
Candidate writes must not reach the driver, verifier, reference directory, or
acceptance policy. All example paths above must be owner-controlled.

For search, run the screen first and reserve the full relevant core tests,
all public field cases, independent held-out grading, resource measurements, and
normal-hardware transplant tests for finalists. Full acceptance orchestration
and the protected generation-to-build worker remain unimplemented. The existing
frontier controller is not changed by selecting a verification tier.

The [negative-control pilot](../../reports/screening-20261029T043608Z/REPORT.md)
compiled a source-changed solver that falsely retained its success report after
scaling solved values by 0.99. The independent manufactured oracle rejected it
on its first case. This is a test of rejection, not an optimization result.

## Runner adapter

Use oracle kind `worldgame_fields_v1` with an owner-controlled policy matching `schemas/field-oracle.schema.json`. The policy pins a reference file SHA-256, its expected element count, and numerical tolerances. The runner loads and hashes the reference before target execution, keeps it outside the rootfs, and records field-comparison results. An ocean output is 1,048,337 bytes; set the output limit above that size, for example 2 MiB. Full native-runner integration is not validated on this Windows host.

## Offline component build kit

`python verification/worldgame/package.py` prepares a kit from the frozen source and the trusted driver, vendors its seven registry crates, pins Rust, and verifies a frozen/offline build with an initially empty Cargo home and fresh target directory. `reports/worldgame/worldgame-portable-kit.zip` contains build inputs, source licenses, Cargo lock/configuration, and dependencies. It does not include compiler binaries, system linkers, libc, or a kernel.

On Linux, install Rust 1.98.0 for the Linux target and a compatible system toolchain, extract the kit, then run `cargo +1.98.0 build --frozen --offline --release` from its root. Record the actual compiler/target, linker/libc, base-image digest or VM image identity, kernel and isolation tool versions before trials. No Linux image or native enforcement result has been produced in this session. Use the kernel fixture gate in `docs/implementation.md` before attempting a pressure experiment.

## Coverage limits

Ocean field equivalence checks the frozen model, including its existing bugs; it does not independently establish physical realism. Manufactured solutions independently test the shared elliptic solver, not the ocean model's forcing or boundary discretization. Evolved heat/salt tracer fields, conservation after time evolution, multiple workload sizes, trusted input generators, and sealed cases remain required before accepting optimizations of the complete `oceanbench` workload. This driver currently narrows the prospective optimization target to circulation generation and the shared solver.

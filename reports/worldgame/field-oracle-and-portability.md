# Field oracle and dependency portability results

## What changed

The new controller-owned Rust driver reads numerical arrays directly from `mote-core`, instead of trusting the candidate benchmark's success summary. It was compiled against the frozen source twice and exercised on three public generated worlds plus three manufactured numerical problems. There was no candidate optimization in these runs.

| Check | Observed result | Supported conclusion |
| --- | --- | --- |
| Circulation fields, seeds 42/7/2026 and radius factors 1.0/0.8/1.2 | 131,040 finite values per case; repeated build/run comparison had maximum absolute difference 0 | These public frozen-baseline cases reproduce at field level on this host |
| Manufactured solver, 17 × 17 | Maximum absolute error 5.7282e-11 | Solved values agree with an independently calculated discrete solution |
| Manufactured solver, 33 × 33 | Maximum absolute error 8.7256e-11 | Same check at a second grid size |
| Manufactured solver, 65 × 65 | Maximum absolute error 9.6489e-11 | Same check at a third grid size |
| Offline dependency kit | Build exit 0 with initially empty Cargo home and fresh target directory | The component driver builds without this host's preexisting Cargo registry cache |
| Current portable Python suite | 26 test methods: 24 passed, 2 native Linux methods skipped | Covered portable policy/decoder checks pass; native enforcement remains untested |

## Independent mathematics and differential evidence

The manufactured problem is `-Laplacian(u) = 2*pi^2*sin(pi*x)*sin(pi*y)` on a unit square with zero Dirichlet boundaries. The trusted driver constructs the finite-difference stencil, calls the library's solver, and emits the computed solution. Python independently computes the discrete solution using the known eigenvalue `lambda_h = 8*sin(pi*h/2)^2/h^2` and amplitude `2*pi^2/lambda_h`. Grading uses values, not the library's convergence claim. Reported errors are against that discrete solution, not against an empirical Earth reference.

For the generated worlds, the driver emits depths, seasonal streamfunctions and seasonal surface streamfunctions. Numerical comparison against the frozen model uses provisional absolute/relative tolerances of `1e-8`. Negative decoder/comparison tests reject fabricated summary text, zeroed nonzero fields, changed values, wrong lengths, non-finite values and trailing bytes. These checks strengthen behavior verification; they are not an adversarial proof, and all current cases are public.

## Evidence files

- [Initial field references and analytic results](field-checks/20261029T015152519351Z/results.json).
- [Separate build/run differential results](field-checks/20261029T015224508710Z/results.json), including all six zero-difference comparisons.
- Raw field binaries and build logs are adjacent to those JSON records.
- [Offline component kit](worldgame-portable-kit.zip), [inventory/build provenance](portable-kit.json), [vendoring log](vendor.log), and [empty-cache build log](portable-build.log).
- [Current Python validation metadata](../validation-run.json) and [test output](../tests.log).
- [Driver, comparison tools, and usage/coverage notes](../../verification/worldgame/README.md).

The portable kit is 1,724,039 bytes and contains 565 files including the frozen source, trusted driver, seven vendored registry crates, lockfile, source-replacement configuration, and Rust 1.98.0 pin. The build used installed compiler/linker tools on Windows. It is source/dependency portable; it is not a validated Linux runtime image or a bit-reproducible binary guarantee. Cargo's [vendor mechanism](https://doc.rust-lang.org/cargo/commands/cargo-vendor.html) and the [toolchain pin](https://rust-lang.github.io/rustup/overrides.html) provide the dependency/toolchain controls used here.

## Remaining gates

The field driver currently covers **circulation generation and the shared elliptic solver**, not the evolved heat/salt transport state exercised by the full ocean benchmark. Independent physical references, transport-field equivalence after stepping, more workloads, per-field tolerance validation, and owner-sealed cases remain incomplete. No source optimization should be promoted on the basis of these public checks alone.

The current environment still cannot supply native Linux enforcement evidence. There is no measured Linux passing budget A or failing budget B. To produce that result, the next host must establish a recorded Linux build/runtime identity, pass the hostile runner fixtures, build its own baseline, and collect actual cgroup counters. Windows working-set numbers are not substituted for those measurements.

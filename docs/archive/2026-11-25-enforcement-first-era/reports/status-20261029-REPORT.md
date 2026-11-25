# Chili Crisp status — 29 October 2026

Chili Crisp has a working portable contract suite and a reproducible Worldgame
field-verification path. It is not yet a validated end-to-end resource-pressure
optimization system. No memory improvement, speedup, or accepted candidate is
established by this run.

## Results

| Check | Result | Meaning |
| --- | --- | --- |
| Chili Crisp Python tests | 36 passed, 2 native tests skipped | Portable schema, frontier, lifecycle, output capture, oracle, and adapter behavior passed. |
| Adapter lint | Passed | Scoped to integrations, their tests, and setup.py; not a whole-repository lint claim. |
| Example experiment | Passed | Schema-valid template; its placeholder paths and hashes do not configure a real experiment. |
| Source distribution and wheel | Built through setuptools fallback | Artifacts exist under `dist/`. |
| Wheel schema smoke test | Passed | Extracted wheel loaded its own modules and schemas outside the source checkout; not a fresh-environment dependency-install test. |
| Standard PEP 517 frontend | Blocked | Managed Windows temporary-directory ACLs cause PermissionError. |
| Distribution metadata check | Unavailable | Twine is not installed locally. Hosted CI was not executed. |
| BenchExec fixture probe | Unsupported here | Windows host; no native BenchExec fixture ran. |
| Linux access | Blocked | WSL enumeration: E_ACCESSDENIED. Docker engine pipe: permission denied. |
| Trusted Worldgame field driver | All six cases passed | Fresh offline release builds against baseline and `Z:\worldgame`. |
| Worldgame `mote-core` suite | 201 passed, 0 failed, 2 ignored | 191 unit tests plus 10 astronomy integration tests; no doc tests. |

## Worldgame evidence

The trusted driver used Rust 1.98.0, building into Chili Crisp's artifact directories.
The candidate source was `Z:\worldgame`; the baseline was
`artifacts/worldgame-frozen`. No source edits were made to Worldgame.

The broader core test command used `cargo +1.98.0 test --offline --locked` with
`-p mote-core` and an explicit target directory under Chili Crisp. All 201 executed
tests passed. The unit-test phase took 194.49 seconds in a debug build; this is a
test duration, not a latency regression measurement. The source tree's two ignored
tests are `climate::tests::equator_seam_report` and
`planet::sweep_tests::sweep_seeds_for_finder_panics`, both declared diagnostic
sweeps; they remain excluded from this claim. These in-repository tests supplement the
independent driver; they do not expand the driver's scientific coverage by themselves.

| Case | Values checked | Maximum absolute difference from baseline |
| --- | ---: | ---: |
| Ocean, seed 42, radius scale 1.0 | 131,040 | 0 |
| Ocean, seed 7, radius scale 0.8 | 131,040 | 0 |
| Ocean, seed 2026, radius scale 1.2 | 131,040 | 0 |
| Manufactured solver, 17 × 17 | 289 | 0 |
| Manufactured solver, 33 × 33 | 1,089 | 0 |
| Manufactured solver, 65 × 65 | 4,225 | 0 |

All 398,723 serialized values matched, including identical output hashes.
The largest error against the independently computed manufactured-solution
reference was approximately **9.65 × 10⁻¹¹**, within the existing comparison
tolerance `1e-8 + 1e-8 * abs(reference)`.

The tested `mote-core` trees, workspace manifests, and original Cargo lockfiles
were identical between the live candidate and frozen baseline. Hashes were also
unchanged before and after the field runs. Therefore this is a reproduction
check against the same core source, not evidence that a new implementation is
equivalent or better. Worldgame has other uncommitted changes; this report does
not validate the full game, renderer, or those changes.

The candidate source hashes were checked again after the full core suite and
remained unchanged.

These are public circulation and manufactured shared-solver cases. They do not
establish full transport correctness, physical realism, hidden-test acceptance,
or constrained-runner isolation. Build/check wall durations are diagnostics,
not performance benchmarks: field serialization deliberately perturbs resources.

## Framework readiness

- **OpenEvolve:** installed 0.3.2; its real EvaluationResult type passed adapter
  tests. Successful resource trials in those tests are simulated. The real Windows
  runner returned unsupported and received zero score. No model-generated source
  was built or optimized in this run.
- **BenchExec:** optional Linux dependency, not installed on this host. The probe
  is separate from the experiment runner. No native compatibility conclusion is
  possible yet.
- **Frontier controller:** portable policy tests pass. Real cgroup OOM boundaries,
  process cleanup, output enforcement, and native recovery remain unverified here.
- **Generation and acceptance:** protected automatic builds, independent grading,
  normal-hardware transplant acceptance, champion promotion, rollback, and two
  consecutive moving-frontier generations remain unfinished.

## Recommended next work

1. Make an unprivileged Linux research host available with delegated cgroup v2 and
   namespaces. Run the existing native suite with `CHILI_FIXTURE_MANIFEST`.
2. Compare BenchExec against the current runner using the same fixture/runtime;
   resolve output-cap enforcement, mount exposure, counters, and recovery before
   switching execution backends.
3. Connect a protected candidate build/freeze worker to OpenEvolve. Keep oracle and
   acceptance policy outside candidate write access.
4. Demonstrate a changed candidate with independent correctness and transplant
   checks, then exercise promotion, rollback, and two moving-frontier generations.

## Reproduce and inspect

`python reports/run-status-check.py` collects checks and raw logs in a fresh
timestamped directory. It currently uses `Z:\worldgame` as the candidate.

- [Commands, exit codes, versions, source hashes, and artifact hashes](results.json)
- [Python test log](unit-tests.log)
- [Worldgame core and astronomy test log](worldgame-core-tests.log)
- [Baseline field evidence](../worldgame/field-checks/20261029T041033487475Z/results.json)
- [Candidate field evidence](../worldgame/field-checks/20261029T041041743646Z/results.json)
- [Build log](setuptools-build.log)
- [Wheel smoke log](wheel-smoke.log)

The session used Python 3.12.10, jsonschema 4.26.0, OpenEvolve 0.3.2, setuptools
78.1.0, build 1.5.0, and Ruff 0.16.4. Existing production code and acceptance
thresholds were unchanged during this verification task.

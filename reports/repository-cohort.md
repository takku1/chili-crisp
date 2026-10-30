# Real-repository cohort and first pilot

29 October 2026 (America/New_York). All three supplied projects were inspected,
selected components were frozen, and their local baselines passed. The first
bounded Wilderbeast candidate reduced sampled peak RSS by 11.3% and was retained
experimentally. No original project was edited and no candidate was promoted.

## Qualified components

| Project | Frozen workload | Correctness | Median process wall seconds | Median sampled RSS MiB |
| --- | --- | --- | ---: | ---: |
| Wilderbeast | Batch-persist 8,000 discovery receipts | 41 tests and independent roundtrip | 0.250 | 36.40 |
| MochiOS | Component resolver; independent and chained graphs of 32/128/512 components | 7 tests, including exhaustive four-node graphs against an independent reference | 0.235 | 5.41 |
| Worldgame | GPU-free `mote-core` ocean benchmark | 201 core/reference tests passed; two ignored; budget residual checks passed | 2.594 | 60.48 |

Each workload ran three times in seeded shuffled order, one measured process
at a time. These are different workloads, not comparable project scores.
Measurements include process startup and harness overhead. They are trusted
Windows host samples, with no enforced scarcity. RSS sampling is incomplete
and may double-count shared pages; short-run timings are screening evidence.
No confidence interval, speedup, or cold-cache result is claimed.

Source parents were Wilderbeast `6188870`, MochiOS `b3f44a40`, and Worldgame
`86718e3`. All had uncommitted changes. Snapshots include those component files,
not merely their parent commits. The source manifests and per-file hashes are
retained in `artifacts/repository-cohort-20261030T015159Z/cohort.json`.
Only generated caches/working outputs were omitted. Rust workspace membership
was narrowed by an owner build adapter, leaving library source unchanged;
workspace package/dependency/lint/profile declarations were retained. Narrowed
lockfiles were generated offline, then builds/tests used `--frozen` with Rust
1.98.0. This is a host component qualification, not a MochiOS boot/kernel test.

The initial sandboxed qualification failed on temporary-file permissions and
its logs remain under each component's `qualification/`. The successful retry
is under `qualification-owner/`. None of those environment failures was treated
as a project regression. The [summary JSON](repository-cohort.json) records
environment, hashes, exact test counts, sample counts and measurement medians.

## First target: Wilderbeast archive serialization

Wilderbeast is the first memory target because its archive uses only Python's
standard library and has a narrow editable boundary. Machine CEGIS remains
unfinished in the upstream project; it was excluded as an optimization target.
Only `src/wilderbeast/evidence/archive.py` was editable. Other source, existing
tests and the new owner workload/check driver were protected by the controller.

The separate allocation diagnostic observed about 14.86 MB of live traced
Python allocations at archive JSON encoder entry, including approximately
2,125 KiB of receipt dictionaries, 1,437 KiB of wrapper dictionaries and
562 KiB of copied provenance lists. This supports a transient-materialization
hypothesis, not a claim that all process memory comes from serialization.
Tracemalloc snapshots perturb execution; they were excluded from ordinary
performance measurements. Raw diagnostic: `wilderbeast/allocation-probe/profile.json`.

Before the edit, the one-candidate policy declared a 10% sampled-RSS target and
a maximum 25% median wall-time regression. The candidate replaces the temporary
list of every serialized dictionary with a lazy list subclass consumed by
`json.dump`. It preserves the atomic temporary-file/replace flow and existing
failure rollback. The [retained patch](wilderbeast-archive.patch) is against the
frozen uncommitted archive version, not necessarily current upstream HEAD.

The actual Chili Crisp development controller performed baseline correctness,
three initial measurements, three paired exploration blocks and three fresh
paired confirmation blocks. Confirmation medians were:

| Metric | Baseline | Candidate |
| --- | ---: | ---: |
| Sampled peak RSS | 38,277,120 bytes | 33,951,744 bytes |
| Observed wall time | 0.250 s | 0.250 s |
| Sampled CPU time | 0.21875 s | 0.21875 s |

The observed RSS difference is 4,325,376 bytes (4.13 MiB), or 11.3%. Coarse
wall-time agreement does not prove zero latency impact. Existing tests cover
archive roundtrip/filtering, failed atomic replacement with memory/disk rollback,
temporary-file cleanup and corrupt-file rejection. The protected owner check
also validates all 8,000 receipt payloads and metadata after reload. Additional
public checks at 0, 1, 257 and 20,000 records produced matching logical hashes.

Decision: `accepted_experimental`; sealed grading was `not_run` and production
was `not_accepted`. This was an owner-reviewed edit by the current agent, not a
matched real-model scarcity/conventional experiment and not evidence of
scarcity's benefit. The bounded pilot stopped at its one-generation cap.
Its first setup attempt rejected generated egg-info metadata as an invalid
protected path; the corrected attempt excluded snapshot-ineligible metadata.
Both setup directories are retained; the first made no submission.

## Next comparison design

Use the same frozen component and identical correctness contract for both arms.
Freeze representative input sizes and private grading cases before model use;
match model configuration, proposal-call counts, token/time caps, edit boundaries,
and normal profiler information. Separate search information from final grading.
Record rejected candidates and actual consumed effort. Fresh confirmation and
normal-condition transfer must precede any upstream integration.

Wilderbeast is the first native pressure port. Its archive workload needs
bounded writable scratch space, and tmpfs charges must be included in the
accounting contract. Sampling evidence here does not substitute for that gate.
MochiOS's dependency-free resolver is the second task; larger graph sizes and
allocation measurements should make memory differences visible above startup.
Worldgame remains the strongest numerical task, but its full ocean benchmark
calls threaded river generation. The current single-process runtime seccomp
policy disallows thread creation. Narrow to the independently verified serial
circulation/solver workload, or implement and validate a dedicated thread policy
before calling the full benchmark a native scarcity experiment. Evolved
heat/salt tracer equivalence also needs stronger coverage than printed residuals.

## Reproduce

```powershell
python tools/prepare-repository-cohort.py
python tools/qualify-repository-cohort.py COHORT --label qualification-owner
python tools/profile-wilderbeast-archive.py COHORT/wilderbeast/baseline PROBE_OUTPUT
python tools/run-wilderbeast-pilot.py COHORT --name local-pilot-2
python tools/summarize-repository-cohort.py COHORT reports/repository-cohort.json
```

The pilot also writes its public size checks and patch. All candidate/source copies and raw output stay
under ignored `artifacts/`; the original three repositories remain untouched.
New harness scripts pass Ruff. The actual frozen project builds/tests, owner
workload and paired controller measurements provide their integration checks.

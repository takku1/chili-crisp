# Chili Crisp: initial implementation validation

## Main finding

The available output shows that the portable control and evidence-handling code passes its current checks. It does **not** yet show that Chili Crisp enforces real Linux memory limits, improves an application, or helps an AI discover better architectures.

This report separates executed checks, synthetic controller behavior, and untested capabilities. There is no real component baseline/candidate comparison in the available evidence.

## Evidence collected

For this report, `python reports/collect.py` reran the test suite and manifest validator, saved their output, recorded the host/Python environment and source SHA-256 hashes, and generated an explicitly synthetic frontier trace. Exact collection time is in [archived validation-run.json](initial/validation-run.json). These artifacts preserve the initial implementation; later fixes are reported separately.

| Check | Observed result | Meaning |
| --- | --- | --- |
| Unit/portable test suite | 13 test methods discovered: 11 passed, 2 skipped; exit code 0 | The executed checks met their assertions. Skips are not successful Linux trials. |
| Example manifest validation | Exit code 0 | The template matches the schema and cross-field budget policy. Host paths, rootfs identity, and native support were not validated. |
| Native Linux failure fixtures | Skipped | No measured OOM, native timeout, namespace, or cgroup-cleanup result is available. |
| Real optimization study | Not performed | No memory saving, speedup, transfer result, or improvement-per-dollar can be calculated. |

See [archived tests.log](initial/tests.log) and [manifest-validation.log](initial/manifest-validation.log). The example manifest's zero hashes and placeholder build identity describe a template, not a built and verified target.

## What the passing checks tell us

| Area | Executed evidence | Practical interpretation and limit |
| --- | --- | --- |
| Manifest constraints | Host networking and an unknown privileged field are rejected; an invalid budget relationship is rejected | These particular invalid requests cannot pass validation. This does not prove every malformed manifest is rejected. |
| Frontier policy | A synthetic threshold yields a passing/failing bracket; trial caps stop search; a mixed pass/OOM point stops as inconclusive | The policy handles the covered deterministic cases without treating noise as a clean boundary. It has not been tested against real kernel variability. |
| Controller failure handling | An injected `cleanup_failure` stops further scheduling | Control flow honors that result. The fixture does not actually kill or remove a Linux cgroup. |
| Bounded output storage | A 100,000-byte in-memory stream retains only 128 bytes while detecting overflow; an actual flooding Python subprocess retains 1,024 bytes before the test kills it | The collector caps retained output in these cases. The flooding subprocess runs as a portable fixture, outside the native sandbox. This does not validate the runner's complete overflow-to-cgroup-termination path. |
| Lifecycle persistence | Illegal transition rejected; `RECOVERY_REQUIRED` survives a file round trip | Journaling works for the covered orderly operations. No controller-crash or power-loss experiment was performed. |
| Unsupported execution | A mocked preflight failure yields schema-valid evidence, zero target invocations, and a finalized lifecycle | The runner records this injected failure correctly. This is not an independent audit of real host preflight. |
| Unfinished-run blocking | A deliberately unfinished journal prevents a new trial | The next run will not silently treat that evidence directory as clean. Concurrent controllers are unsupported. |

## How to read the frontier output

[synthetic-frontier.json](initial/synthetic-frontier.json) contains a controller simulation using a deliberately supplied rule: **pass at budgets of at least 32,768 bytes; report synthetic OOM below that**. No program was memory-limited during this simulation. The word `oom` in this artifact is generated input to the policy, not a kernel event.

| Proposed budget | Supplied outcome | Repetitions |
| --- | --- | --- |
| 65,536 bytes (64 KiB) | Pass | 2 |
| 49,152 bytes (48 KiB) | Pass | 2 |
| 24,576 bytes (24 KiB) | Synthetic OOM | 2 |
| 36,864 bytes (36 KiB) | Pass | 2 |
| 32,768 bytes (32 KiB) | Pass | 2 |
| 28,672 bytes (28 KiB) | Synthetic OOM | 2 |

The policy used 12 synthetic trial outcomes and then returned `INVENT`, with reason `resolution_or_floor`. Its passing point is 32 KiB and its failing point is 28 KiB. This demonstrates descent, confirmation, and local refinement on a known threshold. `INVENT` is permission to begin hypothesis work; it does not mean an invention occurred.

The final bracket is **12.5% wide**, despite the configured 5% tolerance. The controller rounds budgets to 4 KiB pages; the next proposed midpoint rounds back to an already tested budget, so it stops at available resolution. This is an expected limitation of this small synthetic example, and illustrates why the stop reason must accompany the bracket. The simulation uses two confirmations per point; the pilot template uses ten. These synthetic byte limits are not recommended budgets for Python or bubblewrap.

## What is still unknown

The native test methods require Linux, delegated cgroup v2 controllers, an explicitly prepared fixture rootfs, bubblewrap, and libseccomp. They were skipped on this Windows host. Earlier Docker and WSL access attempts were denied. Therefore this report cannot establish that limits are enforced, kernel counters are collected correctly, target processes cannot escape isolation, or recovery cleans up real orphaned tasks.

It also cannot establish whether pressure diagnostics identify an application's bottleneck, whether an architectural change preserves independent required behavior, whether benefits survive normal-hardware execution, or whether scarcity beats conventional optimization under matched budgets. There are no recorded model-token or optimization-cost observations from which to estimate economics.

## Next evidence needed

1. Run the native fixtures on a disposable Linux research host. Require normal output, wrong output, timeout, output flood, OOM, and injected cleanup/recovery cases to pass, with raw counters and journals retained.
2. Independently check namespace/filesystem/network isolation and process-tree termination. Passing the current fixture tests alone is not a complete security review.
3. Measure one real component's unrestricted baseline and pressured trials across input scales. Report pass rates, latency, memory composition, and accounting qualifications.
4. Compare a frozen candidate against that baseline, including independent correctness and normal-hardware checks. Only then report an optimization benefit.
5. Use the controlled arms in the [roadmap](../docs/roadmap.md) to evaluate whether the discovery method adds value beyond ordinary profiling and optimization.

The current evidence supports continuing with native runner validation. It does not support a claim that Chili Crisp has already optimized software.

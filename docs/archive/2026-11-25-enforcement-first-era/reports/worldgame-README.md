# Worldgame pilot: first real baseline

## Finding

`Z:\worldgame` is a suitable candidate for a first component-level pilot. Its GPU-free `mote-core` ocean benchmark built successfully and completed three normal Windows runs. All runs exited with code 0 and passed the benchmark's built-in water, salt, and heat conservation checks. A separately executed release test filter also passed 22 ocean-related tests.

This is a real application baseline, **not a constrained-memory experiment or an optimization result**. Worldgame source was left unchanged; compiled artifacts are under Chili Crisp's `artifacts/worldgame-target`.

## Measured results

The fresh release executable runs a default generated planet, a 180 × 80 ocean grid, a seasonal circulation solve, and 48 water-system steps of 1,800 world-seconds each.

| Run | Whole-process elapsed | Windows peak working set | Windows peak committed memory | Reported seasonal solve | Reported transport/step |
| --- | --- | --- | --- | --- | --- |
| 1 | 2.578 s | 61.27 MiB | 66.02 MiB | 0.365 s | 2.248 ms |
| 2 | 2.500 s | 60.73 MiB | 66.42 MiB | 0.355 s | 2.033 ms |
| 3 | 2.516 s | 60.10 MiB | 65.93 MiB | 0.361 s | 2.113 ms |

Whole-process median elapsed time was **2.516 seconds**. The peak-working-set range was **60.10–61.27 MiB**. These are three sequential runs on one host with uncontrolled cache state, not enough to establish a performance confidence interval or production requirement. Collection adds polling and output-handling overhead; whole-process elapsed includes that handling and is distinct from the benchmark's internal timers.

Memory comes from Windows `GetProcessMemoryInfo`: `PeakWorkingSetSize` and `PeakPagefileUsage` (peak committed memory). They are single-process counters and **are not equivalent to Linux cgroup charged memory or an enforced memory limit**. See Microsoft's [counter definitions](https://learn.microsoft.com/en-us/windows/desktop/api/psapi/ns-psapi-process_memory_counters). The collector samples lifetime peaks, so it does not estimate the peak merely from sampled current working-set values. If the process ends before a successful read, the metric must remain unavailable.

## Correctness evidence

All three runs printed the same numerical residuals: water `0.000e0`, salt `5.985e-16`, and heat `1.971e-15`. The existing benchmark fails if any conservation residual exceeds `1e-12`. Each of the four seasonal solver reports said `converged: true`, with matching iteration counts and residuals across the three runs.

The benchmark also prints **2.32 MiB of selected retained ocean field buffers**. This figure counts selected arrays after setup. It excludes other state and transient generation costs, while the Windows peak is a whole-process lifetime measure. Their difference does not establish a leak, an inefficient object graph, or a removable allocation.

The existing ocean-related test filter passed **22 tests, 0 failures**, with 171 other library tests and 10 integration tests filtered out. This was not a full workspace test run. Existing tests and self-checks are useful starting evidence; they are not an independent hidden oracle and do not prove physical accuracy across inputs.

## Provenance and raw data

- [Baseline metadata, binary hash, source revision/status and Rust-source hashes](run-20261029T013847905892Z/baseline.json).
- Raw stdout: [run 1](run-20261029T013847905892Z/1/stdout), [run 2](run-20261029T013847905892Z/2/stdout), [run 3](run-20261029T013847905892Z/3/stdout). Stderr was empty in all three runs.
- [Ocean-related test output](ocean-tests.log) and [exact test command/exit status](ocean-tests.json).
- [Windows baseline collector](collect.py).

The build used `cargo build --locked --offline --release -p mote-core --example oceanbench` against Worldgame's manifest with an isolated target directory. The source tree already contains modified and untracked files, including `oceanbench.rs`; the commit ID alone cannot reproduce this state. The metadata therefore includes the working-tree status and Rust-source hashes. No source snapshot or portable Linux rootfs was created, so full external reproduction still requires freezing the actual source/dependency assets and environment.

## Important oracle issue discovered

**Follow-up:** the [oracle and snapshot preparation report](oracle-and-snapshot.md) documents the implemented comparator, its validation limits, and the frozen build snapshot. The paragraphs below describe the issue found during the original baseline.

The benchmark writes timings to stdout. Its full stdout hash therefore changes between correct runs, as the raw metadata confirms. Chili Crisp's current exact-stdout-hash verifier cannot use this command directly as a correctness oracle.

Before the constrained pilot, freeze an owner-controlled wrapper/comparator that separates performance fields from deterministic scientific outputs and independently checks conservation, solver convergence, and selected reference values. Do not simply discard all variable output or let the candidate edit the grading logic. Keep existing conservation checks and add multiple seeds/input sizes and sealed cases. A Linux build will need its own baseline and numerical tolerance policy.

## Next experiment

First complete Linux runner validation with the hostile fixtures. Then freeze a GPU-free Worldgame component artifact and independent oracle, build a Linux baseline, and let the controller derive its starting limit from measured cgroup peaks. Diagnose the earliest pressure region before proposing a source change. The current evidence identifies a practical pilot workload; it does not identify an architectural optimization yet.

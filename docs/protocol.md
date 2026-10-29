# Memory experiment protocol (v0.1)

The [runner contract](engineering-contract.md) is mandatory for launch, preflight, cleanup, adaptive decisions, and hidden-test handling. Apply the [invention protocol](invention.md) before candidate edits. Percentages below are configurable starting defaults.

This protocol defines an experiment, not a universal RAM requirement for a codebase. The frontier is conditional on a frozen build, workload, kernel, cgroup configuration, hardware, timeout, and correctness oracle.

## Preconditions

- Linux host with cgroup v2 memory controller delegated to the runner; the runner can create a fresh cgroup for each trial and set `memory.max`.
- Target can run independently under a pinned build and command. The controller and verifier remain outside the target cgroup.
- Public workloads cover at least small, representative, large, and adversarial cases. A separately controlled workload or input generator is reserved for confirmation.
- A frozen behavioral specification, reference implementation, or regression suite can grade the target. Existing behavior and intended behavior are recorded separately where they differ.
- Environment policy declares swap, page cache and warmup state, concurrency, external services, filesystem use, process spawning, timeouts, and what is charged to the target. Different policies produce different frontiers.

If these conditions are unavailable, return **unsupported experiment** with the missing precondition. Do not substitute process RSS for an enforced cgroup memory frontier.

## Metrics and outcome classes

| Item | Source | Interpretation |
| --- | --- | --- |
| Enforced budget | `memory.max`, read back after setting | Hard limit, subject to kernel behavior and page-size rounding |
| Peak charged memory | `memory.peak` from a fresh cgroup | Peak cgroup usage, not process RSS or proof of a minimal requirement |
| Composition | `memory.stat` | Anonymous, file-backed, and kernel categories; parse by key |
| Pressure and OOM | `memory.events` and, if useful, PSI | Reclaim/OOM evidence; events alone do not grade correctness |
| Correctness | Independent verifier | Required behavior for this workload |
| Runtime | Monotonic elapsed timer | Latency under the declared timeout and cache policy |
| I/O and CPU work | cgroup accounting or qualified hardware counters | Secondary tradeoffs with their own provenance |

Classify every trial as `pass`, `wrong_output`, `timeout`, `oom`, `build_failure`, `runner_failure`, or `inconclusive`. A nonzero exit is not automatically OOM; compare exit status with cgroup events. A `memory.max` event without an OOM kill does not automatically mean failure. Preserve raw stdout, stderr, counters, and verifier output.

Linux describes cgroup memory accounting as broad but not fully watertight. `memory.max` may be exceeded briefly and may trigger reclaim before an OOM kill. `memory.peak` is a peak of charged usage, including descendants, and its reset behavior depends on the file descriptor. Fresh cgroups per trial avoid stale peaks and event counters. [Kernel cgroup v2 documentation](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)

## Adaptive search

### 1. Fingerprint, then establish a passing start

Run the unrestricted baseline across each public workload several times. Record the largest observed `memory.peak` for the workload under the declared cache policy. Propose an initial limit `B0 = ceil_page(Pmax × (1 + margin))`, with a **proposed** 10% margin. Verify `B0` with constrained runs. The formula is a starting guess only: if it fails, increase the limit until a stable passing point is found or the trial budget is exhausted. A measured peak below a limit does not guarantee a pass, and a limit below the unconstrained peak can still pass after reclaim.

Do not pool unlike workloads into one unexplained “project size.” For a target with several workload classes, retain a frontier for each class and state whether the reported aggregate requires all classes to pass.

### 2. Descend quickly

From the verified passing budget, test `Bnext = ceil_page(0.75 × Bcurrent)` as a proposed default. A single discovery trial can screen a budget; do not label it a confirmed frontier. Stop descent at the first repeatable failure or a predeclared floor, cost cap, or experiment limit. If a trial is inconsistent, repeat it and mark the region noisy instead of assuming monotonicity.

### 3. Refine only when useful

When a passing and failing region has been observed, test the geometric midpoint `ceil_page(sqrt(Bpass × Bfail))`. Continue while the region is broad enough to change the next hypothesis and the trial budget remains. A proposed 5% relative gap is a convenience threshold, not an accuracy guarantee. If outcomes violate the apparent pass/fail order, sample a small local grid and report pass rates; do not force binary search onto noisy results.

For each important boundary point, use a predeclared confirmation count and report `passes / trials` plus failure types. Ten trials is a reasonable pilot setting, not a statistical confidence guarantee. The exact count should follow observed noise and experiment cost. Keep both pressure latency and hard functional failure visible: a target can remain correct while becoming unusably slow.

### 4. Search for a design, then retest

Select a pressure point that separates the baseline from a plausible candidate. Before source changes, write a cost hypothesis, predicted tradeoffs, and a test that could disprove it. Run candidates under the same frozen inputs and build policy. After a candidate survives screening, repeat the boundary measurements and run hidden inputs and normal-hardware tests. Do not accept a candidate solely because it passes at one tiny limit.

## Optional workload-size model

For components whose meaningful input size can be measured, collect peaks at at least three input scales and validate on a held-out scale. A model such as `M(n) = M0 + a·n^p` may help distinguish fixed startup cost from growth cost, but it is an empirical hypothesis, not a guaranteed scaling law. Reject the fit if it predicts the held-out measurement poorly or if workload composition changes. The model can prioritize an experiment; actual constrained runs establish the frontier.

## Stopping conditions

Stop with an explicit result when baseline behavior is unstable, the runner cannot enforce the declared policy, the frontier is too noisy to guide a change, the time or trial budget expires, or no candidate clears the acceptance gates. “No verified improvement within scope” is preferable to a speculative win.

# System constraints

The target is an experiment engine for multiple system constraints. Memory is
the first searchable resource in the current runner. A resource has three
separate roles: an enforced limit, an observed measurement, and an environmental
condition. No role implies either of the others.

Run `python -m chilicrisp capabilities` for implementation declarations.
This command does not run host preflight or certify enforcement.

| Dimension | Current implementation | Next backend requirement |
| --- | --- | --- |
| Memory | cgroup limit and peak; frontier search | Native enforcement fixtures |
| Swap | Disabled | Explicit swap experiment policy |
| Wall time | Trial and experiment deadlines | Latency distribution and transfer gates |
| Processes | Task cap; pilot syscall policy prevents spawning | Separate threaded/process runtime policy |
| Descriptors | Descriptor cap | Exhaustion classification |
| Scratch | Bounded tmpfs | Separate disk-backed storage adapter |
| Output | Per-stream capture cap | Keep evidence transport distinct from target I/O |
| Network access | Disabled | Controlled topology and endpoint fixtures |
| CPU bandwidth | cgroup quota/period; repeated grid sweep; usage/throttling counters | Transfer acceptance and adaptive CPU policy |
| CPU time | Not independently limited | Aggregate accounting and CPU-time termination |
| Persistent storage | Unsupported | Protected volume quotas and filesystem metadata |
| I/O bandwidth and operations | Unsupported | Device identity, controller delegation, cache controls |
| Network bandwidth | Unsupported | Shaping, latency/loss policy and independent counters |
| GPU memory/compute | Unsupported | Device isolation and vendor-specific accounting |
| Energy | Unsupported | Calibrated counters and attribution policy |

Scratch tmpfs consumes memory. Output capture adds controller work. CPU quotas
can increase elapsed time without increasing CPU time. Cache changes affect
both memory and I/O. Record these interactions; do not attribute a failure to a
resource from its symptom alone. A timeout remains a timeout unless independent
evidence supports a more specific classification.

## Observed pressure maps

`python -m chilicrisp pressure-map EVIDENCE_DIRECTORY` prints JSON from recursively
discovered `result.json` records. Redirect it to a file outside the raw evidence
tree when a persistent report is needed. Malformed records and duplicate trial
identities stop aggregation. The command never executes target code.

Each point pins experiment, candidate, manifest, workload, measurement mode,
phase, requested/effective memory limits, and the complete preflight record.
This deliberately conservative grouping may split otherwise comparable runs.
Every trial retains its relative path, SHA-256, outcome, lifecycle, and metrics.
Metric populations remain separated by unit and measurement method. Statistics
include available values, counts, minimum, median, and maximum. Missing metrics
remain absent; unavailable-only populations are empty. Recovery-required records
retain their outcomes but contribute no measurement statistics.

This is a derived report, not acceptance evidence or a full time-series map.
It does not verify artifact hashes recorded inside a result, infer OOM from
timeouts, interpolate untested budgets, or establish causal explanations.

## Build sequence and acceptance

The existing runner owns enforcement and raw measurements. `resources.py` owns
the implementation capability vocabulary; `pressure.py` owns derived aggregation.
The common CLI dispatches to existing runner, frontier, and recovery commands.
Existing manifests and entry points remain compatible.

The next backend increment should introduce an explicit resource-selected
experiment contract, reject unsupported selections before launch, record
requested and effective limits for every selected dimension, and generalize the
frontier's units and failure classifications. CPU quota controls and accounting
are now implemented and natively exercised; see [the CPU guide](cpu.md).
Add independent dimensions
before joint resource surfaces; keep fixed controls frozen while searching one
axis. Joint experiments need predeclared interaction and total-cost policies.

Native fixtures must demonstrate each limit and verify cleanup. Promotion needs
independent correctness plus transfer checks across declared memory, CPU,
latency, I/O, and maintenance thresholds. Lower usage on one axis alone does not
establish a useful candidate. Local Ubuntu WSL native fixtures now pass; see
[validation evidence](../reports/native-validation.md). Protected candidate builds,
sealed grading, promotion, and independent reproduction remain open prerequisites.

This increment uses portable tests for real unsupported-host result ingestion,
duplicate rejection, synthetic grouping/missing metrics, and capability isolation.
Synthetic measurements test report semantics only. The run is unguarded because
the managed workspace keeps `.git` read-only; existing uncommitted work is retained.

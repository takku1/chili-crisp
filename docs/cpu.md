# CPU bandwidth experiments

The Linux runner can now apply CPU bandwidth controls while keeping a fixed
memory limit. Existing manifests without CPU settings retain their memory-only
enforcement behavior. Adaptive `frontier` remains a memory search; a configured
CPU quota is held fixed for its baselines and frontier trials.

## Research basis

The kernel defines `cpu.max` as a quota/period pair in microseconds. It is a
bandwidth ceiling, not a CPU reservation or a total CPU-time limit.
`cpu.stat` reports group CPU usage and own-quota throttling; newer kernels can
also expose `cpu.stat.local` throttling that includes ancestor effects.
See the [cgroup v2 reference](https://cdn.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html).

Kernel bandwidth documentation describes a 1 ms minimum quota/period and a 1 s
maximum period. It also documents hierarchical and CPU-local-slice caveats, so
short-run wall-time ratios should not be treated as exact CPU capacity.
See [bandwidth control](https://docs.kernel.org/scheduler/sched-bwc.html).

## Manifest and execution

Add this optional object within `isolation`:

```json
"cpu": {"quota_usec": 20000, "period_usec": 100000}
```

This requests an average ceiling equivalent to one fifth of a CPU over the
declared period. Quota and period must be explicit integer microseconds. The
runner requires CPU delegation and a fair-class scheduling policy. It records
ancestor `cpu.max`, CPU weight and effective CPU set when available. For this
first controlled adapter it rejects any finite ancestor quota, even when that
ancestor looks looser than the requested setting, rather than assuming sibling
consumption cannot interfere. Host competition and hardware variability remain.

The fresh trial cgroup receives the requested pair and zero burst where the
kernel exposes burst control. Settings are read back before target execution.
The requested pair is recorded in preflight CPU metadata, and effective settings
are retained in `preflight_record.effective`. The existing manifest hash binds
the requested controls to each result. The target cannot change scheduler policy
through the pilot syscall allowlist.

Run ordinary `runner trial` with this manifest to collect one point, or declare
a complete quota grid:

```text
python -m chilicrisp cpu-sweep MANIFEST --quotas 100000 50000 20000 --period 100000 --budget 67108864 --repetitions 3 --seed 7
```

The example uses a fixed 64 MiB memory cap; choose a known adequate cap for the
target. Sweep arguments override any CPU pair already in the input manifest.
All workload/quota/repetition combinations are shuffled with the recorded seed.
The entire sweep must fit `search.max_trials`, and every invocation receives a
shared `limits.experiment_seconds` deadline. Both limits include failed attempts.
The tool checks returned trial identities, finalized lifecycle, and effective
CPU/memory settings before treating an observation as usable.

Passes and wall-time timeouts are collected as observations. Wrong output, OOM
at the fixed memory limit, unsupported enforcement, cleanup failures or invalid
measurements stop the sweep. `COMPLETED` means the plan was collected; it is not
a claim that all points passed or that a candidate should be promoted. No CPU
frontier, joint resource surface, reserved CPU capacity or total CPU-time limit
is inferred.

## Measurements and native evidence

Result metrics now include CPU usage/user/system seconds, quota periods,
throttled periods, and own-quota throttled seconds. Local throttled seconds are
available only when the kernel supplies that counter; otherwise the value is
explicitly unavailable. Raw counters retain optional CPU/memory pressure data.
These measurements include the launcher and sandbox, consistent with the existing
whole-program memory accounting. Timeouts retain the `timeout` outcome.

The extended native fixture suite checks quota readback, actual throttling,
correct output, wall-time timeout, finite-ancestor rejection, missing-delegation
rejection, and a real four-trial grid alongside the existing isolation/recovery
checks. See [the CPU validation report](../reports/cpu-validation.md).

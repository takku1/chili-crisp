# CPU bandwidth implementation and validation

2026-10-29. This run researched Linux CPU bandwidth semantics against the
[current cgroup v2 reference](https://cdn.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
and [kernel bandwidth-control guide](https://docs.kernel.org/scheduler/sched-bwc.html).
The design and invocation contract are in [CPU experiments](../docs/cpu.md).

## Delivered behavior

Optional `isolation.cpu` accepts an explicit quota/period pair. The runner
requires CPU delegation and a compatible scheduler, records ancestor controls,
rejects finite ancestor quotas for controlled experiments, applies/readbacks
`cpu.max`, disables optional quota burst, and retains CPU usage/throttling data.
Old manifests without CPU settings continue to run. Memory frontier decisions
remain memory-specific; a configured CPU quota is a fixed control.

`cpu-sweep` executes a seeded, repeated quota grid at fixed memory. It enforces
a total trial cap and shared experiment deadline; checks immutable trial
identity, lifecycle, effective settings and required CPU measurements; retains
timeouts as timeouts; and stops on invalid measurements or other failures.
Completion does not mean every point passed or establish optimization acceptance.

## Native execution

Final lab: `/home/chili-runner/chili-lab/fixture-mq2yv546`.
Retained Windows-side evidence: `artifacts/native-fixture-mq2yv546/`, including
`native-summary.json`, `cpu-sweep.json`, native logs, and per-trial artifacts.
Host: Ubuntu-26.04 WSL, Python 3.14.4, bubblewrap 0.12.0.

The final native summary records all expected fixture outcomes and no remaining
trial cgroups. The suite includes the original correct/wrong output, timeout,
output flood, namespace/seccomp, OOM and cleanup/recovery checks, plus:

- CPU quota readback and actual throttling at 20,000/100,000 microseconds.
- CPU-bound work retaining correct output.
- A short wall-time deadline retaining the `timeout` outcome under CPU pressure.
- Rejection of a finite ancestor quota and missing delegated CPU controller.
- A four-trial sweep at 100,000 and 50,000 microsecond quotas, two repetitions,
  100,000 microsecond periods, fixed 64 MiB memory and seed 7. It completed with
  passing public checks for all four observations.

Failed early lab `fixture-oopkx6oq` is retained. It exposed a module name collision
with an existing runner CPU-time variable and the test harness's attempt to
write administrator-owned service quota policy. The module import now has an
explicit alias, and negative tests use a fresh worker-owned delegated child.
Subsequent native runs passed without changing service-level ownership or
disabling system security policy.

## Portable and package checks

64 portable unittest cases pass, with two existing native methods skipped on
Windows. Added coverage includes legacy/invalid CPU manifests, scheduler and
delegation gates, ancestor quotas, unavailable accounting, seeded schedules,
global trial/time caps, failure handling and invalid trial/resource identity.
Ruff and skill validation pass. Wheel checks also validate a CPU-configured
manifest, exercise CPU-accounting imports and reject an oversized sweep before
any workload can run. The coding-agent skill now documents these controls.

This is unguarded work because the managed workspace keeps `.git` read-only.
There is no cross-host reproduction, resource optimization win, aggregate
CPU-time cap, CPU adaptive frontier, I/O backend or independent promotion claim.

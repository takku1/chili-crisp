# Enforced Linux tier

Read this only when the task needs kernel-enforced hard limits (cgroup memory,
CPU quota) rather than measured budgets. It needs an owner-prepared Linux lab.
Framework docs: `docs/current/enforced/` in the Chili Crisp checkout.

```contract
inputs:
  task
order:
  verify#preflight before exec frontier
  verify#preflight before exec cpu sweep
  verify#preflight before exec trial
  verify#idle before exec native recover
```

```logic
enforced:
  require the owner provided an experiment manifest, frozen rootfs, public input and oracle, and a delegated cgroup parent
    otherwise:
      return #missing task as enforced_report

  exec readonly manifest validation from framework as validation
  verify #valid the manifest passed schema validation from validation
    otherwise:
      return #missing validation as enforced_report
  exec readonly native preflight from framework as preflight
  verify #preflight the manifest validated and native prerequisites are ready from preflight
    otherwise:
      return #missing preflight as enforced_report

  label measuring:
  if task explores a memory frontier:
    exec frontier from framework as evidence
  else:
    if task sweeps CPU bandwidth:
      exec cpu sweep from framework as evidence
    else:
      exec trial from framework as evidence

  verify #finished every run finished and no journal is left interrupted from evidence
    otherwise:
      exec readonly process check from host as processes
      verify #idle no active runner owns the interrupted trial from processes
        otherwise:
          return #stopped processes as enforced_report
      exec native recover from framework as evidence
      return to measuring

  exec readonly pressure map from framework as pressure
  return #measured:
    evidence
    pressure
```

| Step | Command |
|---|---|
| `exec readonly manifest validation` | `python -m chilicrisp runner validate MANIFEST` |
| `exec readonly native preflight` | `python -m chilicrisp doctor --manifest MANIFEST` |
| `exec frontier` | `python -m chilicrisp frontier MANIFEST` |
| `exec cpu sweep` | `python -m chilicrisp cpu-sweep MANIFEST --quotas Q1 Q2 ... --period 100000 --budget BYTES --repetitions 3 --seed N` |
| `exec trial` | `python -m chilicrisp runner trial MANIFEST --workload ID --budget BYTES` |
| `exec readonly process check` | list processes and cgroups under the delegated parent that belong to the trial |
| `exec native recover` | `python -m chilicrisp recover MANIFEST` |
| `exec readonly pressure map` | `python -m chilicrisp pressure-map EVIDENCE_DIRECTORY` |

## Step meanings

- **experiment manifest**: owner-provided, distinct from the local project
  configuration. Never build a rootfs by mounting the host root.
- **framework**: the Chili Crisp installation. **host**: the process and
  cgroup listing.
- For `cpu-sweep`, choose a fixed memory budget that suits the target (the
  64 MiB in examples is not a default). `COMPLETED` means the grid ran,
  timeouts included; read each outcome. It does not accept an optimization.

## Report

If preflight fails, keep any local evidence and report the exact missing gate.
Otherwise report raw evidence paths and the pressure map. Never reinterpret a
timeout as OOM, never compare measurements taken under mismatched conditions,
and never claim a limit was enforced unless the runner enforced it. Memory is
the only adaptive frontier; CPU is a predeclared grid. Retained candidates stay
experimental, never production-approved.

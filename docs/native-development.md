# Native scarcity in the development loop

The existing `dev init/request/submit/run/rollback/recover` controller now supports
an opt-in `linux_cgroup` evaluation backend. It uses the existing Linux runner;
there is no unconfined fallback. Default evaluation remains trusted local.

The bridge runs source programs through an owner-provisioned runtime and public
correctness driver, or compiles them first in an
[isolated compiler root](#isolated-compilation). It rejects any project build
command. Dependency installation and generated build hooks are unsupported.

## Owner provisioning and policy

Prepare a normal experiment manifest with a frozen minimal rootfs, pinned inputs
and stdout hashes or supported external oracles, delegated cgroup parent and
standard runner isolation controls. The rootfs needs an empty real `/candidate`
directory. Its owner-controlled command should execute a driver in the runtime
and load code explicitly from `/candidate`; Python should use `-I -B` and explicit
import paths. Keep runtime, controller, grading policies and dependency
provisioning outside the proposed source tree. Same-process public drivers are
not protected hidden judges; also use an independent external output oracle.

The controller mounts a frozen source snapshot read-only at `/candidate`. The
runner hashes runtime/source, clears the inherited environment, unshares
namespaces, disables networking and further user namespaces, drops capabilities,
applies seccomp/cgroup limits, and exposes only the runtime, source, stdin and
constrained scratch/dev/proc surfaces. Host project commands are not executed in
native evaluation. Project configuration still selects source and protected files.

Add these fields to a normal development plan:

```json
{
  "objective": "enforced_budget_bytes",
  "evaluation": {
    "backend": "linux_cgroup",
    "manifest": "/srv/chili/owner/experiment.json",
    "benchmark_workload": "correct",
    "initial_budget": 100663296
  },
  "quantum": 4096,
  "minimum_target": 8388608,
  "reductions": [0.5],
  "regression_limits": {"wall_seconds": 0.15}
}
```

This is a partial policy: normal fields including concept, project_config and
benchmark_command remain required. Host benchmark/test argv are unused here.
Use null project build and no artifact paths. Only enforced budget is supported
as the native objective in this increment; wall time and cgroup peak memory are
available as regression guards. Explicit page-aligned quantum, minimum target and
initial budget are required. Example numbers are fixture values, not defaults
suitable for every program.

Native `dev init/submit/rollback` need no `--trusted-local`. `dev run` still needs
that flag for its caller-selected agent command, which executes with host
permissions. Use an owner-reviewed source-only transport. An unrestricted coding
agent on the host is not isolated by this bridge; candidate evaluation remains
native regardless of the transport flag.

## Pressure and decisions

The initial baseline must pass all declared public workloads at the initial
budget, followed by repeated benchmark trials. This confirms a passing budget;
it does not automatically discover the minimum-memory boundary.

Each submission first probes the incumbent at the new target, preserving its
outcome and cgroup diagnostics. A probe may pass or fail; OOM is feedback, not a
requirement for accepting every useful improvement. Baseline comparisons run at
the incumbent's accepted budget. Candidate correctness on every declared
workload, exploration and fresh confirmation all run at the new enforced target.
Output must pass the configured independent oracle. Latency guards compare
executions under their respective budgets.

After acceptance, the passed enforced budget becomes the next target's basis.
Failure preserves the champion and can relax the next challenge. Rollback
rechecks all public workloads and remeasures the selected historical version at
its accepted budget. Experimental retention does not claim a minimal footprint.

Trial and agent costs are conservatively reserved before launch. Setup, runner
and cleanup failures interrupt the session. Inspect trial lifecycle journals and
perform runner recovery if necessary before controller recovery with
`dev recover --owner-stopped`. Timeouts and OOM remain distinct outcomes.
Runtime/input/oracle/reference and evaluator identities are pinned; changes need
a new lineage. Raw records and journals share the session's `native-evidence`
directory; unfinished journals block new trials and controller recovery until
native recovery succeeds. Measurement summaries and agent artifacts remain in
`runs`, and compact request memory includes public pressure diagnostics.

`native_memory_peak_bytes` is cgroup charged-memory accounting under the declared
cache policy. `enforced_budget_bytes` is observed survival at a limit, not an
exact minimum requirement. Public retention leaves `sealed: not_run` and
`production: not_accepted`. An optional [owner-operated sealed gate](sealed-acceptance.md)
can subsequently mark a policy-verified champion. Broader normal-hardware
reproduction and controlled AI comparison remain separate work.

## Isolated compilation

Add an optional `build` object to `evaluation`:

```json
"build": {"manifest": "/srv/chili/owner/compiler.json", "memory_budget": 536870912}
```

The compiler manifest is a normal experiment manifest with its own frozen
toolchain rootfs, `seccomp: "pilot_build_v1"`, no source mount and exactly one
workload whose oracle is `build_elf_v1`. Its command reads source from
`/candidate` and writes one ELF64 x86_64 executable to stdout. The program
runtime manifest must keep `pilot_allowlist_v1`, and the two roots must be
disjoint.

Each source is compiled twice; the export is retained only if both are
byte-identical and pass the ELF size/format policy. The retained artifact is
mounted read-only at `/candidate` in the program runtime. Builds are cached per
source and compiler manifest under the session; a cache entry is re-verified
before reuse and a tampered entry rejects rather than rebuilding. Compilation
reserves four extra trials per baseline/candidate evaluation. Run
`chilicrisp build MANIFEST SOURCE OUTPUT --budget BYTES` to compile standalone.

Validated toolchains are GCC C (`tools/native-build.py`) and Rust/Cargo
(`tools/native-cargo.py`); see [validation](../reports/isolated-build-validation.md).
For Rust, the owner vendors the permitted crates into the frozen compiler root
while provisioning. Candidates supply `Cargo.toml`, `Cargo.lock` and sources;
the build runs `--offline --locked` against `/vendor` only, so an unvendored
crate or altered lockfile checksum fails the build. Candidate `.cargo`
configuration and `rust-toolchain` files are ignored.

## Reproduce the integration fixture

Inside the configured disposable Ubuntu host, as its provisioning owner:

```text
sudo python3 tools/native-development.py
```

It creates a fresh lab and delegated unprivileged service. Scripted source
variants exercise 96 → 48 → 24 MiB enforced limits, incumbent OOM, wrong-output
rejection, the external-agent protocol and remeasured rollback. See
[validation](../reports/native-development-validation.md). No model calls occur.

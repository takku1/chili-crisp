# Isolated compilation validation

The native development backend can now compile candidate C source inside a
separate frozen compiler root, retain the exported binary only after two fresh
byte-identical builds, and evaluate that binary in the stricter program runtime.
The development controller and the owner-operated sealed gate both use the same
build path. No model calls occurred; candidate sources are scripted.

This closes the first part of the isolated-compilation milestone for one
toolchain (GCC 15.2.0, C, x86_64). Rust/Cargo, pinned third-party dependencies,
cross-host reproducibility and the real-model two-generation experiment remain
open.

## Build boundary

| Property | Implementation |
| --- | --- |
| Toolchain | Minimal copied GCC/binutils/libc headers in its own rootfs, hashed and pinned; no package manager or downloads |
| Isolation | Existing runner: cleared environment, namespaces, no network, dropped capabilities, cgroup memory/pids/CPU, scratch quota |
| Seccomp | New `pilot_build_v1`: runtime allowlist plus `fork`/`vfork`/`kill`/`tgkill` and `clone` with all namespace bits masked out; `clone3` returns `ENOSYS`; x86_64 only |
| Export | Compiler stdout must be a bounded ELF64 x86_64 executable (`build_elf_v1` oracle); it is format validation, not program correctness |
| Reproducibility | Two fresh compiles per source; differing bytes reject the candidate |
| Execution | Exported artifact is mounted read-only at `/candidate` in the program runtime under `pilot_allowlist_v1`; never executed on the host |
| Provenance | `build-record.json` pins manifest, toolchain, builder, budget, source tree, artifact and both trial IDs; cached builds are re-verified, and a corrupted cache rejects instead of rebuilding for free |
| Accounting | Controller and sealed gate reserve four extra trials for compiling baseline and candidate |

Compiler and program roots must be disjoint, and sealed vaults may not sit inside
either. Evaluator identity now includes the build adapter, compiler manifest,
toolchain hash, build input and export policy, so changing any of them needs a
new lineage.

## Controls

Final run: `artifacts/native-fixture-y7pvqulr/` (lab
`/home/chili-runner/chili-lab/fixture-y7pvqulr`, Ubuntu 26.04 WSL,
delegated cgroup service, unprivileged `chili-runner`).

| Control | Expected | Observed |
| --- | --- | --- |
| Valid C source | Retained | Retained |
| Compiler leaves a background child | Retained; child killed with the trial cgroup | Retained, no leaked cgroup |
| Random bytes appended to export | Rejected (non-identical) | Rejected |
| Compiler exceeds timeout | Rejected | Rejected |
| 2 MiB stdout flood over 1 MiB cap | Rejected | Rejected |
| 768 MiB allocation under 512 MiB budget | Rejected | Rejected |
| Invalid C | Rejected | Rejected |
| `#include` of an existing host-only header | Rejected | Rejected |

Inside the compiler sandbox the fixture also asserts that host environment
variables (`CPATH`, a marker secret) are absent, the runner's home is invisible,
TCP sockets fail with `EPERM`, namespace-creating `unshare`/`clone` fail with
`EPERM`, and `clone3` fails with `ENOSYS`. The compiled program itself confirms
that `fork` and `socket` fail with `EPERM` under the runtime profile.

## Controller and sealed gate

A compiled byte-sum session started at 96 MiB and accepted a scripted candidate
with a smaller live chunk at the next enforced target
(`accepted_experimental`). The sealed gate then recompiled both versions from
its own vault copy of the compiler manifest, graded a private input and ran the
matched 256 MiB transfer comparison; it signed a `passed` receipt, which
`dev accept` imported as a policy-verified champion.

`tools/acceptance-audit.py` re-verified the receipt, cached build provenance and
trial accounting: 14 trials total (4 compiler, 10 runtime, all passing) against
a 14-trial policy cap. Median charged memory was 35,860,480 bytes for the
baseline and 9,650,176 bytes for the candidate; median elapsed time 0.111 s and
0.095 s. These are integration measurements on deliberately simple variants,
not established speedups.

`tools/build-audit.py` re-checked all 31 public compiler/runtime trials: 25 pass,
2 wrong output, 2 OOM, 1 timeout, 1 output limit, matching the intended
controls. Every trial was finalized, its effective `memory.max` matched the
requested budget, and artifact hashes matched. No trial cgroups remained.

## Limits

- One C toolchain on one host; the build is reproducible across two runs on the
  same pinned toolchain, not across machines or compiler versions.
- No third-party dependency resolution. A lockfile-pinned vendored dependency
  set (e.g. Cargo `--offline --locked`) is the next build increment.
- The build seccomp profile is x86_64-only and still permits process creation
  inside the cgroup; isolation relies on the runner's namespaces and limits.
- ELF validation checks format and size, not behavior; correctness comes from
  the runtime workloads and oracles.
- The account-separation caveats in [sealed acceptance](../docs/sealed-acceptance.md)
  are unchanged.

Portable validation: 99 tests run on Windows, **97 passed and two Linux-only
tests skipped**; `ruff check .` clean. `tests/test_build.py` covers ELF
header/size validation, retained repeated exports, cache tampering blocking
reuse, nondeterministic export rejection, and refusal to run programs under the
build profile.

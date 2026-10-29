# Isolated compilation validation

The native development backend can now compile candidate C or Rust source inside a
separate frozen compiler root, retain the exported binary only after two fresh
byte-identical builds, and evaluate that binary in the stricter program runtime.
The development controller and the owner-operated sealed gate both use the same
build path. No model calls occurred; candidate sources are scripted.

Two toolchains are validated on x86_64: GCC 15.2.0 for C, and rustc/cargo
1.93.1 with an owner-vendored, lockfile-pinned crate set. Cross-host
reproducibility is covered separately by the CI reproduction.

## Build boundary

| Property | Implementation |
| --- | --- |
| Toolchain | Minimal copied GCC/binutils/libc headers in its own rootfs, hashed and pinned; no package manager or downloads |
| Isolation | Existing runner: cleared environment, namespaces, no network, dropped capabilities, cgroup memory/pids/CPU, scratch quota |
| Seccomp | New `pilot_build_v1`: runtime allowlist plus `fork`/`vfork`/`kill`/`tgkill`, `clone` with all namespace bits masked out, `socketpair` only for `AF_UNIX`, `prctl` only for `PR_SET_NAME`, and `flock`/`linkat`/`eventfd2`/`sendmsg`/`recvmsg`/`recvfrom` for Cargo; `clone3` returns `ENOSYS`; inet sockets stay denied; x86_64 only |
| Export | Compiler stdout must be a bounded ELF64 x86_64 executable (`build_elf_v1` oracle); it is format validation, not program correctness |
| Reproducibility | Two fresh compiles per source; differing bytes reject the candidate |
| Execution | Exported artifact is mounted read-only at `/candidate` in the program runtime under `pilot_allowlist_v1`; never executed on the host |
| Provenance | `build-record.json` pins manifest, toolchain, builder, budget, source tree, artifact and both trial IDs; cached builds are re-verified, and a corrupted cache rejects instead of rebuilding for free |
| Accounting | Controller and sealed gate reserve four extra trials for compiling baseline and candidate |

Compiler and program roots must be disjoint, and sealed vaults may not sit inside
either. Evaluator identity now includes the build adapter, compiler manifest,
toolchain hash, build input and export policy, so changing any of them needs a
new lineage.

## C controls

Final run: `artifacts/native-fixture-niho4rcu/` (lab
`/home/chili-runner/chili-lab/fixture-niho4rcu`, Ubuntu 26.04 WSL,
delegated cgroup service, unprivileged `chili-runner`). Earlier run
`native-fixture-y7pvqulr` passed the same controls before the Cargo syscalls
were added to the build profile.

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

## Rust/Cargo controls

Final run: `artifacts/native-fixture-39l8s65j/` (`tools/native-cargo.py`).
The owner vendors the allowed crates (`itoa =1.0.15`) with network access while
provisioning; the frozen compiler root then contains the Rust toolchain and
`/vendor`. The driver runs `cargo build --release --offline --locked` from
`/tmp` with crates.io replaced by `/vendor`, so candidate `.cargo/config.toml`
and `rust-toolchain` files are never read. It sets `strip=symbols`, one codegen
unit and no incremental build, and exports exactly one binary target.

| Control | Expected | Observed (reason) |
| --- | --- | --- |
| Valid project using the vendored crate, with a build script asserting no host home, no `CHILI_BUILD_SECRET` and failing TCP connect | Retained | Retained |
| Dependency not in the vendored set | Rejected | Rejected (`no matching package named ryu`) |
| Lockfile checksum altered | Rejected | Rejected (`checksum for itoa v1.0.15 changed`) |
| Build script embeds random bytes | Rejected | Rejected (two builds differed) |

The retained Rust binary passed in the program runtime; the runtime gains only
`libgcc_s.so.1`. A Rust controller session and sealed gate then repeated the
C flow below: accepted at the tighter target, signed `passed`, 14 audited
trials (4 compiler, 10 runtime), median charged memory 35,872,768 vs
9,646,080 bytes. `tools/build-audit.py` re-checked 26 trials and all four
controls.

## Controller and sealed gate (C)

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

- Builds are reproducible across two runs on the same pinned toolchain; they are
  not claimed reproducible across compiler versions.
- Dependencies are limited to the crates the owner vendors. Adding a crate
  requires re-provisioning, which changes the toolchain hash and lineage.
- Build scripts and proc macros run inside the compiler sandbox; their isolation
  is the runner's, not a separate review.
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

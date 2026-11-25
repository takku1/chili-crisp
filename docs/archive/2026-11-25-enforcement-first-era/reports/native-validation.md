# Native runner and development workflow validation

Date: 2026-10-29. Changes and checks in this run are unguarded: the managed
workspace keeps `.git` read-only and the initial source tree remains uncommitted.
Existing source and historical reports were retained.

## Native fixtures

Executed `tools/native-fixtures.py` in Ubuntu-26.04 under WSL, using a fresh lab,
minimal frozen Python rootfs and transient systemd service delegated to the
unprivileged `chili-runner` account. Host Python is 3.14.4; bubblewrap is 0.12.0;
kernel is `6.18.33.2-microsoft-standard-WSL2`.

Passing lab: `/home/chili-runner/chili-lab/fixture-x_sp1h1j`.
Copied evidence: `artifacts/native-fixture-x_sp1h1j/`.
`native-summary.json` records `passed: true` and no remaining trial cgroups.

| Fixture | Observed outcome | Trial ID |
| --- | --- | --- |
| Correct output | pass | 9a9febb7e6304cd5a02c1cdffec10579 |
| Wrong output | wrong_output | c97a58be77c04360a2555b3c6fc21ace |
| Sleep beyond deadline | timeout | 51250fe2a23946a2a06ab40add29188e |
| Output flood | output_limit | 99059d773d084046a3dd364ddb70ed40 |
| Namespace, identity, seccomp and capability assertions | pass | d5e2baf3aa5e450f80a03a9512427777 |
| Touched allocations beyond limit | oom | b6f9e328c23a4c6695211883a5d298da |
| Injected cleanup failure followed by recovery | cleanup_failure; no leaked trial cgroup | See summary and lifecycle journal |

Each trial retains result, lifecycle, raw counters, bounded stdout/stderr, and
capture metadata. Trial memory.max was 64 MiB; swap was disabled. These are
whole-program fixture measurements, not optimization gains.

Two preceding labs are retained as failing regression evidence:
`fixture-7e82bjci` demonstrated that `--disable-userns` requires explicit
`--unshare-user`; `fixture-2qy2cqui` demonstrated that the default-deny syscall
filter denied bubblewrap init's wait operation. The runner now requests the user
namespace explicitly and permits `wait4`/`waitid` while still denying process
creation. The subsequent native isolation fixture passed with those fixes.

## Local development workflow

`python tools/demo-local.py` ran a source-changing Python example through baseline
and candidate compilation and public tests. Decision: `public_tests_passed`.
The first retained record is under
`artifacts/local-demo-b6028ec417234c978036bc6a31f1c839/runs/comparison-b2a51dfe5018471388f22fb0b946f9de/`.
This establishes the local command path, not memory improvement or acceptance.

Portable regression tests cover real subprocess success and candidate rejection,
baseline failure, timeout/build stopping, output flooding, missing executables,
configuration preservation, execution-mode requirements and CLI failure status.
The validated `chili-dev` skill documents setup, source changes, comparisons,
isolated trials, stopping rules and evidence reporting.

Final checks: 49 portable unittest cases passed with the two Linux-only methods
skipped on Windows; the separate native worker executed the seven cases above.
Ruff checks, skill validation, source/wheel builds, and an extracted-wheel
baseline/candidate build-test comparison passed. The editable CLI and validated
skill were installed in the user's Python/Codex environments. Installed CLI help
was exercised. Skill discovery in a fresh Codex conversation was not exercised.

## Remaining limits

These fixtures do not certify isolation against kernel exploits, validate the
Worldgame scientific oracle, prove cross-host reproducibility, or exercise an
arbitrary candidate rootfs build. Local builds remain trusted host commands.
CPU/I/O pressure backends, general artifact building, hidden grading and automatic
promotion remain unimplemented. The two existing unittest native methods are
skipped on Windows; the standalone Linux fixture worker ran the native cases
listed above with raw evidence retained.
The retained fixture manifest references a transient service cgroup; it is not
a reusable live delegation after that service exits. Run the fixture provisioning
command again for a fresh delegated fixture environment.

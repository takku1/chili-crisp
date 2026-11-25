# Native development-controller bridge validation

The general controller now runs a source-only `linux_cgroup` backend. An
owner-scripted experiment retained two improvements at shrinking enforced memory
budgets, rejected incorrect output, used `dev run` for its final proposal and
remeasured a historical version during rollback. No model calls were made.

## Experiment

`tools/native-development.py` provisions a fresh lab on the existing Ubuntu 26.04
WSL host. A delegated unprivileged systemd service invokes the actual
`development.create/submit/run/rollback` functions. The candidate receives a
frozen runtime and read-only source mount. Project host test/benchmark argv are
deliberately nonexistent: native evaluation never invokes them.

The fixture sums 67,108,864 bytes of value one. Source variants process the same
logical input with 64 MiB, 32 MiB and 1 MiB live chunks. An owner driver runs code
inside the sandbox; the runner independently checks stdout against a pinned hash.
This is a simple integration fixture, not a hard benchmark or AI invention.

| Stage | Enforced limit | Result |
| --- | ---: | --- |
| Initial baseline | 100,663,296 B (96 MiB) | Correctness and repeated survival |
| First challenge | 50,331,648 B (48 MiB) | Incumbent OOM; first candidate retained |
| Incorrect submission | 25,165,824 B (24 MiB) | Incumbent OOM; wrong output rejected; champion preserved |
| Second challenge | 25,165,824 B (24 MiB) | Incumbent OOM; second candidate retained through external-agent protocol |
| Rollback | 50,331,648 B (48 MiB) | First candidate rechecked and remeasured |

Each accepted generation uses two randomized paired exploration blocks followed
by two fresh paired confirmation blocks. Incumbents run at their accepted limit;
candidates run at the target. Every candidate correctness workload also runs at
the target. Champions remain experimental, with sealed grading and production
acceptance unset. The fixture omits latency guards to isolate enforced survival;
it does not establish a speedup.

The owner driver checks that a controller environment marker is absent, host
home/cgroup paths are invisible, and writes to runtime/source fail. Existing
namespace, network, seccomp and cgroup controls remain active. This supports the
restricted path, not a security certification or arbitrary isolated builds.

## Evidence

Final run: `artifacts/native-fixture-61epioaq/`, from Linux lab
`/home/chili-runner/chili-lab/fixture-61epioaq`. It retains logs, summary, owner
plan/manifest, full session state, source capsules, agent request/response, trial
records, outputs and lifecycle journals.

`python tools/native-development-audit.py artifacts/native-fixture-61epioaq`
passed: **33 trials: 29 passes, three expected OOMs and one expected wrong-output
rejection**. The audit validates schemas, artifact hashes, finalized journals,
requested/effective limits, passing stdout, paired budget assignments and rollback.
It checks record consistency, not authenticity or hidden acceptance. No trial
cgroups remained.

Earlier runs are preserved. `native-fixture-xdb42a88` failed a fixture assertion:
the 16 MiB intermediate source could also survive the next limit. A 32 MiB chunk
made the second probe discriminate. `native-fixture-7g67iaqr` passed manual
submissions; `native-fixture-xertp8wy` also passed the external-agent protocol.
`native-fixture-fe8bhgtj` adds explicit source identity and compact pressure
feedback. The final run additionally uses a shared `native-evidence` recovery
boundary; an unfinished trial blocks later attempts and controller recovery.

Windows validation: **90 tests run, 88 passed, two Linux-only tests skipped**.
Whole-package/test/tool Ruff checks, package builds, metadata checks, wheel
comparison/verification/skill smoke tests and bundled skill validation pass.
Native validation is a separate explicit run; hosted CI has not been claimed to
exercise delegated cgroups.

## Remaining boundaries

The backend rejects project builds and needs owner-frozen dependencies. The
agent transport selected by `dev run --trusted-local` still has host permissions;
the candidate evaluator does not. The initial budget is a confirmed passing
point, not an automatically located minimum-pressure boundary. The separate
frontier can explore boundaries.

A fresh bounded real-model experiment on a harder program, matched conventional
optimization arm, sealed acceptance and normal-hardware transfer remain open.
These scripted generations demonstrate connected enforced scarcity, not that
scarcity produces better AI implementations.

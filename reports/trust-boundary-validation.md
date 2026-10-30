# Separate-account grading and independent reproduction

The compiled sealed-acceptance flow now runs across three unprivileged Unix
accounts, and both it and the isolated C build fixture reproduce on a second,
independently provisioned host. Candidate sources are scripted; no model calls
occurred.

## Roles

`tools/native-trust.py` runs as root only to provision. Every phase then runs
as one account:

| Account | Owns | Does |
| --- | --- | --- |
| `chili-agent` | `agent/` (0755) | Writes the candidate; later signs a forged passing receipt with its own key |
| `chili-runner` | `controller/` (0700), `exchange/` (0755) | Creates the session, evaluates the candidate in its own delegated cgroup unit, exports the request, imports receipts |
| `chili-grader` | `vault/` (0700, files 0600), `receipts/` (0755) | Holds the signing key, hidden input and sealed manifests; recompiles and grades in its own delegated cgroup unit |
| root | `source/`, `venv/`, frozen roots | Installed controller and evaluator code; read-only to all three accounts |

`dev acceptance-request SESSION --export DIR` copies both frozen sources beside a
request with relative paths. The grader re-snapshots them against the pinned
hashes, so the exported copies carry no trust and the grader never reads the
controller session. After import, the runner publishes the accepted session
state to the exchange so the grader can run `tools/acceptance-audit.py` without
controller access.

## Probes

Each account attempted 5 reads and 7 writes across the other roles' files after
grading. The fixture fails unless every attempt outside the account's role is
refused by the OS.

| Account | Permitted (all expected) | Refused |
| --- | --- | --- |
| `chili-agent` | none | vault key, hidden input, policy; controller plan and state; installed code; exchange request; receipt; frozen compiler root |
| `chili-runner` | own plan/state, own exported request | vault key, hidden input, policy; installed code; receipt; frozen compiler root |
| `chili-grader` | own key, input, policy, receipt | controller plan and state; installed code; exchange request; frozen compiler root |

The agent's forged receipt was rejected (`Invalid acceptance signature`) and left
controller state byte-identical. The genuine receipt marked a verified champion;
production approval stayed `not_accepted`.

The probes found one real defect during development: copying the checkout from
the Windows-mounted repository (drvfs) preserved mode 0777, so all three
accounts could rewrite the installed evaluator. The fixture now sets trusted
code to root-owned 0755/0644. Owners deploying from a drvfs, SMB or similar
checkout must normalize modes the same way. A second deployment detail: source
file modes are part of the source identity, so controller files must remain
readable by the grader once exported; protect the controller with its 0700
directory rather than 0600 files.

## Runs

| Host | Kernel/distro | Toolchain | bubblewrap | Result |
| --- | --- | --- | --- | --- |
| WSL lab (`/srv/chili-trust/lab-4mve2gif`) | Ubuntu 26.04, WSL2 | GCC 15.2.0, Python 3.14 | 0.12.0 | passed; 14 audited sealed trials |
| GitHub Actions run 40976888625 | Ubuntu 24.04 runner | GCC 13.3.0, Python 3.12 | 0.12.0 (built from source) | build fixture and trust fixture passed; 14 audited sealed trials |

The CI host reproduced the same accept/reject decisions: all eight compiler
controls; the controller accepting the candidate at the tighter target; the
signed `passed` verdict; forged receipt rejection; and identical probe outcomes.
Matched-transfer medians were 35,667,968 → 9,449,472 bytes charged memory
(WSL: 35,872,768 → 9,670,656). Byte-level build identity is not expected across
the two hosts because the compilers differ. Evidence is the `native-evidence`
workflow artifact (30-day retention).

The `Native fixtures` workflow (`.github/workflows/native.yml`) now runs on each
push to `main`. `tools/ci-native-host.sh` builds bubblewrap 0.12.0 and disables
the AppArmor unprivileged-userns restriction; it is for disposable runners only.

## Limits

- One machine per run: separation is between Unix accounts sharing a kernel,
  not between hosts. A root-level compromise defeats it.
- The proposing agent here is a scripted account, not an unrestricted coding
  agent with shell access; a real agent must run as `chili-agent` (or another
  host) for these results to apply.
- Transport between roles is shared filesystem directories; a network grader
  service and its transport security are not implemented.
- The Rust/Cargo fixture is not in CI yet (it depends on Ubuntu's packaged
  `rust-1.93` layout).

# Tool policy and package cleanup

2026-10-29. This run was unguarded: `.git` remains read-only and the source tree
is still uncommitted. No user source or historical experiment evidence was deleted.

## Implemented tool behavior

- `init` records protected correctness paths, inferring `tests/` and relative
  test-command files by default. Explicit repeated `--protect` options replace
  inference. Missing, escaping, excluded or linked paths are rejected.
- `compare` freezes the baseline correctness-file hashes and rejects candidate
  differences before candidate execution. It rechecks those files after each
  build/test command so a command cannot silently rewrite the configured checks.
- Completed comparisons validate against a comparison schema and receive an
  integrity sidecar. `verify` checks the record digest, command order/arguments,
  saved stage records, retained stream hashes, and passing-decision consistency.
  Invalid or incomplete comparisons return failure. These are consistency checks,
  not signatures or protection against trusted host commands modifying evidence.
- `doctor --manifest` additionally checks the rootfs, input and oracle-policy
  hashes after backend preflight. Unavailable requested setup returns nonzero.
- `skill DESTINATION` exports the bundled agent skill without overwriting an
  existing directory. The installed framework and exported instructions can now
  come from the same package artifact.

## Organization

Canonical schemas and skill files moved under `chilicrisp/`; `contracts.py` loads
schemas using package resources. `runner.validate` remains compatible. Declarative
setuptools package data replaces the custom `setup.py` build shim. Requirements
delegate dependency ownership to `pyproject.toml`. The source distribution now
also includes scientific verification sources used by its tests.

Build and CI outputs go under `artifacts/packages/`. Wheel validation checks all
schemas and the bundled skill, rejects development artifacts, and executes a
comparison, integrity check and skill export from the extracted wheel. Old
`build/`, `dist/`, empty legacy resource folders and five empty temp directories
were preserved under `artifacts/workspace-archive-20261029-022437/`.

## Executed verification

Portable tests: 56 cases passed, with two existing native unittest methods skipped
on Windows. Ruff and skill validation passed. Native fixtures were rerun after
resource reorganization: `artifacts/native-fixture-z5g_h3u_/native-summary.json`
records all seven expected fixture outcomes and no remaining trial cgroups.
Wheel/source builds and extracted-wheel checks passed; the final release check
also exercises the strengthened evidence verification.

## Still outside the implemented tool

Resource-selected CPU/I/O enforcement, arbitrary-project protected rootfs builds,
benchmark repetition/transfer acceptance, sealed grading, generation budgets across
candidate populations, restartable orchestration, promotion/rollback, and an MCP
service remain open. Correctness-path inference needs owner review and is not
complete discovery of an arbitrary project's behavioral contract.

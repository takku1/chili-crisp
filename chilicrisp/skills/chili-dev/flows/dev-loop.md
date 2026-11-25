# Multi-round development loop

Read this when the task needs many automated rounds with moving targets, or a
one-off correctness comparison. The controller owns measurements, decisions
and which version is retained; the agent owns research and candidate source.
It runs on this machine with host permissions; it is not a sandbox.

```contract
inputs:
  task
order:
  write pinned contract before exec dev init
  exec project init before write candidate change
  verify#initialized before write research
  verify#pinned before exec trusted compare
  write candidate copy before write candidate change
  write research before exec dev submit
  verify#recoverable before exec dev recover
  write candidate copy before exec trusted compare
```

```logic
dev-loop:
  write pinned contract with baseline_dir
  exec project init from framework as project_config
  generate development policy from project_config as policy
  write policy with session_parent
  exec dev init from framework as session
  verify #initialized the baseline passed correctness and a first target was derived from session
    otherwise:
      return #stopped session as loop_report

  label round:
  exec readonly dev request from framework as dev_request
  generate research record from dev_request as research
  write candidate copy with candidate_dir
  write candidate change with candidate_dir
  write research with candidate_dir
  exec dev submit from framework as decision
  verify #decided the submit recorded a controller decision with raw measurements from decision
    otherwise:
      exec readonly dev status from framework as status
      unless status shows interrupted work:
        return #stopped status as loop_report
      exec readonly process check from host as processes
      verify #recoverable no executor or runner for the session is still running from processes
        otherwise:
          return #stopped processes as loop_report
      exec dev recover from framework as status
      return to round

  exec readonly dev status from framework as status
  if task asks to revisit an earlier retained version:
    exec dev rollback from framework as status
  if status is STOPPED, cleanup is unresolved, or the task budget is spent:
    return #done status as loop_report
  return to round
```

For a one-off correctness comparison of two snapshots:

```logic
compare:
  write candidate copy with candidate_dir
  exec project init from framework as project_config
  verify #pinned the project config pins the correctness files from project_config
    otherwise:
      return #stopped project_config as compare_report
  write candidate change with candidate_dir
  exec trusted compare from framework as record
  verify #compare-ran the comparison decision is public_tests_passed from record
    otherwise:
      return #stopped record as compare_report
  exec readonly record verify from framework as integrity
  verify #compare-checked the saved record and logs are intact from integrity
    otherwise:
      return #stopped integrity as compare_report
  return #compared integrity as compare_report
```

| Step | Command |
|---|---|
| `exec project init` | `python -m chilicrisp init ROOT --test-command JSON_ARGV [--build-command JSON_ARGV] --protect PATH ...` |
| `exec dev init` | `python -m chilicrisp dev init PLAN SESSION --trusted-local` |
| `exec readonly dev request` | `python -m chilicrisp dev request SESSION` |
| `exec dev submit` | `python -m chilicrisp dev submit SESSION CANDIDATE --research RESEARCH --trusted-local` |
| `exec readonly dev status` | `python -m chilicrisp dev status SESSION` |
| `exec readonly process check` | list processes whose command line names the session or candidate (`ps`, or `Get-Process` on Windows) |
| `exec dev recover` | `python -m chilicrisp dev recover SESSION --owner-stopped` |
| `exec dev rollback` | `python -m chilicrisp dev rollback SESSION CHAMPION --reason TEXT --trusted-local` |
| `exec trusted compare` | `python -m chilicrisp compare CONFIG --candidate CANDIDATE --output RUNS --trusted-local` |
| `exec readonly record verify` | `python -m chilicrisp verify RECORD` |

An existing agent CLI can drive the rounds instead:
`python -m chilicrisp dev run SESSION --agent-command JSON_ARGV --trusted-local`,
with separate `{request}`, `{response}` and `{workspace}` tokens. Use only an
agent that is actually configured, never an invented provider.

## Step meanings

- **pinned contract**: a runnable baseline with owner-reviewed correctness
  tests, representative fixtures and a benchmark driver whose stdout is
  stable. Create them before any candidate exists, and pin them with
  `--protect`; later changes to them reject the candidate.
- **policy**: JSON with `schema_version`, `concept`,
  `project_config`, `benchmark_command`, `objective` (and `artifact_paths` for
  `artifact_bytes`), plus regression limits, repetitions, generations,
  stagnation, wall and command budgets. Objectives: `wall_seconds`,
  `artifact_bytes`, `sampled_peak_rss_bytes`, `sampled_cpu_seconds`,
  `sampled_io_read_bytes`, `sampled_io_write_bytes`. For the enforced
  backend, add an `evaluation` block (`backend: linux_cgroup`, owner
  manifest, `benchmark_workload`, `initial_budget`) with objective
  `enforced_budget_bytes` and page-aligned `quantum` and `minimum_target`;
  see `flows/enforced.md`. Build outputs go in excluded directories
  (`build`, `dist`, `target`, `artifacts`).
- **candidate copy**: a separate copy of the retained source named by the
  request. Never edit the retained or baseline source.
- **candidate change**: edit the implementation only; never weaken tests,
  accuracy requirements or workloads.
- **research**: JSON with `hypothesis`, `mechanism`, `falsification`
  and `sources` (each with `reference` and `supports`). References are
  proposal evidence, not measurements.
- **framework**: the Chili Crisp installation. **host**: the process list.
  **baseline_dir**, **candidate_dir**, **session_parent**: the baseline,
  candidate and the directory that holds the session (outside the source,
  or inside an excluded directory).

## Measurement notes

Local CPU, RSS and I/O are sampled. Batch short workloads so each run gets at
least three samples when those metrics drive decisions. Measured targets are
not hard limits, and retained candidates are experimental, not production
promotions. `public_tests_passed` means only the configured build/test commands
passed; build and test timings are diagnostics. Snapshots exclude `.git`,
`.chilicrisp`, virtual environments, caches, `node_modules`, `build`, `dist`,
`artifacts`, `target` and egg-info; symlinks are unsupported. Local mode is
unconfined, so commands can still write outside their workspaces. Do not use it
for untrusted code or commands that detach background processes.

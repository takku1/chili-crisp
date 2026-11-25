# Constraint briefs: format and commands

## Commands

```text
chilicrisp profiles                       # built-in briefs
chilicrisp brief quarter                  # print the agent-facing brief (markdown)
chilicrisp brief my-brief.json --report .chilicrisp/checks/<stamp>/report.json
chilicrisp brief quarter --out brief.md     # save it instead of printing
chilicrisp check BRIEF [--workspace DIR] [--baseline DIR] [--same-output]
                       [--repeat 3] [--timeout 300] [--out DIR] [--where]
                       [--ratchet FILE [--tolerance 10]] -- COMMAND [ARGS...]
```

`check` runs `COMMAND` with the candidate directory (`--workspace`, default `.`)
as its working directory. With `--baseline`, it also runs the same command in
the original directory, alternating the order on each repetition. It takes the
median of each metric and writes `report.json`, plus per-run stdout, stderr and
measurements, to `--out` (default `.chilicrisp/checks/<timestamp>`). Exit code 0
means `fits`.

`--where` (Python commands only) adds one unmeasured diagnostic run under
`tracemalloc` and lists the top allocation sites close to the traced peak (within
about 10%). `brief --report` shows them as a "Where memory goes" table so the agent
starts from what actually holds the memory. It misses interpreter overhead and
memory held by C extensions, and tracing makes that run slower, so its numbers
are never used for budgets.

`--ratchet FILE` keeps a fixed result fixed. After a `fits`, it saves each
budgeted metric to `FILE`, keeping only a value that is lower than the one
already saved. On later checks, a metric that grows past its saved value by more than
`--tolerance` percent (default 10) is reported, and the verdict becomes
`over_budget` even if the budget still holds. Commit the file and run the same
check in CI to catch regressions. Only compare ratchets taken on the same
machine or runner type.

| Verdict | Meaning |
| --- | --- |
| `fits` | Every run passed, the output is stable (and matches the baseline with `--same-output`), no `forbid` rule matched, and every budget is met |
| `over_budget` | Correct, but at least one budget is exceeded |
| `broken` | A run failed, the output changed, or a `forbid` rule matched |
| `incomplete` | A budget couldn't be judged (a relative budget had no `--baseline`, or a metric was unavailable), or the candidate left changed files behind that a later run could read back |

## Brief file

```json
{
  "schema_version": "1.0",
  "name": "sensor-hub",
  "extends": "quarter",
  "story": "This aggregator moves onto a sensor hub that also runs three other services...",
  "budgets": {"peak_memory_bytes": "25%", "wall_seconds": "150%"},
  "artifacts": ["build/app.bin"],
  "writes": ["out/*.csv"],
  "inputs": [{"args": ["data/small.csv"]}, {"args": ["/data/held-out.csv"], "hidden": true}],
  "rules": ["Totals per sensor must be exactly the same."],
  "forbid": [{"pattern": "import (pandas|numpy)", "glob": "*.py", "why": "no heavy dependencies"}],
  "hints": ["The readings arrive one line at a time."]
}
```

- **budgets**: `peak_memory_bytes`, `wall_seconds`, `cpu_seconds`,
  `artifact_bytes`, `io_read_bytes`, `io_write_bytes`. Values are numbers,
  units (`16MiB`, `1.5MB`, `250ms`, `2s`, `0B`) or percentages of the baseline
  (`25%`).
- **extends**: inherit a built-in profile. Budgets are overridden by key;
  rules, forbid, hints and artifacts are appended.
- **artifacts**: files or directories under the workspace whose logical size
  counts toward `artifact_bytes`. They are measured after the command runs, so
  a build command can produce them.
- **writes**: globs (relative to the workspace) for files the command is
  expected to create or change. Before the first run and after each run,
  `check` records the size and modification time of every file in the
  candidate directory, skipping `.git`, `.chilicrisp`, `__pycache__` and the
  report folder. Any other change is reported and makes the verdict
  `incomplete`, because a later run could read it back as a cache. A file the
  baseline also changes counts as normal output. Writes outside the directory
  (home caches, temp) are not seen.
- **inputs**: argument lists appended to the command, smallest first. Every
  input runs `--repeat` times per arm. The command must succeed, and the output
  must be stable (and match the baseline with `--same-output`) on every input.
  Budgets are judged on the last input, because on small inputs the runtime's
  own startup dominates. Without `inputs`, the command runs as given.
- **hidden** inputs are left out of the rendered brief, findings, `report.json`
  and each run's `command.json`. The program's own stdout and stderr on them
  are still saved in the report folder. For a real held-out check, keep the
  data and `--out` where the agent can't read them.
- **rules**: shown to the agent; not checked (the *imagined* level).
- **forbid**: regex patterns that must not appear in matching source files.
  This is a cheap approximation of a rule, not a security boundary.
- **hints**: shown to the agent before the general design-pressure hints.

The schema is `chilicrisp/schemas/brief.schema.json`. A worked example lives in
`examples/brief-demo/`:

```text
python -m chilicrisp check examples/brief-demo/brief.json \
  --workspace examples/brief-demo/candidate --baseline examples/brief-demo/baseline \
  --same-output -- python aggregate.py
```

On the reference Windows machine (2026-11-25), the baseline peaked at about
210 MiB. The streaming candidate peaked at about 21 MiB, against a 52 MiB
budget. Verdict: `fits`.

## Built-in profiles

| Profile | Story | Budgets |
| --- | --- | --- |
| `half` | Another tenant took half the memory | memory 50%, time 110% |
| `quarter` | One of four copies on the box | memory 25%, time 150% |
| `handheld` | Battery handheld, 16 MiB, no network | 16 MiB, 1 s wall, 1 s CPU; network imports forbidden |
| `edge-function` | Cold-started edge function | 128 MiB, 250 ms, no disk writes |
| `floppy` | Fits on a 1.44 MB disk, 32 MiB RAM | artifact 1,474,560 B, 32 MiB |

Absolute profiles include the runtime itself. A Python interpreter alone
needs about 10 MiB, so `handheld` suits small programs or compiled code.

## Measurement limits

- Peak memory is the larger of the sampled process-tree RSS sum (every 10 ms)
  and the largest single-process OS lifetime peak (`peak_wset` on Windows,
  `VmHWM` on Linux). Shared pages can be double counted. Spikes that are split
  across short-lived processes can be missed.
- CPU and I/O counters are sampled too. A `0B` budget (such as `edge-function`'s
  disk writes) can pass when a write happens between samples, so the report
  adds a finding whenever a zero budget on a sampled counter passes. Use the
  [enforced tier](enforced/resources.md) when zero must be guaranteed.
- The rendered brief states these limits so agents neither over-trust the
  numbers nor try to slip under them.
- Commands that finish in under ~30 ms get too few samples. The report flags
  this; batch more work per run.
- All numbers come from this machine. Compare a candidate only with a baseline
  measured in the same check.

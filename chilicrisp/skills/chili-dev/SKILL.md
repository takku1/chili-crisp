---
name: chili-dev
description: Redesign code to fit a constraint brief (an imagined target machine with memory, time, CPU or size budgets) and verify it with Chili Crisp's measured checks. Use when code must fit tighter resources; not for ordinary feature work without a resource objective.
---

# chili-dev

Give the code an imagined machine to fit, change its design to fit, and prove
the fit with measurements on this machine. The `logic` block is the procedure;
follow it in order. For many automated rounds read
[flows/dev-loop.md](flows/dev-loop.md); for kernel-enforced limits read
[flows/enforced.md](flows/enforced.md).

```contract
inputs:
  request
order:
  verify#available before write candidate copy
  write candidate copy before write candidate change
  verify#baseline before write candidate change
  write hypothesis before write candidate change
  verify#intact before return#report
  verify#tests before return#report
  verify#fits before return#report
  never write * with baseline before return#report
```

```logic
chili-dev:
  require request names code to change and a resource to cut
    otherwise:
      abort with "chili-dev makes code fit tighter resources. Name the code and the resource objective."

  generate task facts from request as task
  if task lacks the target source, correctness tests, measured command, or resource objective:
    ask user for the missing target source, tests, measured command, or objective as details
    apply task update with details as task

  exec readonly availability check from framework as availability
  verify #available the doctor and capabilities commands succeeded from availability
    otherwise:
      abort with "Chili Crisp is not available. Install it from its known checkout into the task's environment; never download an unidentified package with the same name."

  if task needs kernel-enforced hard limits:
    run enforced from flows/enforced.md with:
      task = task
    return #delegated enforced_report as report

  if task needs many automated rounds with moving targets:
    run dev-loop from flows/dev-loop.md with:
      task = task
    return #delegated loop_report as report

  if task needs only a one-off correctness comparison:
    run compare from flows/dev-loop.md with:
      task = task
    return #delegated compare_report as report

  generate brief choice from task as brief
  write brief with brief_file
  write candidate copy with candidate_dir
  exec baseline check from framework as baseline_report
  verify #baseline the baseline command passed every run from baseline_report
    otherwise:
      return #blocked baseline_report as report
  exec readonly brief render from framework as design_brief

  label designing:
  generate hypothesis from design_brief as hypothesis
  write hypothesis with candidate_notes
  write candidate change with candidate_dir
  exec readonly test diff from framework as test_diff
  verify #intact the tests, fixtures, and measured command match the baseline from test_diff
    otherwise:
      write restored tests with candidate_dir
      return to designing
  exec candidate check from framework as candidate_report
  exec project tests from candidate_dir as test_result
  verify #tests the project tests passed from test_result
    otherwise:
      if the run budget is spent:
        return #blocked test_result as report
      return to designing
  verify #fits the verdict is fits from candidate_report
    otherwise:
      if the run budget is spent or the measurements are unstable:
        return #blocked candidate_report as report
      exec readonly brief render with report from framework as design_brief
      return to designing

  return #report:
    candidate_report
    hypothesis
    test_result
```

| Step | Command |
|---|---|
| `exec readonly availability check` | `python -m chilicrisp doctor` and `python -m chilicrisp capabilities` |
| `exec baseline check` | `python -m chilicrisp check BRIEF --workspace ORIGINAL --baseline ORIGINAL -- COMMAND` |
| `exec readonly brief render` | `python -m chilicrisp brief BRIEF` |
| `exec readonly test diff` | `git diff --no-index --stat ORIGINAL/TESTS CANDIDATE/TESTS` for each test, fixture and driver path (empty output = unchanged) |
| `exec candidate check` | `python -m chilicrisp check BRIEF --workspace CANDIDATE --baseline ORIGINAL --same-output -- COMMAND` |
| `exec project tests` | the project's own test command, run in the candidate |
| `exec readonly brief render with report` | `python -m chilicrisp brief BRIEF --report REPORT` (the `report.json` path printed by the last check) |

## Step meanings

- **task facts**: the target source directory, correctness tests, the command
  to measure (argv run inside the code's directory), and the resource
  objective, taken from the request and repository. Infer ordinary details.
- **task update**: fold the user's answers into the task facts.
- **brief choice**: a built-in profile from `python -m chilicrisp profiles`,
  or a JSON brief that `extends` one (format in the framework's
  `docs/current/briefs.md`). Use relative budgets (`25%`) when the target
  machine is "less than today".
- **candidate copy**: copy the original into a separate candidate directory.
  The original is the baseline. Keep the user's existing edits.
- **baseline**: the original directory. Nothing in this procedure writes it.
- **hypothesis**: what consumes the over-budget resource, the change you
  will make, the saving you expect, and what result would prove you wrong.
  Prefer structural changes (streaming, data layout, algorithm, lifetime)
  over small tweaks.
- **candidate change**: edit only the candidate's implementation. Never weaken
  tests, accuracy requirements, fixtures or the measured workload, and never
  move work outside the measured command or cache results between runs.
- **restored tests**: copy the baseline's versions of any changed test,
  fixture or driver back into the candidate.
- **run budget**: the run, wall-time and model/tool budget the task declares,
  counting failed attempts; if none is declared, stop after five designs
  that do not fit.
- **brief_file**: the brief JSON beside the candidate (skip writing it when a built-in profile is used unchanged).
- **framework**: the Chili Crisp installation. **candidate_dir**: the
  candidate directory. **candidate_notes**: a notes file beside the
  candidate.

## Report

Report the hypothesis, the measured baseline and candidate numbers, the verdict,
the test result, tradeoffs (for example time spent to save memory), and the
`report.json` path. Keep unavailable metrics explicit. Budgets are measured after
each run on this machine, not enforced; never say a limit was enforced. A
candidate that fits is a design to review, not an automatic merge: integrating
it needs the task's own authority. If blocked, say which gate stopped the work
and what was tried.

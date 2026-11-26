# A/B study: brief versus plain prompt

**Question:** Does a constraint brief (story, hard budgets, measured verdict)
lead a coding agent to more memory-efficient, still-correct code than a
plain "use less memory" prompt, at similar cost?

This is the experiment that decides whether the brief approach steers agents
better or is only a nicer benchmark harness. Nothing below has been run yet.

## Arms

Same model, same tools, same turn and token cap, same starting code.

| Arm | What the agent gets |
| --- | --- |
| **Plain** | "Reduce this program's peak memory use. Output must stay identical." plus the run command |
| **Brief** | `chilicrisp brief quarter --report REPORT` output for the same task (story, budgets, rules, baseline numbers, `--where` breakdown), and permission to run `chilicrisp check` itself |

To separate the effect of the brief's text from the effect of being able to run
the measurement, add a third arm if the budget allows: **Plain + check**, the plain
prompt plus `chilicrisp check` access but no story or budget.

## Tasks

Each task needs a correct baseline that uses too much memory, a deterministic output, and a
larger held-out input.

1. **Synthetic:** `examples/brief-demo` and a few variations of it, to test the
   harness before any study run.
2. **Benchmark problems:** memory-heavy problems from
   [EffiBench](https://arxiv.org/abs/2402.02037) and
   [ECCO](https://arxiv.org/abs/2407.14044). They come with tests and reference
   solutions, so a correct answer is known.
3. **Real repositories:** a handful of command-line programs with a reproducible
   workload, chosen before any arm runs.

Aim for 20 or more tasks with 3 independent attempts per arm per task. Fix the
task list and the analysis before running.

## Measurement

The final check is the same for every arm and is run by the harness, not the
agent:

```text
chilicrisp check quarter --workspace CANDIDATE --baseline ORIGINAL --same-output \
  --repeat 5 --exact-memory -- COMMAND
```

The brief used for grading declares `inputs` with a final **hidden** input that
neither arm sees, and its data and `--out` sit outside the agent's workspace.

## Outcomes

- **Primary:** share of attempts whose verdict is `fits` on the hidden
  input, compared per task between arms.
- **Secondary:** peak-memory ratio (candidate / baseline) among correct attempts;
  wall-time ratio; tokens and turns used.
- **Gaming:** an attempt counts as a hack, and as a failure, if it leaves files
  between runs (`changed_files`), matches a `forbid` rule, passes the visible
  inputs but fails the hidden one, or a diff review finds the work moved
  outside the measured command. Report the hack rate per arm; GSO started
  reporting scores adjusted for hacks after finding agents gamed its timing
  ([GSO](https://github.com/gso-bench/gso)).

## Analysis

Compare arms task by task, since tasks differ far more than arms do. Report each
task's result for both arms, a sign test on per-task success, and the
median memory ratio with its spread. With about 20 tasks, only a large effect
will show; say so rather than over-reading a small difference.

## What would change the plan

- The brief arm wins on success at similar cost: make briefs the default
  interface of the development loop.
- Only **Plain + check** matches it: the value comes from the measured feedback,
  not from the story. Keep briefs short and lean on `check`.
- Higher hack rate in the brief arm: hard budgets invite gaming. Strengthen the
  fresh-state and hidden-input checks before shipping briefs further.

## Prior results that shaped this

- Without a hint, models usually make only small performance improvements; the
  big gains came when a developer gave detailed context
  ([Yi et al. 2025](https://arxiv.org/abs/2510.15494)). That is the hypothesis
  under test.
- Models rarely improve time or memory without breaking correctness
  ([ECCO](https://arxiv.org/abs/2407.14044)), hence the hidden input and
  `--same-output`.

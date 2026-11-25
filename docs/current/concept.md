# Chili Crisp: the concept

## The idea in one paragraph

Great software often came out of tight machines. People who had 2 MB of RAM
or a 1.44 MB floppy couldn't tune their way to a fit, so they changed the shape
of the solution: streaming, compact layouts, precomputation, better algorithms.
Chili Crisp gives a coding agent that same pressure on purpose. You write a
**constraint brief**, which is a short story about an imagined target machine
plus hard budgets and rules. The agent designs for that machine. Chili Crisp
then runs the result on the ordinary machine you already have, measures it, and
tells you whether it fits. No VM, no emulator, no kernel tricks.

## Three parts

| Part | What it is | Who owns it |
| --- | --- | --- |
| **Brief** | Story, budgets (memory, time, CPU, artifact size, I/O), rules, hints | You |
| **Design** | The candidate change, made against the brief | The agent |
| **Check** | Measured on the real machine, compared with the baseline, verdict | Chili Crisp |

The brief is the creative constraint. The check is what keeps it honest.

## Why imagined machines work

- **Budgets below current usage force structural ideas.** If a program needs
  200 MiB and the budget is 50 MiB, shaving 5% is pointless. The agent has to
  find what actually holds the memory and remove the need for it. That is the
  kind of change worth keeping.
- **A story carries constraints that numbers don't.** "Battery-powered handheld,
  no network" tells the agent to prefer simple, local and predictable designs.
  This holds even where no metric checks it.
- **Relative budgets travel.** `"25%"` means a quarter of whatever the baseline
  uses on this machine, so the same brief works on a laptop and in CI.
- **Measurement only after the fact is enough to learn from.** We don't need the
  kernel to kill a process at 50 MiB to know it used 200. Hard enforcement
  matters for adversarial grading, not for design exploration.

## Honesty levels

Each constraint has one of three levels. Don't treat one level as another.

1. **Imagined**: in the brief only (for example "no network", "stateless").
   It shapes the design and nothing checks it, unless a `forbid` pattern
   approximates it.
2. **Measured** (default): checked after the run on the current machine.
   Memory is the largest of the sampled process-tree RSS and each process's
   OS-recorded lifetime peak. Time is wall clock. CPU and I/O are sampled.
   These are good screening numbers, not exact accounting.
3. **Enforced** (optional, Linux): cgroup limits, an isolated runner, sealed
   grading. It lives in [enforced/](enforced/native-development.md). Use it only
   when you need adversarial guarantees or a true survive-or-die boundary.

## The loop

```text
brief ──► agent designs candidate ──► chilicrisp check ──► fits? ──► keep it, tighten the brief
   ▲                                        │
   └─────────── findings + numbers ─────────┘ (over budget / broken)
```

1. Pick or write a brief (`chilicrisp profiles`, or a JSON file that
   `extends` a profile).
2. Give the agent `chilicrisp brief BRIEF` as its design brief.
3. The agent changes a copy of the code and states what it expects to save.
4. `chilicrisp check BRIEF --baseline ORIGINAL --workspace CANDIDATE
   --same-output -- COMMAND` runs both, alternating, and returns a verdict:
   `fits`, `over_budget`, `broken` or `incomplete`.
5. Feed `chilicrisp brief BRIEF --report report.json` back to the agent, with
   the measured numbers and findings filled in.
6. When it fits, tighten the brief (25% → 10%) or switch machines. The
   [measured development loop](development-loop.md) automates repeated rounds
   with moving targets, checkpoints and rollback.

## Ground rules

- **Behavior is fixed.** Output must match the baseline, and the project's own
  tests must still pass. A candidate that is smaller but wrong is `broken`.
- **No scalar score.** Each budget is reported separately, so trading memory
  for time stays visible and is limited by the time budget.
- **No gaming.** Moving work outside the measured command, caching results
  between runs or weakening tests defeats the purpose. The check alternates
  runs and compares output, but it trusts the code it runs; it is not a sandbox.
- **Fitting is not shipping.** A candidate that fits is a design worth reviewing,
  not an automatic merge.

## Open questions worth testing

- Do imagined-machine briefs produce better *transferable* improvements than a
  plain "make this use less memory" prompt with the same measurement tools? A
  small A/B on real repositories would answer this. Nothing so far shows it.
- Which stories work best? Specific hardware ("handheld"), relative squeeze
  ("quarter"), or ladders that tighten each round?
- Should we add more checkable rules, such as dependency counts, import
  allowlists or allocation counts, without turning briefs into a sandbox spec?

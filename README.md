# Chili Crisp

**Design against an imagined machine. Verify on a real one.**

Tight hardware pushed programmers toward great designs: streaming, compact data
and smarter algorithms. Chili Crisp gives a coding agent that pressure on
purpose. You write a *constraint brief*: a short story about a target machine
plus hard budgets. The agent redesigns for it. Chili Crisp then runs the
result next to the original on your normal machine and tells you whether it
fits. It needs no VM and no emulator.

```text
python -m pip install -e .
python -m chilicrisp profiles
python -m chilicrisp brief quarter            # hand this to your agent
python -m chilicrisp check quarter --baseline original/ --workspace candidate/ --same-output -- python main.py
```

```text
verdict: fits
peak_memory_bytes   within   baseline 209.9 MiB → limit 52.5 MiB → measured 20.9 MiB
wall_seconds        within   baseline 859 ms   → limit 1.29 s   → measured 360 ms
```

Budgets can be absolute (`16MiB`, `250ms`) or relative to the baseline (`25%`).
Rules give context ("no network") and `forbid` patterns check them cheaply.
Verdicts are `fits`, `over_budget`, `broken` (the output changed or a run
failed) or `incomplete`.

## Docs

- [Concept](docs/current/concept.md): why imagined constraints work, the
  honesty levels and the loop
- [Briefs](docs/current/briefs.md): file format, profiles, CLI and measurement limits
- [Development loop](docs/current/development-loop.md): multi-round moving
  targets with checkpoints and rollback (`chilicrisp dev`)
- [Enforced tier](docs/current/enforced/native-development.md): optional Linux
  cgroup limits and isolated builds, for when you need hard guarantees
- [Status](docs/STATUS.md)

## Layout

```text
chilicrisp/      package: constraints, dev loop, measurement, optional enforced runner
  schemas/       versioned JSON contracts
  skills/        chili-dev skill for coding agents (export: chilicrisp skill DEST)
examples/        brief-demo/ (start here), local-project/, enforced-runner manifests
tests/           portable test suite: python -m unittest discover -s tests
tools/           demos, Linux/WSL setup, native fixture and CI drivers
verification/    frozen oracles used by the enforced-tier tests
docs/            STATUS.md, current/, archive/
```

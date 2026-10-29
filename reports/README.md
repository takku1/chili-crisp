# Reports

- [Native development bridge](native-development-validation.md): two retained
  generations at 96 → 48 → 24 MiB enforced budgets, negative controls and rollback.

- [Real model source pilot](model-source-pilot.md): two bounded model submissions,
  a retained public rejection, and protected heldout confirmation of a 4 MiB gain.

- [Measured development loop](development-loop-validation.md): VM-free moving
  targets, agent command protocol, two real generations, recovery and rollback.

- [Chili Crisp decoder self-test](dogfood-decoder.md): a source-changing candidate,
  pinned correctness checks, 18 native resource trials and fresh confirmation.

- [CPU controls and sweeps](cpu-validation.md): web-researched quota semantics,
  native throttling measurements, rejection gates and repeated quota experiments.

- [Native runner and development workflow](native-validation.md): Ubuntu WSL
  isolation, OOM, output limits, cleanup and recovery fixtures.
- [Tool policy and package cleanup](tool-package-cleanup.md): correctness-file
  checks, evidence verification, canonical package resources and release checks.

- [Field-level oracle and portable dependencies](worldgame/field-oracle-and-portability.md): generated-world fields, independent manufactured solutions, and an empty-cache offline component build.

- [Worldgame oracle and frozen source](worldgame/oracle-and-snapshot.md): structured grading of the three saved runs, negative tests, source archive, and an isolated snapshot build.

- [Worldgame real baseline](worldgame/README.md): three Windows ocean benchmark runs, memory/timing counters, conservation residuals, and 22 existing tests.
- [First code-review fixes](review-fixes-validation.md): controller corrections, emergency failure handling, baseline fingerprinting, and updated verification.

- [Initial implementation validation](initial-validation.md): what the current outputs establish, the synthetic frontier behavior, and the remaining evidence gaps.
- [Raw test output](tests.log) and [manifest validation](manifest-validation.log).
- [Run environment, commands, and source hashes](validation-run.json).
- [Synthetic controller trace](synthetic-frontier.json), explicitly not a measured program frontier.

Regenerate local validation artifacts with `python reports/collect.py` from the repository root. This replaces the local logs and metadata; it does not update the interpretation report automatically or run an optimization study. Archive these files before rerunning if historical comparisons are needed.

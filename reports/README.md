# Reports

- [Field-level oracle and portable dependencies](worldgame/field-oracle-and-portability.md): generated-world fields, independent manufactured solutions, and an empty-cache offline component build.

- [Worldgame oracle and frozen source](worldgame/oracle-and-snapshot.md): structured grading of the three saved runs, negative tests, source archive, and an isolated snapshot build.

- [Worldgame real baseline](worldgame/README.md): three Windows ocean benchmark runs, memory/timing counters, conservation residuals, and 22 existing tests.
- [First code-review fixes](review-fixes-validation.md): controller corrections, emergency failure handling, baseline fingerprinting, and updated verification.

- [Initial implementation validation](initial-validation.md): what the current outputs establish, the synthetic frontier behavior, and the remaining evidence gaps.
- [Raw test output](tests.log) and [manifest validation](manifest-validation.log).
- [Run environment, commands, and source hashes](validation-run.json).
- [Synthetic controller trace](synthetic-frontier.json), explicitly not a measured program frontier.

Regenerate local validation artifacts with `python reports/collect.py` from the repository root. This replaces the local logs and metadata; it does not update the interpretation report automatically or run an optimization study. Archive these files before rerunning if historical comparisons are needed.

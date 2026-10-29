# First review fixes and validation

The reported all-passing frontier bug reproduced in a regression test: the old code returned `INVENT` with no failing boundary. A second regression showed that timeout feedback incorrectly refined a memory bracket. Both behaviors are fixed.

| Change | Current behavior | Verification scope |
| --- | --- | --- |
| No-failure descent | Stops at minimum/resolution without claiming an invention; `INVENT` requires a passing/OOM bracket | Regression test against a known all-pass sequence |
| Timeout classification | Stops for latency diagnosis; does not mark a memory failure; controller retains timeout records separately | Policy regression test; real timeout cause remains unclassified |
| Baseline fingerprinting | Repeated target-uncapped runs; peak plus margin rounded to pages; baseline counts against trial/time budget | Injected measured-peak tests, failure-stop tests; native cgroup collection still unverified |
| Failure finalization | Cleanup independent of journal writes; original error retained; emergency diagnostic attempted if ordinary evidence fails | Journal-init, journal-write, and result-write failure injection |
| Output flood handling | Stops reading/hashing on first oversized chunk; marks retained-prefix hash and observed byte count | Real portable flooding process and bounded-stream test |
| Hostile Linux fixtures | Added capability, seccomp, network/process-creation, root-write, and cgroup-visibility checks | Prepared but skipped on Windows |

At this revision, the portable suite had **20 test methods: 18 passed, 2 native methods skipped**. Exact source hashes, command results, and logs are retained in [validation-run.json](review-fixes/validation-run.json) and [tests.log](review-fixes/tests.log). Failure-injection tests establish the exercised control paths, not resilience to every storage failure or crash. If all evidence storage fails, only an in-memory diagnostic can remain; no durable-record guarantee is made.

The original 11-pass/2-skip evidence is preserved under [initial/](initial/validation-run.json), so the original report remains tied to its original results.

There is now a separate real [Worldgame Windows baseline](worldgame/README.md), including three benchmark runs and 22 existing ocean-related tests. It does not clear the native Linux enforcement gate or demonstrate an optimization. Docker and WSL access remain denied in this managed session.

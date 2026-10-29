# Two-tier verification pilot — 29 October 2026

The public Worldgame verifier now has a fast screening tier and a full public
verification tier. A real source change compiled and was rejected on numerical
values by the independent oracle. This validates an early rejection path; it is
not a model-generated optimization experiment or an accepted improvement.

## Observations

| Trial | Build | Result | Total wall time |
| --- | --- | --- | ---: |
| Frozen baseline, screen | Passed | Both public screening cases passed | 8.03 s |
| Frozen baseline, full | Passed | All six public cases passed | 8.09 s |
| Deliberately incorrect solver, screen | Passed | Rejected on first manufactured case | 6.64 s |

The candidate is an isolated copy under `artifacts/incorrect-solver-20261029T043608Z`.
One inserted statement multiplies solved values by 0.99 immediately before the
solver returns its convergence success report. The owner-controlled driver and
analytic comparator were unchanged by this candidate. Original Worldgame source
and the frozen baseline were untouched.

The independent oracle rejected field 18: candidate `0.03780092079852506`,
reference `0.038182748283360816`. The rejected case took approximately 0.047 s,
including process launch and field comparison. No later case or full test suite
was run for that candidate. Rejection output and trial metadata were retained.

Screening evaluates the 17×17 manufactured case first, then ocean seed 42.
Full public verification retains all six existing cases. Reference files are
matched by case identity and hash, with stable original file indexes. Both tiers
record `acceptance_eligible=false`; neither can promote a champion.

Fresh compilation dominates these small runs. Screen and full total wall times
were nearly identical here, so this pilot does not establish an overall speedup.
The benefit demonstrated is early numerical rejection without invoking the
roughly 194-second debug unit-test phase from the preceding status run. These
durations are diagnostics, not benchmark or transplant measurements.

## Checks and limits

The portable suite ran 40 tests: 38 passed, two native Linux tests skipped. Added
tests cover stable screen/full reference indexing and rejection of mismatched or
tampered reference fields. Seven pilot assertions passed, including changed
candidate identity, unchanged baseline identity, successful compilation, baseline
passes, numerical rejection, and absence of an acceptance claim.

The verifier operates on owner-reviewed sources; it does not isolate arbitrary
generated Rust or build scripts. The pilot is a deliberate negative control,
authored locally, with no model call or resource optimization claim. It does not
complete the protected automatic build or finalist acceptance services.

WSL still returns E_ACCESSDENIED and Docker's engine pipe remains permission-denied.
No SSH target was configured in this session. The Linux VM hostname/login is the
missing input for native fixtures and the BenchExec contract comparison. Native
measurements, transplant acceptance, promotion, rollback, and consecutive moving
generations remain unavailable or unfinished.

Scope of this increment: verifier tiers, retained pass/rejection evidence,
focused regression tests, this negative control, and existing roadmap/docs.
No production runner, oracle tolerance, frontier policy, or source in `Z:\worldgame`
was changed. The workspace has no Git checkout; this increment was unguarded.

## Evidence

- [All commands, checks, source hashes, and complete trial results](results.json)
- [Candidate source diff](candidate.diff)
- [Good screening log](good-screen.log)
- [Good full-verification log](good-full.log)
- [Rejected-candidate log](bad-screen.log)
- [Good screening evidence](../worldgame/field-checks/20261029T043609657574Z/results.json)
- [Good full evidence](../worldgame/field-checks/20261029T043617682404Z/results.json)
- [Bad candidate rejection evidence](../worldgame/field-checks/20261029T043625781331Z/results.json)

Reproduce with `python reports/run-screening-pilot.py`. This uses the existing
frozen baseline and full reference directory; it creates a fresh candidate copy
and evidence directory rather than editing an existing Worldgame checkout.

# Pressure-to-invention protocol

A failed budget is evidence of behavior under pressure, not an architectural diagnosis.

1. Identify a meaningful pressure region on public workloads under the frozen environment.
2. Classify measured composition, reclaim, latency, input scaling, and allocation patterns only where instrumented.
3. Generate at least two competing explanations consistent with the evidence.
4. Design discriminating probes without changing the candidate implementation: vary public input shape or scale, inspect counters, or use qualified profiling. If instrumentation perturbs behavior, record and separate that run from frontier measurements.
5. Select the best-supported explanation, or retain uncertainty if neither is supported. Propose one bounded change with a predicted benefit, expected tradeoff, and falsification condition.
6. Test on the same public policy, preserve failed hypotheses, and freeze the candidate before hidden evaluation.
7. Independently compare on normal hardware and apply all acceptance gates.

| Pressure signature | Candidate directions to investigate |
| --- | --- |
| High anonymous memory | Compact representation, streaming, shorter object lifetimes |
| Instrumented allocation spikes | Buffer reuse, arenas, bounded pools |
| File-cache growth with reclaim | Sequential access, chunking, access-pattern changes |
| Growth with input scale | Complexity reduction, streaming, external-memory algorithms |
| Latency degradation before OOM | Working-set localization, less cache churn or recomputation |

These mappings suggest hypotheses; they do not establish causes. External-memory designs must include disk and I/O costs. Every journal entry links observations, competing explanations, probe results, candidate diff, and acceptance decision. An explanation remains hypothetical until its discriminating evidence exists.

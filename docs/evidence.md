# Evidence and acceptance contract

The [runner contract](engineering-contract.md) defines required trial fields, schema validation, evaluation-set exposure, and cost accounting. Hidden confirmation is sealed until candidate freeze; a revision informed by confirmation requires fresh final grading inputs.

The agent's prose is never the source of a performance number. Every reported result links to a runner-produced record and the frozen experiment manifest.

## Frozen manifest

The controller pins and hashes:

- target source revision and permitted edit paths;
- release-oriented build command, compiler and flags, dependencies, lockfiles, binary hash;
- host CPU, memory, kernel, cgroup setup, relevant container or VM image, and environment variables;
- workload identities, input hashes or generator version and seeds, output comparator, behavior specification, and timeout policy;
- memory accounting boundary, swap and cache policy, process and external-service policy;
- search parameters, repetition counts, stopping limits, and acceptance thresholds.

Hidden inputs and their expected results stay outside the candidate workspace. The controller should preserve the manifest and result records in storage the candidate cannot rewrite. Hashes make accidental changes visible, but a hash inside a candidate-writable JSON file is not tamper proof.

## Per-trial record

Each trial needs a unique ID, timestamp, manifest hash, candidate source and artifact hashes, workload ID, budget in bytes, run order or randomization seed, cgroup identifier, exact command, exit status, verifier result, duration, `memory.peak`, before/after `memory.events`, relevant `memory.stat`, raw output locations, and a failure classification. Record metric units and collection method. An absent counter is `unavailable`, never zero.

The experiment journal links each candidate diff to its hypothesis, predicted gain, expected cost, observed outcome, and reason for rejection or recommendation. The report includes all attempted candidates, not only the winner. Repeated runs should show distributions or individual values; a single best run is not a summary.

## Independent correctness

Three statements must remain distinct:

1. **Reference equivalence:** candidate output matches the baseline or reference on tested inputs.
2. **Specification compliance:** candidate satisfies independent required behavior on tested inputs.
3. **Resource improvement:** candidate changes measured resource use under the declared conditions.

A baseline can contain bugs, so equivalence alone is insufficient. A behavior fix is a separate change decision; it must not be silently credited as an optimization. Use frozen regression tests, held-out inputs, differential comparison where a trustworthy reference exists, and property or metamorphic tests where useful. Sanitizers can provide extra evidence for native code but cannot prove general correctness. [Csmith](https://github.com/csmith-project/csmith) illustrates differential testing; it is precedent for a method, not a Chili Crisp oracle.

## Acceptance gates

| Gate | Required result |
| --- | --- |
| Reproducibility | Fresh builds and reruns produce compatible outcomes; all raw records and hashes are retained |
| Behavior | Public and hidden correctness checks pass at normal and pressured limits |
| Transfer | Measured normal-hardware performance and resource tradeoffs are reported on representative inputs |
| Generality | No workload IDs, test-output tables, or input-specific shortcuts; behavior holds across input scales |
| Value | Improvement clears predeclared meaningful threshold without unacceptable latency, I/O, complexity, portability, or reliability cost |

Passing all gates supports a **recommendation for review**, not automatic integration. SPEC's prohibition on [benchmark-specific optimizations](https://www.spec.org/cpu2026/docs/runrules.html) motivates the generality gate; Chili Crisp does not claim SPEC compliance.

## Report language

Use a conditional statement: “On workload W, build H, host E, with policy C, candidate X passed 10/10 trials at budget B; baseline passed 0/10 at B. Normal-hardware median latency changed from L1 to L2 across N runs. Hidden checks passed.” Include uncertainty and other tradeoffs. Do not translate this into “requires B bytes of RAM” or “is 40% faster everywhere.”

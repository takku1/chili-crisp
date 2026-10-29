# Discovery engine roadmap

Chili Crisp is intended to be a model-agnostic experiment engine that external coding agents can use. Constraint-Induced Architectural Discovery (CIAD) names the proposed workflow; it is not an established method or a novelty claim. The current implementation remains a memory-only exploration runner and controller.

The proposed [outer generation controller](evolution.md) manages promotion, rollback, moving challenge budgets, and diminishing returns after native validation. It is a planned contract, not implemented evolutionary search.

## Delivery gates

Current priority is one source-changing optimization generation after native
Linux fixtures pass. Two-tier public Worldgame verification is implemented;
its compiled negative-control pilot demonstrates early numerical rejection.
See [the pilot evidence and remaining blockers](../reports/screening-20261029T043608Z/REPORT.md).
Linux access remains blocked locally; no SSH research VM target is configured.
BenchExec replacement and generation/promotion work remain gated on native
compatibility, protected build transport, and independent acceptance evidence.

The framework now has an initialized local Git repository on `main`, but its
initial commit is blocked: this session cannot create `.git/index.lock` under
the managed read-only `.git` policy. Prepared tracking rules include source,
contracts, tests, and textual reports while excluding generated numerical arrays,
portable ZIP bundles, build outputs, and candidate workspaces. Complete the
[baseline commit](../reports/version-control.md) outside this restricted session
before repeated source modifications. Then use a separate branch or worktree for subsequent source changes,
record the parent commit with each experiment, and retain artifact hashes in
evidence. Earlier reports correctly describe their own runs as unguarded.

Package/framework cleanup now provides installable metadata, wheel schema assets,
portable CI, a BenchExec trusted-fixture probe, and a frozen-candidate OpenEvolve
feedback bridge. [Integration status and remaining gates](frameworks.md) distinguish
these interfaces from native runner replacement and autonomous generation. Reuse
OpenEvolve populations/checkpoints rather than implementing a new candidate database.

| Stage | Deliverable | Gate before advancing |
| --- | --- | --- |
| v0.1 | Runner, isolation/preflight, schemas, bounded output, recovery, deterministic frontier | Native fixtures demonstrate enforcement, correct classification, and no leaked tasks; independently reproduce raw measurements |
| Next | Resource Pressure Map and controlled diagnostic probes | Each plotted point links to raw trials; overhead is quantified; signatures and causal explanations remain distinct |
| Next | Small architectural transformation catalog | Each proposal states prerequisites, competing explanations, falsification criteria, and resource tradeoffs |
| v0.3 research | Candidate Pareto portfolio, constraint curriculum, evidence retrieval | Demonstrated value against simpler search under matched budgets; sealed grading cannot be reused for learning |
| Experimental | Population/evolution and multiple agent workers | Independent benefit exceeds coordination and compute cost |

## Resource Pressure Map contract

The next schema should group observations by immutable candidate, workload class, input scale, environment, cache policy, instrumentation mode, and enforced memory limit. Preserve pass/failure counts, elapsed-time distribution, charged peak memory, memory composition, reclaim/OOM event deltas, available pressure-stall counters, and accounting limitations. Missing measurements remain unavailable. Do not invent a universal reclaim index or interpolate untested budgets into measured outcomes.

The current runner retains `memory.stat`, `memory.events`, `memory.peak`, and `cpu.stat`, but lacks the complete time series, sampling policy, and pressure-map aggregation. A high file-cache count alone does not identify an object-graph bottleneck. Connect any architecture claim to a profiler or a discriminating probe.

Counterfactual probes should change one declared variable where feasible, retain control runs, randomize order, and distinguish input-shape tests from implementation-changing interventions. Omitting an intermediate representation or altering allocation lifetime changes the program and belongs in a diagnostic candidate, not an unchanged-source measurement. Measure instrumented and uninstrumented controls separately; do not insert profiler-affected measurements into an ordinary frontier without qualification.

## Transformation and evidence records

A future catalog can cover compact layouts, streaming, lifetime changes, buffer reuse, bounded pools, and recomputation. Entries are conditional suggestions, never automatic diagnoses. Store pressure signature, applicability conditions, source/artifact identity, candidate diff, hypothesis, rejected alternatives, probes, public and sealed correctness evidence, transfer results, costs, and limitations. Retrieve only evidence allowed by evaluation policy. Hold out entire components when testing whether retrieval generalizes; avoid benchmark-solution contamination.

Keep nondominated candidates only among comparable, correctness-eligible measurements. Include uncertainty and declared latency/I/O limits before Pareto selection. Do not equate lower memory with superiority. A future capability or storage curriculum requires its own enforcement and accounting contract; it must not silently extend the memory pilot.

## Controlled comparison

| Arm | Information and tools |
| --- | --- |
| A | Code, public tests, ordinary profiler/measurement access, conventional optimization prompt |
| B | A plus enforced artificial memory pressure and its trial results |
| C | B plus structured pressure mapping and discriminating diagnostic probes |
| D | C plus transformation catalog, eligible evidence retrieval, and candidate selection |

Keep the model/version, component, oracle, normal profiler access, and declared cost caps matched. B adds scarcity without removing A's tools. C versus B measures the diagnostic package; D versus C measures a bundle, so additional ablations are required to isolate mutation proposals, retrieval, and selection individually. Agent behavior cannot be blinded to resource feedback, but grading and run scheduling can be separated from candidate generation.

Randomize assignment and normal-hardware run order, preregister primary outcomes and stopping rules, retain failed attempts, and use independent sealed grading. Measure verified transferable improvements per dollar and compute-hour, actual budget consumption, behavior failures, memory/latency/I/O changes, and reproduction rate. Diversity of architectural transformations needs a predeclared classification procedure rather than an agent's self-description.

These arms support bounded causal estimates under the tested conditions. They cannot make an unassailable claim of superiority across software. A versus D tests the package; it does not prove every mechanism in the package. Separate profiler-access effects, diagnostic overhead, and search effort in the analysis.

## Prior work and benchmark selection

[AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) already combines LLM proposals, automatic evaluation, a program database, and evolutionary selection. Therefore neither evolutionary code search nor automated architectural proposals establish Chili Crisp's novelty. Compare the proposed pressure-guided discovery protocol empirically, rather than asserting competitors lack architectural reasoning.

[GSO (NeurIPS 2025)](https://proceedings.neurips.cc/paper_files/paper/2025/hash/ddd98389004161943e646322a16348c3-Abstract-Datasets_and_Benchmarks_Track.html), [SWE-Perf (ICML 2026)](https://proceedings.mlr.press/v306/he26y.html), and [SWE-fficiency (ICML 2026)](https://proceedings.mlr.press/v306/ma26l.html) provide repository performance tasks and report agent limitations in their evaluations. They motivate evaluation, not a claim that all agents perform blind search. Check licenses, task leakage, reproducibility, and compatibility with the isolated runtime before adopting tasks. Add separately frozen memory-sensitive workloads; runtime-optimization benchmarks alone cannot validate a memory-pressure methodology.

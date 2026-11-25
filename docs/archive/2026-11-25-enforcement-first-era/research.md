# Research notes and source map

## Academic framework and implementation foundations

Additional comparators and evaluation sources: [AlphaEvolve's primary paper](https://arxiv.org/abs/2506.13131), [GSO](https://proceedings.neurips.cc/paper_files/paper/2025/hash/ddd98389004161943e646322a16348c3-Abstract-Datasets_and_Benchmarks_Track.html), [SWE-Perf](https://proceedings.mlr.press/v306/he26y.html), and [SWE-fficiency](https://proceedings.mlr.press/v306/ma26l.html). Their methodological implications and the limits of four-arm attribution are recorded in the [roadmap](roadmap.md).

The first sandbox adapter follows [bubblewrap's option semantics](https://github.com/containers/bubblewrap/blob/main/bwrap.xml) and uses a controlled rootfs, namespaces, and a generated seccomp filter. Its minimum version follows the [upstream rootfs setup advisory](https://github.com/containers/bubblewrap/security/advisories/GHSA-pxhw-h44j-8pfx). Native conformance still requires the Linux fixtures; dependency selection is not evidence that the assembled sandbox is secure.

- [Kalibera and Jones, Rigorous Benchmarking in Reasonable Time (ISMM 2013)](https://kar.kent.ac.uk/33611/) examines uncertainty across benchmark repetitions and execution levels. Adopt a nested measurement plan: distinguish builds, fresh processes, and within-process iterations; choose repetition effort from observed variance. Ten executions do not automatically provide ten independent samples.
- [Curtsinger and Berger, STABILIZER (ASPLOS 2013)](https://people.cs.umass.edu/~emery/pubs/stabilizer-asplos13-draft.pdf) studies performance bias from execution layout and randomization. Its result motivates checking confounders; ordinary run-order randomization is not equivalent to implementing STABILIZER and cannot remove every layout bias.
- [Ansel et al., OpenTuner (PACT 2014)](https://commit.csail.mit.edu/papers/2014/ansel-pact14-opentuner.pdf) presents a framework for domain-specific, multi-objective autotuning and adaptive search techniques. It is a close methodological comparator. Chili Crisp's proposed addition is pressure-guided architectural hypothesis generation; superiority remains untested.
- [clone(2), including clone3 and CLONE_INTO_CGROUP](https://www.man7.org/linux/man-pages/man2/clone.2.html) documents creation directly inside a cgroup. This supports eliminating workload-start migration races; availability and permissions still require preflight.

For a research evaluation, preregister the primary outcome, effect threshold, stopping rule, workload sampling, exclusion criteria, budget allocation, and treatment assignment before running the comparison. Report effect sizes and uncertainty at the actual independent sampling level. Repeated trials of one component cannot support claims about all software. Treat adaptive exploration as hypothesis generation and sealed grading as evaluation. These are adopted experimental policies, not conclusions established by a Chili Crisp study.

Research checked 2026-10-28. These sources support methods and limits; they do not establish that Chili Crisp outperforms ordinary optimization.

| Source | What it establishes | Design consequence |
| --- | --- | --- |
| [Linux kernel: cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html) | `memory.max` is a hard cgroup limit; `memory.peak`, `memory.stat`, and `memory.events` expose charged usage and pressure. Accounting is broad but not completely watertight; reclaim and temporary limit overruns matter. | Use fresh cgroups, record the entire target process tree and raw counters, and avoid equating a measured peak with minimum viable RAM. |
| [Google Benchmark user guide](https://github.com/google/benchmark/blob/main/docs/user_guide.md) and [random interleaving](https://github.com/google/benchmark/blob/main/docs/random_interleaving.md) | Repetition, distributions, warmup, and interleaving address benchmark variability. | Store per-run results and compare distributions under a declared cache/warmup policy. The exact statistical design is Chili Crisp's responsibility. |
| [SPEC CPU2026 run rules](https://www.spec.org/cpu2026/docs/runrules.html) | Benchmark-specific “specials” can misrepresent transferable improvement. SPEC defines its own reporting and validation rules. | Use hidden inputs, varied scales, and a transfer check; do not claim SPEC certification. |
| [Linux `perf-list` manual](https://man7.org/linux/man-pages/man1/perf-list.1.html) | Hardware events can be multiplexed and counts can be misleading when workload profiles vary. | Treat instructions/cycles as qualified secondary metrics, not a simulated CPU clock. |
| [STOKE paper](https://www.microsoft.com/en-us/research/publication/stochastic-superoptimization/) and [Souper paper](https://arxiv.org/abs/1711.04422) | Automated search for optimizations is established at machine-code and compiler-IR levels. | Position Chili Crisp as a proposed source/architecture experiment protocol; evaluate novelty empirically. |
| [Csmith project](https://github.com/csmith-project/csmith) | Differential testing can expose behavioral divergence using generated programs. | Compare candidates with a reference where appropriate, while keeping independent specification checks. |

## Corrections to the brainstorm

- **Codebase size is not a RAM formula.** Runtime and workload dominate. Use measured fingerprints and verify every proposed budget.
- **256 KB is an example, not a default.** The pilot starts near its observed resource envelope and descends from there.
- **Binary search assumes a clean boundary.** Memory pressure may yield noisy results. Use geometric discovery, repeated local sampling, and pass-rate reporting.
- **RSS is not the budget metric.** Use an enforced cgroup boundary and its counters; document any uncharged or shared resources.
- **CPU throttling is not 20 MHz emulation.** Any historical machine claim would require a separate emulator or instruction model.
- **A measured optimization does not prove the methodology.** A controlled comparison against ordinary optimization is needed.

The Crash Bandicoot and RollerCoaster Tycoon anecdotes in the brainstorm may motivate the idea, but they are unnecessary to the technical case and are omitted from the specification.

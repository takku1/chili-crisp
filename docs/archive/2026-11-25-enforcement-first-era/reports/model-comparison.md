# Bounded real-model comparison

29 October 2026, America/New_York. Framework parent: `a342325` plus the
uncommitted proposal-transport and target-description changes identified in
the frozen protocol. Both arms passed sealed grading. This pilot demonstrates
the complete workflow; it provides no evidence of an advantage from scarcity.

## Frozen design and actual effort

The task is the separate-account fixture's C byte sum: return the exact sum of
`n` bytes whose values are one. The baseline allocates and touches up to 64 MiB.
The protected contract, compiler, runtime, oracle, public input, withheld input,
grading policy and model configuration are shared across arms. The withheld
input was inaccessible to the model, which received exported public text only.

Two repetitions per arm were scheduled with seed 29026, producing order
scarcity-0, scarcity-1, conventional-0, conventional-1. Each run allowed at most
two generations, with 600 seconds per model call. Scarcity used shrinking
enforced budgets (96 -> 48 -> 24 MiB). Conventional optimization targeted
measured cgroup peak memory under a fixed 96 MiB ceiling. Both used the same
public controller/history and 50% target-reduction policy. This is not the
full ordinary-profiler-versus-scarcity comparison specified in the roadmap.

Claude Sonnet was attempted first, with a $1 per-call cap. All four initial
requests returned `usage_limit_reached`, zero tokens and zero reported cost;
no candidate was produced. Those failures remain under
`artifacts/model-study-20261030T012336Z/`. The harness now stops on the first
infrastructure/provider failure instead of continuing to the other runs.

A fresh study used the installed Codex CLI, explicitly configured with
`gpt-6.1-sol`, ignored user configuration, ephemeral sessions, read-only sandbox,
disabled shell features and structured output. Six completed calls reported
zero tool events. The response events do not independently report resolved
model identity; the recorded name identifies the requested CLI configuration.
Dollar cost was unavailable and remains null, rather than estimated.

Both scarcity runs consumed two generations. Both conventional runs stopped
after one because their next target reached the configured 8 MiB minimum.
Equal maximum generation caps therefore did not yield equal consumed effort.
All six public submissions were retained; there were three distinct program
texts, and the first proposal was byte-identical across all four runs. This is
not six independent architectural discoveries. Both arms replaced the buffer
and loop with the exact arithmetic result `n`; later scarcity proposals changed
stdio details. The task makes that transformation particularly easy.

| Arm | Calls | Input tokens | Output tokens | Model wall seconds |
| --- | ---: | ---: | ---: | ---: |
| Scarcity | 4 | 73,066 | 2,192 | 79.172 |
| Conventional | 2 | 31,791 | 695 | 27.766 |
| Total | 6 | 104,857 | 2,887 | 106.938 |

Cache-read tokens were zero. Native orchestration and grading add wall time;
per-run totals are retained in the machine-readable summary.

## Independent final grading

Compilation and development ran as `chili-runner`; the vault and signing key
belonged to `chili-grader`. The owner relayed only selected public source and
feedback to the Windows model transport. Model proposals had no observed tools
and were never compiled or executed on Windows. This extends the account
fixture with a real model; it does not isolate an unrestricted shell-capable
agent or protect against the root owner.

Each grader run independently compiled baseline and final candidate twice,
checked sealed correctness and performed three paired transfer repetitions at
the same 256 MiB ceiling. The separate grader audit verified each signed
receipt and all 14 trials per run (four compiler and ten runtime trials).
All runtime trials passed; all grader cleanup checks found no remaining trial
cgroups. Production status stayed `not_accepted`.

| Arm/run | Baseline charged peak bytes | Candidate charged peak bytes | Reduction | Baseline/candidate median elapsed seconds |
| --- | ---: | ---: | ---: | ---: |
| Scarcity 0 | 35,864,576 | 4,722,688 | 86.83% | 0.11559 / 0.04099 |
| Scarcity 1 | 35,868,672 | 4,456,448 | 87.58% | 0.10526 / 0.04858 |
| Conventional 0 | 35,872,768 | 4,452,352 | 87.59% | 0.10470 / 0.04456 |
| Conventional 1 | 35,864,576 | 4,448,256 | 87.60% | 0.10785 / 0.04563 |

These are whole-program charged cgroup peaks, including the fixed runtime
wrapper. The public survival budget and actual measured transfer memory are
different quantities. Short elapsed measurements include launch overhead;
small differences between candidates do not establish an arm-level effect.

## Evidence and reproduction

The [machine-readable summary](model-comparison.json) includes protocol and
prompt hashes, program/source identities, usage, signed-receipt hashes, audit
counts and medians. Full public requests, provider events, candidates, signed
receipts and accepted controller sessions remain in
`artifacts/model-study-20261030T012506Z/`. The four `/srv/chili-trust/model-*`
labs retain private grader inputs and raw grader trials. Keys are not exported.
The frozen protocol records the exact study-tool hashes used; later transport
hardening adds clearer rate-limit errors, fail-fast orchestration and rejection
of unrecognized CLI item types.

With a disposable Ubuntu lab provisioned by `tools/native-trust.py`, run on
Windows (adjust paths to the installed CLI and fixture):

```powershell
python tools/run-model-study.py --provider codex --model gpt-6.1-sol --executable PATH_TO_CODEX_EXE
```

Then use `tools/collect-model-study.py` as the Linux owner, specifying the study
path and fixture Python. It runs audits as the grader and exports public final
evidence. `tools/summarize-model-study.py STUDY OUTPUT` regenerates the JSON
summary without running any model or candidate. Reproduction requires model
access and does not guarantee identical proposals or timings.

The result is limited to one synthetic task on one WSL host, two repetitions per
arm and unequal actual search effort. Representative repository workloads,
matched consumed budgets, a conventional profiler baseline and substantially
more independent runs remain necessary before drawing causal conclusions.

## Final project checks

The portable suite ran 103 tests: 101 passed and two Linux-only tests skipped.
Ruff passed. Source and wheel builds, the extracted-wheel workflow/schema/skill
smoke check, and Twine metadata checks all passed. Native model trials and all
four separate-account receipt audits passed as described above. The build emits
the existing setuptools package-data discovery warnings. Sandbox access to
temporary build files required running package checks with owner approval.

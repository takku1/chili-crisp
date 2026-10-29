# Framework integration and package cleanup

## Scope and ownership

Current package layout: runtime modules in `chilicrisp/`, canonical versioned
contracts in `chilicrisp/schemas/`, bundled skill in `chilicrisp/skills/`, executable
examples in `examples/`, portable regressions in `tests/`, native/scientific
adapters in `verification/`, and developer/setup commands in `tools/`. Research
reports stay in `reports/`; generated runs/packages/archived clutter stay in
ignored `artifacts/`. Empty legacy resource folders and old build/temp folders
were archived, preserving their contents.

The package uses declarative setuptools package data and one `contracts.py`
schema provider. `runner.validate` remains a compatible import. Source and wheel
resources use the same paths. The source distribution includes scientific
verification sources needed by its tests; runtime wheels exclude development
tests, tools, reports and run artifacts. CI builds to `artifacts/packages/` and
exercises comparison, integrity verification and skill export from an extracted
wheel. Local correctness selections and output evidence are enforced by tool
code, with independent acceptance still outside that boundary.

Chili Crisp owns the frozen behavioral contract, frontier policy, oracle boundary,
evidence, and eventual promotion/rollback decisions. Reuse BenchExec for execution
after compatibility testing and OpenEvolve for generic evolutionary search. Neither
framework receives authority to change an oracle or promote a production candidate.

Current implementation: an installable Python package, wheel-contained schemas,
optional dependencies, portable CI, a BenchExec trusted-fixture probe, and an
OpenEvolve evaluator for already frozen single-source candidates. The existing
bubblewrap runner remains the only experiment backend. This directory is not a Git
checkout during that increment, so that work was unguarded; no Git diff or
run-guard claim was available. A local Git repository on `main` has since been
initialized, but staging and the baseline commit are blocked by this session's
read-only `.git` policy; see [version-control setup](../reports/version-control.md).

## Research and choices

Primary sources inspected on 2026-10-28; upstream `main` is moving documentation,
not a reproducibility pin. Actual trials must retain installed dependency versions.
Dependency ranges in `pyproject.toml` are compatibility ranges, not a lock file.

| Provider | Evidence and decision | Remaining fit gap |
| --- | --- | --- |
| BenchExec, Apache-2.0 | [RunExecutor source](https://github.com/sosy-lab/benchexec/blob/main/benchexec/runexecutor.py) exposes memory/wall limits, separate output files, measurements, and termination reasons. Adapt after native checks. | `maxLogfileSize` shrinks logs; it does not implement Chili Crisp's terminate-on-output-cap rule. Raw counter coverage, scratch/pids/swap policy, exact rootfs exposure, cleanup recovery, and seccomp require comparison. |
| BenchExec containers | [ContainerExecutor source](https://github.com/sosy-lab/benchexec/blob/main/benchexec/containerexecutor.py) offers namespaces, directory policies, network isolation, and cgroup access control. | Default container directory policy is not Chili Crisp's minimal frozen rootfs. Do not execute generated hostile candidates through this probe. |
| OpenEvolve, Apache-2.0 | [EvaluationResult](https://github.com/algorithmicsuperintelligence/openevolve/blob/main/openevolve/evaluation_result.py) provides numeric metrics and text/byte artifacts. Reuse this API; do not build a parallel population database. Local API test uses installed 0.3.2. | Generation-to-build transport, protected build worker, independent grading, promotion, and rollback remain unimplemented. Population hooks on upstream main need a release-specific compatibility check before adoption. |
| pyperf | [Metadata collection](https://pyperf.readthedocs.io/en/latest/cli.html#pyperf-collect-metadata) and [system stability guidance](https://pyperf.readthedocs.io/en/stable/system.html) are useful for future normal-hardware Python controls. | Optional later tool. Does not replace constrained execution; no host tuning is performed. |
| asv | [Environment management](https://asv.readthedocs.io/en/stable/using.html) is useful for historical Python performance comparisons. | Defer: isolated Python environments are not a hostile-code sandbox, and history tracking is not the immediate experiment gate. |

CodSpeed/Bencher remain deferred optional reporting choices from the supplied
brief. No additional benchmark platform is installed. No competitor speedup or
novelty claim is used as evidence that these adapters satisfy our contract.

## Install and build

```sh
python -m venv .venv
# Activate .venv using your shell, then:
python -m pip install -e ".[dev,evolution]"
# On the prepared Linux research host:
python -m pip install -e ".[benchexec]"
python -m unittest discover -s tests -v
python -m build
python -m twine check dist/*
python tools/check-wheel.py
```

Base installations use jsonschema and psutil; importing Chili Crisp does not load an
LLM SDK. `requirements.txt` remains supported for existing source-tree workflows.
Authoritative schemas live in `chilicrisp/schemas/` and the reusable skill in
`chilicrisp/skills/`. Setuptools includes them directly as package data; schema
loading uses Python package resources in both source and installed environments.
No custom build shim or duplicate resource tree is maintained.
Install a wheel with `pip install dist/FILE.whl`.
No project license was invented; choose one before public distribution.

BenchExec's execution modules use Apache-2.0; its distribution also declares
licenses for bundled components. Preserve upstream notices when redistributing;
see its [package metadata](https://github.com/sosy-lab/benchexec/blob/main/pyproject.toml).

## BenchExec compatibility pilot

Run as an unprivileged user on a prepared disposable Linux VM with delegated
cgroups and user namespaces, following [upstream installation instructions](https://github.com/sosy-lab/benchexec/blob/main/doc/INSTALL.md).

```sh
chili-benchexec-probe /owner/evidence/benchexec-pilot-001
```

The path must be new. The probe executes only three embedded trusted Python
fixtures, with 64 MiB and two-second limits. It saves stdout/stderr, upstream raw
results, installed version, and `probe.json`. It restores signal handlers and
calls `stop()` on interruption. Unsupported hosts return failure without running
a subprocess. Fixture success means `fixtures_passed`, never full compatibility.
No unconfined fallback exists.

Before replacing the existing runner, run both engines on the same prepared
fixture/runtime. Compare normal/wrong output, OOM, wall timeout, output flooding,
process-tree escape/cleanup, interruption/recovery, filesystem/network access,
all resource limits, counter units and availability, and oracle/evidence asset
visibility. Reconcile differences explicitly. The existing native suite is still
enabled only through `CHILI_FIXTURE_MANIFEST`; portable CI is not certification.

## OpenEvolve feedback pilot

In an owner-controlled evaluator module, bind a frozen manifest to the callable:

```python
import json
from pathlib import Path
from chilicrisp.integrations.openevolve import FrozenEvaluator

evaluate = FrozenEvaluator(
    json.loads(Path('/owner/frozen-candidate.json').read_text()),
    budget=67108864,
    repetitions=3,
)
```

OpenEvolve calls `evaluate(program_path)` and receives its own `EvaluationResult`.
For this adapter only, the manifest's `target.source_hash` must be the SHA256 of
that single source file. The manifest also binds its trusted, prebuilt rootfs.
Do not point the source hash at a repository/tree hash. Changed source receives
`candidate_not_frozen` without execution: an owner must build, freeze, and verify
the corresponding artifact before constructing a new evaluator. The adapter
never imports generated source or accepts a generated manifest. This is a frozen
artifact evaluation bridge, not an autonomous generation/build pipeline.

Every declared public workload must pass all requested repetitions with finalized
evidence, matching experiment/manifest/rootfs/workload/budget identity, measured
memory peak and elapsed time. Otherwise the search score is zero. The bounded
score is `1 / (1 + max_peak / budget)` and is comparable only within a fixed
workload, budget, environment, and repetition policy. It is a search heuristic,
not an improvement estimate or acceptance rule. Missing metrics stay absent.

Feedback contains public outcomes and trial IDs; protected errors, paths,
reference arrays, and policy files are withheld. The runner retains full evidence
for the owner. Filesystem permissions must separate the candidate agent from the
evaluator, manifest, build artifacts, and evidence. A Python deepcopy freezes
configuration within this API; it is not a security boundary against a process
with owner-level filesystem or interpreter access.

## Delivery gates and blockers

1. Package and portable adapter contracts: verify build, installed-wheel schema
   loading, real OpenEvolve result compatibility, mismatch rejection, missing
   metrics, budget/deadline caps, and unsupported-host behavior.
2. BenchExec replacement: blocked on native Linux contract comparison above.
3. Automatic candidate pipeline: blocked on protected build transport, native
   runner acceptance, independent scientific oracle coverage, and grading policy.
4. Two-generation moving frontier: follows generation/build and promotion/rollback
   evidence. Continue using [the existing evolution contract](evolution.md);
   do not treat OpenEvolve's best-program pointer as an accepted champion.

Write set for this increment: package/build metadata, optional integration modules,
the runner schema loader, portable integration tests, wheel verification tool,
CI, README, this note, and the existing roadmap/implementation status. Existing
oracle rules, manifests, evidence schemas, and frontier decisions are preserved.

## Executed verification

On this Windows/Python 3.12 session, 38 unit tests ran: 36 passed and two native
Linux tests skipped. Tests use the real installed OpenEvolve 0.3.2 result class;
successful trial measurements are test doubles, not Linux measurements. The real
runner's unsupported-host path also passed through the evaluator with zero score.
Scoped Ruff checks passed. The example manifest validated.

`setup.py sdist bdist_wheel` built both artifacts, and `tools/check-wheel.py`
loaded the extracted wheel outside the checkout and validated its packaged schemas.
The preferred `python -m build --no-isolation` failed on managed Windows temporary
directory ACLs; direct setuptools invocation was the local verification fallback,
not the recommended user build command. `twine check` was not run successfully
because twine is absent locally; CI installs it. The workflow itself has not run.

BenchExec's probe returned unsupported on Windows without starting fixtures. WSL
enumeration returned `E_ACCESSDENIED`; Docker's engine pipe returned permission
denied. No native BenchExec, cgroup, namespace, or two-generation compatibility
result is claimed. Build output is retained in `reports/framework-build.log`.

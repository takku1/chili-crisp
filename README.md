# Chili Crisp

Verified scarcity experiments: use measured memory pressure to investigate software designs, then independently check candidate behavior and tradeoffs.

The repository contains versioned JSON Schemas, a deterministic frontier policy,
a Linux bubblewrap/cgroup runner, lifecycle recovery, bounded output capture,
trusted local candidate comparisons, and an AI coding skill. Native fixtures now
pass on the local Ubuntu WSL host; see [validation evidence](reports/native-validation.md).
A decoder [self-test](reports/dogfood-decoder.md) measured a scoped memory reduction
in an experimental candidate. No production acceptance is claimed.
A subsequent [real model pilot](reports/model-source-pilot.md) retained a public
rejection and confirmed a 4 MiB peak-memory reduction on fresh heldout input.

Read the [design index](docs/README.md) and [implementation guide](docs/implementation.md).
See [current project status](docs/STATUS.md) for delivered milestones and remaining research.

For the CLI and AI coding workflow, start with [getting started](docs/getting-started.md).
The reusable skill is [chili-dev](chilicrisp/skills/chili-dev/SKILL.md).
The [measured development loop](docs/development-loop.md) runs without a VM:
baseline, research/proposal, build/test, repeated measurement, experimental
retention, and a tighter next target. Run `python tools/demo-development.py`
for a two-generation integration example.
The opt-in [native development backend](docs/native-development.md) connects the
same controller to enforced Linux memory budgets, optionally compiling C or
Rust (vendored, lockfile-pinned crates) candidates in an isolated,
reproducibility-checked build root.
An optional [owner-operated acceptance gate](docs/sealed-acceptance.md) checks
sealed workloads and identical-condition transfer, returning a signed final verdict.
See [AI development priorities](docs/ai-improvements.md) for bounded experiment
memory and the next isolated-build, sealed-grading and comparison increments.

The broader target includes CPU, time, storage, I/O, process, network, GPU, and
energy constraints. See [resource capabilities and build sequence](docs/resources.md)
for the distinction between implemented controls and planned backends.
Linux CPU quota enforcement and repeated grid experiments are covered in the
[CPU guide](docs/cpu.md).

```powershell
python -m chilicrisp capabilities
python -m chilicrisp runner validate examples/experiment.json
python -m chilicrisp pressure-map evidence
```

The common CLI also exposes `frontier` and `recover`; existing commands remain
available. Source and bundled contracts/skills live in `chilicrisp/`, verification in
`tests/` and `verification/`, setup utilities in `tools/`, and retained research
evidence in `reports/`. Ignored build outputs and local artifacts remain local.

The package is installable with `python -m pip install -e .`. Optional
`.[evolution]` and Linux `.[benchexec]` extras provide framework integrations.
See [framework setup, research, and compatibility gates](docs/frameworks.md).
BenchExec is a separate trusted-fixture probe; the OpenEvolve bridge evaluates
owner-frozen candidates. Automatic isolated rootfs builds and promotion are not
implemented; the local comparison workflow runs trusted build/test commands.

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m chilicrisp.runner validate examples/experiment.json
```

The example is a schema-valid template. Replace its rootfs, identities, and environment paths before a Linux trial.

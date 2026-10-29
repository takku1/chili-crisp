# Use Chili Crisp with a coding agent

Chili Crisp provides a CLI, the `chili-dev` skill and a persistent
[measured development loop](development-loop.md). The default loop runs locally,
measures real commands and tightens targets across accepted experimental versions.
The Linux runner separately performs optional isolated resource-pressure trials.

## Install and check

From this checkout, install into the Python environment your agent uses:

```text
python -m pip install -e .
python -m chilicrisp doctor
python -m chilicrisp capabilities
python tools/demo-local.py
python tools/demo-development.py
```

The demo changes a sum-of-squares implementation from an intermediate list to a
generator and runs compilation plus public correctness checks on both versions.
Its JSON output points to a retained comparison under `artifacts/`. This confirms
the development path; it does not measure memory savings or justify promotion.

The skill source is `chilicrisp/skills/chili-dev/SKILL.md`. Export the exact bundled
version with `python -m chilicrisp skill /path/to/agent/skills/chili-dev`; the
destination must not already exist. Then use `$chili-dev` with a target
repository and a resource objective. The installed skill expects Chili Crisp to
be importable in the execution environment. It is not a background model service
and requires no model API key of its own. The calling coding agent supplies the
proposal and editing capabilities.

## Onboard a project

Choose a known executable and public correctness command. For example, from a
shell that preserves JSON argument quoting:

```text
python -m chilicrisp init /path/to/baseline --test-command '["python", "check.py"]'
```

When PowerShell/native-command quoting interferes with JSON, invoke the Python
API directly or write `.chilicrisp/project.json` using the project schema:

```python
from chilicrisp.project import initialize
config = initialize("/path/to/baseline", ["/path/to/python", "check.py"],
                    build=["/path/to/python", "-m", "py_compile", "solver.py"])
```

Configuration pins command argument arrays, per-command and total deadlines,
and output caps. The source root resolves relative to the configuration file.
Initialization refuses to overwrite an existing configuration. Review the
commands and required environment before running them.

Initialization automatically pins an existing `tests/` directory and relative
files named by the test command. Use repeated `--protect PATH` arguments to
explicitly select other correctness files/directories. The selection replaces
inference. The tool rejects missing, escaping or snapshot-excluded protected
paths, candidate edits to pinned files, and commands that modify those files.
Old configurations without `protected_paths` infer the same defaults when loaded.
Review the selected paths: arbitrary test discovery cannot be inferred completely.
These are drift checks for trusted local execution, not adversarial protection.

Create a candidate checkout/copy, make the proposed change there, then run:

```text
python -m chilicrisp compare /path/to/baseline/.chilicrisp/project.json --candidate /path/to/candidate --output /path/to/runs --trusted-local
python -m chilicrisp status /path/to/runs/comparison-ID/comparison.json
python -m chilicrisp verify /path/to/runs/comparison-ID/comparison.json
```

Both inputs are copied before execution, with source hashes recorded. Build runs
before tests. Baseline failure prevents candidate evaluation. Failed comparisons
exit nonzero. Stage records retain commands, outcome, exit code, elapsed time,
bounded stdout/stderr, and capture hashes. A finalized decision is either
`baseline_failed`, `candidate_rejected`, or `public_tests_passed`.
Completed comparisons also have a `comparison.sha256` sidecar. `verify` checks
that digest, stage-record consistency, retained stream hashes, and passing
decision consistency, returning nonzero for incomplete or changed evidence.
The sidecar is an integrity check, not a signature or independent grading service.
Legacy records without a sidecar remain readable with `status` but fail `verify`.

Local mode executes trusted commands with inherited host permissions and
environment; source copies provide workspace separation, not sandbox isolation.
Dependencies must be available in the selected runtime or prepared by the build
command. Links, junctions and special source files are rejected. Snapshot exclusions
are declared in the skill and `project.EXCLUDED`; do not place required source in
excluded directories. Commands must not detach background processes. Cancellation
attempts process cleanup and records interruption; a stale RUNNING record after
abrupt host termination must be inspected, not resumed as a successful run.

## Linux pressure trials

`doctor --manifest MANIFEST` performs read-only manifest preflight. A valid local
project configuration is not a sandbox manifest. See [runner preparation](implementation.md)
for protected rootfs, input/oracle, cgroup delegation and accounting requirements.

In a disposable Ubuntu VM with the documented prerequisites and `chili-runner`
account, `sudo python3 tools/native-fixtures.py` creates a fresh lab beneath
`/home/chili-runner/chili-lab`, constructs a minimal fixture rootfs, and runs a
transient delegated systemd service as the unprivileged runner. It installs the
runtime dependencies in that lab's venv. Labs and raw evidence are retained;
the tool does not delete old runs or disable host security policy. Results are
copied into `artifacts/native-fixture-*` in the framework checkout.
The fixture manifest's delegated cgroup exists only for its transient service;
rerun provisioning for another fixture run rather than reusing that manifest.

Native fixtures check correct/wrong output, timeout, output flooding, isolation,
OOM, cleanup failure and recovery. They do not establish a production security
certification, scientific validity, or a candidate optimization result.

CPU quota trials and repeated grids are documented in [CPU experiments](cpu.md).
I/O backends, automatic rootfs builds for arbitrary target projects, sealed
grading, automatic promotion, and MCP remain future work. See [resource direction](resources.md).

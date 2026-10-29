# Chili Crisp

Verified scarcity experiments: use measured memory pressure to investigate software designs, then independently check candidate behavior and tradeoffs.

The repository now contains versioned JSON Schemas, a deterministic frontier policy, a Linux bubblewrap/cgroup runner, lifecycle recovery, bounded output capture, and validation fixtures. The native Linux isolation path has **not been validated in this Windows session**. No optimization result or production acceptance is claimed.

Read the [design index](docs/README.md) and [implementation guide](docs/implementation.md).

The package is installable with `python -m pip install -e .`. Optional
`.[evolution]` and Linux `.[benchexec]` extras provide framework integrations.
See [framework setup, research, and compatibility gates](docs/frameworks.md).
BenchExec is a separate trusted-fixture probe; the OpenEvolve bridge evaluates
owner-frozen candidates. Automatic candidate builds and promotion are not implemented.

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m chilicrisp.runner validate examples/experiment.json
```

The example is a schema-valid template. Replace its rootfs, identities, and environment paths before a Linux trial.

# Local version-control baseline — 29 October 2026

Chili Crisp has an initialized local Git repository with branch `main`, but
**no baseline commit exists yet**. `git init --initial-branch=main` succeeded;
the subsequent `git add` failed with:

```text
fatal: Unable to create 'Z:/chilicrisp/.git/index.lock': Permission denied
```

The session's managed filesystem configuration grants read access to `.git`.
No attempt was made to redirect the index or otherwise bypass that restriction.
The prepared baseline scope is framework source, schemas, design contracts,
verification driver, tests, setup/build tools, and textual experiment evidence.

Generated candidate/build trees under `artifacts/`, build distributions, temporary
directories, numerical `.bin` arrays, and ZIP bundles under `reports/` remain
excluded by `.gitignore`. Existing result JSON files preserve hashes and experiment identity;
the source scripts describe how to regenerate outputs. These ignored artifacts
remain on disk. Git history alone is not an archive of all experiment artifacts.

No Git remote was configured and nothing was published. An existing Git identity
is configured, but no commit was created. Historical reports saying their work
was unguarded remain accurate for those runs.

## GitHub publication path

The owner subsequently authorized publication to `takku1/chili-crisp`. The
connected GitHub API has push access, so it can publish the prepared framework
snapshot independently of the blocked local Git index. Local `.git` staging and
checkout synchronization remain restricted. After API publication, remote Git
history is authoritative for that baseline; this local working directory still
requires synchronization from a terminal with write access to `.git`.

No Credential Manager token is extracted by this publication path. Source and
text evidence are included; generated binary arrays and ZIP bundles remain
excluded by the prepared tracking rules.

## Complete the baseline outside this restricted session

Run in a regular terminal with write access to `Z:\chilicrisp\.git`:

```powershell
cd Z:\chilicrisp
git add -- .gitignore .github MANIFEST.in README.md pyproject.toml requirements.txt setup.py chilicrisp docs examples schemas tests tools verification reports
git diff --cached --check
git diff --cached --stat
git commit -m "Establish verified Chili Crisp framework baseline"
git status --short
git log -1 --oneline
```

Review the staged summary before committing. No global Git configuration changes
or repository publication are required.

For each subsequent candidate experiment:

1. Record the framework commit, candidate source hash, parent candidate identity,
   oracle/driver hashes, workload policy, and environment identity.
2. Isolate candidate source in a branch/worktree or owner-frozen artifact copy.
3. Keep oracle and evaluation policy outside candidate write access. Version
   control records changes; it does not supply a build sandbox.
4. Retain rejection evidence. Promotion requires independent correctness,
   kernel-enforced resource measurements, and normal-hardware transfer checks.

After committing, inspect the baseline with `git log --oneline` and working
changes with `git status --short`.

Remaining infrastructure blocker: WSL and Docker access are denied in the agent
session, and no SSH research VM alias is configured. The Linux VM hostname/IP
and login are required before native fixtures and BenchExec compatibility tests
can proceed. No Linux execution, resource improvement, or promotion is claimed
by creating this repository.

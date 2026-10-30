# Native Wilderbeast transfer and sealed grading

30 October 2026 UTC (29 October America/New_York). The existing owner-reviewed
archive candidate passed native sealed grading on previously unseen inputs.
A deliberately overfitted control passed public development and was rejected
by the sealed gate. This strengthens transfer evidence for the candidate; it
does not test whether scarcity helps a model discover optimizations.

## Result

The separate grader ran three randomized paired transfer blocks with a fixed
128 MiB memory ceiling, one CPU quota, disabled swap and a 64 MiB scratch tmpfs.
The policy, frozen before evaluation, required at least 5% lower charged peak
memory and no more than 25% median latency regression.

| Grader median | Baseline | Candidate |
| --- | ---: | ---: |
| Charged `memory.peak` | 50,348,032 bytes | 43,532,288 bytes |
| Elapsed time | 0.39518 s | 0.39512 s |

Peak reduction: 6,815,744 bytes (6.5 MiB), approximately 13.54%. Do not equate
this directly with the prior 11.3% sampled Windows RSS result: runtime, inputs,
accounting and scratch storage differ. Elapsed times are effectively the same
at this resolution; no speedup is claimed.

The valid lineage received a signed `passed` verdict; its independent audit
verified all 12 runtime trials. The overfitted lineage received signed
`rejected` after four correctness trials (three passes and one wrong output).
Both audits passed and both graders reported no remaining trial cgroups.
Production stayed `not_accepted`.

## Component and correctness boundary

`verification/wilderbeast/frozen/` retains the minimal unchanged standard-library
archive source and provenance, including its parent commit and uncommitted
source identities. Portable fixture identities normalize CRLF to LF and also
retain original byte hashes. The candidate is reproduced by one shared rewrite
helper, identical to the prior retained patch.

The protected native driver checks small empty/single/multiple-record
roundtrips, nested metadata, Unicode, filtering, invalid JSON, encoding failure
and atomic-replace failure with memory/disk rollback and temporary-file cleanup.
Resource trials separately persist a larger receipt batch and incrementally
hash actual file bytes; they do not materialize parsed JSON for correctness
inside the measured process. An owner reference constructs the exact expected
JSON schema without importing or executing candidate code. UUID/time metadata
is fixed by the driver, making exact output comparison deterministic.

Public batches had 8,000 records. Private sizes and seed values were generated
by the owner before evaluation, kept in the grader vault and never sent to a
model. The negative control intentionally raises an error only on larger
batches, so it passes public tests but fails hidden persistence. No model calls
occurred and the valid patch was already known.

`chili-runner` operated the controller; `chili-grader` owned the private inputs,
policy and signing key. Root provisioned the lab. Frozen runtime, libraries,
driver and installed code were root-owned and read-only to those accounts.
The JSON output file resides in tmpfs: its pages are included in cgroup peak
memory and the same storage policy applies to both variants.

The driver imports Python candidate code into its own interpreter. It is not
an adversarial oracle boundary: arbitrary code could tamper with interpreter
state. These results are scoped to the reviewed patch and scripted control,
not unrestricted model-generated Python. Separate accounts also share a kernel;
the owner/root account remains trusted. A remote grader service is not added.

## Serializer compatibility and CI

Six new regression tests exercise the actual frozen archive/candidate. They
cover provenance identities; byte-for-byte JSON equality and reload for empty,
single and multiple records with nested Unicode metadata; default and forced
pure-Python encoder paths; lazy conversion at encoder entry; encoding and
replacement failures; and the provisioner's signed rejection-label handling.
They pass locally on Windows Python 3.12 and Linux Python 3.14. The supported
path is `json.dump`; no broader promise about arbitrary encoders or
`json.dumps` internals is made.
The complete portable suite passes 109 tests (107 passes, two Linux-only skips),
and Ruff is clean. Source/wheel builds, the extracted-wheel workflow and fixture
presence checks, and Twine metadata checks pass. Existing setuptools
package-data discovery warnings remain non-fatal.

Portable CI now includes Python 3.14 in addition to 3.12/3.13. Native CI is
configured to run this transfer/negative-control fixture after its account
fixture. Those workflow changes have not yet run remotely. Both workflows on
the reviewed commit `4a8fb9d` are confirmed green:
[package/portable](https://github.com/takku1/chili-crisp/actions/runs/40997711777)
and [native](https://github.com/takku1/chili-crisp/actions/runs/40997711765).

## Evidence and reproduction

[Public summary](native-wilderbeast.json) records signed-receipt hashes, source
identities, medians and audit counts. Full exported sessions and receipts remain
under `artifacts/native-wilderbeast-420a40e3942d/`; private evidence remains in
the two `/srv/chili-trust/wb-*` labs named by the summary. No key is exported.
The original provisioner exited nonzero because its final check expected
`failed` rather than the actual signed label `rejected`; the stored grade and
both audits succeeded. The label check is fixed and regression-tested. That
fix changes no candidate, policy, measurement or receipt.

On a disposable Ubuntu host with `tools/native-trust.py` already passed:

```sh
sudo python3 tools/native-wilderbeast.py
```

The provisioner selects the latest locally successful account-fixture lab, or
accepts explicit `--template`. No registry downloads or model access are needed.
`tools/summarize-native-wilderbeast.py RUN OUTPUT` exports only public results.
The [real-repository study checkpoint](../docs/real-repository-study.md) defines
the next comparison and its remaining token-budget and oracle launch gates.

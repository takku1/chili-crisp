# Owner-operated sealed acceptance and transfer validation

An offline owner-operated final gate now complements public native retention.
It grades frozen source against private workloads, performs a matched transfer
comparison, and emits an Ed25519-signed public receipt. `dev accept` verifies the
signature and exact source/policy/evaluator/lineage bindings before changing a
champion's acceptance state. No new model calls occurred.

This increment does not complete the proposed v0.2 milestone: isolated builds,
two distinct real-model scarcity generations and a controlled conventional arm
remain unproven.

## Positive and overfitting controls

The native fixture creates two independent public sessions. Both optimize the
same exact byte-sum contract and pass public evaluation at a lower enforced limit.
The positive source handles varying input sizes using bounded storage; the
negative source hardcodes the public answer. Sealed input size is privately
randomized and differs from the public fixture.

| Final gate | Positive candidate | Public-overfitting candidate |
| --- | --- | --- |
| Sealed correctness | Pass | Wrong output |
| Paired transfer | Three paired blocks, after warmup | Not run |
| Public receipt | Signed pass | Signed rejection |
| Controller result | Policy-verified champion | Experimental champion preserved |
| Production status | Not accepted | Not accepted |

The owner policy uses the **same 256 MiB finite memory ceiling**, same frozen
runtime, workload, CPU quota and cache policy for both versions. This safety cap
avoids unbounded host allocation. It is an identical-condition comparison, not
unrestricted normal-hardware transfer or external reproduction.

In the final positive fixture, median charged memory was 42,790,912 bytes for the
baseline and 10,280,960 bytes for the candidate. Median elapsed time was 0.138760
and 0.060798 seconds respectively. These simple scripted variants demonstrate
the gate; three pairs do not establish a general speedup. The fixture preregisters
a 10% minimum memory improvement and a deliberately loose 100% latency-regression
guard, not a production performance standard.

## Evidence and audit

Final run: `artifacts/native-fixture-uk2dbpeh/`. It retains public session states,
source capsules, native public trials and signed receipts. Detailed sealed
evidence and the private key remain exclusively under Linux lab
`/home/chili-runner/chili-lab/fixture-uk2dbpeh/private-acceptance-vault` and are not
copied into the repository's artifacts or agent requests.

The owner-account `tools/acceptance-audit.py` verified signatures, policy/manifest
pins, source identities, raw result schemas, artifact hashes, finalized journals,
independent stdout checks and matched execution controls:

- Positive final gate: 10 passing native trials (two correctness, two warmups,
  six transfer trials).
- Negative final gate: one passing reference and one wrong-output candidate;
  no transfer execution after rejection.
- No trial cgroups remained.

Attempts to query either campaign again were blocked even with a new lineage.
The private claim is consumed before source execution. Reference-baseline
failure, setup failure, interruption and cleanup failure cannot produce a passing
receipt; a regression test verifies that reference failure interrupts without
signing and cannot be retried under the same campaign.

Earlier fixture `native-fixture-zcksxgk8` used an unbounded trial memory setting;
that experiment is retained but superseded by the finite-cap policy. Fixture
`native-fixture-xm7hissx` exercised the bounded version before the additional
reference-failure handling. The final fixture includes that handling.

## Trust boundary and limits

This is an owner-operated protocol, not a deployed protected network service.
The vault checks Unix ownership and owner-only permissions. Candidate execution
uses the existing sandbox and never mounts the vault. Production deployment
still requires a separate grader account/host, protected controller trust roots
and owner-controlled transport. The fixture's proposing sources are scripted;
it does not demonstrate a hostile unrestricted host agent being contained.
Separate `nobody` account read-access probes confirmed that it could read neither
the vault's signing key nor its sealed input; no secret content was printed.

Public feedback consists only of a signed verdict and identity bindings. No
hidden input, private path, metric detail or sealed failure explanation is
imported into session experiment memory. Either verdict ends the lineage;
rollback and further public optimization are blocked after final acceptance.
Signatures authenticate the pinned grader's statement, not the truth of an
arbitrary malicious grader or comprehensive semantic correctness.

Portable validation: 95 tests run, **93 passed and two Linux-only tests skipped**
on Windows. Tests cover signature/body tampering, wrong keys, source/lineage/policy
binding, replay, source drift, hidden receipt-field rejection, reference failure
and preservation of production non-acceptance. See
[the owner workflow](../docs/sealed-acceptance.md) for operational requirements.

# Owner-operated final acceptance

Chili Crisp can now import an independently signed sealed-correctness and
equal-condition transfer decision for a retained native candidate. This is an
offline owner-operated gate, not a network grading service or an isolated build
worker. Install the optional `.[acceptance]` extra on the grader and receipt
verifier; `.[dev]` includes it for package tests.

## Execution boundary

Run the grader under a dedicated Linux account or separate host inaccessible to
the proposing agent. Put policy, manifest, inputs, external oracle assets, signing
key, claim registry and raw evidence in an owner-only vault. The implementation
checks Unix ownership and owner-only permissions on grading assets. It cannot
establish an account boundary by itself: an unrestricted same-account or
administrator agent can read that account's vault. The existing trusted host
agent transport is not made safe by signing receipts.
Controller state, installed code and pinned trust roots must also remain outside
the proposing agent's write authority. A signature cannot protect a verifier
whose trusted public key or implementation the same agent can replace.

Candidate source runs only through the native cgroup/bubblewrap runner. The vault
and signing key are not mounted into the candidate runtime. Secret workload input
is delivered through stdin; expected-output hashes and external grading assets
stay outside the sandbox. Candidate code necessarily sees the workload input
while executing it, but cannot read grading files or detailed results through
the public controller protocol. Owner-provided same-process drivers are not
themselves hidden oracles; external output checks remain the acceptance authority.

The current fixture validates source-process isolation and the gate's protocol,
not a deployed multi-account or remote service. Provisioning that operational
separation remains the owner's responsibility.

## Pin before optimization

Create a 32-byte Ed25519 private key under the vault with mode 0600, using the
`cryptography` library. Keep only its 32-byte public key in the development plan.
The [library's signing documentation](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/)
describes key generation, serialization, signing and verification.

Prepare a private `acceptance-policy` JSON using the bundled schema. It declares
an opaque campaign name, sealed experiment manifest path and SHA256,
benchmark_workload, a generous page-aligned transfer_budget, repetitions (at least three), seed, wall/trial caps,
maximum_latency_regression and minimum_memory_improvement. Manifest inputs and
oracle/reference files require owner-only permissions and must be in the vault.
The frozen minimal rootfs must exclude the vault and contain empty `/candidate`.
Use absolute manifest/input/oracle paths to avoid working-directory ambiguity.

Compute the evaluator identity **on the grader host**:

```text
python -m chilicrisp.acceptance identity
```

It hashes the grading/controller/runner implementations and records the
cryptography package version. Freeze a development plan's `acceptance` object:

```json
{
  "campaign": "owner-selected-unique-campaign",
  "public_key": "64 hexadecimal characters of raw public key",
  "policy_sha256": "SHA256 of the exact private policy file",
  "evaluator_sha256": "identity returned by the grader installation"
}
```

This is a field illustration, not a schema-valid complete plan. Only native
source-only sessions support this gate. Keep hidden policy content outside the
public plan; the public fields pin its identity without publishing workloads.

## Freeze, grade, import

After public optimization stops, export a public request with `dev
acceptance-request SESSION` to JSON. It identifies the initial baseline, current
retained source and lineage; it contains no private grading assets. Transfer
source capsules to the grader if needed, preserving their identities and changing
only the request's source paths to the transferred capsules.

On the owner-controlled grader:

```text
python -m chilicrisp.acceptance grade --request REQUEST.json --policy PRIVATE_POLICY.json --key PRIVATE_KEY --vault PRIVATE_VAULT --receipt PUBLIC_RECEIPT.json
```

The campaign is claimed exclusively before source execution. One attempt is
allowed per campaign in its vault, even if a caller changes lineage or output
paths. Rejection, interruption and cleanup failure consume the claim. Do not
delete claims or reuse the same hidden campaign to optimize against final
feedback. A genuinely new study needs owner-reviewed fresh assets and a new
campaign/policy pin.

The grader freezes and checks both source identities, runs every sealed workload
on both versions, then performs warmups and randomized paired transfer runs.
Both use identical runtime, workload, CPU, cache and other isolation policies;
both use the same owner-selected finite `transfer_budget`. Choose a cap with
ample measured headroom for both programs that is safe for this host. Host and
ancestor constraints and the fixed CPU quota still apply and are recorded. This
is an identical-condition comparison, not unrestricted hardware or external transfer.
Prespecified median memory/latency criteria determine the result. Small sample
counts remain screening evidence, not statistical proof.

Raw trials and detailed failure reasons remain in the private vault. Only a
canonical Ed25519-signed receipt with pass/fail, source identities, lineage,
campaign, policy hash and evaluator hash is published. It uses a versioned domain
prefix; verification uses the plan's pinned public key. Runner/setup/cleanup
failures produce no receipt and cannot turn into a passing verdict.

On the development-controller side:

```text
python -m chilicrisp dev accept SESSION PUBLIC_RECEIPT.json
```

Receipt import checks signature and every binding, rechecks frozen source, and
rejects replays. Passing marks `acceptance_state: verified_champion` and records
sealed/transfer pass for this policy. Rejection preserves the experimental
champion. Either result ends the lineage; rollback and further optimization of
that finalized lineage are blocked. **Production remains `not_accepted`**. No
merge, deployment or broad correctness recommendation follows automatically.

See [native acceptance validation](../reports/sealed-acceptance-validation.md).

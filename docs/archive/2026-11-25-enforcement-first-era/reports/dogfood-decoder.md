# Chili Crisp tests a Chili Crisp decoder change

Status: **supported improvement for the declared workload**, retained as an
experimental candidate. The working package's decoder was not promoted or changed.

## Result

The candidate replaces `values.frombytes(data[17:])` with
`values.frombytes(memoryview(data)[17:])`, avoiding an intermediate payload copy.
The exact [candidate patch](dogfood-decoder.patch) is retained for reproduction.

| Fresh confirmation, median of four processes per variant | Baseline | Candidate |
| --- | --- | --- |
| Whole-program charged peak memory | 21,098,496 bytes | 16,898,048 bytes |
| Elapsed time | 281.48 ms | 274.80 ms |
| Charged CPU usage | 254.28 ms | 246.02 ms |

The confirmation memory reduction is **4,200,448 bytes (19.91%)**. Exploration
previously measured 3,794,944 bytes less peak memory, with 1.80% higher median
elapsed time. Confirmation measured 2.37% lower median elapsed time. The small
timing sample is sufficient for the declared regression screen, not a reliable
general speedup claim. No tail-latency conclusion is made.

## Frozen experiment and correctness

The source capsules and plan were saved before native measurements under
`artifacts/dogfood-c7d84a8dadc8420aadb0c14f05938326/`. The only decoder change is
the buffer view. Baseline source SHA-256:
`2d53e05a896eb2c4d66be3c06ac829813b95748367ffbaea7ab2010c385ba989`.
Candidate source SHA-256:
`aebcb4c0da738f83538c3603b198dd5f477f43b4d7aa21059e87adff82ad7f05`.

Chili Crisp's `compare` created separate writable source snapshots and ran the full
public unittest suite on each. It pinned tests, schema files and the benchmark
driver. Both passed, and `verify` accepted the saved comparison evidence.
Additional checks cover bytes, bytearray and contiguous memoryview inputs,
signed zero, extreme finite values, the maximum stream length and invalid lengths.
The final suite contains 67 tests: 65 passed and two Linux methods were skipped
in Windows runs. Native checks were executed separately.

The native owner generated a frozen stream of 500,000 finite signed doubles and
calculated the expected output digest directly from that payload. The trusted
driver called the actual `decode` function 16 times and hashed the resulting
array bytes without another full-payload copy. Baseline and candidate used
identical input, driver and minimal Python runtime. The driver was outside the
candidate proposal and protected by the local correctness configuration.

The declared native budget was 18 trials and 180 seconds: two warmups, four
randomized paired exploration blocks, then four fresh paired confirmation blocks.
Seed: 29. Both variants had a 64 MiB enforced memory cap and a 100,000/100,000
microsecond CPU quota. The declared success criteria were at least 2 MiB lower
median peak memory and no more than 15% higher median elapsed time in exploration
and confirmation. No thresholds were adjusted after observing measurements.

All 18 native trials returned the independently pinned expected output and
finalized cleanly. An evidence audit checked the frozen schedule, raw result
identity, artifact hashes, expected stdout digest, effective resource settings
and lifecycle. It verified all 18 records. No trial cgroups remained.

## Diagnostics and evidence

A separate Windows allocation diagnostic measured 8,250,165 bytes peak Python
allocation for baseline decode and 4,250,700 for the candidate, with identical
decoded-output digests. This supports the intermediate-copy explanation; these
instrumented runs were not mixed into native measurements. A baseline cProfile
report is retained beside the allocation diagnostic.

Native evidence: `artifacts/native-fixture-i5_ckmz9/`, including
`dogfood-plan.json`, `dogfood-measurements.json`, `dogfood-summary.json`,
`dogfood-audit.json`, native logs, and per-trial raw artifacts. The original
frozen Linux artifacts remain in `/home/chili-runner/chili-lab/fixture-i5_ckmz9`.
Environment: Ubuntu-26.04 WSL, Python 3.14.4, bubblewrap 0.12.0; CPU topology,
kernel identity, rootfs hashes and input/driver hashes are retained in the plan.

The earlier local comparison at `artifacts/dogfood-73241b85befd423aa0cac8d6508f3514/`
failed because the newly added regression test contained a syntax typo. The tool
correctly stopped candidate evaluation. That failed record remains intact; the
typo was corrected and new source capsules were created before resource trials.

## Reproduce

From the unchanged baseline decoder in this checkout:

```text
python tools/dogfood-prepare.py
python tools/dogfood-profile.py artifacts/dogfood-ID
```

Then, in the prepared disposable Ubuntu environment:

```text
sudo python3 /mnt/z/chilicrisp/tools/dogfood-linux.py /mnt/z/chilicrisp/artifacts/dogfood-ID
```

Audit the resulting Windows-side evidence:

```text
python tools/dogfood-audit.py artifacts/native-fixture-ID
```

The lab builder prepares known owner-controlled artifacts; it is not an arbitrary
project build service. New runs preserve old labs. Dependency/runtime selection
must be matched before comparing results across runs.

## Limits and disposition

This is one small source transformation on the decoder's maximum supported
stream, on one host. It demonstrates a working candidate/correctness/measurement
path through Chili Crisp, not the CIAD hypothesis, production transfer, scientific
oracle validity or an OOM frontier. Both variants passed at 64 MiB; no claim is
made about their minimum feasible memory limits. Cache accounting and sandbox
overhead qualify the whole-program measurements. There is no independent sealed
grading or automatic promotion. Work remains unguarded because `.git` is
read-only; source capsule hashes provide the retained identities.

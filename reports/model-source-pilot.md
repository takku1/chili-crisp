# Bounded model participation pilot

The decoder pilot now includes a real Codex CLI proposal, public rejection,
measured feedback, and protected evaluation of the resubmission. This establishes
model participation; it does not establish superiority over ordinary optimization.
The production decoder remains unchanged.

## Protocol and execution boundary

The owner froze the baseline, selected one Python source module, capped model use
at two calls of at most 180 seconds each, and required a hypothesis, mechanism,
falsification criteria and references. `tools/propose-codex.py` uses structured
noninteractive output, disables execution tools and uses a read-only sandbox.
It parses the proposed source without importing or executing it on the host.
See the [Codex noninteractive documentation](https://learn.chatgpt.com/docs/non-interactive-mode).
References in a proposal are model-supplied rationale, not proof of correctness.

The owner harness executes the frozen module in the existing Linux bubblewrap,
seccomp and cgroup boundary. No generated build scripts run on the host. Trials
use a fixed 64 MiB budget and one CPU quota. The moving challenge is a measured
peak-memory target; the enforced limit does not shrink in this pilot.

The public workload decodes 500,000 doubles sixteen times. Correctness checks
cover supported buffer types, return types, validation failures and output hashes.
After source freeze, the harness generates a fresh random finite-double workload
for confirmation. Baseline and candidate see the same input within each phase.
No model calls occur after heldout grading. This is one limited heldout check,
not a sealed-grading service or a verified-champion promotion.

## Results, including rejection

| Attempt | Target peak bytes | Public median peak, baseline → candidate | Decision |
| --- | ---: | ---: | --- |
| 1 | 16,878,796 | 21,110,784 → 16,896,000 | Reject; target missed by 17,204 bytes |
| 2 | 18,999,705 | 20,828,160 → 17,174,528 | Pass public screen; evaluate heldout |

The predeclared single retry relaxed the challenge from 20% to 10% below the
fresh public control. The model returned **byte-identical source** on the second
call: a memoryview avoids a temporary payload slice for exact bytes/bytearray
inputs, with the existing fallback retained for other types. These are two
submissions of one implementation, not two distinct inventions or generations.

Fresh heldout confirmation used three randomized paired blocks:

| Metric | Baseline median | Candidate median |
| --- | ---: | ---: |
| Cgroup peak memory, bytes | 20,832,256 | 16,637,952 |
| Elapsed seconds | 0.281304 | 0.266450 |

Peak charged memory fell by 4,194,304 bytes (20.13%). No median latency regression
was observed; three pairs do not support a general speedup claim. All 14 final
trials passed output and lifecycle checks; the independent artifact audit passed
all 14. The first attempt retained eight public/warmup trials and never reached
heldout grading. Neither session left experiment cgroups behind.

## Retained local evidence

- First proposal: `artifacts/ai-source-pilot-3f9fcae565ea48bf90bfc4846240db1c/`;
  rejected native run: `artifacts/native-fixture-0qjsn_qe/`.
- Final proposal: `artifacts/ai-source-pilot-b362ce84c8c9489f876af75df67b1e87/`;
  accepted experiment: `artifacts/native-fixture-o5c31xgf/`.
- Baseline source SHA256: `2d53e05a896eb2c4d66be3c06ac829813b95748367ffbaea7ab2010c385ba989`.
- Candidate source SHA256: `11e2f8a78bef25c3952d60cf82954b17018099f83c25f509e4f959ef062d5fed`.

Both proposal directories retain request, prompt, schema, event stream, stderr,
structured source, research and timing/usage metadata. Calls took 27.297 and
23.953 seconds. Reported usage totals: 32,219 input tokens, 1,924 output tokens,
and 213 reasoning-output tokens (do not add reasoning again to output totals).
Dollar cost and actual model identity were unavailable in the retained trace.
CLI version was 0.165.0; no explicit model override was supplied.

The reusable transport is `tools/propose-codex.py`; preparation and evaluation are
`tools/prepare-ai-pilot.py`, `tools/prepare-ai-evaluation.py` and
`tools/dogfood-linux.py --source-only`. These use the request/response/workspace
convention but the native harness remains separate from generic `dev run`.
Transport tests cover timeout cleanup, rejection of tool execution events, and
writing source without executing it. This pilot spends both allowed model calls;
re-running preparation creates a new experiment, not more calls in this one.

## Remaining work

Connect protected native evaluation to the general development controller;
introduce an independent sealed acceptance policy; retain useful multidimensional
tradeoffs; run a harder solver pilot and a matched conventional-optimization arm.
No Worldgame experiment, production acceptance, unattended build isolation or
causal comparison is claimed here.

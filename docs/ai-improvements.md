# AI development priorities

Chili Crisp benefits from better proposal context and evaluation evidence before
adding autonomous orchestration. The existing external-agent protocol keeps the
controller independent of a specific model or provider.

## Implemented context improvement

Each development request now supplies a compact public experiment memory: the
eight most recent controller decisions, targets, source identities and measured
phase medians. All attempts remain in session state. Research statements are
excluded from the compact observations so a hypothesis cannot become a measured
fact through repetition. Identical frozen source identities are labelled with
`repeat_of`, but evaluated again because policy targets can change.

This is a context mechanism, not learned optimization knowledge or evidence that
agents make better decisions. Existing immediate feedback remains compatible.
Requests and per-command output already remain in session run directories.

## Next increments, in order

1. Connect the native evaluator to the general controller. Pin evaluator, driver,
   input and source identities; reserve costs before launch; propagate cancellation
   and cleanup failures; reject unsupported backends before running candidate code.
   Keep owner provisioning separate from agent-writable source. Demonstrate actual
   shrinking enforced budgets as a distinct experiment from measured targets.
2. Add sealed acceptance with an owner-controlled boundary and withheld workloads.
   Public feedback and agent context must not include sealed inputs or detailed
   failures. Keep experimental retention separate from verified acceptance.
3. Normalize provider traces and usage. Record model identity when actually
   reported, prompt/configuration identities, observed tool events and usage;
   represent unavailable cost explicitly. Never reconstruct private reasoning.
4. Compare scarcity feedback with conventional optimization using matched tasks,
   identical model/configuration and budgets, randomized arm order and repeated
   independent runs. Measure correctness, wall time, tokens, resource improvement
   and severe failures. Preserve failed runs and distinguish repeated submissions
   from distinct implementations.

Structured traces make workflow failures inspectable; that is consistent with
[OpenAI's trace-grading guidance](https://developers.openai.com/api/docs/guides/trace-grading).
Chili Crisp should use deterministic correctness and resource checks as its
acceptance authority. A model critique can suggest a new hypothesis, but cannot
override measured results or replace the protected grader.

Defer vector databases, multi-agent swarms, automatic prompt optimization and
fine-tuning until experiment volume and controlled evaluations show a concrete
need. Local JSON session history is sufficient for this bounded memory feature.

## Validation scope

Tests cover bounded history, exclusion of unmeasured research claims, repeat
labelling and actual remeasurement after identical-source rejection. This change
does not run another model experiment, integrate native `dev run`, implement a
sealed service or establish that compact memory improves optimization quality.
Work was unguarded because this workspace exposes `.git` as read-only; existing
uncommitted files were preserved.

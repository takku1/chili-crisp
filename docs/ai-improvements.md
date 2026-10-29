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

1. Extend the [implemented source-only native bridge](native-development.md) with
   isolated compilation and a bounded real-model two-generation experiment.
   Shrinking enforced budgets now pass a deterministic controller fixture.
2. Harden deployment of the [owner-operated sealed gate](sealed-acceptance.md)
   across separate accounts/hosts and independently reproduce its results.
   Keep public feedback separate from private assets and detailed failures.
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

The original memory increment's tests cover bounded history, exclusion of unmeasured research claims, repeat
labelling and actual remeasurement after identical-source rejection. That increment
did not run another model experiment or establish that compact memory improves
optimization quality. Its work was unguarded under the managed `.git` restriction.
Subsequent [native bridge validation](../reports/native-development-validation.md)
exercises `dev run` and shrinking enforced limits. The subsequent owner-operated
sealed gate adds policy-scoped verification; remote service deployment remains open.

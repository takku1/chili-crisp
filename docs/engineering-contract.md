# Runner and experiment policies

This document adds mandatory implementation requirements to the memory protocol. MUST means a conformance requirement; SHOULD permits a documented exception. A runner that cannot satisfy a required policy returns `unsupported` before launching the target.

The [implementation guide](implementation.md) records the executable policy, lifecycle, output limits, and remaining conformance gaps. Cgroups provide resource accounting; the pilot additionally requires a controlled filesystem/mount namespace, network isolation, unprivileged execution, syscall filtering, inaccessible controller secrets and hidden inputs, and limits for processes, descriptors, scratch, and output. Do not treat memory enforcement alone as isolation.

## Measurement modes

`whole_program` is the v0.1 implementation target. The target interpreter, dynamic linker, libraries, startup, threads, children, and shutdown all count inside the cgroup. The controller and verifier do not. Runtime overhead is reported, never subtracted to claim an application-only frontier.

`component_allocation` is a separately labeled future adapter. It requires a defined allocation API or instrumented arena, a limit enforced on every relevant allocation, overflow handling, and validation that target operations cannot bypass the allocator. It measures allocation-budget compliance, not total physical memory. Record host runtime memory separately. Results from these modes MUST NOT share a frontier or percentage comparison.

## Launch and lifetime

1. Create a fresh target cgroup and configure limits before creating the workload process.
2. Prefer `clone3(CLONE_INTO_CGROUP)` with an open target-cgroup descriptor. This creates the child in the destination cgroup. A fallback launcher must join the cgroup and acknowledge membership before `exec` of any target code; disclose launcher allocations and inherited state. Starting the workload and migrating it afterward is forbidden. See [clone(2)](https://www.man7.org/linux/man-pages/man2/clone.2.html).
3. Verify membership and configuration from the controller. Do not give target processes permission to migrate themselves or change limits. Children inherit the accounting boundary.
4. Start a monotonic watchdog outside the cgroup. At timeout, record the event, terminate the entire target cgroup with a bounded grace period, then force termination. Killing only the leader is insufficient.
5. Wait for all tasks to exit, collect final counters and artifacts, and remove the empty cgroup. Cleanup failure invalidates reuse of the environment and is recorded separately from target failure. A controller crash must leave enough external state for recovery and orphan cleanup.

## Enforced preflight

The controller MUST record requested and effective settings, including ancestor constraints. Inspect available controllers, delegation, `memory.max`, `memory.high`, `memory.swap.max`, relevant ancestor limits, and host pressure. The default pilot disables target swap with `memory.swap.max=0`, uses no intentional `memory.high` throttling, and rejects environments whose tighter ancestors invalidate the intended budget. These are pilot choices, not universal deployment advice.

Cache policy MUST name a reproducible preparation procedure and its scope. A fresh cgroup does not imply a cold filesystem cache. Record which process first reads shared files; shared page charges can belong elsewhere. Do not claim a cold-cache experiment merely because a process restarted. If equivalent cache preparation cannot be verified, use an explicitly qualified warm-cache policy or reject the requested experiment.

Anonymous mappings and tmpfs count under the declared cgroup policy; tmpfs is not a free overflow store. Shared mappings with outside processes, external helpers, and network offloading are prohibited in the pilot. Subprocesses stay inside the cgroup. Explicit huge pages require verified separate accounting or must be unavailable to the target; record transparent huge-page policy separately. Filesystem scratch use needs a bounded, recorded policy so memory savings cannot silently become unlimited disk use. The [kernel cgroup documentation](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html) defines the interfaces and accounting qualifications.

## Adaptive controller policy

Reduction factor, minimum budget, refinement tolerance, repetition counts, and cost caps MUST be manifest parameters. The controller records each decision and evidence used.

| Observation | Decision |
| --- | --- |
| Repeated stable passes far from pressure | Permit a larger geometric reduction within declared bounds |
| First failure | Repeat to establish a usable bracket |
| Stable bracket | Refine geometrically only if precision will inform a change |
| Inconsistent outcomes | Repeat nearby points and report empirical pass rates |
| Correctness preserved but latency threshold crossed | Record a performance-pressure region independently of OOM |
| Cost cap reached or refinement cannot change a decision | Stop search and generate hypotheses from existing evidence |

Each workload class retains its own outcomes. No fitted input-size model is required.

## Hidden evaluation policy

Exploration uses public workloads and detailed feedback. Confirmation begins only after candidate source, build settings, and artifact are frozen by hash. Hidden outcomes and diagnostics remain unavailable to the optimizing agent until the evaluation closes. If a failed candidate is revised using confirmation feedback, that confirmation set is spent: final grading requires an independent sealed set. Record every exposure and prohibit silently reusing a spent set as held out.

## Artifact and cost contract

An experiment is one frozen manifest, one baseline, and a bounded sequence of candidate attempts. A candidate is an immutable source/build configuration; a trial is one execution of one candidate on one workload at one budget. Count failed builds and abandoned candidates.

Every trial record MUST contain `schema_version`, `experiment_id`, `trial_id`, `candidate_hash`, `manifest_hash`, `measurement_mode`, `workload_id`, `phase`, `requested_budget_bytes`, `effective_budget_bytes`, `outcome`, `metrics`, `artifact_hashes`, `preflight_record`, and `cost`. Metrics include value, unit, collection method, and availability status. Artifacts include raw output, kernel counters, verifier output, and launch/cleanup logs. Missing values are explicit; schema validation failure blocks aggregation. Versioned executable schemas now reside in `schemas/`; the result schema currently covers public exploration trials.

Cost includes candidate count, tool calls, test invocations, build/runner CPU time, elapsed time, agent-active time where observable, and input/output tokens and monetary cost where supplied by the model provider. Unknown costs stay unknown. Include setup and failed attempts; distinguish one-time infrastructure from per-experiment cost.

Normal-hardware comparison MUST use reproducibly randomized baseline/candidate order in blocks with the same warmup policy. Retain the seed and full order. Equal agent wall time alone is insufficient: evaluation must predeclare both the main budget and secondary resource caps and report actual consumption.

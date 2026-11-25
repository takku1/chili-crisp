# Archive: enforcement-first era (2026-10-28 to 2026-11-25)

Chili Crisp started as "verified scarcity experiments": kernel-enforced cgroup
memory frontiers, bubblewrap isolation, separate Unix accounts and signed
sealed grading. Its main question was whether artificial scarcity helps AI
agents find transferable optimizations.

On 2026-11-25 the concept was reset to **constraint briefs**. Constraints are
set conceptually and checked by measurement on the host
(see [current concept](../../current/concept.md)). The enforced tier still
exists and is documented under `docs/current/enforced/`.

This folder holds the earlier design docs (`design.md`, `protocol.md`,
`roadmap.md`, `research.md`, ...), the last enforcement-era status
(`STATUS-2026-10-30.md`) and the narrative validation reports (`reports/`).
Raw logs, JSON, patches and pilot scripts were removed from the tree. Check out
commit `790326b` to see them. Links in these files that point to raw evidence
resolve only at that commit.

Results worth remembering:
- A decoder self-test cut whole-program charged peak memory by 19.91% on its
  largest workload, under enforced limits.
- A native Wilderbeast archive transfer cut charged memory by 13.54% and passed
  signed sealed grading. A negative control was correctly rejected.
- A real-model comparison completed the workflow on a synthetic task. It did not
  show that scarcity beats a conventional prompt; that question is still open.

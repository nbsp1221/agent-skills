# Orchestration Patterns

These patterns are for coding workflows where delegation improves signal without creating merge chaos.

## Research Split

- Ideal use case: independent codebase or documentation exploration across modules, services, or source sets
- Required inputs: question to answer, scope boundary, expected deliverable shape
- Expected outputs: concise findings with file paths, constraints, and recommended next action
- Default budget: 2-4 subagents
- Maximum v1 guidance: 4 unless the work is clearly partitioned and low risk
- Fallback to one agent when: the same files keep appearing across threads or synthesis cost dominates
- Common failure mode: overlapping exploration produces repetitive summaries with no new information

Prefer this over a single-agent workflow when exploration is broad enough to pressure context but still separable.

## Review Fan-out

- Ideal use case: one implementation or plan needs independent review lenses
- Required inputs: diff, plan, target files, review scope, output contract
- Expected outputs: evidence-backed findings by severity and confidence
- Default budget: 3 reviewers
- Maximum v1 guidance: 3 by default; add more only for exceptional regulated or security-sensitive work
- Fallback to one agent when: reviewers repeat each other or the task is too small to justify fan-out
- Common failure mode: persona multiplication without better findings

Prefer this over a single-agent workflow when independent critique matters more than raw implementation speed.

## Serial Build

- Ideal use case: one implementer writes while other agents explore, review, or test around the edges
- Required inputs: bounded file ownership, clear task, verification target, handoff contract when another stage will consume the result
- Expected outputs: code changes plus verification evidence
- Default budget: 1 writer
- Maximum v1 guidance: 1 unless file ownership is explicitly disjoint
- Fallback to one agent when: write boundaries are unclear or neighboring changes are tightly coupled
- Common failure mode: multiple writers edit adjacent logic and force expensive reconciliation

Prefer this over parallel writing unless the write sets are explicitly separated before work starts.

## Evidence Return

- Ideal use case: any delegated task whose output could otherwise collapse into vague summary language
- Required inputs: requested evidence format and claim structure
- Expected outputs: concrete file paths, observed behavior, why it matters, next action
- Default budget: applies to every subagent, not a separate fan-out class
- Fallback to one agent when: the delegated task is too trivial to justify handoff overhead
- Common failure mode: "looks good" or "probably fine" output with no basis

Use this pattern whenever a delegated result will influence implementation or review decisions.

## Contracted Handoff

- Ideal use case: a delegated stage will hand work to another worker, reviewer, or parent synthesis pass
- Required inputs: scope, owner, acceptance criteria, evidence format, next-step consumer
- Expected outputs: a handoff artifact that the next stage can read without reconstructing context from scratch
- Default budget: applies to every multi-stage delegated workflow
- Fallback to one agent when: the work is a one-shot question with no downstream consumer
- Common failure mode: the next stage receives a summary but not the conditions for success

Prefer this over informal summaries whenever work spans planning, implementation, review, or QA boundaries.

## Human Gate

- Ideal use case: auth, public API, migrations, external contracts, destructive operations, or unclear risk
- Required inputs: risk summary, options, recommended path
- Expected outputs: go/no-go or narrowed instruction from the human
- Default budget: not a fan-out pattern; apply at decision points
- Fallback to one agent when: no genuine risk boundary exists and the gate would be performative
- Common failure mode: agents approving each other on high-risk work with no human checkpoint

Use this pattern to stop automation from drifting across trust boundaries.

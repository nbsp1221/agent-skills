# Review Fan-out and Synthesis

Default review fan-out is three reviewers:
- Security
- Correctness and testing
- Maintainability and performance

Do not create an unbounded reviewer set unless the task is unusually high risk and each added reviewer has a distinct signal source.

## Reviewer Output Contract

Each reviewer should return:
- Concrete file path or artifact reference
- Behavioral claim
- Why it matters
- Suggested next action
- Confidence level when uncertainty remains

Reject outputs that only say "looks good", "seems risky", or "probably fine".

## Parent Synthesis Contract

The parent agent must:
- Read the handoff contract or delegated artifact before merging findings
- Deduplicate overlapping findings
- Reconcile contradictory findings
- Prioritize by severity and confidence
- Separate required fixes from advisory notes
- Produce one final recommendation

The parent agent owns the final judgment. Review fan-out is input, not authority transfer.

## Merge Discipline

- Duplicate findings: merge into one item and keep the strongest evidence
- Conflicting findings: inspect the underlying evidence and resolve explicitly
- Low-confidence findings: keep only if the risk is material or the evidence is still actionable
- Advisory-only findings: include only when they do not obscure higher-severity issues

## Stop Policy

Stop adding reviewers when:
- Findings are repeating
- New reviewers are not materially changing the decision
- The synthesis burden is larger than the confidence gain

Discard low-signal reviewer output rather than padding the final answer with noise.

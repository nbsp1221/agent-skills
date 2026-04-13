# Host Compatibility and Limits

This skill is behavioral guidance, not a claim that every host supports the same delegation model.

## Capability Matrix

| Host mode | Context model | Communication model | Best fit | Avoid when |
| --- | --- | --- | --- | --- |
| Claude Code subagents | Isolated delegated worker context | Parent delegates and later synthesizes | Research split, bounded review, narrow sidecar implementation support | You need sustained peer coordination |
| Claude Code agent teams | Separate sessions with teammate-style coordination | Agents can collaborate more directly at higher cost | Parallel research, competing hypotheses, multi-step collaboration | The task is just large, not collaborative |
| Codex subagents | Separate delegated worker context | Parent-directed orchestration | Explicitly requested exploration, review fan-out, isolated sidecar work | Delegation is implicit, vague, or overlapping on writes |

## Claude Code Subagents

- Use for isolated delegated work with separate context.
- Good fits: research split, bounded review, narrow implementation support.
- Keep delegation shallow and keep the parent as the coordinator.
- Default review and research workers to read-only minimal tools. Grant edit-capable tools only to the bounded writer when needed.
- Prefer lighter or cheaper workers for narrow read-heavy tasks when the host configuration supports it.

## Claude Code Agent Teams

- Use when the work genuinely needs sustained multi-agent collaboration rather than one-shot delegation.
- Agent teams cost more and coordinate differently; do not escalate to teams just because a task is large.
- If team-style coordination is unavailable, degrade to one main agent plus shallow delegated reviewers or researchers.

## Codex Subagents

- Use only when delegation is explicit or clearly desired by the human.
- Best fits are bounded read-heavy exploration, review fan-out, and isolated sidecar work.
- Be conservative about token cost and context pollution.
- Treat concurrent writing as risky unless ownership is explicit and disjoint.
- Keep review and research delegates read-only whenever the host configuration allows it.
- Prefer smaller, faster workers for scans and sidecar analysis when available, and keep final synthesis with the parent.

## Fallback Rules

- If auto-delegation is not appropriate, route deliberately and keep prompts specific.
- If nested delegation is unsupported, keep the parent as the sole coordinator.
- If sustained collaboration is unavailable, use serial orchestration with clear checkpoints.
- If concurrent writes are risky, collapse to one writer and keep everyone else read-only.
- If the host's constraints are unclear, assume the safer model: shallow delegation, one writer, strong synthesis.

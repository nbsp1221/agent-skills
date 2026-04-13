# Anti-Patterns

## Multi-writer overlap

What goes wrong:
- Multiple subagents edit the same files or adjacent logic and create merge friction, hidden regressions, and confused ownership.

Do this instead:
- Keep one writer by default, or split ownership only when file boundaries are explicit before work begins.

## Persona zoo without routing logic

What goes wrong:
- Large collections of specialist agents create overhead without improving decisions.

Do this instead:
- Use a small set of reviewers with distinct responsibilities and a clear reason for each one.

## Vague delegation prompts

What goes wrong:
- Subagents return generic summaries because the task shape and evidence contract were never specified.

Do this instead:
- Delegate bounded tasks with required inputs, expected outputs, and evidence format.

## Summary-only outputs with no evidence

What goes wrong:
- The parent agent cannot verify claims and ends up trusting tone instead of substance.

Do this instead:
- Require file paths, observed behavior, why it matters, and next action.

## Fan-out without synthesis

What goes wrong:
- Reviewer output piles up, duplicates remain unresolved, and the final decision becomes less clear than the starting point.

Do this instead:
- Make the parent agent reconcile and prioritize before presenting any conclusion.

## Handoff without contract

What goes wrong:
- The next stage inherits a vague summary, re-derives context, and drifts from the original success conditions.

Do this instead:
- Pass a handoff artifact with scope, owner, acceptance criteria, evidence, and next-step note.

## Reflexive subagent use

What goes wrong:
- Large tasks trigger automatic fan-out even when a single agent would be faster and more reliable.

Do this instead:
- Delegate only when the task is naturally separable or independent review meaningfully raises confidence.

## Strategy by vibe

What goes wrong:
- Guidance collapses into slogans like "use subagents strategically" with no decision rules.

Do this instead:
- Define budgets, stop conditions, ownership rules, and host-specific limits.

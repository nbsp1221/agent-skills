# Simplification Principles

Translate clean-code ideas into recoverability-oriented editing decisions.

## Priority Ladder

Apply principles in this order:

1. Intent clarity
2. Local reasoning
3. Responsibility reduction
4. Control-flow simplicity
5. Cautious DRY

If two principles conflict, prefer the one earlier in the ladder.

## Intent Clarity

Make the code reveal what it is trying to do.

Prefer:
- Names that expose role, boundary, or phase
- Code that shows why a branch exists
- Explicit intermediate values when they make meaning visible

Avoid:
- Shorter names that hide purpose
- Helpers whose names are vague while the real logic is now farther away
- Dense expressions that compress several ideas into one line

Rule:
- If the reader must mentally expand the code to understand intent, the code is not simplified enough

## Local Reasoning

Make the next change possible without scanning half the file.

Prefer:
- Sequencing that reads top-to-bottom
- Nearby related logic
- Narrow edits to one clear region

Avoid:
- Indirection that forces bouncing between helpers for a simple question
- Hidden mutation or side effects at a distance
- Coupling unrelated branches through a generic helper

Rule:
- If a likely future edit still requires tracing many distant locations, keep simplifying

## Responsibility Reduction

Reduce overloaded units before chasing duplicate lines.

Prefer:
- Separating validation from transformation or side effects when that boundary is already present
- Splitting a function when one part decides and another part executes
- Keeping one unit focused on one immediate concern

Avoid:
- Giant "orchestrator" functions that validate, normalize, mutate, log, and respond in one place
- Merging distinct responsibilities just because they share some code

Rule:
- A little duplication is cheaper than one abstraction that mixes responsibilities

## Control-Flow Simplicity

Prefer direct, debuggable flow.

Prefer:
- Guard clauses over incidental nesting
- Straightforward branches over nested ternaries
- Explicit error and async paths

Avoid:
- Clever chains
- Compact rewrites that make step boundaries disappear
- Reordering effectful code unless the equivalence is obvious and verified

Rule:
- If a rewrite makes it harder to set a breakpoint or inspect state, it is not simpler

## DRY

Use DRY last and conservatively.

Good:
- Remove repetition when both behavior and reason to change are the same
- Extract repeated code when the shared name makes intent clearer

Bad:
- Unify code that only looks similar
- Invent generic helpers for two call sites with different semantics
- Couple edge cases to mainline flow just to reuse a few lines

Rule:
- Prefer honest duplication over a misleading abstraction

## Scope Discipline

This skill is a cleanup pass for recoverability, not a general rewrite pass.

Prefer:
- Touched files first
- Adjacent edits only when needed to clarify the current target
- Follow-up notes for wider cleanup ideas

Avoid:
- Repo-wide consistency edits
- Rewriting neighboring modules because they are also ugly
- Turning one cleanup pass into architecture migration

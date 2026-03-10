# Examples

These examples show what recoverability-oriented simplification should and should not do.

## Good Simplification: Intent First

Situation:
- A bug fix added nested `if` blocks, repeated null checks, and a dense final condition

Good move:
- Keep the same checks
- Convert the outer nesting into guard clauses
- Name the final condition if that makes the rule visible

Why:
- Behavior stays the same
- The reader can now see the happy path and the stop conditions in one pass

## Good Simplification: Better Next Edit

Situation:
- One function validates input, normalizes values, writes to storage, and builds a response

Good move:
- Keep the function local to the same file
- Split obvious private phases so validation and side effects are easier to modify separately

Why:
- The next change to validation or persistence has a more obvious home
- Responsibilities are less entangled without broad redesign

## Bad Simplification: Code Golf

Situation:
- Several simple branches can be compressed into a nested ternary or one expression chain

Bad move:
- Replace readable branching with a dense one-liner

Why it is bad:
- The code is shorter, but debugging and later edits become harder

## Bad Simplification: False DRY

Situation:
- Two branches each validate input, but one also normalizes and the other logs metrics

Bad move:
- Force both branches through one generic helper because they share some lines

Why it is bad:
- Duplication decreases, but responsibilities blur
- The next change now risks breaking both paths together

## Bad Simplification: Hidden Complexity

Situation:
- A long function is hard to read

Bad move:
- Extract three vaguely named helpers that each mutate shared state

Why it is bad:
- Visual length goes down, but reasoning cost goes up
- The complexity moved; it did not disappear

## Good Simplification: Leave A Note

Situation:
- A wider architecture cleanup would help, but it is not required to improve the current diff safely

Good move:
- Simplify only the touched area
- Mention the wider cleanup as a follow-up suggestion

Why:
- Keeps the current task safe and reviewable
- Still preserves momentum for a later, explicit redesign

# Acceptable vs Unacceptable Changes

Use this file to decide whether a simplification meaningfully improves recoverability without drifting into redesign.

## Usually Acceptable

- Renaming unclear locals, parameters, or private helpers
- Replacing repeated property access with clear local values
- Flattening unnecessary nesting with guard clauses
- Separating obvious phases inside one function when the behavior stays identical
- Extracting a small private helper when it removes present complexity and keeps intent visible
- Removing dead code that is clearly unused
- Removing comments that only restate obvious code
- Reordering local statements when the new order exposes the actual data flow and preserves effects

## Acceptable With Extra Care

- Changing helper boundaries
- Splitting a large function into two or more private helpers
- Reorganizing async control flow
- Reshaping error-handling flow
- Simplifying tests that encode subtle behavioral guarantees
- Consolidating similar branches that may have slightly different semantics
- Adjusting types or internal interfaces used across several call sites

Before making these edits:
- State what behavior must remain true
- Inspect nearby call sites and side effects
- Prefer boundaries that expose meaning instead of hiding it
- Choose the smaller edit if the equivalence is hard to prove

## Usually Unacceptable

- Changing public API shape during a cleanup-only pass
- Changing outputs, side effects, ordering, or concurrency semantics
- Changing error behavior without an explicit reason
- Changing logging or telemetry contracts that downstream code may rely on
- Adding new features while simplifying
- Replacing explicit logic with a shorter but harder-to-debug construct
- Broad architecture rewrites or moving logic across unrelated modules
- Introducing speculative abstractions for future reuse

## Recovery-Positive Signals

Signs an edit is probably worth keeping:

- The likely next edit has a more obvious home
- A function's responsibilities are easier to explain in one sentence
- It takes fewer jumps to follow a request, state transition, or side effect
- The code can be debugged in order without decoding a generic abstraction first

## Red Flags

Stop and reconsider when the simplification:

- Needs a long proof that it is "really equivalent"
- Only saves lines while making meaning less obvious
- Relocates complexity into a helper with a hand-wavy name
- Merges responsibilities that used to be locally understandable
- Broadens scope from one diff to many files
- Depends on assumptions you have not verified

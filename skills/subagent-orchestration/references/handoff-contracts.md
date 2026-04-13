# Handoff Contracts

Use a handoff contract whenever delegated work crosses a stage boundary such as:
- planner to implementer
- implementer to reviewer
- reviewer to parent synthesis
- builder to QA

## Minimum Contract

Every handoff artifact should include:
- Scope: the bounded chunk of work under discussion
- Owner: who is responsible for producing or judging it
- Acceptance criteria: what must be true for this stage to count as done
- Evidence required: what concrete proof must come back
- Next-step note: what the next stage should do with this result

## Contract First

If the workflow has more than one stage, define the contract before code or review work starts.

Why:
- It bridges the gap between a high-level request and a testable chunk of work.
- It prevents later stages from inventing their own definition of done.
- It makes pass/fail judgments easier to justify.

## Suggested Artifact Shape

Use any durable format the host supports, but keep the fields recognizable:

```text
Scope:
Owner:
Acceptance criteria:
- ...
- ...

Evidence required:
- ...

Next-step note:
```

## Acceptance Criteria Guidance

Good acceptance criteria are:
- observable
- testable
- bounded to one stage

Bad acceptance criteria are:
- vague quality claims
- hidden implementation preferences
- goals that require the next stage to guess what success means

## Handoff Discipline

- The producing stage should write the artifact before handing off.
- The receiving stage should read it before acting.
- If the artifact is missing or ambiguous, stop and repair it instead of guessing.

## When To Skip

Skip a formal contract only when:
- the task is a one-shot question
- there is no downstream consumer
- the handoff would be pure ceremony

Otherwise, prefer a short contract over an informal summary.

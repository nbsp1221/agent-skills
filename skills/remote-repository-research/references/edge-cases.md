# Edge Cases

Use these fallbacks when the default shallow-clone workflow would hide important evidence.

## Large Monorepos

Risk:
- a naive first pass can drown in unrelated packages

Adjustments:
- inspect workspace files first
- identify the surface relevant to the user's goal before deep reading
- use sparse or selective fetch if available and useful

## Tag- or Branch-Specific Questions

Risk:
- the default branch does not represent the version the user cares about

Adjustments:
- fetch the specific tag or branch
- say explicitly which revision you analyzed

## History-Dependent Questions

Risk:
- shallow clone hides the evidence

Adjustments:
- use a fuller clone or targeted history fetch
- do not pretend release or evolution questions can be answered from a shallow clone alone

## Submodule-Heavy Repositories

Risk:
- important architecture lives outside the initial tree

Adjustments:
- inspect submodule declarations explicitly
- note which conclusions are incomplete until submodule contents are inspected

## Documentation-Only Repositories

Risk:
- code-oriented heuristics may send you looking for `src/` when the source-of-truth is content and publishing config

Adjustments:
- inspect content roots, docs config, generators, and publishing workflow first

## Poorly Onboarded Repositories

Risk:
- missing manifests or weak docs can make the structure ambiguous

Adjustments:
- rely more heavily on tree shape, CI, tests, examples, automation, and import/module structure
- increase uncertainty in the final brief

## Inaccessible or Non-Cloneable Targets

Risk:
- the repository-first workflow cannot fully run

Adjustments:
- say the clone requirement was not satisfiable
- continue only with clearly limited remote-only analysis
- reduce confidence and explain what evidence is missing

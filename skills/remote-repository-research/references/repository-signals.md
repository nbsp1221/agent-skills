# Repository Signals

Use these signals to infer the apparent repository type and adjust the analysis lens. This is an informed heuristic, not a rigid taxonomy.

## Apparent Repository Type Cues

### Application or Product Repository

Common cues:
- app/server/web runtime roots such as `app/`, `server/`, `src/`, `backend/`, `frontend/`
- environment config, deployment config, service wiring
- integration-heavy code, API routes, job runners, workers

Prioritize:
- runtime boundaries
- config and environment handling
- integrations
- deployment and CI

### Library or Framework

Common cues:
- public API exports and package entrypoints
- example projects or sample integrations
- tests validating API behavior
- release/versioning emphasis

Prioritize:
- API surface
- extension points
- examples
- tests
- versioning and packaging

### Documentation or Content Repository

Common cues:
- `docs/`, `content/`, `website/`, `mkdocs.yml`, `docusaurus.config.*`, `mdx/`
- docs-generation or publishing pipeline
- sparse implementation code relative to authored content

Prioritize:
- content structure
- generation pipeline
- source-of-truth docs
- publishing workflow

### CLI or Tooling Repository

Common cues:
- command entrypoints
- argument parsing layers
- shell completions
- package/install logic
- automation hooks

Prioritize:
- command surface
- config loading
- packaging
- automation

### Infrastructure or Deployment Repository

Common cues:
- Terraform, Pulumi, Helm, Kubernetes, Ansible, Nix, Docker-heavy layouts
- environment overlays or stage-specific config
- infra modules and automation with little business logic

Prioritize:
- module boundaries
- environments
- state/config assumptions
- automation and operational workflow

### Monorepo or Mixed Repository

Common cues:
- workspaces, packages, apps, services, shared libs
- multiple manifests or multiple top-level surfaces
- platform repo with product, libraries, docs, or infra together

Prioritize:
- workspace/package boundaries
- shared infrastructure
- the surface most relevant to the user's question

For mixed repos, report multiple relevant surfaces instead of forcing one dominant type.

## Credibility and Maturity Signals

Look for:
- examples that mirror real usage rather than toy snippets
- tests near the important behavior
- active CI or automation
- clear release/tag history
- issue and PR hygiene
- contributor documentation
- recent maintenance activity

Warning signs:
- stale automation
- no tests around the most important code paths
- examples that do not match the actual current code
- docs that reference files or commands that no longer exist
- archived or abandoned maintenance signals

## Fact vs Inference

Keep these separate:
- **Observed fact:** "The repo has `examples/`, `tests/`, and `pnpm-workspace.yaml`."
- **Inference:** "This appears to be a monorepo-oriented library ecosystem with examples used as adoption material."

If the type is uncertain, say so. Use language such as `apparent repository type`, `primary analysis lens`, or `mixed`.

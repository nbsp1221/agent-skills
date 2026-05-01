# Research Workflow

Use this workflow to keep repository research grounded in the actual cloned contents.

## 1. Frame the Goal

Start by restating the research goal in one sentence.

Examples:
- "Understand how this project structures plugins."
- "Find the parts relevant to background job orchestration."
- "Assess whether this repository is a useful reference for multi-package builds."

This controls scope and prevents broad, low-signal browsing.

## 2. Gather Lightweight Remote Signals

Before cloning, inspect lightweight metadata:
- repository description
- default branch
- primary languages
- recent commit activity
- release presence
- size signals if available

This step is a gate, not the answer. Do not treat metadata as sufficient analysis.

## 3. Clone Into `/tmp`

Default behavior:
- shallow clone first
- clone the default branch unless a tag or branch is clearly more relevant
- keep the clone out of the current working repository

Recommended shape:

```bash
git clone --depth 1 <repo-url> /tmp/remote-repository-research/<repo-name>
```

Use the fallbacks in [edge-cases.md](edge-cases.md) when shallow clone is not enough.

## 4. Do a Topology Pass

Before reading deeply, identify:
- top-level directories
- manifests and build files
- likely source-of-truth roots
- whether the repository is single-surface, mixed, or monorepo-shaped

Good first-pass targets:
- `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile`, `pom.xml`
- workspace files such as `pnpm-workspace.yaml`, `turbo.json`, `nx.json`
- docs/publishing config
- CI and automation files

Use fast search first. Prefer `rg`, root listings, and focused file reads over opening many large files blindly.

## 5. Choose Inspection Roots By Apparent Type

Use [repository-signals.md](repository-signals.md) to infer the apparent repository type.

Default roots by lens:
- application/product: runtime roots, integrations, config, deployment surfaces
- library/framework: API-bearing source roots, examples, tests, versioning config
- documentation/content: content roots, generation pipeline, publishing config, source-of-truth docs
- CLI/tooling: command entry points, config loading, packaging, automation
- infrastructure/deployment: modules, environments, overlays, automation, state/config boundaries
- monorepo/mixed: workspace roots, package boundaries, shared infrastructure, then the surface most relevant to the user's goal

Read README and contributor docs early, but only after the topology pass shows where the actual source-of-truth likely lives.

## 6. Minimum Local Evidence Threshold

Do not use external sources until you have inspected, at minimum:
- the top-level tree
- the primary manifests or build files
- at least one source-of-truth root relevant to the question
- at least one supporting evidence area such as tests, examples, docs source, CI, or automation

If you have not met this threshold, keep inspecting the clone.

For multi-repository tasks, apply this threshold per repository. If one repository cannot meet the threshold because of access, size, time, or environment limits, label that repository's conclusions as lower-confidence or incomplete instead of letting evidence from another repository stand in for it.

## 7. Secondary Evidence

Only after the local inspection should you use:
- issues and pull requests
- releases and changelog
- official docs
- external writeups

Use them to answer specific questions raised by the cloned repository. Do not use them to replace repository inspection.

## 8. Deliver the Brief

Use the fixed template in [output-format.md](output-format.md).

Default delivery:
- inline response unless the user explicitly asks for a file
- saved markdown document only when the user explicitly asks for one

# Conventional Commits Reference

Use this when the repo clearly follows conventional commits or when you need a default rule set and no other guidance exists.

## Format

`type(scope)!: subject`

- type: required, from the allowed list
- scope: optional unless the repo commonly includes it
- !: use for breaking changes
- subject: required, imperative, no period

## Allowed type list

Use only allowed types. Prefer the repo's explicit or historical type set over this default list.

- `feat`: new user-facing capability
- `fix`: bug fix or defect correction
- `docs`: documentation-only change
- `style`: formatting or whitespace-only change
- `refactor`: code change without behavior change
- `perf`: performance improvement
- `test`: add/update tests only
- `build`: build system, tooling, or dependencies
- `ci`: CI/CD pipeline or workflow changes
- `chore`: maintenance and housekeeping
- `revert`: revert a previous commit

## Subject rules

- Imperative: `add`, `fix`, `update`, `remove`
- Prefer lowercase start unless the repo uses title case
- Try <= 50 chars; hard limit 72 unless the repo allows longer
- No trailing period

## Scope rules

- Use kebab-case: `auth-flow`, `api-client`
- Only use scopes that appear in repo history or docs

## Body and trailers

- Use a body for non-trivial changes; wrap at 72 chars
- Use trailers when relevant: `Fixes #123`, `Refs #123`

## Breaking changes

Use only for backward-incompatible changes that break users or public interfaces (API, CLI, config, data behavior). Do not use for internal refactors.

Use one of:
- `type(scope)!: subject`
- `BREAKING CHANGE: explanation in footer`

## Reverts

Use `revert: <subject>` and explain the revert in the body if possible.

## Examples

### Good

- `feat(auth): add google oauth login support`
- `fix: handle null pointer in user profile`
- `docs(api): update endpoint documentation`

### Bad

- `feat(auth): add oauth flow.` (period)
- `fix: fixed login bug` (past tense)
- `update login flow` (missing type)

# Agent Skills

A curated collection of Agent Skills for coding agents. Each skill is a self-contained folder with a `SKILL.md` file and optional references or scripts.

## Quick Install

```bash
# Using the skills CLI
npx skills add https://github.com/nbsp1221/agent-skills/tree/main/skills/commit

# Using the skill-installer
$skill-installer install https://github.com/nbsp1221/agent-skills/tree/main/skills/commit
```

> To install another skill, replace the last path segment with the desired skill folder name.

## Skills by Category

### Engineering

#### commit
- **Description:** Detects the repo's commit convention (Conventional Commits, Gitmoji, or custom) and creates commits accordingly.
- **Use when:** "Commit these changes with the repo's convention"
- **Location:** `skills/commit`

#### docker-compose
- **Description:** Writes/reviews Docker Compose files with consistent conventions (naming, ordering, env handling, readiness).
- **Use when:** "Standardize this docker-compose.yml to our conventions"
- **Location:** `skills/docker-compose`

### Product & Validation

#### idea-validation-autopilot
- **Description:** Runs autonomous idea validation from raw concept to evidence-backed decision memo and MVP scope.
- **Use when:** "I have an idea, research the market/competitors, tell me what MVP to build, and decide go/no-go with minimal questions"
- **Location:** `skills/idea-validation-autopilot`

## Structure Guidelines

- Every skill lives at `skills/<skill-name>`.
- Each skill includes at least `SKILL.md`.
- Optional folders: `references/`, `scripts/`, `assets/`.
- Skill names must be unique; a flat `skills/` layout makes collisions immediately obvious.

```
skills/
  <skill-name>/
    SKILL.md
    references/ (optional)
    scripts/ (optional)
    assets/ (optional)
```

## References

- [Agent Skills specification](https://agentskills.io/specification)
- [Agent Skills examples](https://github.com/anthropics/skills)

# 🧠 Agent Skills

Personal collection of Agent Skills and instructions for AI agents.

Skills are folders of instructions, scripts, and references that agents can load to perform tasks more accurately. This repo follows the [Agent Skills](https://agentskills.io/) format.

## Installation

Install a skill by pointing your agent's installer at the repo path.

```bash
$skill-installer install https://github.com/nbsp1221/agent-skills/tree/main/engineering/commit
```

After installing, restart your agent to pick up new skills.

## Available Skills

### commit

Detect the repo's commit convention (Conventional Commits, Gitmoji, or a custom template) and create commits.

**Use when:**
- You want to commit changes with the repo's existing convention
- You want a commit message generated from current changes
- You want to commit and push with the right format

**Example usage:**
- "Commit these changes with the repo's convention"
- "Generate a commit message for this diff"
- "Commit and push"

Location: `engineering/commit`

## Skill Structure

Each skill is a folder that includes:

- `SKILL.md` for instructions and workflow
- `references/` for detailed rules and documentation

## References

- [Agent Skills specification](https://agentskills.io/specification)
- [Agent Skills examples](https://github.com/anthropics/skills)

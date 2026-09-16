---
name: gh-create-repo
description: Research, propose, approve, and create GitHub repositories with the gh CLI. Use when the user wants to name or create a repository, decide its visibility, derive descriptions and topics from their existing GitHub conventions, validate that proposed topics are active and relevant, or apply approved repository metadata. Require explicit user approval before creating a repository or changing remote metadata.
---

# Create a GitHub Repository

Use `gh` to ground repository metadata in the user's actual conventions and the current GitHub ecosystem. Separate research and approval from mutation.

## Workflow

### 1. Establish the repository intent

- Identify the repository's purpose, intended audience, owner, and any name already chosen.
- Preserve a user-selected name unless the user asks for alternatives or it conflicts within the target account.
- Infer the authenticated owner with `gh api user` when it is not stated.
- Ask only about choices that cannot be discovered and would materially change the result.
- Do not research npm, domains, or unrelated registries unless publishing there is in scope.

### 2. Inspect the user's GitHub conventions

Check authentication, then inspect repository metadata with `gh`:

```bash
gh auth status
gh api user
gh repo list --limit 200 \
  --json name,nameWithOwner,visibility,isPrivate,description,repositoryTopics,createdAt,updatedAt,isArchived,isFork
```

Prioritize recent, non-archived source repositories and repositories similar to the proposed one. Infer:

- lowercase, separators, prefixes, and branding patterns;
- description language, length, punctuation, and emoji usage;
- typical topic count and specificity;
- whether comparable personal or reusable work is public or private.

Use private-repository metadata only as internal evidence. Do not reproduce private names or descriptions unless the user asks.

### 3. Check the name and ecosystem

- Verify whether `<owner>/<name>` already exists with `gh repo view`.
- Treat names in other GitHub namespaces as evidence, not conflicts.
- Inspect official and strong ecosystem repositories for terminology, descriptions, and topics.
- Explain material naming ambiguity; do not optimize for hypothetical future products.

If the name is undecided, propose a focused set of candidates and recommend one. If it is already decided, do not reopen naming without evidence of a real problem.

### 4. Research topics

Build candidates from four layers:

1. exact project or ecosystem;
2. technical domain;
3. operating model or use case;
4. artifact type, only when it describes the repository itself.

Inspect official repositories:

```bash
gh api repos/<owner>/<repo> --jq '{description,topics}'
```

Check each candidate's adoption and recent activity:

```bash
gh api search/repositories \
  -f q='topic:<topic>' \
  -f sort=updated \
  -f order=desc \
  -f per_page=3 \
  --method GET
```

- Recommend 6–10 active, accurate topics unless the user specifies another range.
- Prefer relevance over raw repository count.
- Exclude dead, redundant, excessively broad, and misleading topics.
- Do not apply a content-type topic such as `plugin`, `template`, or `library` merely because the repository contains one; the topic must describe the repository as a whole.
- Normalize topics to GitHub's lowercase hyphenated form.

### 5. Draft descriptions

- Produce exactly five materially different descriptions.
- Match the user's observed style rather than imposing a generic house style.
- Keep each concise and truthful about the repository's current purpose.
- Use an emoji only when the account convention or project identity supports it.
- Recommend one candidate and explain the decisive distinction briefly.
- Avoid claims such as official, production-ready, distribution, framework, or marketplace unless already true.

### 6. Present an approval gate

Present one consolidated proposal containing:

```text
Owner:
Repository:
Visibility:
Description: <recommended candidate>
Topics:
- ...
```

Also show all five numbered description candidates. State what will intentionally remain uninitialized. Request explicit approval or a description number plus approval.

Do not create, reserve, rename, transfer, or edit a remote repository before approval.

### 7. Create only the approved repository

After explicit approval, use the approved values without silently revisiting them:

```bash
gh repo create <owner>/<repo> --public --description '<description>'
gh repo edit <owner>/<repo> --add-topic <topic> ...
```

Use `--private` instead when approved. If the repository appeared between research and creation, stop and report the conflict instead of editing it.

Do not add a README, license, `.gitignore`, homepage, local clone, branch protection, Actions workflow, or package publication unless separately approved.

Verify the result from GitHub rather than assuming the commands succeeded:

```bash
gh api repos/<owner>/<repo> \
  --jq '{nameWithOwner:.full_name,visibility,description,topics,url:.html_url,defaultBranch:.default_branch,isEmpty:(.size == 0)}'
```

Report the clickable repository URL, effective visibility, description, topics, and whether it remains empty.

## Guardrails

- Read repository metadata by default, not secrets or repository contents.
- Never print authentication tokens or credential-bearing environment variables.
- Base visibility on the user's intent and comparable repositories; do not assume public merely because reuse is possible.
- Distinguish evidence from recommendation, especially when star counts or topic activity may change.
- Keep the first iteration lean. Defer scaffolding and productization decisions to later approvals.

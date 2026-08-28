---
name: create-pr
description: Create a review-ready GitHub pull request from a completed task branch after explicit authorization. Use only when the user explicitly asks to create, open, raise, or submit the pull request, or when applicable instructions explicitly pre-authorize creating it. Validate the complete branch diff, repository conventions, verification evidence, squash-compatible title, publication safety, remote head, and duplicate PR state before creation. Do not use merely to assess readiness, draft PR text, review an existing PR, or discuss how a PR should be created.
---

# Create PR

Create exactly one review-ready GitHub pull request from the current task branch. Treat pull request creation as an externally visible action. Authorization, repository state, publication safety, and post-creation verification are mandatory boundaries.

## Hard boundaries

- Do not create a pull request without explicit authorization in the current request or applicable instructions.
- Treat a direct request such as “create the PR” or “open a PR” as authorization. Do not treat questions such as “can this become a PR?”, requests to draft or assess one, or discussion of this skill as authorization.
- Do not create from `main`, `master`, or the repository's default branch.
- Do not create a duplicate pull request for a head branch that already has an open pull request.
- Do not modify an existing pull request, request reviewers, apply labels, enable auto-merge, merge, close, or delete branches unless separately authorized.
- Do not make code changes, create commits, rewrite history, or perform unrelated cleanup. Report a blocker when the branch is not ready.
- Follow more specific repository and directory instructions over this skill.

## 1. Establish authorization and repository identity

1. Record the exact instruction that authorizes pull request creation.
2. Resolve the repository from the authenticated GitHub remote instead of assuming it from the working directory name.
3. Check `gh auth status`.
4. Resolve the repository's default branch, current local branch, configured upstream, base repository, and head repository.
5. Fetch the target base branch without changing tracked files.
6. Stop if the current branch is protected or if the intended base or head is ambiguous.

Do not use `gh pr create --dry-run` as a harmless preview; it may push the branch.

## 2. Check branch and duplicate state

Inspect `git status --short --branch`, commits in `base..HEAD`, the complete `base...HEAD` diff and diff stat, upstream divergence, and open pull requests for the exact head branch.

Require a non-empty base-to-head diff, no unresolved conflicts, no unexpected tracked or untracked task files, no unrelated changes, secrets, internal planning files, or generated artifacts, and no existing open pull request for the same head.

If an open pull request already exists, return its URL and stop without modifying it.

## 3. Verify the complete change

Read applicable guidance including `AGENTS.md`, contribution and release guidance, and pull request templates from the target base branch.

Run the repository-required checks for the affected scope. Reuse verification evidence only when it was produced for the exact current HEAD and remains applicable. Otherwise rerun the checks.

Do not create a normal review-ready pull request with failed required checks. Create a draft with incomplete verification only when the user explicitly requests that outcome.

Record exact commands, results, and material limitations for the pull request body.

## 4. Prepare the squash-compatible title

Treat the entire `base...HEAD` range as one prospective squash commit. The title must describe the aggregate change, not the latest commit.

Use this precedence:

1. Explicit repository pull request title rules
2. Installed `$commit` skill
3. Repository commit and recently merged pull request conventions
4. Clear imperative fallback title

When `$commit` is installed, invoke it in dry-run, subject-only mode with this contract:

> Analyze `base...HEAD` as one prospective squash commit. Detect and follow the repository convention. Return only the subject. Do not stage, commit, amend, or push anything.

If `$commit` cannot honor that range without mutation, use only its detected convention and compose the aggregate subject locally. Never use `gh pr create --fill` to derive a multi-commit squash title.

Require the title to follow the repository convention, summarize the complete pull request, use an imperative description, omit a trailing period, respect the repository's normal length, include ticket notation only when repository history or guidance supports it, and avoid claims not present in the final diff.

## 5. Prepare the reviewer-facing body

Use the pull request template from the target base branch when one applies. Fill every applicable section, remove unused placeholders, and preserve repository-required structure.

When no repository template applies, use:

```markdown
## Summary

- <reviewer-facing outcome and purpose>
- <major implementation or behavior change>

## Verification

- `<command>` — <result>
```

Add `Review focus`, `Risks and rollout`, `Screenshots`, or `Related issues` sections only when useful. Do not leave empty headings or ceremonial checklists.

Use an issue-closing keyword for a GitHub issue only when closing that GitHub issue on merge is explicitly intended. Do not treat external ticket identifiers as GitHub issues.

When the work is tracked by Multica, handle its merge-to-Done close intent separately:

- Verify the exact Multica identifier from explicit task context or a read-only tracker lookup. Never infer it from unrelated text.
- Add a standalone `Closes <identifier>` line to the pull request body only when this pull request fully delivers that ticket and merging it should move the ticket to `done`.
- Do not add close intent for a partial delivery, parent or umbrella ticket, or work with required follow-ups. Keep the identifier in the branch or title for linking, or use `Related to <identifier>` when useful.
- If completion intent is ambiguous or the tracker cannot be verified, omit close intent and report the ambiguity instead of guessing.

For configured Multica Git integration, the identifier must immediately follow `Closes`, `Fixes`, or `Resolves`; a branch or title reference links the pull request but does not complete the ticket.

## 6. Enforce the publication boundary

Treat every pull request title and body as a durable externally visible artifact regardless of repository visibility. Include only information needed by a reviewer to understand the change, verify it, and assess its risks.

Never include:

- credentials, tokens, passwords, cookies, private keys, authentication headers, or connection strings
- unnecessary names, email addresses, phone numbers, or other personal information
- local usernames, hostnames, home directories, machine identifiers, private IPs, internal DNS names, or machine-specific URLs
- absolute workspace, temporary, backup, credential, or secret-store paths
- `.internal/` content or private planning documents
- prompts, system instructions, private conversation, agent reasoning, tool transcripts, session identifiers, or token usage
- private repositories, ticket contents, logs, or documents the pull request audience cannot access; a bare external ticket identifier is allowed only when deliberately required for configured pull request linking or verified close intent
- abandoned approaches, intermediate mistakes, or user-agent negotiation unless the resulting design tradeoff remains relevant
- claims, files, behavior, or verification not supported by the final diff and actual evidence

Translate necessary internal context into reviewer-facing product rationale. Prefer repository-relative paths and stable environment descriptions.

For every sentence, confirm:

1. Does the reviewer need it?
2. Is it grounded in the final diff, actual verification, or shareable requirements?
3. Is every person who can read the pull request authorized to know it?
4. Is it acceptable as a permanent searchable record?

Run `scripts/check-pr-content.py` against the final title and body. Resolve every finding before creation. Never print a detected sensitive value while reporting a finding.

## 7. Push the exact head safely

Check again whether the branch has an open pull request immediately before pushing.

Push only when applicable instructions authorize it. Push explicitly with `git push`; do not let `gh pr create` implicitly push or create a fork. Verify that the remote head SHA exactly matches local `HEAD` before creating the pull request. Never force-push.

## 8. Create exactly one pull request

Write the final body to a permission-restricted temporary file and remove it after use.

Create the pull request with explicit `--repo`, `--base`, `--head`, `--title`, and `--body-file` values. Add `--draft` only when explicitly requested or explicitly authorized for incomplete work.

Do not infer labels, reviewers, assignees, milestones, projects, or auto-merge. Include an issue or ticket close intent only when it has been established under section 5.

## 9. Verify the published result

Read the created pull request back with `gh pr view` and verify the repository, base branch, head branch, head SHA, title, body, draft state, and URL.

If any value differs, do not silently edit or recreate the pull request. Report the discrepancy and request authorization for corrective action.

Synchronize an external tracker only when applicable instructions separately authorize or require it.

Return the pull request URL, title, base and head, verification summary, and any known limitation. Stop without monitoring CI, handling reviews, or merging.

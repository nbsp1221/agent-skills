---
name: reviewed-delete
description: Execute an already-decided filesystem deletion through an exact dry-run manifest, a separately approved recoverable staging move, independent verification, and a separately approved permanent purge or restore. Use only when the user explicitly invokes reviewed-delete after the deletion candidates have already been agreed. Do not use to discover or judge candidates, for ordinary development edits, or as an automatic response to general cleanup requests.
compatibility: Requires an agent host that can read Markdown, run the bundled Python helper, and present a complete user-visible approval message. The workflow is independent of any specific agent, UI, channel, or command name.
---

# Reviewed Delete

Act only as the execution protocol for an already-decided deletion list.
Do not select, expand, or reinterpret candidates.
Use Python 3.12+ and only `scripts/reviewed_delete.py` for every filesystem mutation after this skill is invoked.

## Host-neutral presentation contract

This skill is an Agent Skills-compatible procedure. The host may call it with a slash command, chat command, menu action, or another mechanism; the procedure must not assume a particular tool, channel, renderer, or terminal UI.

This portability model follows the open Agent Skills format (`https://agentskills.io/specification`), while keeping host-specific invocation as an adapter concern. The same separation is used by Claude Code's cross-tool Agent Skills documentation (`https://code.claude.com/docs/en/skills`).

Before each approval, put the complete approval record in the same user-visible message that asks for approval. The record must include the exact target paths, preserved paths, action, top-level count, recursive entry count, logical size, staging or purge state, manifest path, and full canonical manifest SHA-256. Never put required facts only in an intermediate/progress message, tool transcript, collapsed panel, or earlier turn and then ask “approve?” in a later message.

Use raw absolute paths in a fenced text or JSON block. Do not rely on link labels, table cells, “as above,” or hidden/collapsible output to expose a path. If the host has separate progress and final channels, repeat the complete approval record in the final channel. If visibility is uncertain, treat the report as incomplete and resend it before requesting approval.

Each approval authorizes exactly one action: staging, purge, or restore. State which action it authorizes and that the other actions are not authorized. Treat ambiguous or context-free affirmative replies as no approval.

### Host adapter examples (non-normative)

These examples explain how a host maps the portable rule; they do not make the procedure dependent on a host.

- Codex: `commentary` is progress-only and may be collapsed; the complete approval record and approval question belong in `final`.
- A tool with `progress` and `answer` fields: `progress` is optional status; repeat the complete record in `answer`.
- A single-message chat host: put the complete record and the one approval question in that same message.

Never write “approve?” in a user-visible final/answer field while leaving the target list, digest, or consequences only in commentary/progress/tool output.


## Do / don't / best practices

Do:

- freeze the exact candidate set before planning and show every top-level path;
- bind every approval to the helper-reported canonical manifest SHA-256;
- report recoverability and irreversible effects in plain language before asking;
- independently verify staging, then issue a new complete report before purge;
- retain the manifest and operation receipt until the terminal state is reviewed;
- repeat essential facts in the final user-visible response even when progress output already showed them.

Don't:

- select additional paths discovered during execution;
- use globs, implicit expansions, or commands that mutate outside the helper;
- assume the user can see tool output, intermediate messages, links, or a previous answer;
- combine staging and purge approval, or treat “delete it” from before staging as purge approval;
- ask for approval with a one-line question whose target, digest, or consequences are elsewhere;
- report completion from a lost stream without reconciling the helper's durable status.

## Non-negotiable boundaries

- Treat the exact top-level paths agreed immediately before invocation as the complete candidate set.
- Pass explicit absolute paths only.
- Quote every filesystem path as a separate shell argument.
- Never pass a glob, shell expansion, `find` result generated after approval, package-manager cleanup command, or newly discovered path.
- Never mutate candidates with `rm`, `rmdir`, `find -delete`, a package-manager cleanup command, a temporary deletion script, `shutil.rmtree`, `Path.unlink`, or any tool other than the bundled helper.
- Use read-only inspection freely before `plan`; candidate selection remains the agent/user's job.
- Obtain two fresh approvals.
- Approval to stage never authorizes purge.
- A deletion request made before staging never counts as permanent-purge approval.
- Bind each report and approval to the full helper-reported canonical manifest SHA-256.
- Treat this as a digest of canonical manifest data, not the bytewise hash of the pretty-printed file.
- Never replace or precheck it with `sha256sum` or another raw-file hashing command.
- Any candidate, manifest, count, byte total, staged entry, or recorded identity/metadata change invalidates the earlier approval and requires a new plan.
- Keep the manifest in a stable control location outside every target and retain it until the purge or restore result has been reviewed.
- Treat the helper-owned purge operation file and `status` reconciliation as authoritative when live terminal output is delayed or lost.
- Preserve every long-running execution session identifier and poll the same session until it exits; never discard session metadata while forwarding only stdout.
- Stop on every helper error.
- For partial or indeterminate results, inspect and report; never retry blindly.

The helper uses portable Python standard-library operations and never requests elevation.
It requires rename-only staging on one filesystem and never falls back to copy-and-delete.
It rejects mount boundaries inside deletion targets instead of traversing them.
On Linux it reads `/proc/self/mountinfo` without elevated privileges and fails closed if mount boundaries cannot be inspected.
It does not inspect processes, package state, ownership policy, or whether data is disposable.

## Workflow

### 1. Freeze the candidate set

State the exact paths and what must remain untouched.
Choose the narrowest stable absolute `--scope` directories implied by the agreed deletion.
Treat `--scope` as a safety boundary, not a convenience argument, and never widen it merely to make a target pass.
Every scope must strictly contain its targets.
Run:

```text
python scripts/reviewed_delete.py plan \
  --output ABSOLUTE_NEW_MANIFEST \
  --scope ABSOLUTE_SCOPE [--scope ...] \
  --expected-count N \
  [--staging-root ABSOLUTE_NEW_STAGING_ROOT] \
  -- ABSOLUTE_TARGET [ABSOLUTE_TARGET ...]
```

`--expected-count` must equal the already-decided top-level target count.
It detects expansions that change the expected argument count, but it cannot determine whether an already-expanded argument originated from a shell glob.
The helper rejects relative paths, roots, the home directory itself, overlap, scope escape, manifest/staging overlap, existing staging roots, mount boundaries, and detectable cross-filesystem moves.
Choose `ABSOLUTE_NEW_MANIFEST` in a stable control directory, not inside a temporary cleanup target or a location expected to disappear before status reconciliation is complete.

Inspect the manifest and every `PLAN_SOURCE_JSON` record.
Do not stage in the same turn.

### 2. Report and wait for stage approval

Show one unambiguous approval object.
List every unrelated top-level target separately and summarize only descendants of a listed directory.
Never use `/path/*` as a scope description.
Never interpolate filesystem paths as raw Markdown or place arbitrary paths directly in Markdown table cells.
Render targets, scopes, preserved paths, and the staging root as JSON string literals inside fenced JSON blocks so newlines, control characters, and table delimiters cannot alter the report structure.

Use a scalar summary table:

| Field | Required content |
|---|---|
| Deletion coverage | For each target directory, “directory itself and all descendants” |
| Top-level count | `TOP_LEVEL_COUNT` |
| Recursive entries | `TOTAL_ENTRIES` |
| Logical size | Human-readable `LOGICAL_BYTES` |
| Next action | Recoverable staging move; no permanent deletion |
| Manifest | Full helper-reported canonical `MANIFEST_SHA256` |

Follow it with one fenced JSON object containing `targets`, `safety_boundaries`, `preserved`, and `staging_root`.
Use the exact decoded values from the helper's `_JSON` outputs when available.

Ask whether to move exactly that manifest to recoverable staging.
Stop and wait.
Accept ordinary affirmative language only as approval for the single stage action immediately preceding it.

### 3. Stage and verify

After approval #1, pass the exact `STAGE_TOKEN` printed by `plan`:

```text
python scripts/reviewed_delete.py stage \
  --manifest ABSOLUTE_MANIFEST \
  --confirm-stage STAGE_TOKEN
```

Do not recompute the digest externally.
The `stage` command canonicalizes the current manifest and rejects it unless the approved token still matches.

Then run `verify` as a separate command:

```text
python scripts/reviewed_delete.py verify --manifest ABSOLUTE_MANIFEST
```

Successful standalone verification creates a helper-owned receipt with a random nonce.
Restore and purge tokens include that nonce; deriving a token from the manifest digest or skipping this command must fail.

Do not treat a successful stage as purge approval.
If stage or verify fails, read `references/status-contract.md`, preserve all evidence, and report the exact state.

### 4. Report and wait for a permanent-purge decision

Report the verified result with this scalar table:

| Field | Required content |
|---|---|
| Stage result | Completed and independently verified |
| Moved targets | Verified top-level count |
| Recursive entries | Verified total entries |
| Logical size | Verified logical bytes |
| Unexpected entries | None, or stop |
| Original locations | Expected sources absent |
| Current state | Recoverable |
| Manifest | Full helper-reported canonical SHA-256 |

Show original locations and the staging root in a separate fenced JSON object.
State that permanent deletion has not happened.
Ask only whether to permanently purge this exact verified manifest.
State that an ordinary affirmative reply authorizes only that purge and that the user can instead say `restore` to recover the targets.
Stop and wait for a new decision made after this report.
Treat an ambiguous response as no authorization.

### 5a. Restore

When the user explicitly chooses recovery, use the `RESTORE_TOKEN` from the successful verify:

```text
python scripts/reviewed_delete.py restore \
  --manifest ABSOLUTE_MANIFEST \
  --confirm-restore RESTORE_TOKEN
```

Report restored paths and wrapper-cleanup status.
The helper refuses restore when a source exists at the final pre-rename check.
A concurrent recreation between that check and `rename()` is outside the helper's guarantee.

### 5b. Permanently purge

Only a fresh affirmative response to the single post-verify purge question authorizes:

```text
python scripts/reviewed_delete.py purge \
  --manifest ABSOLUTE_MANIFEST \
  --confirm-purge PURGE_TOKEN
```

Start purge with a short initial yield so live output is returned promptly.
The helper emits flushed `PURGE_STARTED_JSON`, periodic `PURGE_PROGRESS_JSON`, and terminal `PURGE_RESULT_JSON` events.
During `PREFLIGHT`, `preflight_records_checked` and `preflight_top_level_checked` advance while `records_completed` remains zero; no irreversible deletion has begun.
Treat `records_completed` as removed manifest records only after the phase changes to `PURGING`.
If the execution tool returns a session identifier, preserve it and poll that exact session until the process exits while giving the user concise progress updates.
Never wrap a destructive command in orchestration that forwards only its current output and discards its session identifier or exit status.

The helper writes a durable operation file outside the staging root before irreversible mutation begins.
On successful completion it prints `OPERATION_JSON`; retain this small file as the terminal receipt.
Report `PURGE_COMPLETED=true` only when emitted by the helper or when the helper's `status` command independently reports `observed_status` as `SUCCEEDED`.
Treat wrapper cleanup separately from data purge.
On `PURGE_PARTIAL`, `PURGE_BLOCKED`, or `PURGE_INDETERMINATE`, follow `references/status-contract.md` and never reconstruct a deletion set from the remaining files.

If live output is lost, the process session disappears, or a connection closes before a terminal event, do not rerun purge.
Run the read-only reconciliation command:

```text
python scripts/reviewed_delete.py status --manifest ABSOLUTE_MANIFEST
```

Use `OPERATION_STATUS_JSON.observed_status` as the recovered result.
`SUCCEEDED` means all manifest records are absent from staging; `PARTIAL` means at least one reviewed identity was removed but the full set was not; `BLOCKED` means no reviewed identity was removed; `INDETERMINATE` means reconciliation could not establish a safe terminal state; and `RUNNING` means a fresh heartbeat still exists.

For an independently attached live view, run:

```text
python scripts/reviewed_delete.py watch \
  --manifest ABSOLUTE_MANIFEST \
  --interval 2
```

`watch` reads the durable operation file and exits when it reaches a terminal state or its heartbeat becomes stale, then prints a reconciled `OPERATION_STATUS_JSON`.

## Implementation boundary

The helper freezes a recursive identity/metadata snapshot, moves only manifest top-level paths by rename, never follows symlinks or Windows junctions, rejects mount boundaries, verifies the exact staged set, and purges only manifest records.
It protects against ordinary agent mistakes and filesystem drift, not a malicious same-user process racing the final OS operation, repeated termination signals, `SIGKILL`, power loss, kernel faults, or compromised Python.
It does not hash regular-file contents or record xattrs/ACLs; same-size content changes with a restored mtime and unrecorded metadata changes are outside its integrity claim.

Keep test harnesses, review notes, and generated bundles outside the deployable skill directory.

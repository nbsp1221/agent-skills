# Status contract

Read this reference after any stage, restore, purge, or wrapper-cleanup failure.

## Stage failure

If reconciliation confirms that every exact entry reached staging, the helper reports `STAGE_COMPLETED=true`; continue with standalone verify and do not rerun stage.
Otherwise, the helper attempts to roll moved entries back only when the original source is absent and the staged snapshot is unchanged.
Before each rollback rename, it refuses rollback when the source exists at the final pre-rename check.
A concurrent recreation between that check and `rename()` is outside the helper's guarantee.
For any result other than `STAGE_COMPLETED=true`, preserve the staging root, report every rollback detail contained in `ERROR_JSON`, and do not continue to verify or purge.

## Restore failure

- `RESTORE_BLOCKED=true`: reconciliation confirmed that no top-level entry was restored.
- `RESTORE_PARTIAL=true`: reconciliation confirmed that entries are split between original locations and staging.
- `RESTORE_INDETERMINATE=true`: reconciliation could not classify at least one entry as exact-restored or exact-staged.
- `RESTORE_COMPLETED=true` on an error path: reconciliation confirmed that all data was restored, but wrapper cleanup or final reporting did not finish.
- `RESTORE_RETRY=false`: inspect both original paths and the staging root; do not retry blindly.

`RESTORED_TOP_LEVEL`, `STILL_STAGED_TOP_LEVEL`, and `INDETERMINATE_TOP_LEVEL` report the reconciled top-level counts.
Restore refuses to proceed when a source exists at the final pre-rename check.
A concurrent recreation between that check and `rename()` is outside the helper's guarantee.
A partial restore can leave exact entries split between original locations and staging.
Missing or invalid standalone verification receipts block restore and purge before mutation.
A manifest digest alone is never a valid restore or purge token.

## Purge failure

- `PURGE_BLOCKED=true`: no reviewed identity was confirmed removed.
- `PURGE_PARTIAL=true`: irreversible removal of at least one reviewed identity was confirmed.
- `PURGE_INDETERMINATE=true`: the syscall outcome and subsequent reconciliation could not establish whether a reviewed identity was removed.
- `PURGE_COMPLETED=true` on an error path: reconciliation confirmed that every reviewed identity was removed, but wrapper cleanup or final reporting did not finish.
- `PURGE_RETRY=false`: inspect remaining staging state; never rerun purge from a freshly discovered list.

`PURGED_MUTATIONS` counts confirmed or reconciled removed manifest records.
`PURGED_TOP_LEVEL` counts fully completed top-level entries.
`CURRENT_ENTRY_JSON` identifies the entry being processed.

## Lost purge output or execution session

Purge creates an atomic operation file outside the staging root before irreversible mutation begins.
Live `PURGE_STARTED_JSON`, `PURGE_PROGRESS_JSON`, and `PURGE_RESULT_JSON` events are observable hints; the operation file plus filesystem reconciliation is the recoverable source of truth.
`PREFLIGHT` progress reports checked records separately and keeps `records_completed=0`; `PURGING` is the first phase in which `records_completed` can represent irreversible removals.
Both phases refresh the durable heartbeat during long tree walks.

If the terminal connection, tool session, or final stdout is lost, never rerun purge and never infer completion from process listings or free-space changes alone.
Run `status --manifest ABSOLUTE_MANIFEST` and use `OPERATION_STATUS_JSON.observed_status`:

- `RUNNING`: a non-stale heartbeat exists; keep polling the original session or use `watch`.
- `SUCCEEDED`: reconciliation confirms every reviewed manifest identity is absent from staging.
- `PARTIAL`: reconciliation confirms at least one reviewed identity was removed but the full manifest was not.
- `BLOCKED`: no reviewed identity was removed and the durable operation ended blocked.
- `INDETERMINATE`: the operation is stale or reconciliation cannot classify the remaining state.
- `NOT_STARTED`: no durable purge operation exists for this manifest.

The operation file remains after successful staging-wrapper cleanup, so a missing staging root is no longer the only completion evidence.
Preserve the manifest and operation file until the result has been reviewed.

## Wrapper cleanup

`STAGING_CLEANUP_COMPLETE=false` does not reverse a completed restore or purge.
The helper refuses to clean a wrapper containing unexpected items.
Inspect it manually; never treat an old wrapper as a new staging destination.

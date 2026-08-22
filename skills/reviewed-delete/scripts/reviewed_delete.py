#!/usr/bin/env python3
"""Manifest-bound reviewed deletion with reversible staging."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import signal
import stat
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict, cast


SCHEMA_VERSION = 1
OPERATION_SCHEMA_VERSION = 1
MARKER_NAME = ".reviewed-delete-manifest-sha256"
RECEIPT_NAME = ".reviewed-delete-verified.json"
PAYLOAD_NAME = "payload"
SAFE_NAME_LIMIT = 80
OPERATION_PREFIX = ".reviewed-delete-operation-"
PROGRESS_RECORD_INTERVAL = 10_000
PROGRESS_TIME_INTERVAL_SECONDS = 2.0
STALE_HEARTBEAT_SECONDS = 30.0

if sys.version_info < (3, 12):
    raise SystemExit("ERROR: Python 3.12 or newer is required")


class GateError(Exception):
    """A fail-closed protocol or filesystem error."""


class MutationFailure(GateError):
    def __init__(self, message: str, state: "MutationState") -> None:
        super().__init__(message)
        self.state = state


class TerminationRequested(BaseException):
    """A catchable process-termination request during a guarded operation."""

    def __init__(self, signum: int) -> None:
        self.signum = signum
        try:
            name = signal.Signals(signum).name
        except ValueError:
            name = str(signum)
        super().__init__(f"termination requested by {name}")


type OperationStatus = Literal[
    "RUNNING",
    "BLOCKED",
    "PARTIAL",
    "INDETERMINATE",
    "SUCCEEDED",
]
type TerminalOperationStatus = Literal[
    "BLOCKED",
    "PARTIAL",
    "INDETERMINATE",
    "SUCCEEDED",
]
type OperationPhase = Literal["PREFLIGHT", "PURGING", "TERMINAL"]
type ObservedOperationStatus = Literal[
    "NOT_STARTED",
    "RUNNING",
    "BLOCKED",
    "PARTIAL",
    "INDETERMINATE",
    "SUCCEEDED",
]


class OperationProgress(TypedDict):
    records_completed: int
    records_total: int
    top_level_completed: int
    top_level_total: int
    current_entry: str | None
    preflight_records_checked: NotRequired[int]
    preflight_records_total: NotRequired[int]
    preflight_top_level_checked: NotRequired[int]
    preflight_top_level_total: NotRequired[int]


class OperationConditions(TypedDict):
    data_purged: bool
    wrapper_cleaned: bool


class OperationData(TypedDict):
    schema_version: int
    operation_id: str
    kind: Literal["purge"]
    manifest_path: str
    manifest_sha256: str
    status: OperationStatus
    phase: OperationPhase
    started_at: str
    updated_at: str
    heartbeat_at: str
    ended_at: str | None
    progress: OperationProgress
    conditions: OperationConditions
    error: str | None


@dataclass
class MutationState:
    completed: int = 0
    uncertain: bool = False
    on_completed: Callable[[int], None] | None = None

    def record_completion(self) -> None:
        self.completed += 1
        if self.on_completed is not None:
            self.on_completed(self.completed)

    def unlink(self, path: Path) -> None:
        try:
            os.unlink(path)
        except BaseException:
            self.uncertain = True
            raise
        self.record_completion()

    def rmdir(self, path: Path) -> None:
        try:
            os.rmdir(path)
        except BaseException:
            self.uncertain = True
            raise
        self.record_completion()


def fail(message: str) -> None:
    raise GateError(message)


def lexical_absolute(raw: str, label: str) -> Path:
    if not raw:
        fail(f"empty {label} path is not allowed")
    path = Path(raw)
    if not path.is_absolute():
        fail(f"{label} path must be absolute: {raw!r}")
    return Path(os.path.abspath(os.fspath(path)))


def lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def lstat(path: Path, label: str = "path") -> os.stat_result:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        fail(f"{label} is missing: {path}")
    except OSError as exc:
        fail(f"cannot inspect {label} {path}: {exc}")


def link_kind(path: Path, current: os.stat_result | None = None) -> str | None:
    current = current if current is not None else lstat(path)
    if stat.S_ISLNK(current.st_mode) or os.path.islink(path):
        return "symlink"
    try:
        return "junction" if os.path.isjunction(path) else None
    except OSError as exc:
        fail(f"cannot inspect junction state for {path}: {exc}")


def is_link_like(path: Path, current: os.stat_result | None = None) -> bool:
    return link_kind(path, current) is not None


def decode_mountinfo_path(value: bytes) -> Path:
    decoded = re.sub(
        rb"\\([0-7]{3})",
        lambda match: bytes((int(match.group(1), 8),)),
        value,
    )
    return Path(os.fsdecode(decoded))


def linux_mount_targets() -> list[Path]:
    mountinfo = Path("/proc/self/mountinfo")
    try:
        lines = mountinfo.read_bytes().splitlines()
    except OSError as exc:
        fail(f"cannot inspect Linux mount boundaries via {mountinfo}: {exc}")
    result: list[Path] = []
    for line in lines:
        fields = line.split(b" ")
        if len(fields) < 5:
            fail("Linux mountinfo contains a malformed record")
        target = decode_mountinfo_path(fields[4])
        if target.is_absolute():
            result.append(Path(os.path.abspath(os.fspath(target))))
    return result


def reject_mount_boundaries(path: Path) -> None:
    current = lstat(path)
    if is_link_like(path, current) or not stat.S_ISDIR(current.st_mode):
        return
    if sys.platform.startswith("linux"):
        for target in linux_mount_targets():
            if target == path or is_within(target, path, strict=True):
                fail(f"mount boundary is not allowed in a deletion target: {target}")
        return

    pending = [path]
    while pending:
        current_path = pending.pop()
        current_stat = lstat(current_path)
        if is_link_like(current_path, current_stat):
            continue
        if not stat.S_ISDIR(current_stat.st_mode):
            continue
        try:
            if os.path.ismount(current_path):
                fail(f"mount boundary is not allowed in a deletion target: {current_path}")
            with os.scandir(current_path) as iterator:
                children = [current_path / entry.name for entry in iterator]
        except OSError as exc:
            fail(f"cannot inspect mount boundaries below {current_path}: {exc}")
        pending.extend(children)


def canonical_existing(raw: str, label: str = "source") -> Path:
    lexical = lexical_absolute(raw, label)
    current = lstat(lexical, label)
    try:
        if is_link_like(lexical, current):
            result = lexical.parent.resolve(strict=True) / lexical.name
        else:
            result = lexical.resolve(strict=True)
    except OSError as exc:
        fail(f"cannot canonicalize {label} {lexical}: {exc}")
    reject_root_or_home(result, label)
    return result


def canonical_directory(raw: str, label: str) -> Path:
    lexical = lexical_absolute(raw, label)
    try:
        result = lexical.resolve(strict=True)
    except OSError as exc:
        fail(f"cannot canonicalize {label} {lexical}: {exc}")
    if not result.is_dir() or is_link_like(result):
        fail(f"{label} must be a real directory: {result}")
    if result == Path(result.anchor):
        fail(f"filesystem root cannot be a {label}: {result}")
    return result


def canonical_new_path(raw: str, label: str) -> Path:
    lexical = lexical_absolute(raw, label)
    try:
        parent = lexical.parent.resolve(strict=True)
    except OSError as exc:
        fail(f"cannot canonicalize {label} parent {lexical.parent}: {exc}")
    if not parent.is_dir() or is_link_like(parent):
        fail(f"{label} parent must be a real directory: {parent}")
    result = parent / lexical.name
    if lexists(result):
        fail(f"{label} must not already exist: {result}")
    return result


def canonical_manifest(raw: str) -> Path:
    lexical = lexical_absolute(raw, "manifest")
    current = lstat(lexical, "manifest")
    if is_link_like(lexical, current) or not stat.S_ISREG(current.st_mode):
        fail(f"manifest must be a regular non-link file: {lexical}")
    try:
        return lexical.resolve(strict=True)
    except OSError as exc:
        fail(f"cannot canonicalize manifest {lexical}: {exc}")


def reject_root_or_home(path: Path, label: str) -> None:
    if path == Path(path.anchor):
        fail(f"filesystem root is not an allowed {label}: {path}")
    try:
        home = Path.home().resolve(strict=True)
    except OSError:
        home = Path.home().absolute()
    if path == home:
        fail(f"the user home directory itself is not an allowed {label}: {path}")


def is_within(path: Path, parent: Path, *, strict: bool = False) -> bool:
    if strict and path == parent:
        return False
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def require_scope(path: Path, scopes: list[Path]) -> None:
    if not any(is_within(path, scope, strict=True) for scope in scopes):
        fail(f"path is outside every approved scope: {path}")


def reject_overlaps(paths: list[Path]) -> None:
    ordered = sorted(paths, key=lambda item: (len(item.parts), os.path.normcase(str(item))))
    for index, path in enumerate(ordered):
        for other in ordered[index + 1 :]:
            if path == other or is_within(other, path, strict=True):
                fail(f"duplicate or overlapping targets: {path} and {other}")


def device(path: Path) -> int:
    try:
        value = getattr(os.stat(path, follow_symlinks=False), "st_dev", None)
    except OSError as exc:
        fail(f"cannot determine filesystem device for {path}: {exc}")
    if not isinstance(value, int):
        fail(f"filesystem device is unavailable for {path}")
    return value


def same_filesystem(left: Path, right: Path) -> bool:
    return device(left) == device(right)


def node_kind(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISBLK(mode):
        return "block-device"
    if stat.S_ISCHR(mode):
        return "character-device"
    return "other"


def record(path: Path, relative: str) -> dict[str, Any]:
    current = lstat(path)
    special = link_kind(path, current)
    item: dict[str, Any] = {
        "relative": relative,
        "kind": special or node_kind(current.st_mode),
        "device": int(getattr(current, "st_dev", 0)),
        "inode": int(getattr(current, "st_ino", 0)),
        "mode": int(stat.S_IMODE(current.st_mode)),
        "size": int(current.st_size),
        "mtime_ns": int(getattr(current, "st_mtime_ns", 0)),
        "nlink": int(getattr(current, "st_nlink", 0)),
    }
    if item["kind"] in ("symlink", "junction"):
        try:
            item["target"] = os.readlink(path)
        except OSError as exc:
            fail(f"cannot read link-like target {path}: {exc}")
    return item


def snapshot(
    path: Path,
    *,
    on_visited: Callable[[int], None] | None = None,
) -> list[dict[str, Any]]:
    reject_mount_boundaries(path)
    result: list[dict[str, Any]] = []
    pending: list[tuple[Path, str]] = [(path, ".")]
    while pending:
        current, relative = pending.pop()
        item = record(current, relative)
        result.append(item)
        if on_visited is not None:
            on_visited(len(result))
        if item["kind"] != "directory":
            continue
        try:
            with os.scandir(current) as iterator:
                names = sorted(entry.name for entry in iterator)
        except OSError as exc:
            fail(f"cannot scan directory {current}: {exc}")
        for name in reversed(names):
            child_relative = name if relative == "." else f"{relative}/{name}"
            pending.append((current / name, child_relative))
    return result


def tree_metrics(tree: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "entries": len(tree),
        "logical_bytes": sum(
            int(item["size"]) for item in tree if item["kind"] == "file"
        ),
    }


def totals(entries: list[dict[str, Any]]) -> dict[str, int]:
    result = {"entries": 0, "logical_bytes": 0}
    for entry in entries:
        metrics = tree_metrics(entry["tree"])
        result["entries"] += metrics["entries"]
        result["logical_bytes"] += metrics["logical_bytes"]
    return result


def json_text(
    data: Any,
    *,
    indent: int | None = None,
    separators: tuple[str, str] | None = None,
) -> str:
    options: dict[str, Any] = {"sort_keys": True, "ensure_ascii": False}
    if indent is not None:
        options["indent"] = indent
    if separators is not None:
        options["separators"] = separators
    rendered = json.dumps(data, **options)
    try:
        rendered.encode("utf-8")
    except UnicodeEncodeError:
        options["ensure_ascii"] = True
        rendered = json.dumps(data, **options)
    return rendered


def manifest_digest(data: dict[str, Any]) -> str:
    canonical = json_text(data, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def write_manifest(path: Path, data: dict[str, Any]) -> str:
    rendered = json_text(data, indent=2) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
    except OSError as exc:
        fail(f"cannot create manifest {path}: {exc}")
    return manifest_digest(data)


def read_manifest(path: Path) -> tuple[dict[str, Any], str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read manifest {path}: {exc}")
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        fail("unsupported or malformed manifest schema")
    if not isinstance(data.get("entries"), list) or not data["entries"]:
        fail("manifest has no entries")
    return data, manifest_digest(data)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def parse_utc(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.timestamp()


def emit_event(label: str, data: dict[str, Any]) -> None:
    print(f"{label}_JSON={json_text(data, separators=(',', ':'))}", file=sys.stderr, flush=True)


def fsync_parent(path: Path) -> None:
    try:
        descriptor = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    rendered = json_text(data, indent=2) + "\n"
    temporary = path.parent / f".reviewed-delete-operation-tmp-{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            if handle.write(rendered) != len(rendered):
                fail(f"short write while updating operation state {path}")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_parent(path)
    except OSError as exc:
        fail(f"cannot update operation state {path}: {exc}")
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        except OSError:
            pass


def operation_path(qroot: Path, digest: str) -> Path:
    return qroot.parent / f"{OPERATION_PREFIX}{digest}.json"


def operation_lock_path(qroot: Path, digest: str) -> Path:
    return qroot.parent / f"{OPERATION_PREFIX}{digest}.lock"


def operation_integer(data: dict[str, Any], key: str, label: str) -> int:
    value = data.get(key)
    if type(value) is not int or value < 0:
        fail(f"operation state has invalid {label} {key}")
    return value


def validate_operation_progress(value: Any) -> OperationProgress:
    if not isinstance(value, dict):
        fail("operation state has invalid progress")
    progress = cast(dict[str, Any], value)
    records_completed = operation_integer(progress, "records_completed", "progress")
    records_total = operation_integer(progress, "records_total", "progress")
    top_level_completed = operation_integer(
        progress, "top_level_completed", "progress"
    )
    top_level_total = operation_integer(progress, "top_level_total", "progress")
    if records_completed > records_total or top_level_completed > top_level_total:
        fail("operation progress exceeds its recorded totals")
    current_entry = progress.get("current_entry")
    if current_entry is not None and not isinstance(current_entry, str):
        fail("operation state has invalid progress current_entry")

    preflight_keys = {
        "preflight_records_checked",
        "preflight_records_total",
        "preflight_top_level_checked",
        "preflight_top_level_total",
    }
    present_preflight_keys = preflight_keys.intersection(progress)
    if present_preflight_keys and present_preflight_keys != preflight_keys:
        fail("operation state has incomplete preflight progress")
    if present_preflight_keys:
        preflight_records_checked = operation_integer(
            progress, "preflight_records_checked", "preflight progress"
        )
        preflight_records_total = operation_integer(
            progress, "preflight_records_total", "preflight progress"
        )
        preflight_top_level_checked = operation_integer(
            progress, "preflight_top_level_checked", "preflight progress"
        )
        preflight_top_level_total = operation_integer(
            progress, "preflight_top_level_total", "preflight progress"
        )
        if (
            preflight_records_checked > preflight_records_total
            or preflight_top_level_checked > preflight_top_level_total
        ):
            fail("operation preflight progress exceeds its recorded totals")
    return cast(OperationProgress, progress)


def validate_operation_conditions(value: Any) -> OperationConditions:
    if not isinstance(value, dict):
        fail("operation state has invalid conditions")
    conditions = cast(dict[str, Any], value)
    if set(conditions) != {"data_purged", "wrapper_cleaned"} or any(
        type(conditions[key]) is not bool
        for key in ("data_purged", "wrapper_cleaned")
    ):
        fail("operation state has invalid conditions")
    return cast(OperationConditions, conditions)


def validate_operation_data(data: Any, digest: str) -> OperationData:
    if not isinstance(data, dict) or data.get("schema_version") != OPERATION_SCHEMA_VERSION:
        fail("unsupported or malformed operation state schema")
    if data.get("manifest_sha256") != digest or data.get("kind") != "purge":
        fail("operation state does not match the purge manifest")
    for key in ("operation_id", "manifest_path"):
        if not isinstance(data.get(key), str) or not data[key]:
            fail(f"operation state has no valid {key}")

    status = data.get("status")
    phase = data.get("phase")
    valid_statuses = {"RUNNING", "BLOCKED", "PARTIAL", "INDETERMINATE", "SUCCEEDED"}
    valid_phases = {"PREFLIGHT", "PURGING", "TERMINAL"}
    if status not in valid_statuses or phase not in valid_phases:
        fail("operation state has invalid status or phase")
    if (status == "RUNNING") != (phase != "TERMINAL"):
        fail("operation status and phase are inconsistent")

    for key in ("started_at", "updated_at", "heartbeat_at"):
        if parse_utc(data.get(key)) is None:
            fail(f"operation state has invalid {key}")
    ended_at = data.get("ended_at")
    if status == "RUNNING":
        if ended_at is not None:
            fail("running operation state has an end timestamp")
    elif parse_utc(ended_at) is None:
        fail("terminal operation state has no valid end timestamp")

    validate_operation_progress(data.get("progress"))
    validate_operation_conditions(data.get("conditions"))
    if data.get("error") is not None and not isinstance(data["error"], str):
        fail("operation state has invalid error detail")
    return cast(OperationData, data)


def read_operation(path: Path, digest: str) -> OperationData | None:
    if not lexists(path):
        return None
    if not path.is_file() or path.is_symlink():
        fail(f"operation state is not a regular non-link file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read operation state {path}: {exc}")
    return validate_operation_data(data, digest)


class PurgeOperation:
    def __init__(
        self,
        path: Path,
        lock_path: Path,
        data: OperationData,
    ) -> None:
        self.path = path
        self.lock_path = lock_path
        self.data = data
        self.last_written_work_units = 0
        self.last_written_phase: OperationPhase = "PREFLIGHT"
        self.last_written_monotonic = time.monotonic()

    @classmethod
    def start(
        cls,
        manifest_path: Path,
        qroot: Path,
        digest: str,
        totals_data: dict[str, int],
        top_level_total: int,
    ) -> "PurgeOperation":
        path = operation_path(qroot, digest)
        lock_path = operation_lock_path(qroot, digest)
        if lexists(path) or lexists(lock_path):
            fail(
                "a purge operation already exists for this manifest; "
                f"inspect it with status: {path}"
            )
        try:
            lock_path.mkdir(mode=0o700)
        except OSError as exc:
            fail(f"cannot acquire purge operation lock {lock_path}: {exc}")
        now = utc_now()
        data: OperationData = {
            "schema_version": OPERATION_SCHEMA_VERSION,
            "operation_id": str(uuid.uuid4()),
            "kind": "purge",
            "manifest_path": str(manifest_path),
            "manifest_sha256": digest,
            "status": "RUNNING",
            "phase": "PREFLIGHT",
            "started_at": now,
            "updated_at": now,
            "heartbeat_at": now,
            "ended_at": None,
            "progress": {
                "records_completed": 0,
                "records_total": totals_data["entries"],
                "top_level_completed": 0,
                "top_level_total": top_level_total,
                "current_entry": None,
                "preflight_records_checked": 0,
                "preflight_records_total": totals_data["entries"] * 2,
                "preflight_top_level_checked": 0,
                "preflight_top_level_total": top_level_total * 2,
            },
            "conditions": {
                "data_purged": False,
                "wrapper_cleaned": False,
            },
            "error": None,
        }
        operation = cls(path, lock_path, data)
        try:
            atomic_write_json(path, data)
        except BaseException:
            try:
                os.rmdir(lock_path)
            except OSError:
                pass
            raise
        emit_event(
            "PURGE_STARTED",
            {
                "operation_id": data["operation_id"],
                "operation_path": str(path),
                "manifest_sha256": digest,
                "phase": "PREFLIGHT",
                "records_total": totals_data["entries"],
                "top_level_total": top_level_total,
            },
        )
        return operation

    def _checkpoint_due(
        self,
        *,
        phase: OperationPhase,
        work_units: int,
        force: bool,
    ) -> tuple[bool, float]:
        now_monotonic = time.monotonic()
        if force or phase != self.last_written_phase:
            return True, now_monotonic
        work_delta = work_units - self.last_written_work_units
        time_delta = now_monotonic - self.last_written_monotonic
        return (
            work_delta >= PROGRESS_RECORD_INTERVAL
            or time_delta >= PROGRESS_TIME_INTERVAL_SECONDS
        ), now_monotonic

    def _write_checkpoint(
        self,
        *,
        phase: OperationPhase,
        work_units: int,
        progress: OperationProgress,
        force: bool,
    ) -> None:
        due, now_monotonic = self._checkpoint_due(
            phase=phase,
            work_units=work_units,
            force=force,
        )
        if not due:
            return
        now = utc_now()
        self.data["phase"] = phase
        self.data["updated_at"] = now
        self.data["heartbeat_at"] = now
        self.data["progress"] = progress
        atomic_write_json(self.path, self.data)
        self.last_written_work_units = work_units
        self.last_written_phase = phase
        self.last_written_monotonic = now_monotonic
        emit_event(
            "PURGE_PROGRESS",
            {
                "operation_id": self.data["operation_id"],
                "phase": phase,
                **progress,
            },
        )

    def preflight_checkpoint(
        self,
        *,
        records_checked: int,
        top_level_checked: int,
        current_entry: str | None,
        force: bool = False,
    ) -> None:
        progress: OperationProgress = {
            **self.data["progress"],
            "preflight_records_checked": records_checked,
            "preflight_top_level_checked": top_level_checked,
            "current_entry": current_entry,
        }
        self._write_checkpoint(
            phase="PREFLIGHT",
            work_units=records_checked,
            progress=progress,
            force=force,
        )

    def checkpoint(
        self,
        *,
        records_completed: int,
        top_level_completed: int,
        current_entry: str | None,
        force: bool = False,
    ) -> None:
        progress: OperationProgress = {
            **self.data["progress"],
            "records_completed": records_completed,
            "top_level_completed": top_level_completed,
            "current_entry": current_entry,
        }
        self._write_checkpoint(
            phase="PURGING",
            work_units=records_completed,
            progress=progress,
            force=force,
        )

    def finish(
        self,
        *,
        status: TerminalOperationStatus,
        records_completed: int,
        top_level_completed: int,
        current_entry: str | None,
        data_purged: bool,
        wrapper_cleaned: bool,
        error: str | None,
    ) -> None:
        now = utc_now()
        self.data["status"] = status
        self.data["phase"] = "TERMINAL"
        self.data["updated_at"] = now
        self.data["heartbeat_at"] = now
        self.data["ended_at"] = now
        self.data["progress"] = {
            **self.data["progress"],
            "records_completed": records_completed,
            "top_level_completed": top_level_completed,
            "current_entry": current_entry,
        }
        self.data["conditions"] = {
            "data_purged": data_purged,
            "wrapper_cleaned": wrapper_cleaned,
        }
        self.data["error"] = error
        atomic_write_json(self.path, self.data)
        emit_event(
            "PURGE_RESULT",
            {
                "operation_id": self.data["operation_id"],
                "status": status,
                "records_completed": records_completed,
                "records_total": self.data["progress"]["records_total"],
                "top_level_completed": top_level_completed,
                "top_level_total": self.data["progress"]["top_level_total"],
                "data_purged": data_purged,
                "wrapper_cleaned": wrapper_cleaned,
                "error": error,
            },
        )
        try:
            os.rmdir(self.lock_path)
        except OSError:
            pass


def identity_record(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    current = record(path, str(expected["relative"]))
    for field in ("kind", "device", "inode"):
        if current[field] != expected[field]:
            fail(f"identity changed at {path}: {field}")
    if current["kind"] in ("symlink", "junction"):
        if current.get("target") != expected.get("target"):
            fail(f"link-like target changed: {path}")
    return current


def records_match(
    current: dict[str, Any], expected: dict[str, Any], *, ignore_nlink: bool
) -> bool:
    if ignore_nlink:
        current = {key: value for key, value in current.items() if key != "nlink"}
        expected = {key: value for key, value in expected.items() if key != "nlink"}
    return current == expected


def scope_records(scopes: list[Path]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for scope in scopes:
        current = lstat(scope, "scope")
        result.append(
            {
                "path": str(scope),
                "device": int(getattr(current, "st_dev", 0)),
                "inode": int(getattr(current, "st_ino", 0)),
            }
        )
    return result


def directory_record(path: Path) -> dict[str, Any]:
    current = lstat(path, "directory")
    return {
        "path": str(path),
        "device": int(getattr(current, "st_dev", 0)),
        "inode": int(getattr(current, "st_ino", 0)),
    }


def validate_directory_record(
    item: Any, label: str, *, expected_path: Path | None = None
) -> Path:
    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
        fail(f"manifest has no valid {label} record")
    path = canonical_directory(item["path"], label)
    if str(path) != item["path"]:
        fail(f"{label} canonical path changed: {item['path']} -> {path}")
    if expected_path is not None and path != expected_path:
        fail(f"{label} path does not match source parent: {path} != {expected_path}")
    current = lstat(path, label)
    if int(getattr(current, "st_dev", 0)) != int(item.get("device", -1)):
        fail(f"{label} device changed: {path}")
    if int(getattr(current, "st_ino", 0)) != int(item.get("inode", -1)):
        fail(f"{label} identity changed: {path}")
    return path


def validate_scope_records(data: dict[str, Any]) -> list[Path]:
    items = data.get("scopes")
    if not isinstance(items, list) or not items:
        fail("manifest has no scopes")
    scopes: list[Path] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            fail("manifest has a malformed scope record")
        scope = canonical_directory(item["path"], "scope")
        if str(scope) != item["path"]:
            fail(f"scope canonical path changed: {item['path']} -> {scope}")
        current = lstat(scope, "scope")
        if int(getattr(current, "st_dev", 0)) != int(item.get("device", -1)):
            fail(f"scope device changed: {scope}")
        if int(getattr(current, "st_ino", 0)) != int(item.get("inode", -1)):
            fail(f"scope identity changed: {scope}")
        scopes.append(scope)
    return scopes


RECORD_KINDS = {
    "file",
    "directory",
    "symlink",
    "junction",
    "fifo",
    "socket",
    "block-device",
    "character-device",
    "other",
}


def tree_index(tree: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not isinstance(tree, list) or not tree:
        fail("manifest tree is empty or malformed")
    result: dict[str, dict[str, Any]] = {}
    for item in tree:
        if not isinstance(item, dict):
            fail("manifest tree contains a malformed record")
        required = ("relative", "kind", "device", "inode", "mode", "size", "mtime_ns", "nlink")
        if any(field not in item for field in required):
            fail("manifest tree record is missing a required field")
        relative = item["relative"]
        if not isinstance(relative, str) or not relative:
            fail("manifest tree contains an invalid relative path")
        if relative != ".":
            parts = relative.split("/")
            if any(not part or part in (".", "..") for part in parts):
                fail(f"manifest tree contains an unsafe relative path: {relative!r}")
        if relative in result:
            fail(f"manifest tree contains a duplicate relative path: {relative!r}")
        if not isinstance(item["kind"], str) or item["kind"] not in RECORD_KINDS:
            fail(f"manifest tree contains an invalid kind: {item['kind']!r}")
        for field in ("device", "inode", "mode", "size", "mtime_ns", "nlink"):
            if not isinstance(item[field], int):
                fail(f"manifest tree field {field} must be an integer")
        if item["kind"] in ("symlink", "junction") and not isinstance(item.get("target"), str):
            fail("link-like manifest record has no string target")
        result[relative] = item
    if "." not in result:
        fail("manifest tree has no root record")
    for relative in result:
        if relative == ".":
            continue
        parent = relative.rpartition("/")[0] or "."
        parent_item = result.get(parent)
        if parent_item is None or parent_item["kind"] != "directory":
            fail(f"manifest tree has a disconnected entry: {relative!r}")
    return result


def children_by_parent(
    index: dict[str, dict[str, Any]],
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for relative in index:
        if relative == ".":
            continue
        parent, _, name = relative.rpartition("/")
        result.setdefault(parent or ".", set()).add(name)
    return result


def qroot_from(data: dict[str, Any]) -> Path:
    raw = data.get("staging_root")
    if not isinstance(raw, str):
        fail("manifest has no staging root")
    qroot = lexical_absolute(raw, "staging root")
    try:
        canonical = qroot.resolve(strict=False)
    except OSError as exc:
        fail(f"cannot canonicalize staging root {qroot}: {exc}")
    if canonical != qroot:
        fail(f"staging root canonical path changed: {qroot} -> {canonical}")
    reject_root_or_home(qroot, "staging root")
    return qroot


def validate_manifest_shape(
    manifest_path: Path, data: dict[str, Any]
) -> tuple[Path, list[dict[str, Any]], list[Path]]:
    qroot = qroot_from(data)
    scopes = validate_scope_records(data)
    entries = data["entries"]
    sources: list[Path] = []
    destinations: list[Path] = []
    payload = qroot / PAYLOAD_NAME
    for entry in entries:
        if not isinstance(entry, dict):
            fail("manifest contains a malformed entry")
        source_raw = entry.get("source")
        destination_raw = entry.get("destination")
        tree = entry.get("tree")
        if not isinstance(source_raw, str) or not isinstance(destination_raw, str):
            fail("manifest entry contains an invalid path")
        source = lexical_absolute(source_raw, "source")
        destination = lexical_absolute(destination_raw, "destination")
        if str(source) != source_raw or str(destination) != destination_raw:
            fail("manifest contains a non-canonical path")
        reject_root_or_home(source, "source")
        require_scope(source, scopes)
        if destination.parent != payload:
            fail(f"destination is not a direct staging payload entry: {destination}")
        if not is_within(destination, payload, strict=True):
            fail(f"destination escapes staging payload: {destination}")
        if is_within(manifest_path, source) or is_within(manifest_path, destination):
            fail("manifest overlaps a source or staging entry")
        if qroot == source or is_within(qroot, source) or is_within(source, qroot):
            fail(f"staging root overlaps source: {qroot} and {source}")
        validate_directory_record(
            entry.get("source_parent"), "source parent", expected_path=source.parent
        )
        tree_index(tree)
        if entry.get("metrics") != tree_metrics(tree):
            fail(f"entry metrics do not match tree: {source}")
        sources.append(source)
        destinations.append(destination)
    reject_overlaps(sources)
    normalized_destinations = {os.path.normcase(str(path)) for path in destinations}
    if len(normalized_destinations) != len(destinations):
        fail("manifest contains duplicate staging destinations")
    expected_totals = totals(entries)
    if data.get("totals") != expected_totals:
        fail(f"manifest totals are inconsistent; expected {expected_totals}")
    parent_record = data.get("staging_parent")
    if not isinstance(parent_record, dict) or not isinstance(parent_record.get("path"), str):
        fail("manifest has no staging parent record")
    qparent = canonical_directory(parent_record["path"], "staging parent")
    if qparent != qroot.parent or str(qparent) != parent_record["path"]:
        fail("staging parent canonical path changed")
    current = lstat(qparent, "staging parent")
    if int(getattr(current, "st_dev", 0)) != int(parent_record.get("device", -1)):
        fail(f"staging parent device changed: {qparent}")
    if int(getattr(current, "st_ino", 0)) != int(parent_record.get("inode", -1)):
        fail(f"staging parent identity changed: {qparent}")
    return qroot, entries, scopes


def validate_source(entry: dict[str, Any], scopes: list[Path]) -> None:
    source = Path(entry["source"])
    current = canonical_existing(str(source), "source")
    if current != source:
        fail(f"source canonical path changed: {source} -> {current}")
    require_scope(source, scopes)
    if snapshot(source) != entry["tree"]:
        fail(f"source changed since plan: {source}")


def destination_name(index: int, source: Path) -> str:
    digest = hashlib.sha256(os.fsencode(os.fspath(source))).hexdigest()[:16]
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", source.name).strip("._") or "entry"
    safe = safe[:SAFE_NAME_LIMIT]
    return f"{index:06d}-{safe}-{digest}"


def default_staging_root(first_source: Path) -> Path:
    return first_source.parent / f".reviewed-delete-{uuid.uuid4().hex}"


def command_plan(args: argparse.Namespace) -> None:
    if args.expected_count != len(args.paths):
        fail(
            "explicit path count differs from --expected-count; "
            "possible shell expansion or candidate drift"
        )
    sources = [canonical_existing(raw) for raw in args.paths]
    reject_overlaps(sources)
    scopes = [canonical_directory(raw, "scope") for raw in args.scope]
    for source in sources:
        require_scope(source, scopes)

    if args.staging_root:
        qroot = canonical_new_path(args.staging_root, "staging root")
    else:
        qroot = canonical_new_path(str(default_staging_root(sources[0])), "staging root")
    if qroot.parent == Path(qroot.parent.anchor):
        fail(f"staging root cannot be directly below a filesystem root: {qroot}")
    reject_root_or_home(qroot, "staging root")
    for source in sources:
        if qroot == source or is_within(qroot, source) or is_within(source, qroot):
            fail(f"staging root overlaps source: {qroot} and {source}")
        if not same_filesystem(source, qroot.parent):
            fail(f"source and staging parent are on different filesystems: {source}")

    output = canonical_new_path(args.output, "manifest")
    if is_within(output, qroot) or any(is_within(output, source) for source in sources):
        fail("manifest overlaps a source or staging root")

    entries: list[dict[str, Any]] = []
    for index, source in enumerate(sources, start=1):
        tree = snapshot(source)
        destination = qroot / PAYLOAD_NAME / destination_name(index, source)
        entries.append(
            {
                "source": str(source),
                "source_parent": directory_record(source.parent),
                "destination": str(destination),
                "tree": tree,
                "metrics": tree_metrics(tree),
            }
        )
    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scopes": scope_records(scopes),
        "staging_root": str(qroot),
        "staging_parent": directory_record(qroot.parent),
        "entries": entries,
        "totals": totals(entries),
    }
    digest = write_manifest(output, data)
    print(f"MANIFEST_JSON={json_text(str(output))}")
    print(f"MANIFEST_SHA256={digest}")
    print(f"TOP_LEVEL_COUNT={len(entries)}")
    print(f"TOTAL_ENTRIES={data['totals']['entries']}")
    print(f"LOGICAL_BYTES={data['totals']['logical_bytes']}")
    print(f"STAGE_TOKEN=STAGE:{digest}")
    for entry in entries:
        print(f"PLAN_SOURCE_JSON={json_text(entry['source'])}")
        print(f"PLAN_DESTINATION_JSON={json_text(entry['destination'])}")


def marker_path(qroot: Path) -> Path:
    return qroot / MARKER_NAME


def create_wrapper(qroot: Path, digest: str) -> None:
    if lexists(qroot):
        fail(f"staging root already exists: {qroot}")
    try:
        qroot.mkdir(mode=0o700)
        (qroot / PAYLOAD_NAME).mkdir(mode=0o700)
        with marker_path(qroot).open("x", encoding="ascii", newline="\n") as handle:
            handle.write(digest + "\n")
    except OSError as exc:
        fail(f"cannot create staging wrapper {qroot}: {exc}")


def check_wrapper(qroot: Path, digest: str) -> Path:
    if not qroot.is_dir() or is_link_like(qroot):
        fail(f"staging root is missing or not a real directory: {qroot}")
    payload = qroot / PAYLOAD_NAME
    marker = marker_path(qroot)
    if not payload.is_dir() or is_link_like(payload):
        fail(f"staging payload is missing or link-like: {payload}")
    if not marker.is_file() or marker.is_symlink():
        fail(f"staging marker is missing or invalid: {marker}")
    try:
        marker_value = marker.read_text(encoding="ascii").strip()
        top_names = {child.name for child in qroot.iterdir()}
    except OSError as exc:
        fail(f"cannot inspect staging wrapper {qroot}: {exc}")
    if marker_value != digest:
        fail("staging marker does not match manifest digest")
    valid_top_sets = (
        {PAYLOAD_NAME, MARKER_NAME},
        {PAYLOAD_NAME, MARKER_NAME, RECEIPT_NAME},
    )
    if top_names not in valid_top_sets:
        fail(f"unexpected staging wrapper entries: {sorted(top_names)!r}")
    return payload


def expected_payload_names(entries: list[dict[str, Any]]) -> set[str]:
    return {Path(entry["destination"]).name for entry in entries}


def verify_staged(
    data: dict[str, Any],
    digest: str,
    *,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, int]:
    qroot = qroot_from(data)
    payload = check_wrapper(qroot, digest)
    try:
        actual_names = {child.name for child in payload.iterdir()}
    except OSError as exc:
        fail(f"cannot list staging payload {payload}: {exc}")
    expected_names = expected_payload_names(data["entries"])
    if actual_names != expected_names:
        fail(
            "staging payload differs from manifest: "
            f"expected {sorted(expected_names)!r}, got {sorted(actual_names)!r}"
        )
    records_checked = 0
    top_level_checked = 0
    for entry in data["entries"]:
        source = Path(entry["source"])
        destination = Path(entry["destination"])
        if lexists(source):
            fail(f"source exists while staged: {source}")
        if not lexists(destination):
            fail(f"staged entry is missing: {destination}")
        base_records = records_checked
        visit_callback: Callable[[int], None] | None = None
        if on_progress is not None:
            progress_callback = on_progress

            def report_visit(
                count: int,
                base: int = base_records,
                current: str = str(destination),
                top: int = top_level_checked,
                callback: Callable[[int, int, str], None] = progress_callback,
            ) -> None:
                callback(base + count, top, current)

            visit_callback = report_visit
        current_tree = snapshot(
            destination,
            on_visited=visit_callback,
        )
        records_checked += len(current_tree)
        if current_tree != entry["tree"]:
            fail(f"staged entry differs from manifest: {destination}")
        top_level_checked += 1
        if on_progress is not None:
            on_progress(records_checked, top_level_checked, str(destination))
    return totals(data["entries"])


def rollback_stage(moved: list[tuple[dict[str, Any], Path, Path]]) -> list[str]:
    problems: list[str] = []
    for entry, source, destination in reversed(moved):
        if not lexists(destination):
            problems.append(f"ROLLBACK_MISSING destination disappeared: {destination}")
            continue
        if lexists(source):
            problems.append(f"ROLLBACK_CONFLICT source reappeared; preserved: {destination}")
            continue
        try:
            if snapshot(destination) != entry["tree"]:
                problems.append(f"ROLLBACK_DRIFT preserved changed staging entry: {destination}")
                continue
            os.rename(destination, source)
        except (OSError, GateError) as exc:
            problems.append(f"ROLLBACK_FAILED {destination} -> {source}: {exc}")
    return problems


def command_stage(args: argparse.Namespace) -> None:
    manifest_path = canonical_manifest(args.manifest)
    data, digest = read_manifest(manifest_path)
    expected_token = f"STAGE:{digest}"
    if args.confirm_stage != expected_token:
        fail(f"stage confirmation token mismatch; expected {expected_token}")
    qroot, entries, scopes = validate_manifest_shape(manifest_path, data)
    if lexists(qroot):
        fail(f"staging root already exists: {qroot}")
    for entry in entries:
        source = Path(entry["source"])
        if not same_filesystem(source, qroot.parent):
            fail(f"source and staging parent are on different filesystems: {source}")
        validate_source(entry, scopes)

    create_wrapper(qroot, digest)
    moved: list[tuple[dict[str, Any], Path, Path]] = []
    try:
        for entry in entries:
            source = Path(entry["source"])
            destination = Path(entry["destination"])
            validate_source(entry, scopes)
            if lexists(destination):
                fail(f"staging destination already exists: {destination}")
            os.rename(source, destination)
            moved.append((entry, source, destination))
        verify_staged(data, digest)
        print("STAGE_COMPLETED=true")
        print(f"STAGED_TOP_LEVEL={len(entries)}")
        print(f"STAGING_ROOT_JSON={json_text(str(qroot))}")
        print(f"MANIFEST_SHA256={digest}")
    except BaseException as exc:
        reconciled = reconcile_restore(entries)
        if (
            reconciled.staged == len(entries)
            and reconciled.restored == 0
            and reconciled.indeterminate == 0
        ):
            print("STAGE_COMPLETED=true", file=sys.stderr)
            print(f"STAGED_TOP_LEVEL={reconciled.staged}", file=sys.stderr)
            print(f"STAGING_ROOT_JSON={json_text(str(qroot))}", file=sys.stderr)
            print("STAGE_RETRY=false", file=sys.stderr)
            raise GateError(
                "stage completed and reconciled, but final reporting was interrupted; "
                "continue with standalone verify"
            ) from exc
        for entry in entries:
            source = Path(entry["source"])
            destination = Path(entry["destination"])
            if lexists(destination) and not any(item[2] == destination for item in moved):
                moved.append((entry, source, destination))
        problems = rollback_stage(moved)
        detail = "; ".join(problems) if problems else "rollback completed"
        raise GateError(f"stage failed; {detail}; inspect staging root: {qroot}") from exc


def command_verify(args: argparse.Namespace) -> None:
    manifest_path = canonical_manifest(args.manifest)
    data, digest = read_manifest(manifest_path)
    qroot, entries, _ = validate_manifest_shape(manifest_path, data)
    verified = verify_staged(data, digest)
    nonce = create_or_read_receipt(qroot, digest, verified)
    print("VERIFY_COMPLETED=true")
    print(f"STAGING_ROOT_JSON={json_text(str(qroot))}")
    print(f"TOP_LEVEL_COUNT={len(entries)}")
    print(f"TOTAL_ENTRIES={verified['entries']}")
    print(f"LOGICAL_BYTES={verified['logical_bytes']}")
    print(f"MANIFEST_SHA256={digest}")
    print(f"RESTORE_TOKEN=RESTORE:{digest}:{nonce}")
    print(f"PURGE_TOKEN=PURGE:{digest}:{nonce}")


def receipt_path(qroot: Path) -> Path:
    return qroot / RECEIPT_NAME


def validate_receipt_data(
    data: Any,
    digest: str,
    expected_totals: dict[str, int],
) -> str:
    if not isinstance(data, dict):
        fail("verification receipt is malformed")
    if data.get("manifest_sha256") != digest or data.get("totals") != expected_totals:
        fail("verification receipt does not match the staged manifest")
    nonce = data.get("nonce")
    if (
        not isinstance(nonce, str)
        or len(nonce) != 64
        or any(character not in "0123456789abcdef" for character in nonce)
    ):
        fail("verification receipt nonce is malformed")
    return nonce


def create_or_read_receipt(
    qroot: Path,
    digest: str,
    expected_totals: dict[str, int],
) -> str:
    path = receipt_path(qroot)
    if lexists(path):
        return read_receipt(qroot, digest, expected_totals)
    nonce = secrets.token_hex(32)
    data = {
        "manifest_sha256": digest,
        "nonce": nonce,
        "totals": expected_totals,
    }
    rendered = json_text(data, indent=2) + "\n"
    temporary = qroot.parent / f".reviewed-delete-receipt-{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            if handle.write(rendered) != len(rendered):
                fail(f"short write while creating verification receipt {path}")
        os.replace(temporary, path)
    except OSError as exc:
        fail(f"cannot create verification receipt {path}: {exc}")
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        except OSError:
            pass
    return nonce


def read_receipt(
    qroot: Path,
    digest: str,
    expected_totals: dict[str, int],
) -> str:
    path = receipt_path(qroot)
    if not path.is_file() or path.is_symlink():
        fail("successful standalone verify receipt is missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read verification receipt {path}: {exc}")
    return validate_receipt_data(data, digest, expected_totals)


def cleanup_wrapper(qroot: Path) -> bool:
    try:
        actual = {child.name for child in qroot.iterdir()}
        if actual != {PAYLOAD_NAME, MARKER_NAME, RECEIPT_NAME}:
            return False
        payload = qroot / PAYLOAD_NAME
        if any(payload.iterdir()):
            return False
        os.unlink(receipt_path(qroot))
        os.unlink(marker_path(qroot))
        os.rmdir(payload)
        os.rmdir(qroot)
    except OSError:
        return False
    return True


@dataclass
class RestoreState:
    restored: int = 0
    staged: int = 0
    indeterminate: int = 0


def path_presence(path: Path) -> bool | None:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError:
        return None
    return True


def snapshot_matches(path: Path, tree: list[dict[str, Any]]) -> bool | None:
    try:
        return snapshot(path) == tree
    except GateError:
        return None


def reconcile_restore(entries: list[dict[str, Any]]) -> RestoreState:
    state = RestoreState()
    for entry in entries:
        source = Path(entry["source"])
        destination = Path(entry["destination"])
        source_present = path_presence(source)
        destination_present = path_presence(destination)
        if source_present is True and destination_present is False:
            if snapshot_matches(source, entry["tree"]) is True:
                state.restored += 1
            else:
                state.indeterminate += 1
        elif source_present is False and destination_present is True:
            if snapshot_matches(destination, entry["tree"]) is True:
                state.staged += 1
            else:
                state.indeterminate += 1
        else:
            state.indeterminate += 1
    return state


def report_restore_failure(
    state: RestoreState,
    total: int,
    current_entry: str,
    qroot: Path,
) -> None:
    if state.indeterminate:
        print("RESTORE_INDETERMINATE=true", file=sys.stderr)
        summary = "restore state could not be fully reconciled"
    elif state.restored == total:
        print("RESTORE_COMPLETED=true", file=sys.stderr)
        cleanup_complete = path_presence(qroot) is False
        print(
            f"STAGING_CLEANUP_COMPLETE={str(cleanup_complete).lower()}",
            file=sys.stderr,
        )
        summary = (
            "all reviewed entries are restored; wrapper cleanup completed"
            if cleanup_complete
            else "all reviewed entries are restored; wrapper cleanup requires inspection"
        )
    elif state.restored:
        print("RESTORE_PARTIAL=true", file=sys.stderr)
        summary = "reviewed entries are split between source locations and staging"
    else:
        print("RESTORE_BLOCKED=true", file=sys.stderr)
        summary = "no reviewed top-level entry was restored"
    print(f"RESTORED_TOP_LEVEL={state.restored}", file=sys.stderr)
    print(f"STILL_STAGED_TOP_LEVEL={state.staged}", file=sys.stderr)
    print(f"INDETERMINATE_TOP_LEVEL={state.indeterminate}", file=sys.stderr)
    print(f"CURRENT_ENTRY_JSON={json_text(current_entry)}", file=sys.stderr)
    print("RESTORE_RETRY=false", file=sys.stderr)
    print(
        f"RESTORE_STATE_JSON={json_text(f'{summary}; inspect source paths and {qroot}')}",
        file=sys.stderr,
    )


def report_restore_blocked() -> None:
    print("RESTORE_BLOCKED=true", file=sys.stderr)
    print("RESTORED_TOP_LEVEL=0", file=sys.stderr)
    print("CURRENT_ENTRY=<preflight>", file=sys.stderr)
    print("RESTORE_RETRY=false", file=sys.stderr)


def command_restore(args: argparse.Namespace) -> None:
    manifest_path = canonical_manifest(args.manifest)
    data, digest = read_manifest(manifest_path)
    try:
        qroot, entries, _ = validate_manifest_shape(manifest_path, data)
        nonce = read_receipt(qroot, digest, data["totals"])
    except BaseException as exc:
        report_restore_blocked()
        raise GateError(f"restore preflight failed: {exc}") from exc
    expected_token = f"RESTORE:{digest}:{nonce}"
    if args.confirm_restore != expected_token:
        fail(f"restore confirmation token mismatch; expected {expected_token}")
    try:
        verify_staged(data, digest)
        for entry in entries:
            source = Path(entry["source"])
            destination = Path(entry["destination"])
            if lexists(source):
                fail(f"restore source already exists: {source}")
            if not source.parent.is_dir() or is_link_like(source.parent):
                fail(f"restore source parent is missing or link-like: {source.parent}")
            if not same_filesystem(destination, source.parent):
                fail(f"restore would cross filesystems: {destination} -> {source}")
    except BaseException as exc:
        report_restore_blocked()
        raise GateError(f"restore preflight failed: {exc}") from exc

    restored = 0
    current_entry = "<none>"
    try:
        for entry in entries:
            source = Path(entry["source"])
            destination = Path(entry["destination"])
            current_entry = str(source)
            if lexists(source):
                fail(f"restore source reappeared: {source}")
            if snapshot(destination) != entry["tree"]:
                fail(f"staged entry changed before restore: {destination}")
            os.rename(destination, source)
            restored += 1
            if snapshot(source) != entry["tree"]:
                fail(f"restored entry differs from manifest: {source}")
        print("RESTORE_COMPLETED=true")
        print(f"RESTORED_TOP_LEVEL={restored}")
        if cleanup_wrapper(qroot):
            print("STAGING_CLEANUP_COMPLETE=true")
        else:
            print("STAGING_CLEANUP_COMPLETE=false", file=sys.stderr)
            print("STAGING_CLEANUP_RETRY=manual-inspection", file=sys.stderr)
        print(f"MANIFEST_SHA256={digest}")
    except BaseException as exc:
        reconciled = reconcile_restore(entries)
        report_restore_failure(reconciled, len(entries), current_entry, qroot)
        raise GateError(f"restore failed: {exc}; inspect source paths and {qroot}") from exc


def validate_purge_tree(
    path: Path,
    tree: list[dict[str, Any]],
    *,
    allow_nlink_drift: bool = False,
    on_visited: Callable[[int], None] | None = None,
) -> None:
    reject_mount_boundaries(path)
    index = tree_index(tree)
    children = children_by_parent(index)
    visited: set[str] = set()
    pending: list[tuple[Path, str]] = [(path, ".")]
    while pending:
        current, relative = pending.pop()
        expected = index.get(relative)
        if expected is None:
            fail(f"purge encountered a path outside the manifest: {current}")
        current_record = identity_record(current, expected)
        if not records_match(current_record, expected, ignore_nlink=allow_nlink_drift):
            fail(f"metadata changed before purge: {current}")
        visited.add(relative)
        if on_visited is not None:
            on_visited(len(visited))
        if expected["kind"] != "directory":
            continue
        try:
            with os.scandir(current) as iterator:
                actual_names = {entry.name for entry in iterator}
        except OSError as exc:
            fail(f"cannot scan purge directory {current}: {exc}")
        expected_names = children.get(relative, set())
        if actual_names != expected_names:
            fail(f"purge child set changed at {current}")
        for name in reversed(sorted(expected_names)):
            child_relative = name if relative == "." else f"{relative}/{name}"
            pending.append((current / name, child_relative))
    if visited != set(index):
        fail("manifest tree contains unreachable records")


def remove_manifest_tree(
    path: Path,
    tree: list[dict[str, Any]],
    *,
    on_completed: Callable[[int], None] | None = None,
    on_validated: Callable[[int], None] | None = None,
) -> int:
    state = MutationState(on_completed=on_completed)
    try:
        index = tree_index(tree)
        children = children_by_parent(index)
        validate_purge_tree(
            path,
            tree,
            allow_nlink_drift=True,
            on_visited=on_validated,
        )
        actions: list[tuple[str, Path, str]] = [("enter", path, ".")]
        while actions:
            action, current, relative = actions.pop()
            expected = index[relative]
            if action == "exit":
                try:
                    with os.scandir(current) as iterator:
                        actual_names = {entry.name for entry in iterator}
                except OSError as exc:
                    fail(f"cannot scan emptied purge directory {current}: {exc}")
                if actual_names:
                    fail(f"unexpected contents appeared during purge: {current}")
                identity_record(current, expected)
                state.rmdir(current)
                continue

            current_record = identity_record(current, expected)
            if expected["kind"] not in ("directory", "junction"):
                if not records_match(current_record, expected, ignore_nlink=True):
                    fail(f"metadata changed before unlink: {current}")
                state.unlink(current)
                continue
            if expected["kind"] == "junction":
                if not records_match(current_record, expected, ignore_nlink=True):
                    fail(f"junction changed before removal: {current}")
                state.rmdir(current)
                continue

            expected_names = children.get(relative, set())
            try:
                with os.scandir(current) as iterator:
                    actual_names = {entry.name for entry in iterator}
            except OSError as exc:
                fail(f"cannot scan purge directory {current}: {exc}")
            if actual_names != expected_names:
                fail(f"unexpected contents before purge: {current}")
            actions.append(("exit", current, relative))
            for name in reversed(sorted(expected_names)):
                child_relative = name if relative == "." else f"{relative}/{name}"
                actions.append(("enter", current / name, child_relative))
    except MutationFailure:
        raise
    except BaseException as exc:
        raise MutationFailure(str(exc), state) from exc
    return state.completed


@dataclass
class PurgeState:
    removed: int = 0
    completed_top_level: int = 0


def reconcile_purge(data: dict[str, Any]) -> PurgeState | None:
    state = PurgeState()
    for entry in data["entries"]:
        destination = Path(entry["destination"])
        expected = tree_index(entry["tree"])
        if not lexists(destination):
            state.removed += len(expected)
            state.completed_top_level += 1
            continue
        try:
            current = {item["relative"]: item for item in snapshot(destination)}
        except GateError:
            return None
        entry_removed = 0
        for relative, expected_record in expected.items():
            current_record = current.get(relative)
            if current_record is None:
                entry_removed += 1
                continue
            if any(
                current_record[field] != expected_record[field]
                for field in ("kind", "device", "inode")
            ):
                entry_removed += 1
        state.removed += entry_removed
        if entry_removed == len(expected):
            state.completed_top_level += 1
    return state


def classify_observed_purge_status(
    operation: OperationData | None,
    reconciled: PurgeState | None,
    *,
    total_records: int,
    heartbeat_stale: bool,
) -> ObservedOperationStatus:
    if operation is None:
        return "NOT_STARTED"
    running = operation["status"] == "RUNNING" and not heartbeat_stale
    if reconciled is None:
        return "RUNNING" if running else "INDETERMINATE"
    if reconciled.removed == total_records:
        return "SUCCEEDED"
    if reconciled.removed > 0:
        return "RUNNING" if running else "PARTIAL"
    if operation["status"] == "BLOCKED":
        return "BLOCKED"
    return "RUNNING" if running else "INDETERMINATE"


def classify_failed_purge(
    *,
    mutation_count: int,
    total_records: int,
    reconciliation_available: bool,
    mutation_uncertain: bool,
) -> TerminalOperationStatus:
    if mutation_count == total_records:
        return "SUCCEEDED"
    if mutation_count > 0:
        return "PARTIAL"
    if reconciliation_available:
        return "BLOCKED"
    if mutation_uncertain:
        return "INDETERMINATE"
    return "BLOCKED"


def report_purge_blocked() -> None:
    print("PURGE_BLOCKED=true", file=sys.stderr, flush=True)
    print("PURGED_MUTATIONS=0", file=sys.stderr, flush=True)
    print("PURGED_TOP_LEVEL=0", file=sys.stderr, flush=True)
    print("CURRENT_ENTRY=<preflight>", file=sys.stderr, flush=True)
    print("PURGE_RETRY=false", file=sys.stderr, flush=True)


def operation_status_snapshot(
    manifest_path: Path,
    data: dict[str, Any],
    digest: str,
) -> dict[str, Any]:
    qroot = qroot_from(data)
    path = operation_path(qroot, digest)
    lock_path = operation_lock_path(qroot, digest)
    operation = read_operation(path, digest)
    reconciled = reconcile_purge(data) if operation is not None else None
    if operation is not None:
        operation = read_operation(path, digest)
    qroot_present = path_presence(qroot)
    heartbeat_age: float | None = None
    stale = False
    if operation is not None:
        heartbeat = parse_utc(operation.get("heartbeat_at"))
        if heartbeat is not None:
            heartbeat_age = max(0.0, time.time() - heartbeat)
            stale = heartbeat_age > STALE_HEARTBEAT_SECONDS

    observed_status = classify_observed_purge_status(
        operation,
        reconciled,
        total_records=data["totals"]["entries"],
        heartbeat_stale=stale,
    )

    return {
        "operation_id": operation.get("operation_id") if operation else None,
        "operation_path": str(path),
        "manifest_path": str(manifest_path),
        "manifest_sha256": digest,
        "durable_status": operation.get("status") if operation else "NOT_STARTED",
        "observed_status": observed_status,
        "phase": operation.get("phase") if operation else None,
        "heartbeat_age_seconds": round(heartbeat_age, 3) if heartbeat_age is not None else None,
        "heartbeat_stale": stale,
        "progress": operation.get("progress") if operation else None,
        "conditions": operation.get("conditions") if operation else None,
        "error": operation.get("error") if operation else None,
        "reconciliation": (
            {
                "records_removed": reconciled.removed,
                "records_total": data["totals"]["entries"],
                "top_level_removed": reconciled.completed_top_level,
                "top_level_total": len(data["entries"]),
            }
            if reconciled is not None
            else None
        ),
        "staging_root_present": qroot_present,
        "operation_lock_present": lexists(lock_path),
    }


def command_status(args: argparse.Namespace) -> None:
    manifest_path = canonical_manifest(args.manifest)
    data, digest = read_manifest(manifest_path)
    status = operation_status_snapshot(manifest_path, data, digest)
    print(f"OPERATION_STATUS_JSON={json_text(status, separators=(',', ':'))}", flush=True)


def command_watch(args: argparse.Namespace) -> None:
    if args.interval < 0.25:
        fail("watch interval must be at least 0.25 seconds")
    manifest_path = canonical_manifest(args.manifest)
    data, digest = read_manifest(manifest_path)
    qroot = qroot_from(data)
    path = operation_path(qroot, digest)
    last_rendered: str | None = None
    while True:
        operation = read_operation(path, digest)
        if operation is None:
            fail(f"purge operation has not started: {path}")
        summary = {
            "operation_id": operation["operation_id"],
            "status": operation.get("status"),
            "phase": operation.get("phase"),
            "heartbeat_at": operation.get("heartbeat_at"),
            "progress": operation.get("progress"),
            "conditions": operation.get("conditions"),
            "error": operation.get("error"),
        }
        rendered = json_text(summary, separators=(",", ":"))
        if rendered != last_rendered:
            print(f"OPERATION_WATCH_JSON={rendered}", flush=True)
            last_rendered = rendered
        heartbeat = parse_utc(operation.get("heartbeat_at"))
        stale = heartbeat is None or time.time() - heartbeat > STALE_HEARTBEAT_SECONDS
        if operation.get("status") != "RUNNING" or stale:
            status = operation_status_snapshot(manifest_path, data, digest)
            print(
                f"OPERATION_STATUS_JSON={json_text(status, separators=(',', ':'))}",
                flush=True,
            )
            return
        time.sleep(args.interval)


def authorize_purge(
    manifest_path: Path,
    data: dict[str, Any],
    digest: str,
    confirmation: str,
) -> tuple[Path, list[dict[str, Any]]]:
    qroot, entries, _ = validate_manifest_shape(manifest_path, data)
    nonce = read_receipt(qroot, digest, data["totals"])
    expected_token = f"PURGE:{digest}:{nonce}"
    if confirmation != expected_token:
        fail(f"purge confirmation token mismatch; expected {expected_token}")
    return qroot, entries


def preflight_purge(
    data: dict[str, Any],
    digest: str,
    entries: list[dict[str, Any]],
    operation: PurgeOperation,
) -> None:
    def verify_progress(records: int, top_level: int, current: str) -> None:
        operation.preflight_checkpoint(
            records_checked=records,
            top_level_checked=top_level,
            current_entry=current,
        )

    verify_staged(data, digest, on_progress=verify_progress)
    records_checked = data["totals"]["entries"]
    top_level_checked = len(entries)
    for entry in entries:
        current_entry = str(entry["destination"])
        base_records = records_checked

        def report_visit(
            count: int,
            base: int = base_records,
            current: str = current_entry,
            top: int = top_level_checked,
        ) -> None:
            operation.preflight_checkpoint(
                records_checked=base + count,
                top_level_checked=top,
                current_entry=current,
            )

        validate_purge_tree(
            Path(current_entry),
            entry["tree"],
            on_visited=report_visit,
        )
        records_checked += len(entry["tree"])
        top_level_checked += 1
        operation.preflight_checkpoint(
            records_checked=records_checked,
            top_level_checked=top_level_checked,
            current_entry=current_entry,
        )
    operation.preflight_checkpoint(
        records_checked=records_checked,
        top_level_checked=top_level_checked,
        current_entry=None,
        force=True,
    )
    operation.checkpoint(
        records_completed=0,
        top_level_completed=0,
        current_entry=None,
        force=True,
    )


@dataclass
class PurgeExecutionState:
    mutation_count: int = 0
    mutation_uncertain: bool = False
    completed_top_level: int = 0
    current_entry: str = "<none>"


def execute_purge(
    entries: list[dict[str, Any]],
    operation: PurgeOperation,
    state: PurgeExecutionState,
) -> None:
    for entry in entries:
        state.current_entry = entry["destination"]
        try:
            base_mutation_count = state.mutation_count
            state.mutation_count += remove_manifest_tree(
                Path(state.current_entry),
                entry["tree"],
                on_completed=lambda entry_count, base=base_mutation_count: operation.checkpoint(
                    records_completed=base + entry_count,
                    top_level_completed=state.completed_top_level,
                    current_entry=state.current_entry,
                ),
                on_validated=lambda _count: operation.checkpoint(
                    records_completed=state.mutation_count,
                    top_level_completed=state.completed_top_level,
                    current_entry=state.current_entry,
                ),
            )
        except MutationFailure as exc:
            state.mutation_count += exc.state.completed
            state.mutation_uncertain = state.mutation_uncertain or exc.state.uncertain
            raise
        state.completed_top_level += 1
        if lexists(Path(state.current_entry)):
            fail(f"purged top-level entry remains: {state.current_entry}")
        operation.checkpoint(
            records_completed=state.mutation_count,
            top_level_completed=state.completed_top_level,
            current_entry=state.current_entry,
            force=True,
        )


def report_successful_purge(
    operation: PurgeOperation,
    digest: str,
    state: PurgeExecutionState,
    cleanup_complete: bool,
) -> None:
    print("PURGE_COMPLETED=true", flush=True)
    print(f"PURGED_TOP_LEVEL={state.completed_top_level}", flush=True)
    print(f"STAGING_CLEANUP_COMPLETE={str(cleanup_complete).lower()}", flush=True)
    if not cleanup_complete:
        print("STAGING_CLEANUP_RETRY=manual-inspection", file=sys.stderr, flush=True)
    print(f"OPERATION_JSON={json_text(str(operation.path))}", flush=True)
    print(f"MANIFEST_SHA256={digest}", flush=True)


def report_failed_purge(
    data: dict[str, Any],
    qroot: Path,
    operation: PurgeOperation,
    execution: PurgeExecutionState,
    error: BaseException,
) -> None:
    reconciled = reconcile_purge(data)
    if reconciled is not None:
        execution.mutation_count = max(execution.mutation_count, reconciled.removed)
        execution.completed_top_level = max(
            execution.completed_top_level,
            reconciled.completed_top_level,
        )
    total_records = data["totals"]["entries"]
    terminal_status = classify_failed_purge(
        mutation_count=execution.mutation_count,
        total_records=total_records,
        reconciliation_available=reconciled is not None,
        mutation_uncertain=execution.mutation_uncertain,
    )
    cleanup_complete = False
    if terminal_status == "SUCCEEDED":
        print("PURGE_COMPLETED=true", file=sys.stderr, flush=True)
        state_detail = "all reviewed identities were removed"
        cleanup_complete = path_presence(qroot) is False
        print(
            f"STAGING_CLEANUP_COMPLETE={str(cleanup_complete).lower()}",
            file=sys.stderr,
            flush=True,
        )
    elif terminal_status == "PARTIAL":
        print("PURGE_PARTIAL=true", file=sys.stderr, flush=True)
        state_detail = "irreversible purge began; inspect remaining staging state"
    elif terminal_status == "INDETERMINATE":
        print("PURGE_INDETERMINATE=true", file=sys.stderr, flush=True)
        state_detail = "mutation outcome is uncertain; inspect staging state"
    else:
        print("PURGE_BLOCKED=true", file=sys.stderr, flush=True)
        state_detail = (
            "no reviewed identity was removed"
            if reconciled is not None
            else "no irreversible mutation was confirmed"
        )
    try:
        operation.finish(
            status=terminal_status,
            records_completed=execution.mutation_count,
            top_level_completed=execution.completed_top_level,
            current_entry=execution.current_entry,
            data_purged=execution.mutation_count == total_records,
            wrapper_cleaned=cleanup_complete,
            error=str(error),
        )
    except BaseException as operation_exc:
        emit_event("PURGE_OPERATION_ERROR", {"error": str(operation_exc)})
    print(f"PURGED_MUTATIONS={execution.mutation_count}", file=sys.stderr, flush=True)
    print(
        f"PURGED_TOP_LEVEL={execution.completed_top_level}",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"CURRENT_ENTRY_JSON={json_text(execution.current_entry)}",
        file=sys.stderr,
        flush=True,
    )
    print(f"OPERATION_JSON={json_text(str(operation.path))}", file=sys.stderr, flush=True)
    print("PURGE_RETRY=false", file=sys.stderr, flush=True)
    print(f"PURGE_STATE={state_detail}", file=sys.stderr, flush=True)


def command_purge(args: argparse.Namespace) -> None:
    manifest_path = canonical_manifest(args.manifest)
    data, digest = read_manifest(manifest_path)
    try:
        qroot, entries = authorize_purge(
            manifest_path,
            data,
            digest,
            args.confirm_purge,
        )
    except BaseException as exc:
        report_purge_blocked()
        raise GateError(f"purge authorization failed: {exc}") from exc

    operation = PurgeOperation.start(
        manifest_path,
        qroot,
        digest,
        data["totals"],
        len(entries),
    )
    try:
        preflight_purge(data, digest, entries, operation)
    except BaseException as exc:
        try:
            operation.finish(
                status="BLOCKED",
                records_completed=0,
                top_level_completed=0,
                current_entry=None,
                data_purged=False,
                wrapper_cleaned=False,
                error=str(exc),
            )
        except BaseException as operation_exc:
            emit_event("PURGE_OPERATION_ERROR", {"error": str(operation_exc)})
        report_purge_blocked()
        raise GateError(f"purge preflight failed: {exc}") from exc

    execution = PurgeExecutionState()
    try:
        execute_purge(entries, operation, execution)
        cleanup_complete = cleanup_wrapper(qroot)
        operation.finish(
            status="SUCCEEDED",
            records_completed=execution.mutation_count,
            top_level_completed=execution.completed_top_level,
            current_entry=execution.current_entry,
            data_purged=True,
            wrapper_cleaned=cleanup_complete,
            error=None,
        )
        report_successful_purge(operation, digest, execution, cleanup_complete)
    except BaseException as exc:
        report_failed_purge(data, qroot, operation, execution, exc)
        raise GateError(f"purge failed: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan", help="freeze exact paths in a dry-run manifest")
    plan.add_argument("--output", required=True, help="new absolute manifest path")
    plan.add_argument("--staging-root", help="new absolute same-filesystem staging root")
    plan.add_argument("--scope", action="append", required=True, help="absolute scope; repeatable")
    plan.add_argument("--expected-count", required=True, type=int)
    plan.add_argument("paths", nargs="+", help="already-decided explicit absolute paths")
    plan.set_defaults(func=command_plan)

    stage = commands.add_parser("stage", help="move exactly the reviewed manifest entries")
    stage.add_argument("--manifest", required=True)
    stage.add_argument("--confirm-stage", required=True)
    stage.set_defaults(func=command_stage)

    verify = commands.add_parser("verify", help="verify the recoverable staged state")
    verify.add_argument("--manifest", required=True)
    verify.set_defaults(func=command_verify)

    restore = commands.add_parser("restore", help="restore all verified staged entries")
    restore.add_argument("--manifest", required=True)
    restore.add_argument("--confirm-restore", required=True)
    restore.set_defaults(func=command_restore)

    purge = commands.add_parser("purge", help="permanently purge a verified staged manifest")
    purge.add_argument("--manifest", required=True)
    purge.add_argument("--confirm-purge", required=True)
    purge.set_defaults(func=command_purge)

    status = commands.add_parser(
        "status",
        help="reconcile and report the durable purge operation state",
    )
    status.add_argument("--manifest", required=True)
    status.set_defaults(func=command_status)

    watch = commands.add_parser(
        "watch",
        help="follow durable purge progress until terminal or stale",
    )
    watch.add_argument("--manifest", required=True)
    watch.add_argument("--interval", type=float, default=2.0)
    watch.set_defaults(func=command_watch)
    return parser


def install_termination_handlers() -> dict[int, Any]:
    previous: dict[int, Any] = {}

    def request_termination(signum: int, _frame: Any) -> None:
        raise TerminationRequested(signum)

    for name in ("SIGTERM", "SIGHUP"):
        signum = getattr(signal, name, None)
        if signum is None:
            continue
        previous[int(signum)] = signal.getsignal(signum)
        signal.signal(signum, request_termination)
    return previous


def restore_signal_handlers(previous: dict[int, Any]) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    previous_handlers = install_termination_handlers()
    try:
        args.func(args)
    except GateError as exc:
        print(f"ERROR_JSON={json_text(str(exc))}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(f"ERROR_JSON={json_text('interrupted by SIGINT')}", file=sys.stderr)
        return 130
    except TerminationRequested as exc:
        print(f"ERROR_JSON={json_text(str(exc))}", file=sys.stderr)
        return 128 + exc.signum
    finally:
        restore_signal_handlers(previous_handlers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

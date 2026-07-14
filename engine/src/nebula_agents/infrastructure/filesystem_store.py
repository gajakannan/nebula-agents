from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import time
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator
from uuid import uuid4

from nebula_agents.domain.enums import Action, RunStatus
from nebula_agents.domain.errors import ErrorCode, NebulaError, error
from nebula_agents.domain.models import (
    Actor,
    AuditEventSummary,
    RecoverableRun,
    RunRecord,
    RuntimeEvent,
    deserialize_run_record,
    serialize_record,
)

from .schema_registry import JsonSchemaRegistry


_RUN_ID = re.compile(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{8}$")
_STATE_IMAGE_LIMIT = 4


class FilesystemRunRepository:
    def __init__(self, runtime_root: Path, schema: JsonSchemaRegistry, lock_timeout_seconds: float = 5.0) -> None:
        self._runtime_root = runtime_root.expanduser().resolve()
        self._runs_root = self._runtime_root / "runs"
        self._schema = schema
        self._lock_timeout = lock_timeout_seconds

    def initialize(self) -> None:
        try:
            self._runtime_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._runs_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            for directory in (self._runtime_root, self._runs_root):
                details = directory.lstat()
                if directory.is_symlink() or not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != 0o700:
                    raise PermissionError("unsafe runtime repository directory")
        except OSError as exc:
            raise error(ErrorCode.RUNTIME_DIR_DENIED, "Runtime repository cannot be initialized safely", "preflight", "Restore owner-only runtime and runs directories with mode 0700.") from exc

    @property
    def runtime_root(self) -> Path:
        return self._runtime_root

    def _validate_existing_roots(self) -> bool:
        if not self._runtime_root.exists():
            return False
        try:
            runtime_details = self._runtime_root.lstat()
            if self._runtime_root.is_symlink() or not stat.S_ISDIR(runtime_details.st_mode) or runtime_details.st_uid != os.getuid() or stat.S_IMODE(runtime_details.st_mode) != 0o700:
                raise PermissionError("unsafe runtime root")
            if not self._runs_root.exists():
                return False
            runs_details = self._runs_root.lstat()
            if self._runs_root.is_symlink() or not stat.S_ISDIR(runs_details.st_mode) or runs_details.st_uid != os.getuid() or stat.S_IMODE(runs_details.st_mode) != 0o700:
                raise PermissionError("unsafe runs root")
        except OSError as exc:
            raise error(ErrorCode.RUNTIME_DIR_DENIED, "Runtime repository is unavailable or unsafe", "preflight", "Restore owner-only runtime and runs directories with mode 0700.") from exc
        return True

    def run_directory(self, run_id: str) -> Path:
        if not _RUN_ID.fullmatch(run_id):
            raise error(ErrorCode.USAGE_ERROR, "Run identifier is invalid", "usage", "Use YYYY-MM-DD-8hex.")
        return self._runs_root / run_id

    @contextmanager
    def _lock(self, directory: Path) -> Iterator[None]:
        try:
            directory_details = directory.lstat()
        except OSError as exc:
            raise error(ErrorCode.STATE_CORRUPT, "Run directory is unavailable", "state-io", "Restore the owner-only run directory.") from exc
        if directory.is_symlink() or not stat.S_ISDIR(directory_details.st_mode) or directory_details.st_uid != os.getuid() or stat.S_IMODE(directory_details.st_mode) != 0o700:
            raise error(ErrorCode.STATE_CORRUPT, "Run directory ownership or permissions are unsafe", "state-io", "Restore the owner-only run directory mode to 0700.")
        lock_path = directory / ".lock"
        try:
            fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            lock_details = os.fstat(fd)
            if not stat.S_ISREG(lock_details.st_mode) or lock_details.st_uid != os.getuid() or stat.S_IMODE(lock_details.st_mode) != 0o600:
                raise PermissionError("unsafe run lock")
        except OSError as exc:
            if "fd" in locals():
                os.close(fd)
            raise error(ErrorCode.STATE_CORRUPT, "Run state lock is unsafe", "state-io", "Restore the owner-only run lock.") from exc
        deadline = time.monotonic() + self._lock_timeout
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise error(ErrorCode.STATE_LOCK_TIMEOUT, "Run state lock timed out", "timeout", "Wait for the active operation and retry.")
                    time.sleep(0.05)
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def _load_path(self, path: Path) -> RunRecord:
        try:
            if path.is_symlink():
                raise PermissionError("snapshot is a symlink")
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                details = os.fstat(fd)
                payload = os.read(fd, max(1, details.st_size + 1))
            finally:
                os.close(fd)
            if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != 0o600:
                raise PermissionError("unsafe snapshot mode")
            document = json.loads(payload.decode("utf-8"))
            if not isinstance(document, dict):
                raise ValueError("snapshot is not an object")
            # Read legacy v1 snapshots without weakening new approval binding.
            # Missing binding fields are filled with safe display metadata and
            # null freshness values, which forces a validator rerun before any
            # subsequent approval.
            validator = document.get("latest_validator")
            if isinstance(validator, dict):
                templates = {
                    "stories": "python3 validate-stories.py --product-root {workspace} {feature}",
                    "trackers": "python3 validate-trackers.py --product-root {workspace} --skip-feature-evidence",
                    "templates": "python3 validate_templates.py",
                }
                validator.setdefault("command_template", templates.get(str(validator.get("validator_key")), ""))
                validator.setdefault("gate_id", None)
                validator.setdefault("validated_revision", None)
                validator.setdefault("evidence_digest", None)
            transcript = document.get("transcript")
            if isinstance(transcript, dict):
                transcript.setdefault("failure_reason", None)
            self._schema.validate("f0001-run-record.schema.json", document)
            return deserialize_run_record(document)
        except NebulaError:
            raise
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise error(ErrorCode.STATE_CORRUPT, "Run snapshot is unavailable or corrupt", "state-io", "Use run recovery and inspect the preserved snapshot.") from exc

    def load(self, run_id: str) -> RunRecord:
        roots_ready = self._validate_existing_roots()
        path = self.run_directory(run_id) / "run.json"
        if not path.exists():
            available = [] if not roots_ready else sorted(
                (item.name for item in self._runs_root.iterdir() if item.is_dir() and _RUN_ID.fullmatch(item.name)), reverse=True,
            )[:20]
            raise error(
                ErrorCode.RUN_NOT_FOUND,
                "Run was not found",
                "not-found",
                "List known sessions and select an existing run.",
                run_id=run_id,
                available_run_ids=available,
            )
        return self._load_path(path)

    def list(self, status: RunStatus | None = None) -> tuple[RunRecord, ...]:
        if not self._validate_existing_roots():
            return ()
        records: list[RunRecord] = []
        for path in sorted(self._runs_root.glob("*/run.json"), reverse=True):
            try:
                record = self._load_path(path)
            except NebulaError:
                continue
            if status is None or record.status is status:
                records.append(record)
        return tuple(records)

    def list_recoverable(self) -> tuple[RecoverableRun, ...]:
        """Discover corrupt latest snapshots that have an exact durable recovery point."""
        if not self._validate_existing_roots():
            return ()
        recoverable: list[RecoverableRun] = []
        for directory in sorted(self._runs_root.iterdir(), reverse=True):
            if not directory.is_dir() or directory.is_symlink() or _RUN_ID.fullmatch(directory.name) is None:
                continue
            try:
                self._load_path(directory / "run.json")
                continue
            except NebulaError:
                pass
            try:
                sequences, last_event = self._event_history(directory, directory.name)
                selected = self._select_recovery_record(directory, directory.name, len(sequences))
            except NebulaError:
                continue
            recoverable.append(RecoverableRun(selected, last_event))
        return tuple(recoverable)

    @staticmethod
    def _data(document: object, *, pretty: bool) -> bytes:
        if pretty:
            return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        return (json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

    @staticmethod
    def _write_file(path: Path, data: bytes) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            remaining = memoryview(data)
            while remaining:
                written = os.write(fd, remaining)
                if written <= 0:
                    raise OSError("run state write did not progress")
                remaining = remaining[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(path, 0o600)

    def _prepare(self, directory: Path, record: RunRecord) -> Path:
        document = serialize_record(record)
        self._schema.validate("f0001-run-record.schema.json", document)
        pending = directory / "pending.json"
        data = self._data(document, pretty=True)
        self._write_file(pending, data)
        # A validated state image pairs every event sequence with a deterministic
        # recovery point. It allows replay after a successfully published latest
        # snapshot is later corrupted, without weakening the append-only log.
        self._write_file(directory / f"state-{record.last_event_sequence:08d}.json", data)
        state_images = sorted(directory.glob("state-*.json"), reverse=True)
        for stale in state_images[_STATE_IMAGE_LIMIT:]:
            if not stale.is_symlink():
                stale.unlink(missing_ok=True)
        return pending

    def _append_event(self, directory: Path, event: RuntimeEvent) -> None:
        document = serialize_record(event)
        self._schema.validate("f0001-runtime-event.schema.json", document)
        path = directory / "events.jsonl"
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            remaining = memoryview(self._data(document, pretty=False))
            while remaining:
                written = os.write(fd, remaining)
                if written <= 0:
                    raise OSError("audit event write did not progress")
                remaining = remaining[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(path, 0o600)

    @staticmethod
    def _publish(directory: Path, pending: Path) -> None:
        snapshot = directory / "run.json"
        backup = directory / "run.json.bak"
        if snapshot.exists():
            os.replace(snapshot, backup)
            os.chmod(backup, 0o600)
        os.replace(pending, snapshot)
        os.chmod(snapshot, 0o600)
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def create(self, record: RunRecord, event: RuntimeEvent) -> RunRecord:
        self.initialize()
        directory = self.run_directory(record.run_id)
        expected_audit = str((directory / "events.jsonl").resolve())
        if str(Path(record.audit_log_path).resolve()) != expected_audit or record.owner.uid != os.getuid():
            raise error(ErrorCode.STATE_CORRUPT, "Initial run identity is inconsistent", "state-io", "Create the run with the current owner and canonical audit path.")
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise error(ErrorCode.CONFLICT, "Run identifier already exists", "conflict", "Choose a new run identifier.", run_id=record.run_id) from exc
        os.chmod(directory, 0o700)
        with self._lock(directory):
            if record.revision != 0 or record.last_event_sequence != 1 or event.sequence != 1 or event.run_id != record.run_id:
                raise error(ErrorCode.STATE_CORRUPT, "Initial run revision is inconsistent", "state-io", "Retry with a fresh run identifier.")
            pending = self._prepare(directory, record)
            self._append_event(directory, event)
            self._publish(directory, pending)
        return record

    def commit(self, *, expected_revision: int, next_record: RunRecord, event: RuntimeEvent) -> RunRecord:
        directory = self.run_directory(next_record.run_id)
        if not directory.is_dir():
            raise error(ErrorCode.RUN_NOT_FOUND, "Run was not found", "not-found", "List known sessions and select an existing run.")
        with self._lock(directory):
            current = self._load_path(directory / "run.json")
            self._commit_locked(directory, current, expected_revision, next_record, event)
        return next_record

    @staticmethod
    def _immutable_identity(record: RunRecord) -> tuple[object, ...]:
        return (
            record.schema_version,
            record.run_id,
            record.feature_id,
            record.story_id,
            record.provider_key,
            record.tmux_session,
            record.workspace_root,
            record.prompt_contract,
            record.prompt_action,
            record.owner,
            record.audit_log_path,
            record.created_at,
        )

    def _commit_locked(
        self,
        directory: Path,
        current: RunRecord,
        expected_revision: int,
        next_record: RunRecord,
        event: RuntimeEvent,
    ) -> None:
        if current.revision != expected_revision:
            raise error(ErrorCode.STALE_REVISION, "The run changed after it was displayed", "conflict", "Refresh and retry.", current_revision=current.revision)
        if self._immutable_identity(next_record) != self._immutable_identity(current):
            raise error(ErrorCode.STATE_CORRUPT, "Immutable run identity changed", "state-io", "Reload the current snapshot and preserve its identity fields.")
        if next_record.revision != current.revision + 1 or next_record.last_event_sequence != current.last_event_sequence + 1:
            raise error(ErrorCode.STATE_CORRUPT, "Run revision or event sequence is inconsistent", "state-io", "Reload the current snapshot.")
        if event.run_id != current.run_id or event.sequence != next_record.last_event_sequence:
            raise error(ErrorCode.STATE_CORRUPT, "Audit event does not match the state transition", "state-io", "Reload the current snapshot.")
        pending = self._prepare(directory, next_record)
        self._append_event(directory, event)
        self._publish(directory, pending)

    def commit_authorized(
        self,
        *,
        expected_revision: int,
        next_record: RunRecord,
        event: RuntimeEvent,
        authorize: Callable[[RunRecord], None],
        denied_actor: Actor,
        denied_action: Action,
    ) -> RunRecord:
        directory = self.run_directory(next_record.run_id)
        if not directory.is_dir():
            raise error(ErrorCode.RUN_NOT_FOUND, "Run was not found", "not-found", "List known sessions and select an existing run.")
        with self._lock(directory):
            current = self._load_path(directory / "run.json")
            if current.revision != expected_revision:
                raise error(ErrorCode.STALE_REVISION, "The run changed after it was displayed", "conflict", "Refresh and retry.", current_revision=current.revision)
            try:
                authorize(current)
            except NebulaError:
                denied_event = RuntimeEvent(
                    "1.0", current.run_id, current.last_event_sequence + 1, "AuthorizationDenied",
                    event.occurred_at, denied_actor, uuid4(), {"action": denied_action.value},
                )
                denied_record = replace(
                    current,
                    revision=current.revision + 1,
                    last_event_sequence=current.last_event_sequence + 1,
                    updated_at=event.occurred_at,
                )
                self._commit_locked(directory, current, current.revision, denied_record, denied_event)
                raise
            self._commit_locked(directory, current, expected_revision, next_record, event)
        return next_record

    def record_authorization_denied(
        self,
        run_id: str,
        actor: Actor,
        action: Action,
        occurred_at: datetime,
    ) -> None:
        directory = self.run_directory(run_id)
        if not directory.is_dir():
            return
        with self._lock(directory):
            current = self._load_path(directory / "run.json")
            denied = replace(
                current,
                revision=current.revision + 1,
                last_event_sequence=current.last_event_sequence + 1,
                updated_at=occurred_at,
            )
            event = RuntimeEvent(
                "1.0", run_id, denied.last_event_sequence, "AuthorizationDenied", occurred_at,
                actor, uuid4(), {"action": action.value},
            )
            self._commit_locked(directory, current, current.revision, denied, event)

    def _event_history(
        self, directory: Path, run_id: str,
    ) -> tuple[tuple[int, ...], AuditEventSummary | None]:
        path = directory / "events.jsonl"
        sequences: list[int] = []
        last_event: AuditEventSummary | None = None
        try:
            if path.is_symlink():
                raise PermissionError("event log is a symlink")
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                details = os.fstat(fd)
                if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != 0o600:
                    raise PermissionError("event log mode is unsafe")
                with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as stream:
                    for line in stream:
                        document = json.loads(line)
                        self._schema.validate("f0001-runtime-event.schema.json", document)
                        if document.get("run_id") != run_id:
                            raise ValueError("event belongs to a different run")
                        sequence = int(document["sequence"])
                        occurred_at = datetime.fromisoformat(str(document["occurred_at"]).replace("Z", "+00:00"))
                        sequences.append(sequence)
                        last_event = AuditEventSummary(sequence, str(document["event_type"]), occurred_at)
            finally:
                os.close(fd)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            raise error(ErrorCode.STATE_CORRUPT, "Run event history is corrupt", "state-io", "Preserve the run directory for inspection.") from exc
        if sequences != list(range(1, len(sequences) + 1)):
            raise error(ErrorCode.STATE_CORRUPT, "Run event history is not contiguous", "state-io", "Preserve the run directory for inspection.")
        return tuple(sequences), last_event

    def _event_sequences(self, directory: Path, run_id: str) -> tuple[int, ...]:
        return self._event_history(directory, run_id)[0]

    def _select_recovery_record(self, directory: Path, run_id: str, event_count: int) -> RunRecord:
        candidates = (
            directory / "run.json",
            directory / "pending.json",
            directory / "run.json.bak",
            *sorted(directory.glob("state-*.json"), reverse=True),
        )
        valid: list[tuple[Path, RunRecord]] = []
        for candidate in candidates:
            if not candidate.exists():
                continue
            try:
                record = self._load_path(candidate)
                expected_audit = str((directory / "events.jsonl").resolve())
                if record.run_id != run_id or str(Path(record.audit_log_path).resolve()) != expected_audit:
                    continue
                valid.append((candidate, record))
            except NebulaError:
                continue
        if not valid:
            raise error(ErrorCode.STATE_CORRUPT, "No valid run snapshot can be recovered", "state-io", "Preserve the run directory for manual inspection.")
        eligible = [(path, record) for path, record in valid if record.last_event_sequence <= event_count]
        if not eligible:
            raise error(ErrorCode.STATE_CORRUPT, "No snapshot matches the event history", "state-io", "Preserve the run directory for manual inspection.")
        _, selected = max(eligible, key=lambda item: item[1].last_event_sequence)
        if selected.last_event_sequence != event_count:
            raise error(ErrorCode.STATE_CORRUPT, "The event suffix has no recoverable state image", "state-io", "Preserve pending.json and the event log for inspection.")
        return selected

    def recover(self, run_id: str) -> RunRecord:
        directory = self.run_directory(run_id)
        if not directory.is_dir():
            raise error(ErrorCode.RUN_NOT_FOUND, "Run was not found", "not-found", "List known sessions and select an existing run.")
        with self._lock(directory):
            sequences = self._event_sequences(directory, run_id)
            selected = self._select_recovery_record(directory, run_id, len(sequences))
            try:
                current_matches = self._load_path(directory / "run.json") == selected
            except NebulaError:
                current_matches = False
            if not current_matches:
                recovery = directory / "recovered.json"
                self._write_file(recovery, self._data(serialize_record(selected), pretty=True))
                self._publish(directory, recovery)
            pending = directory / "pending.json"
            if pending.exists():
                pending.rename(directory / f"pending.corrupt-{int(time.time())}.json")
            return selected

from __future__ import annotations

import json
import fcntl
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import JsonValue

from .schema_registry import JsonSchemaRegistry


class LocalPolicyStore:
    def __init__(self, runtime_root: Path, schema: JsonSchemaRegistry) -> None:
        self._runtime_root = runtime_root.expanduser().resolve()
        self._path = self._runtime_root / "policy.json"
        self._schema = schema

    @property
    def path(self) -> Path:
        return self._path

    def initialize(self, owner_uid: int) -> None:
        try:
            self._runtime_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            details = self._runtime_root.stat()
        except OSError as exc:
            raise error(ErrorCode.RUNTIME_DIR_DENIED, "Runtime directory cannot be initialized", "preflight", "Choose a writable owner-only runtime directory.") from exc
        if details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) & 0o077:
            raise error(ErrorCode.RUNTIME_DIR_DENIED, "Runtime directory ownership or permissions are unsafe", "preflight", "Use an owner-only runtime directory.")
        try:
            lock_fd = os.open(self._runtime_root / ".policy.lock", os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            lock_details = os.fstat(lock_fd)
            if not stat.S_ISREG(lock_details.st_mode) or lock_details.st_uid != os.getuid() or stat.S_IMODE(lock_details.st_mode) != 0o600:
                raise PermissionError("unsafe policy lock")
        except OSError as exc:
            if "lock_fd" in locals():
                os.close(lock_fd)
            raise error(ErrorCode.RUNTIME_DIR_DENIED, "Policy lock is unavailable or unsafe", "preflight", "Restore the owner-only runtime directory.") from exc
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            if self._path.is_symlink():
                raise error(ErrorCode.FORBIDDEN, "Local policy cannot be a symbolic link", "forbidden", "Restore an owner-only regular policy.json.")
            if self._path.exists():
                return
            document: dict[str, JsonValue] = {
                "schema_version": "1.0",
                "policy_version": 1,
                "default_effect": "deny",
                "bindings": [{"subject_type": "uid", "subject_id": owner_uid, "role": "LocalOperator"}],
                "reviewer_grants": {
                    "reviewer_can_launch": False,
                    "reviewer_can_attach": False,
                    "reviewer_can_hold": False,
                    "reviewer_can_approve": False,
                    "reviewer_can_configure_transcript": False,
                },
                "validator_allowlist": ["stories", "trackers", "templates"],
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            self._schema.validate("f0001-local-policy.schema.json", document)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(self._path, flags, 0o600)
            try:
                data = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
                remaining = memoryview(data)
                while remaining:
                    written = os.write(fd, remaining)
                    if written <= 0:
                        raise OSError("policy write did not progress")
                    remaining = remaining[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)

    def load(self) -> Mapping[str, JsonValue]:
        try:
            if self._path.is_symlink():
                raise PermissionError("policy is a symlink")
            fd = os.open(self._path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                details = os.fstat(fd)
                payload = os.read(fd, max(1, details.st_size + 1))
            finally:
                os.close(fd)
            if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != 0o600:
                raise PermissionError("unsafe policy ownership or mode")
            document = json.loads(payload.decode("utf-8"))
            if not isinstance(document, dict):
                raise ValueError("policy is not an object")
            self._schema.validate("f0001-local-policy.schema.json", document)
            self._validate_binding_uniqueness(document)
            return document
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise error(ErrorCode.FORBIDDEN, "Local policy is unavailable or unsafe", "forbidden", "Restore owner-only policy.json.") from exc

    @staticmethod
    def _validate_binding_uniqueness(document: Mapping[str, JsonValue]) -> None:
        """Reject duplicate subjects even when their requested roles agree."""

        bindings = document.get("bindings")
        if not isinstance(bindings, list):
            raise ValueError("policy bindings are not an array")
        subjects: set[tuple[str, int]] = set()
        for binding in bindings:
            if not isinstance(binding, dict):
                raise ValueError("policy binding is not an object")
            subject_type = binding.get("subject_type")
            subject_id = binding.get("subject_id")
            if not isinstance(subject_type, str) or not isinstance(subject_id, int):
                raise ValueError("policy binding subject is invalid")
            subject = (subject_type, subject_id)
            if subject in subjects:
                raise ValueError("policy contains duplicate subject bindings")
            subjects.add(subject)

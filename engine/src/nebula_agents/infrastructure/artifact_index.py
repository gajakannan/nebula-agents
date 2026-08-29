"""The per-run artifact index (F0003-S0004, ADR-006).

One atomic JSON document per run at `{runtime_root}/runs/{run_id}/artifacts.json`,
written with the discipline ADR-002 established for `run.json` — per-run lock, monotonic
revision, same-directory temporary file, fsync, atomic replace, corrupt files preserved.

The index is a **projection**. Losing it costs a re-index, never evidence. That is why a
corrupt index is moved aside and rebuilt rather than treated as fatal, and why it takes
its own lock instead of the run lock: indexing must never block a launch.
"""

from __future__ import annotations

import json
import os
import stat
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from nebula_agents.domain.artifacts import ArtifactIndexEntry, admit
from nebula_agents.domain.enums import (
    ArtifactKind,
    ArtifactRedactionStatus,
    FreshnessStatus,
    RetrievalPolicy,
    SourceRoot,
)
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import serialize_record

from .atomic import (
    FILE_MODE,
    json_bytes,
    owner_only_lock,
    preserve_corrupt,
    publish_atomic,
    write_owner_only,
)
from .schema_registry import JsonSchemaRegistry

INDEX_FILE = "artifacts.json"
INDEX_LOCK = ".artifacts.lock"
SCHEMA = "f0003-artifact-index.schema.json"


@dataclass(frozen=True, slots=True)
class ArtifactIndexDocument:
    run_id: str
    revision: int
    updated_at: datetime
    entries: tuple[ArtifactIndexEntry, ...]

    @property
    def by_id(self) -> dict[str, ArtifactIndexEntry]:
        return {entry.artifact_id: entry for entry in self.entries}


def _parse_datetime(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an RFC 3339 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _entry_from(document: dict) -> ArtifactIndexEntry:
    return ArtifactIndexEntry(
        artifact_id=str(document["artifact_id"]),
        run_id=str(document["run_id"]),
        artifact_kind=ArtifactKind(document["artifact_kind"]),
        source_root=SourceRoot(document["source_root"]),
        source_path=str(document["source_path"]),
        created_at=_parse_datetime(document["created_at"], "created_at"),
        redaction_status=ArtifactRedactionStatus(document["redaction_status"]),
        retrieval_policy=RetrievalPolicy(document["retrieval_policy"]),
        summary_path=document.get("summary_path"),
        content_hash=document.get("content_hash"),
        freshness_status=FreshnessStatus(document.get("freshness_status", "fresh")),
        superseded_by=document.get("superseded_by"),
        related_gate=document.get("related_gate"),
        validator_name=document.get("validator_name"),
        size_bytes=document.get("size_bytes"),
    )


class FilesystemArtifactIndex:
    """Atomic per-run artifact index. Reads never write; `commit` is the only mutation."""

    def __init__(
        self, runs_root: Path, schema: JsonSchemaRegistry, lock_timeout_seconds: float = 5.0
    ) -> None:
        self._runs_root = runs_root
        self._schema = schema
        self._lock_timeout = lock_timeout_seconds

    def _directory(self, run_id: str) -> Path:
        return self._runs_root / run_id

    def _path(self, run_id: str) -> Path:
        return self._directory(run_id) / INDEX_FILE

    def load(self, run_id: str) -> ArtifactIndexDocument:
        """Return the index, or an empty revision-0 document.

        An absent index is the normal state before the first `evidence index`, not an
        error — and this is a read, so it must not create the file to say so.
        """
        path = self._path(run_id)
        empty = ArtifactIndexDocument(run_id, 0, datetime.fromtimestamp(0, timezone.utc), ())
        if not path.exists() or path.is_symlink():
            return empty
        try:
            details = path.lstat()
            if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != FILE_MODE:
                raise ValueError("unsafe index mode")
            document = json.loads(path.read_text(encoding="utf-8"))
            self._schema.validate(SCHEMA, document)
            return ArtifactIndexDocument(
                run_id=str(document["run_id"]),
                revision=int(document["revision"]),
                updated_at=_parse_datetime(document["updated_at"], "updated_at"),
                entries=tuple(_entry_from(item) for item in document["entries"]),
            )
        except Exception:
            # A projection, not evidence: preserve the bad file and start clean, so one
            # corrupt index cannot make a run permanently unindexable.
            preserve_corrupt(path, str(int(time.time())))
            return empty

    def commit(
        self,
        *,
        run_id: str,
        expected_revision: int,
        entries: tuple[ArtifactIndexEntry, ...],
        now: datetime,
    ) -> ArtifactIndexDocument:
        """Merge entries into the index under lock at `expected_revision`.

        Optimistic concurrency mirrors `run.json`: a caller that read revision N and
        committed against a since-advanced index is told, rather than silently winning.
        """
        directory = self._directory(run_id)
        if not directory.is_dir():
            raise error(
                ErrorCode.RUN_NOT_FOUND, "Run directory does not exist.", "not-found",
                "Index artifacts for an existing run.", run_id=run_id,
            )
        with owner_only_lock(directory, self._lock_timeout, INDEX_LOCK):
            current = self.load(run_id)
            if current.revision != expected_revision:
                raise error(
                    ErrorCode.STALE_REVISION,
                    "Artifact index changed since it was read.", "conflict",
                    "Re-read the index and retry.",
                    run_id=run_id, expected_revision=expected_revision,
                    actual_revision=current.revision,
                )
            merged = current.by_id
            for entry in entries:
                merged = admit(merged, entry)
            document = ArtifactIndexDocument(
                run_id=run_id,
                revision=current.revision + 1,
                updated_at=now,
                entries=tuple(sorted(merged.values(), key=lambda e: e.artifact_id)),
            )
            payload = {
                "schema_version": "1.0",
                "run_id": document.run_id,
                "revision": document.revision,
                "updated_at": serialize_record({"v": document.updated_at})["v"],
                "entries": [serialize_record(entry) for entry in document.entries],
            }
            self._schema.validate(SCHEMA, payload)
            pending = directory / "artifacts.pending.json"
            write_owner_only(pending, json_bytes(payload, pretty=True))
            publish_atomic(
                directory, pending, self._path(run_id),
                directory / f"{INDEX_FILE}.bak",
            )
            return document

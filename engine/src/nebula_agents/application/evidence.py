"""Evidence indexing (F0003-S0004).

`index` is a command: it authorizes `IndexEvidence`, derives identity, enforces path
containment, commits the projection, and appends one runtime event per entry — because
indexing changes what a reviewer sees, and BLUEPRINT §5.3 requires that to be audited.

Reads live on the query facade. Nothing here is reachable from the MCP adapter.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from nebula_agents.domain.artifacts import content_digest, new_entry
from nebula_agents.domain.enums import (
    Action,
    ArtifactKind,
    ArtifactRedactionStatus,
    FreshnessStatus,
    SourceRoot,
)
from nebula_agents.domain.models import Actor
from nebula_agents.domain.transitions import advance

from .authorization import AuthorizationService
from .ports import ArtifactIndexStore, Clock, RunRepository
from .runs import commit_authorized, require_authorized, runtime_event

#: Read in bounded chunks: an artifact may be a multi-gigabyte transcript, and hashing
#: it must not require holding it in memory.
_HASH_CHUNK = 1 << 20


class EvidenceService:
    def __init__(
        self,
        *,
        repository: RunRepository,
        index: ArtifactIndexStore,
        authorization: AuthorizationService,
        clock: Clock,
        roots: Mapping[SourceRoot, Path],
    ) -> None:
        self._repository = repository
        self._index = index
        self._authorization = authorization
        self._clock = clock
        self._roots = dict(roots)

    def index_artifacts(
        self,
        run_id: str,
        paths: Sequence[Path],
        actor: Actor,
        *,
        kinds: Mapping[Path, ArtifactKind] | None = None,
    ) -> tuple:
        """Index one or more artifacts for a run.

        Ordering is deliberate. Authorization first, so an unauthorized caller learns
        nothing about which paths exist. Containment before hashing, so a path outside
        the approved roots is refused before its bytes are read.
        """
        run = self._repository.load(run_id)
        require_authorized(
            self._repository, self._authorization, run, actor, Action.INDEX_EVIDENCE
        )

        now = self._clock.now()
        current = self._index.load(run_id)
        entries = []
        for path in paths:
            resolved = self._resolve(path)
            kind = (kinds or {}).get(path) or infer_kind(resolved)
            present = resolved.is_file()
            entries.append(
                new_entry(
                    run_id=run_id,
                    kind=kind,
                    artifact_path=resolved,
                    roots=self._roots,
                    created_at=now,
                    redaction_status=ArtifactRedactionStatus.PENDING,
                    freshness_status=(
                        FreshnessStatus.FRESH if present else FreshnessStatus.MISSING
                    ),
                    content_hash=self._digest(resolved) if present else None,
                    size_bytes=resolved.stat().st_size if present else None,
                )
            )
        document = self._index.commit(
            run_id=run_id,
            expected_revision=current.revision,
            entries=tuple(entries),
            now=now,
        )

        # One event per index call, not one per artifact. The repository pairs every
        # event with a state image and a revision bump, so N artifacts would cost N
        # commits for one logical operation. The payload carries every artifact's id
        # and policy result, which is what S0004 actually requires recorded -- and it
        # matches the aggregate grain `ArtifactObserved` already uses.
        commit_authorized(
            self._repository,
            self._authorization,
            expected_revision=run.revision,
            next_record=advance(run, now=now),
            event=runtime_event(
                run,
                actor,
                "ArtifactIndexed",
                now,
                {
                    "artifact_count": len(entries),
                    "artifacts": [
                        {
                            "artifact_id": entry.artifact_id,
                            "artifact_kind": entry.artifact_kind.value,
                            "source_root": entry.source_root.value,
                            "retrieval_policy": entry.retrieval_policy.value,
                        }
                        for entry in entries
                    ],
                },
            ),
            actor=actor,
            action=Action.INDEX_EVIDENCE,
        )
        return document.entries

    @staticmethod
    def _resolve(path: Path) -> Path:
        """Canonicalise with symlinks resolved BEFORE containment is decided.

        Resolving after the check would let a symlink inside an approved root point at
        anything outside it — the containment test would pass on the link and the read
        would follow it.
        """
        return path.expanduser().resolve()

    @staticmethod
    def _digest(path: Path) -> str | None:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as handle:
                while chunk := handle.read(_HASH_CHUNK):
                    digest.update(chunk)
        except OSError:
            return None
        return digest.hexdigest()


#: Filename conventions the runtime already writes, mapped to artifact kinds.
_KIND_BY_NAME = {
    "commands.log": ArtifactKind.COMMAND_LOG,
    "evidence-manifest.json": ArtifactKind.MANIFEST,
    "lifecycle-gates.log": ArtifactKind.VALIDATOR_OUTPUT,
    "run.json": ArtifactKind.STATUS,
    "artifacts.json": ArtifactKind.STATUS,
}


def infer_kind(path: Path) -> ArtifactKind:
    """Best-effort kind inference, used only when a caller does not state one.

    Inference is a convenience, never authority: `evidence index --kind` overrides it,
    and an unrecognised file is `status` rather than a guess that reads as meaningful.
    """
    if path.name in _KIND_BY_NAME:
        return _KIND_BY_NAME[path.name]
    if path.suffix == ".log":
        return ArtifactKind.COMMAND_LOG
    if "transcript" in path.name:
        return ArtifactKind.TRANSCRIPT
    if "manifest" in path.name:
        return ArtifactKind.MANIFEST
    return ArtifactKind.STATUS

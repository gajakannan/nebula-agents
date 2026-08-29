"""Artifact identity, root selection, and the index entry (F0003-S0004, ADR-006).

Identity derives from an artifact's *location within a named approved root*, which is
what actually stays constant across re-index, restart, and a moved runtime directory.
Content hashing is kept, but as an attribute rather than as identity — that is what lets
two byte-identical artifacts keep distinct IDs.

Nothing here touches the filesystem beyond the canonical paths it is handed. Reading
bytes, locking, and writing the index belong to infrastructure.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Final, Mapping

from .enums import (
    ArtifactKind,
    ArtifactRedactionStatus,
    FreshnessStatus,
    RetrievalPolicy,
    SourceRoot,
)
from .errors import ErrorCode, error

#: Digest length in hex characters. Fixed at 12 rather than deferred to G0 (ADR-006,
#: resolving plan-review finding M2); the committed schema already pinned 12.
DIGEST_LENGTH: Final = 12

#: Tie-break order when two approved roots resolve to the same path (ADR-006 step 3).
#: Earlier wins. Order is fixed so the result never depends on configuration order.
ROOT_TIEBREAK: Final = (SourceRoot.RUNTIME, SourceRoot.EVIDENCE, SourceRoot.WORKSPACE)


def resolve_owning_root(
    artifact_path: Path, roots: Mapping[SourceRoot, Path]
) -> tuple[SourceRoot, Path]:
    """Return the approved root that owns `artifact_path`, by longest match.

    S0004 admits three approved roots and they nest in practice: the evidence root and
    the default runtime directory both sit inside the workspace, while an override can
    move the runtime root outside it entirely. A fixed root order would therefore give
    different answers under different configurations, and "relative to the run root" has
    no value at all for an artifact outside the run directory.

    Longest match makes the answer independent of configuration order and correct under
    any nesting. Ties break `runtime > evidence > workspace`.

    Callers must pass canonical paths with symlinks already resolved. Resolving here
    would be too late: containment must be decided on the real path, never on the link.

    Raises PATH_DENIED when no root is an ancestor. That is a policy violation to be
    recorded, not a crash — S0004 requires indexing to fail and say so.
    """
    candidates = []
    for root in ROOT_TIEBREAK:
        base = roots.get(root)
        if base is None:
            continue
        if artifact_path == base or base in artifact_path.parents:
            candidates.append((len(base.parts), -ROOT_TIEBREAK.index(root), root, base))
    if not candidates:
        raise error(
            ErrorCode.PATH_DENIED,
            "Artifact path is outside every approved root.",
            "forbidden",
            "Index only paths inside the workspace, runtime, or evidence root.",
            artifact_path=str(artifact_path),
        )
    _, _, root, base = max(candidates)
    return root, base


def relative_key(artifact_path: Path, root_path: Path) -> str:
    """The canonical POSIX path of an artifact relative to its owning root."""
    return PurePosixPath(artifact_path.relative_to(root_path)).as_posix()


def path_digest(relative: str) -> str:
    return hashlib.sha256(relative.encode("utf-8")).hexdigest()[:DIGEST_LENGTH]


def derive_artifact_id(
    run_id: str,
    kind: ArtifactKind,
    artifact_path: Path,
    roots: Mapping[SourceRoot, Path],
) -> str:
    """`{run_id}/{artifact_kind}/{root_key}-{path_digest12}` (ADR-006).

    The ID is opaque to callers. `root_key` must not be parsed to reconstruct a
    filesystem path — it identifies which root the digest is relative to, nothing more.
    """
    root, base = resolve_owning_root(artifact_path, roots)
    return f"{run_id}/{kind.value}/{root.key}-{path_digest(relative_key(artifact_path, base))}"


def content_digest(payload: bytes) -> str:
    """Full SHA-256 over the bytes.

    Deliberately not truncated and deliberately not identity: this powers duplicate
    linking and staleness only.
    """
    return hashlib.sha256(payload).hexdigest()


def retrieval_policy_for(
    redaction: ArtifactRedactionStatus, freshness: FreshnessStatus
) -> RetrievalPolicy:
    """Derive the retrieval policy rather than letting a caller assert one.

    A failed redaction forces `Blocked`, and it outranks everything else — an artifact
    that is both missing and redaction-failed must not be reported as merely missing,
    because `Missing` reads as recoverable and `Blocked` does not.
    """
    if redaction is ArtifactRedactionStatus.FAIL:
        return RetrievalPolicy.BLOCKED
    if freshness is FreshnessStatus.MISSING:
        return RetrievalPolicy.MISSING
    if redaction is ArtifactRedactionStatus.PENDING:
        return RetrievalPolicy.SUMMARY_ONLY
    return RetrievalPolicy.LOCAL_ONLY


@dataclass(frozen=True, slots=True)
class ArtifactIndexEntry:
    """One indexed evidence artifact.

    `source_root` is persisted so an entry is self-describing: a reader can interpret
    the ID without holding the configuration that produced it.
    """

    artifact_id: str
    run_id: str
    artifact_kind: ArtifactKind
    source_root: SourceRoot
    source_path: str
    created_at: datetime
    redaction_status: ArtifactRedactionStatus
    retrieval_policy: RetrievalPolicy
    summary_path: str | None = None
    content_hash: str | None = None
    freshness_status: FreshnessStatus = FreshnessStatus.FRESH
    superseded_by: str | None = None
    related_gate: str | None = None
    validator_name: str | None = None
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        expected = retrieval_policy_for(self.redaction_status, self.freshness_status)
        if self.retrieval_policy is not expected:
            raise error(
                ErrorCode.CONFLICT,
                "Retrieval policy contradicts redaction and freshness state.",
                "conflict",
                "Construct entries with `new_entry`, which derives the policy.",
                artifact_id=self.artifact_id,
            )

    def marked_missing(self) -> ArtifactIndexEntry:
        """An artifact absent at retrieval keeps its entry and ID.

        References stay resolvable and explain themselves, which is the point: a
        dangling ID that returns nothing is worse than one that returns "missing".
        """
        return replace(
            self,
            freshness_status=FreshnessStatus.MISSING,
            retrieval_policy=retrieval_policy_for(
                self.redaction_status, FreshnessStatus.MISSING
            ),
        )

    def superseded(self, by_artifact_id: str) -> ArtifactIndexEntry:
        """An artifact moved within a run is delete-plus-add; the prior ID is kept."""
        return replace(self, superseded_by=by_artifact_id)


def new_entry(
    *,
    run_id: str,
    kind: ArtifactKind,
    artifact_path: Path,
    roots: Mapping[SourceRoot, Path],
    created_at: datetime,
    redaction_status: ArtifactRedactionStatus,
    freshness_status: FreshnessStatus = FreshnessStatus.FRESH,
    content_hash: str | None = None,
    summary_path: str | None = None,
    related_gate: str | None = None,
    validator_name: str | None = None,
    size_bytes: int | None = None,
) -> ArtifactIndexEntry:
    """Build an entry with identity, owning root, and retrieval policy all derived."""
    root, base = resolve_owning_root(artifact_path, roots)
    relative = relative_key(artifact_path, base)
    return ArtifactIndexEntry(
        artifact_id=f"{run_id}/{kind.value}/{root.key}-{path_digest(relative)}",
        run_id=run_id,
        artifact_kind=kind,
        source_root=root,
        source_path=relative,
        created_at=created_at,
        redaction_status=redaction_status,
        retrieval_policy=retrieval_policy_for(redaction_status, freshness_status),
        summary_path=summary_path,
        content_hash=content_hash,
        freshness_status=freshness_status,
        superseded_by=None,
        related_gate=related_gate,
        validator_name=validator_name,
        size_bytes=size_bytes,
    )


def admit(
    existing: Mapping[str, ArtifactIndexEntry], entry: ArtifactIndexEntry
) -> dict[str, ArtifactIndexEntry]:
    """Add an entry to an index, raising on a truncated-digest collision.

    Re-indexing the same path is idempotent: same path, same root, same ID, same
    `source_path`, so the entry replaces itself. A *different* path colliding on the
    12-hex digest within one run and kind is a conflict and must be loud — silently
    overwriting would lose evidence, which no re-index could recover.
    """
    prior = existing.get(entry.artifact_id)
    if prior is not None and prior.source_path != entry.source_path:
        raise error(
            ErrorCode.DIGEST_COLLISION,
            "Two distinct artifact paths produced the same identifier.",
            "conflict",
            "Re-index after moving one artifact; do not overwrite the existing entry.",
            artifact_id=entry.artifact_id,
        )
    return {**existing, entry.artifact_id: entry}

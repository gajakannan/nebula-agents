"""Evidence indexing and summarization (F0003-S0004, F0003-S0005).

Both are commands: each authorizes `IndexEvidence`, writes a projection, and appends a
runtime event — because both change what a reviewer sees, and BLUEPRINT §5.3 requires
that to be audited.

Reads live on the query facade. Nothing here is reachable from the MCP adapter.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace as _replace
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from nebula_agents.domain.artifacts import content_digest, new_entry, retrieval_policy_for
from nebula_agents.domain.enums import (
    Action,
    ArtifactKind,
    ArtifactRedactionStatus,
    FreshnessStatus,
    SourceRoot,
)
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import Actor
from nebula_agents.domain.summaries import ArtifactSummary, resolve_status, truncate
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
        summaries=None,
        extractor=None,
        marker_limit: int = 200,
    ) -> None:
        self._repository = repository
        self._index = index
        self._authorization = authorization
        self._clock = clock
        self._roots = dict(roots)
        self._summaries = summaries
        self._extractor = extractor
        self._marker_limit = marker_limit

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

    def summarize(self, run_id: str, actor: Actor, artifact_id: str | None = None) -> tuple:
        """Summarize one artifact, or every artifact in a run.

        Summarization is a command: it authorizes `IndexEvidence`, writes summary
        artifacts, and updates the index with each summary's path and resolved redaction
        status. A summary failure leaves the artifact indexed with
        `summary_status: Failed` -- an artifact whose summary could not be produced is
        still evidence, and dropping the entry would lose the only record of it.
        """
        run = self._repository.load(run_id)
        require_authorized(
            self._repository, self._authorization, run, actor, Action.INDEX_EVIDENCE
        )
        if self._summaries is None:
            raise error(
                ErrorCode.COMMAND_FAILED, "Summary store is unavailable.", "command-failed",
                "Rebuild the application composition.",
            )

        now = self._clock.now()
        current = self._index.load(run_id)
        targets = [
            entry for entry in current.entries
            if artifact_id is None or entry.artifact_id == artifact_id
        ]
        if artifact_id is not None and not targets:
            raise error(
                ErrorCode.ARTIFACT_NOT_FOUND, "Artifact is not indexed.", "not-found",
                "Run evidence index for this run, then retry.", artifact_id=artifact_id,
            )

        produced, updated = [], []
        for entry in targets:
            summary, redaction = self._summarize_one(entry, now)
            self._summaries.save(run_id, summary)
            produced.append(summary)
            updated.append(
                _replace(
                    entry,
                    summary_path=self._summaries.relative_path(summary.summary_id),
                    redaction_status=redaction,
                    retrieval_policy=retrieval_policy_for(redaction, entry.freshness_status),
                )
            )

        if updated:
            self._index.commit(
                run_id=run_id, expected_revision=current.revision,
                entries=tuple(updated), now=now,
            )
            blocked = sum(
                1 for s in produced if s.summary_status.value in {"Blocked", "Failed"}
            )
            commit_authorized(
                self._repository,
                self._authorization,
                expected_revision=run.revision,
                next_record=advance(run, now=now),
                event=runtime_event(
                    run, actor,
                    "SummaryBlocked" if blocked and blocked == len(produced) else "ArtifactSummarized",
                    now,
                    {
                        "summary_count": len(produced),
                        "rule_set_version": self._extractor.rule_set_version,
                        "summaries": [
                            {
                                "artifact_id": s.artifact_id,
                                "summary_status": s.summary_status.value,
                                "redaction_status": s.redaction_status.value,
                            }
                            for s in produced
                        ],
                    },
                ),
                actor=actor,
                action=Action.INDEX_EVIDENCE,
            )
        return tuple(produced)

    def _summarize_one(self, entry, now):
        """Extract, resolve status, and truncate -- keeping every failure marker."""
        root = self._roots[entry.source_root]
        path = root / entry.source_path
        try:
            payload = path.read_bytes()
            readable = True
        except OSError:
            payload, readable = b"", False

        extraction, supported, extracted = self._extractor.extract(entry.artifact_kind, payload)
        # Findings mean a credential was present and replaced. The artifact is still
        # summarizable -- the marker is in the output -- so this is Pass, not Fail. A
        # Fail is reserved for redaction that could not complete.
        redaction = (
            ArtifactRedactionStatus.NOT_REQUIRED if not supported
            else ArtifactRedactionStatus.PASS if readable
            else ArtifactRedactionStatus.PENDING
        )
        key_events, dropped = truncate(
            extraction.key_events, extraction.failure_markers, self._marker_limit
        )
        status = resolve_status(
            extracted=extracted and readable,
            redaction=redaction,
            supported=supported,
            dropped_failure_markers=dropped,
            input_complete=extraction.input_complete and readable,
        )
        return (
            ArtifactSummary(
                summary_id=summary_id_for(entry.artifact_id),
                artifact_id=entry.artifact_id,
                artifact_kind=entry.artifact_kind,
                summary_status=status,
                redaction_status=redaction,
                rule_set_version=self._extractor.rule_set_version,
                generated_at=now,
                source_reference=entry.artifact_id,
                key_events=key_events,
                failure_markers=extraction.failure_markers,
                warning_markers=extraction.warning_markers,
                open_questions=extraction.open_questions,
                truncation_count=dropped or None,
                last_observed_marker=extraction.last_observed_marker,
            ),
            redaction,
        )




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
    stem = path.name.lower()
    # Name hints are checked before the extension: a file called `validator.txt` is
    # validator output whatever it is suffixed with, and misfiling it as `status` costs
    # more than the guess is worth -- `status` has no summarizer rules for failures, so
    # a real validator failure would never reach a learning proposal.
    if "transcript" in stem:
        return ArtifactKind.TRANSCRIPT
    if "validator" in stem or "gates" in stem:
        return ArtifactKind.VALIDATOR_OUTPUT
    if "manifest" in stem:
        return ArtifactKind.MANIFEST
    if "metric" in stem:
        return ArtifactKind.METRIC
    if path.suffix in (".log", ".jsonl"):
        return ArtifactKind.COMMAND_LOG
    return ArtifactKind.STATUS

def summary_id_for(artifact_id: str) -> str:
    """Derived from the artifact id, so re-summarizing overwrites rather than accumulates."""
    return hashlib.sha256(artifact_id.encode("utf-8")).hexdigest()[:16]

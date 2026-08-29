"""Deterministic artifact summaries (F0003-S0005, ADR-008).

Summaries are rule-extracted. No model call participates in producing one, and identical
input yields byte-identical output — asserted by fixture, not assumed.

The invariant that shapes this module: **failure markers are never dropped for size.**
When a size limit would require dropping one, the summary becomes `Partial` rather than
`Pass`, because a smaller summary that still reads as complete is worse than one that
admits it is not.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from .enums import ArtifactKind, ArtifactRedactionStatus, SummaryStatus
from .errors import ErrorCode, error


@dataclass(frozen=True, slots=True)
class SummaryMarker:
    """One extracted event. `ordinal` fixes the order, so output cannot drift."""

    ordinal: int
    label: str
    detail: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None


@dataclass(frozen=True, slots=True)
class ArtifactSummary:
    summary_id: str
    artifact_id: str
    artifact_kind: ArtifactKind
    summary_status: SummaryStatus
    redaction_status: ArtifactRedactionStatus
    rule_set_version: str
    generated_at: datetime
    source_reference: str
    key_events: tuple[SummaryMarker, ...]
    failure_markers: tuple[SummaryMarker, ...]
    warning_markers: tuple[SummaryMarker, ...] = ()
    open_questions: tuple[str, ...] = ()
    truncation_count: int | None = None
    last_observed_marker: str | None = None

    def __post_init__(self) -> None:
        if self.redaction_status is ArtifactRedactionStatus.FAIL and (
            self.summary_status is not SummaryStatus.BLOCKED
        ):
            raise error(
                ErrorCode.REDACTION_FAILED,
                "A summary whose redaction failed must be Blocked.",
                "gate-blocked",
                "Re-run evidence summarize after resolving the redaction failure.",
                artifact_id=self.artifact_id,
            )
        for group in (self.key_events, self.failure_markers, self.warning_markers):
            ordinals = [marker.ordinal for marker in group]
            if ordinals != sorted(ordinals):
                raise error(
                    ErrorCode.CONFLICT,
                    "Summary markers are not in ordinal order.",
                    "conflict",
                    "Emit markers in extraction order; determinism depends on it.",
                    artifact_id=self.artifact_id,
                )


def resolve_status(
    *,
    extracted: bool,
    redaction: ArtifactRedactionStatus,
    supported: bool,
    dropped_failure_markers: int,
    input_complete: bool,
) -> SummaryStatus:
    """The single place summary status is decided.

    Ordering matters and is deliberate: redaction outranks everything, because a summary
    that leaks is worse than one that is missing; an unsupported kind is reported before
    extraction failure, because "binary artifact" is more useful than "extraction
    failed"; and a dropped failure marker downgrades a would-be `Pass` to `Partial`.
    """
    if redaction is ArtifactRedactionStatus.FAIL:
        return SummaryStatus.BLOCKED
    if not supported:
        return SummaryStatus.UNSUPPORTED
    if not extracted:
        return SummaryStatus.FAILED
    if dropped_failure_markers > 0 or not input_complete:
        return SummaryStatus.PARTIAL
    return SummaryStatus.PASS


def truncate(
    markers: tuple[SummaryMarker, ...],
    failures: tuple[SummaryMarker, ...],
    limit: int,
) -> tuple[tuple[SummaryMarker, ...], int]:
    """Trim passing noise to `limit`, keeping every failure marker.

    Returns the retained key events and the count discarded. Failure markers are passed
    in only so their budget is reserved — they are never candidates for removal, which
    is why they are a separate parameter rather than part of `markers`.
    """
    if limit < 0:
        raise ValueError("limit must be non-negative")
    budget = max(limit - len(failures), 0)
    if len(markers) <= budget:
        return markers, 0
    return markers[:budget], len(markers) - budget

"""Runtime metric derivation (F0003-S0006).

Metrics are **derived, never authoritative**. Every call recomputes from run state and
the artifact index, and `derived_from` pins the revisions it was computed against — so
recomputability is checkable rather than asserted, and a snapshot taken at older
revisions is *superseded*, not wrong.

This is a read. It appends no runtime event and writes nothing, which is why it lives on
the query side.
"""

from __future__ import annotations

from datetime import datetime

from nebula_agents.domain.enums import (
    ArtifactStatus,
    FreshnessStatus,
    MetricName,
    TranscriptStatus,
)
from nebula_agents.domain.metrics import (
    DerivedFrom,
    RuntimeMetricSnapshot,
    metric,
    not_applicable,
)


def derive(run, index_document, now: datetime) -> RuntimeMetricSnapshot:
    """Compute every metric in the closed set for one run.

    A metric that does not apply is emitted with `applicable: false`, never omitted and
    never zero. Omission and zero are both misreadings: "no gate wait recorded" is not
    "waited zero seconds", and a consumer that sees neither cannot tell which happened.
    """
    entries = index_document.entries
    metrics = [
        _duration(run, now),
        _gate_wait(run, now),
        *_validator_counts(run),
        _transcript_health(run),
        _evidence_freshness(entries),
        metric(MetricName.ARTIFACT_COUNT, len(entries)),
        _blocked_launches(run),
    ]
    return RuntimeMetricSnapshot(
        run_id=run.run_id,
        metric_generated_at=now,
        derived_from=DerivedFrom(
            run_revision=run.revision,
            artifact_index_revision=index_document.revision,
        ),
        metrics=tuple(metrics),
    )


def _duration(run, now: datetime):
    started = getattr(run, "created_at", None)
    if started is None:
        return not_applicable(MetricName.RUN_DURATION_SECONDS)
    ended = getattr(run, "updated_at", None) or now
    return metric(MetricName.RUN_DURATION_SECONDS, max((ended - started).total_seconds(), 0.0))


def _gate_wait(run, now: datetime):
    """Time the run has spent waiting on a gate decision.

    Only meaningful while a gate is actually pending or blocked. A run whose gate was
    never engaged reports inapplicable rather than zero.
    """
    gate = getattr(run, "gate", None)
    if gate is None or gate.status.value not in {"Pending", "Blocked"}:
        return not_applicable(MetricName.GATE_WAIT_SECONDS)
    since = getattr(gate, "updated_at", None) or getattr(run, "updated_at", None)
    if since is None:
        return not_applicable(MetricName.GATE_WAIT_SECONDS)
    return metric(MetricName.GATE_WAIT_SECONDS, max((now - since).total_seconds(), 0.0))


def _validator_counts(run):
    latest = getattr(run, "latest_validator", None)
    if latest is None:
        return (
            not_applicable(MetricName.VALIDATOR_PASS_COUNT),
            not_applicable(MetricName.VALIDATOR_FAIL_COUNT),
            not_applicable(MetricName.LATEST_FAILING_VALIDATOR),
        )
    passed = 1 if latest.exit_code == 0 else 0
    return (
        metric(MetricName.VALIDATOR_PASS_COUNT, passed),
        metric(MetricName.VALIDATOR_FAIL_COUNT, 1 - passed),
        metric(MetricName.LATEST_FAILING_VALIDATOR, latest.key.value)
        if not passed
        else not_applicable(MetricName.LATEST_FAILING_VALIDATOR),
    )


def _transcript_health(run):
    transcript = getattr(run, "transcript", None)
    if transcript is None or transcript.status is TranscriptStatus.DISABLED:
        return not_applicable(MetricName.TRANSCRIPT_HEALTH)
    return metric(MetricName.TRANSCRIPT_HEALTH, transcript.status.value)


def _evidence_freshness(entries):
    """The worst freshness across the index, because that is what a reviewer must act on.

    An index that is 90% fresh and 10% missing is not "mostly fresh" — the missing
    artifacts are exactly the ones a reviewer will fail to open.
    """
    if not entries:
        return not_applicable(MetricName.EVIDENCE_FRESHNESS)
    order = [
        FreshnessStatus.MISSING,
        FreshnessStatus.STALE,
        FreshnessStatus.UNKNOWN,
        FreshnessStatus.FRESH,
    ]
    present = {entry.freshness_status for entry in entries}
    worst = next(status for status in order if status in present)
    return metric(MetricName.EVIDENCE_FRESHNESS, worst.value)


def _blocked_launches(run):
    artifacts = getattr(run, "artifacts", ()) or ()
    denied = sum(1 for item in artifacts if item.status is ArtifactStatus.DENIED)
    return metric(MetricName.BLOCKED_LAUNCH_COUNT, denied)

"""F0003-S0006 — metric derivation.

Metrics are derived, never authoritative. These assert the two properties that make that
claim checkable: `derived_from` pins the revisions used, and a metric that does not apply
is emitted with a null value rather than omitted or zeroed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from nebula_agents.application.metrics import derive
from nebula_agents.domain.enums import (
    ArtifactStatus,
    FreshnessStatus,
    GateStatus,
    MetricName,
    TranscriptStatus,
    ValidatorKey,
)

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def index(entries=(), revision: int = 1):
    return SimpleNamespace(revision=revision, entries=tuple(entries))


def entry(freshness: FreshnessStatus):
    return SimpleNamespace(freshness_status=freshness)


def run(**overrides):
    base = dict(
        run_id="2026-08-29-16075bda",
        revision=4,
        created_at=NOW - timedelta(minutes=10),
        updated_at=NOW - timedelta(minutes=1),
        gate=SimpleNamespace(status=GateStatus.UNKNOWN, updated_at=NOW),
        latest_validator=None,
        transcript=None,
        artifacts=(),
    )
    return SimpleNamespace(**{**base, **overrides})


def by_name(snapshot) -> dict[MetricName, object]:
    return {m.metric_name: m for m in snapshot.metrics}


def test_every_metric_in_the_closed_set_is_emitted() -> None:
    """Never omitted. A consumer that sees a missing key cannot tell why."""
    snapshot = derive(run(), index(), NOW)
    assert {m.metric_name for m in snapshot.metrics} == set(MetricName)


def test_derived_from_pins_the_revisions_the_snapshot_was_computed_against() -> None:
    """Without this, a stale snapshot is indistinguishable from a current one."""
    snapshot = derive(run(revision=7), index(revision=3), NOW)
    assert snapshot.derived_from.run_revision == 7
    assert snapshot.derived_from.artifact_index_revision == 3


def test_run_duration_is_measured_between_creation_and_last_update() -> None:
    assert by_name(derive(run(), index(), NOW))[MetricName.RUN_DURATION_SECONDS].metric_value == 540.0


def test_gate_wait_is_inapplicable_when_no_gate_is_engaged() -> None:
    """Not zero. "No gate wait recorded" is not "waited zero seconds"."""
    metric = by_name(derive(run(), index(), NOW))[MetricName.GATE_WAIT_SECONDS]
    assert metric.applicable is False and metric.metric_value is None


@pytest.mark.parametrize("status", [GateStatus.PENDING, GateStatus.BLOCKED])
def test_gate_wait_is_measured_while_a_gate_is_pending_or_blocked(status: GateStatus) -> None:
    waiting = run(gate=SimpleNamespace(status=status, updated_at=NOW - timedelta(minutes=5)))
    metric = by_name(derive(waiting, index(), NOW))[MetricName.GATE_WAIT_SECONDS]
    assert metric.metric_value == 300.0


def test_validator_metrics_are_inapplicable_before_any_validator_runs() -> None:
    metrics = by_name(derive(run(), index(), NOW))
    for name in (
        MetricName.VALIDATOR_PASS_COUNT,
        MetricName.VALIDATOR_FAIL_COUNT,
        MetricName.LATEST_FAILING_VALIDATOR,
    ):
        assert metrics[name].applicable is False


def test_a_failing_validator_is_counted_and_named() -> None:
    failed = run(latest_validator=SimpleNamespace(exit_code=1, key=ValidatorKey.STORIES))
    metrics = by_name(derive(failed, index(), NOW))
    assert metrics[MetricName.VALIDATOR_FAIL_COUNT].metric_value == 1
    assert metrics[MetricName.LATEST_FAILING_VALIDATOR].metric_value == "stories"


def test_a_passing_validator_leaves_latest_failing_inapplicable() -> None:
    passed = run(latest_validator=SimpleNamespace(exit_code=0, key=ValidatorKey.STORIES))
    metrics = by_name(derive(passed, index(), NOW))
    assert metrics[MetricName.VALIDATOR_PASS_COUNT].metric_value == 1
    assert metrics[MetricName.LATEST_FAILING_VALIDATOR].applicable is False


def test_evidence_freshness_reports_the_worst_entry_not_an_average() -> None:
    """An index 90% fresh and 10% missing is not "mostly fresh".

    The missing artifacts are exactly the ones a reviewer will fail to open.
    """
    mixed = index([entry(FreshnessStatus.FRESH)] * 9 + [entry(FreshnessStatus.MISSING)])
    assert by_name(derive(run(), mixed, NOW))[MetricName.EVIDENCE_FRESHNESS].metric_value == "missing"


def test_evidence_freshness_is_inapplicable_for_an_empty_index() -> None:
    assert by_name(derive(run(), index(), NOW))[MetricName.EVIDENCE_FRESHNESS].applicable is False


def test_transcript_health_is_inapplicable_when_capture_is_disabled() -> None:
    disabled = run(transcript=SimpleNamespace(status=TranscriptStatus.DISABLED))
    assert by_name(derive(disabled, index(), NOW))[MetricName.TRANSCRIPT_HEALTH].applicable is False


def test_blocked_launches_count_denied_artifacts() -> None:
    denied = run(artifacts=(SimpleNamespace(status=ArtifactStatus.DENIED),
                            SimpleNamespace(status=ArtifactStatus.AVAILABLE)))
    assert by_name(derive(denied, index(), NOW))[MetricName.BLOCKED_LAUNCH_COUNT].metric_value == 1


def test_deriving_twice_from_unchanged_state_gives_an_identical_snapshot() -> None:
    """Recomputability is the claim; this is the check."""
    fixed = run()
    first, second = derive(fixed, index(), NOW), derive(fixed, index(), NOW)
    assert first == second

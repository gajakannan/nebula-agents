"""F0003 domain records: summaries, capabilities, proposals, metrics.

These assert the invariants that later steps rely on being true by construction rather
than re-checking at every call site.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from nebula_agents.domain.capabilities import (
    Capability,
    freshness_of,
    launch_decision,
    report_for,
)
from nebula_agents.domain.enums import (
    ArtifactKind,
    ArtifactRedactionStatus,
    CapabilityName,
    CapabilityRequirement,
    Confidence,
    FreshnessStatus,
    LaunchDecision,
    MetricKind,
    MetricName,
    ProbeResult,
    ProposalDecisionKind,
    ProposalStatus,
    ProviderKey,
    ProviderMode,
    ReviewerRole,
    SummaryStatus,
)
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.metrics import (
    METRIC_KINDS,
    DerivedFrom,
    RuntimeMetricSnapshot,
    metric,
    not_applicable,
)
from nebula_agents.domain.models import serialize_record
from nebula_agents.domain.proposals import (
    LearningProposal,
    ProposalDecision,
    assert_target_allowed,
    authorized_role,
    suppressed_by_rejection,
)
from nebula_agents.domain.summaries import (
    ArtifactSummary,
    SummaryMarker,
    resolve_status,
    truncate,
)

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Summaries (S0005, ADR-008)
# --------------------------------------------------------------------------- #
def test_truncation_never_drops_a_failure_marker() -> None:
    """The rule the whole module is shaped around.

    A summary that silently loses the failure it was written to surface is worse than
    no summary at all.
    """
    failures = tuple(SummaryMarker(i, f"fail-{i}") for i in range(3))
    passing = tuple(SummaryMarker(10 + i, f"ok-{i}") for i in range(20))
    kept, dropped = truncate(passing, failures, limit=5)
    assert len(kept) == 2 and dropped == 18


def test_a_dropped_failure_marker_downgrades_pass_to_partial() -> None:
    assert resolve_status(
        extracted=True, redaction=ArtifactRedactionStatus.PASS, supported=True,
        dropped_failure_markers=1, input_complete=True,
    ) is SummaryStatus.PARTIAL


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(extracted=True, redaction=ArtifactRedactionStatus.FAIL, supported=True,
              dropped_failure_markers=0, input_complete=True), SummaryStatus.BLOCKED),
        (dict(extracted=True, redaction=ArtifactRedactionStatus.PASS, supported=False,
              dropped_failure_markers=0, input_complete=True), SummaryStatus.UNSUPPORTED),
        (dict(extracted=False, redaction=ArtifactRedactionStatus.PASS, supported=True,
              dropped_failure_markers=0, input_complete=True), SummaryStatus.FAILED),
        (dict(extracted=True, redaction=ArtifactRedactionStatus.PASS, supported=True,
              dropped_failure_markers=0, input_complete=False), SummaryStatus.PARTIAL),
        (dict(extracted=True, redaction=ArtifactRedactionStatus.PASS, supported=True,
              dropped_failure_markers=0, input_complete=True), SummaryStatus.PASS),
    ],
)
def test_summary_status_precedence(kwargs: dict, expected: SummaryStatus) -> None:
    """Redaction outranks an unsupported kind, which outranks extraction failure."""
    assert resolve_status(**kwargs) is expected


def test_a_redaction_failure_cannot_be_recorded_as_a_passing_summary() -> None:
    with pytest.raises(NebulaError) as caught:
        ArtifactSummary(
            summary_id="s", artifact_id="a", artifact_kind=ArtifactKind.TRANSCRIPT,
            summary_status=SummaryStatus.PASS,
            redaction_status=ArtifactRedactionStatus.FAIL,
            rule_set_version="1.0", generated_at=NOW, source_reference="ref",
            key_events=(), failure_markers=(),
        )
    assert caught.value.code is ErrorCode.REDACTION_FAILED


def test_out_of_order_markers_are_rejected_because_determinism_depends_on_order() -> None:
    with pytest.raises(NebulaError):
        ArtifactSummary(
            summary_id="s", artifact_id="a", artifact_kind=ArtifactKind.COMMAND_LOG,
            summary_status=SummaryStatus.PASS,
            redaction_status=ArtifactRedactionStatus.PASS,
            rule_set_version="1.0", generated_at=NOW, source_reference="ref",
            key_events=(SummaryMarker(2, "b"), SummaryMarker(1, "a")),
            failure_markers=(),
        )


# --------------------------------------------------------------------------- #
# Capabilities (S0002)
# --------------------------------------------------------------------------- #
def required(result: ProbeResult, *, fallback: bool = False) -> Capability:
    return Capability(CapabilityName.LAUNCH, CapabilityRequirement.REQUIRED, result,
                      fallback_available=fallback)


def test_launch_is_allowed_only_when_every_required_capability_passes() -> None:
    assert launch_decision((required(ProbeResult.PASS),))[0] is LaunchDecision.ALLOWED


def test_a_required_timeout_blocks_launch() -> None:
    """A probe that times out is not a pass: an unanswered probe is not a positive one."""
    decision, reason = launch_decision((required(ProbeResult.TIMEOUT),))
    assert decision is LaunchDecision.BLOCKED
    assert "launch" in reason


def test_an_explicit_fallback_allows_launch_with_fallback() -> None:
    decision, _ = launch_decision((required(ProbeResult.FAIL, fallback=True),))
    assert decision is LaunchDecision.ALLOWED_WITH_FALLBACK


def test_an_optional_failure_does_not_block() -> None:
    optional = Capability(
        CapabilityName.TRANSCRIPT, CapabilityRequirement.OPTIONAL, ProbeResult.FAIL
    )
    assert launch_decision((required(ProbeResult.PASS), optional))[0] is LaunchDecision.ALLOWED


def test_a_report_cannot_assert_a_decision_its_capabilities_contradict() -> None:
    report = report_for(
        provider_key=ProviderKey.CODEX, provider_mode=ProviderMode.TMUX_NATIVE,
        report_generated_at=NOW, capabilities=(required(ProbeResult.FAIL),),
    )
    assert report.launch_decision is LaunchDecision.BLOCKED
    assert report.blocked_reason


def test_report_freshness_is_derived_from_max_age() -> None:
    age = timedelta(hours=1)
    assert freshness_of(NOW - timedelta(minutes=30), NOW, age) is FreshnessStatus.FRESH
    assert freshness_of(NOW - timedelta(hours=2), NOW, age) is FreshnessStatus.STALE
    assert freshness_of(NOW + timedelta(hours=1), NOW, age) is FreshnessStatus.UNKNOWN


# --------------------------------------------------------------------------- #
# Proposals (S0006, ADR-009)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("target", "role"),
    [
        ("planning-mds/security/f0001-authorization-model.md", ReviewerRole.SECURITY),
        ("planning-mds/architecture/SOLUTION-PATTERNS.md", ReviewerRole.ARCHITECT),
        ("agents/actions/feature.md", ReviewerRole.ARCHITECT),
        ("planning-mds/features/REGISTRY.md", ReviewerRole.PRODUCT_MANAGER),
    ],
)
def test_authorized_role_is_resolved_from_the_target_document(
    target: str, role: ReviewerRole
) -> None:
    assert authorized_role(target) is role


@pytest.mark.parametrize(
    "target",
    ["/etc/passwd", "../outside.md", "engine/src/nebula_agents/bootstrap.py"],
)
def test_a_target_outside_the_allowlist_is_refused_at_generation(target: str) -> None:
    with pytest.raises(NebulaError) as caught:
        assert_target_allowed(target)
    assert caught.value.code is ErrorCode.PROPOSAL_TARGET_FORBIDDEN
    assert caught.value.exit_code == 5


def proposal(**overrides) -> LearningProposal:
    base = dict(
        proposal_id="p1", run_id="2026-08-29-16075bda", generated_at=NOW,
        source_artifact_ids=("run/transcript/rt-abcdef012345",),
        target_document="planning-mds/architecture/SOLUTION-PATTERNS.md",
        proposal_summary="Record the retry rule.", proposal_status=ProposalStatus.DRAFT,
        source_content_hashes=("h1",), confidence=Confidence.MEDIUM,
    )
    return LearningProposal(**{**base, **overrides})


def test_a_proposal_must_link_to_source_evidence() -> None:
    with pytest.raises(NebulaError):
        proposal(source_artifact_ids=())


def test_owning_the_run_does_not_confer_the_right_to_decide_its_proposals() -> None:
    """The rule a Security Reviewer needs, enforced where the decision is appended."""
    with pytest.raises(NebulaError) as caught:
        proposal().decide(
            ProposalDecision(NOW, ProposalDecisionKind.ACCEPTED, ReviewerRole.PRODUCT_MANAGER)
        )
    assert caught.value.code is ErrorCode.FORBIDDEN


def test_reject_and_archive_require_a_reason() -> None:
    for kind in (ProposalDecisionKind.REJECTED, ProposalDecisionKind.ARCHIVED):
        with pytest.raises(NebulaError) as caught:
            ProposalDecision(NOW, kind, ReviewerRole.ARCHITECT)
        assert caught.value.exit_code == 2
    ProposalDecision(NOW, ProposalDecisionKind.ACCEPTED, ReviewerRole.ARCHITECT)


def test_decisions_are_append_only() -> None:
    first = proposal().decide(
        ProposalDecision(NOW, ProposalDecisionKind.EDITED, ReviewerRole.ARCHITECT)
    )
    second = first.decide(
        ProposalDecision(
            NOW + timedelta(hours=1), ProposalDecisionKind.REJECTED,
            ReviewerRole.ARCHITECT, decision_reason="superseded",
        )
    )
    assert len(second.decisions) == 2
    assert second.decisions[0] == first.decisions[0]
    assert second.proposal_status is ProposalStatus.REJECTED


def test_rejection_is_sticky_until_the_source_evidence_changes() -> None:
    rejected = proposal(proposal_status=ProposalStatus.REJECTED)
    assert suppressed_by_rejection(rejected, ("h1",)) is True
    assert suppressed_by_rejection(rejected, ("h2",)) is False
    assert suppressed_by_rejection(proposal(), ("h1",)) is False


def test_sticky_rejection_ignores_source_ordering() -> None:
    rejected = proposal(proposal_status=ProposalStatus.REJECTED,
                        source_content_hashes=("h1", "h2"))
    assert suppressed_by_rejection(rejected, ("h2", "h1")) is True


# --------------------------------------------------------------------------- #
# Metrics (S0006)
# --------------------------------------------------------------------------- #
def test_metric_kind_mapping_is_total_over_the_closed_name_set() -> None:
    assert set(METRIC_KINDS) == set(MetricName)


def test_an_inapplicable_metric_is_emitted_with_a_null_value_never_zero() -> None:
    """Omission and zero are both misreadings of "does not apply"."""
    m = not_applicable(MetricName.GATE_WAIT_SECONDS)
    assert m.applicable is False and m.metric_value is None
    assert m.metric_kind is MetricKind.DURATION_SECONDS


def test_a_snapshot_rejects_a_duplicated_metric_name() -> None:
    with pytest.raises(NebulaError):
        RuntimeMetricSnapshot(
            run_id="r", metric_generated_at=NOW, derived_from=DerivedFrom(1, 1),
            metrics=(metric(MetricName.ARTIFACT_COUNT, 2),
                     metric(MetricName.ARTIFACT_COUNT, 3)),
        )


def test_an_older_snapshot_is_superseded_not_wrong() -> None:
    older = RuntimeMetricSnapshot("r", NOW, DerivedFrom(1, 1), (metric(MetricName.ARTIFACT_COUNT, 2),))
    newer = RuntimeMetricSnapshot("r", NOW, DerivedFrom(2, 3), (metric(MetricName.ARTIFACT_COUNT, 5),))
    assert older.superseded_by(newer) is True
    assert newer.superseded_by(older) is False


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #
def test_every_new_record_serializes_through_the_existing_helper() -> None:
    """F0003 records add no serializer of their own; `serialize_record` is generic."""
    snapshot = RuntimeMetricSnapshot(
        "r", NOW, DerivedFrom(1, 1), (metric(MetricName.ARTIFACT_COUNT, 4),)
    )
    document = serialize_record(snapshot)
    assert document["derived_from"] == {"run_revision": 1, "artifact_index_revision": 1}
    assert document["metrics"][0]["metric_name"] == "artifact_count"
    assert document["metric_generated_at"].endswith("Z")

    document = serialize_record(proposal())
    assert document["proposal_status"] == "Draft"
    assert document["confidence"] == "Medium"

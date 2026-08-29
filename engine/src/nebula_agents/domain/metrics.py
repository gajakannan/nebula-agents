"""Runtime metric snapshots (F0003-S0006).

Metrics are **derived, never authoritative**. A snapshot is recomputable from run state
and the artifact index, and `derived_from` pins the revisions it was computed against —
so recomputability is checkable rather than asserted, and a snapshot taken at older
revisions is *superseded*, not wrong.

The metric name set is closed, so a consumer never meets an unknown key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import MetricKind, MetricName
from .errors import ErrorCode, error

#: The kind each metric reports. Total over MetricName by construction, asserted by test.
METRIC_KINDS: dict[MetricName, MetricKind] = {
    MetricName.RUN_DURATION_SECONDS: MetricKind.DURATION_SECONDS,
    MetricName.GATE_WAIT_SECONDS: MetricKind.DURATION_SECONDS,
    MetricName.VALIDATOR_PASS_COUNT: MetricKind.COUNT,
    MetricName.VALIDATOR_FAIL_COUNT: MetricKind.COUNT,
    MetricName.LATEST_FAILING_VALIDATOR: MetricKind.IDENTIFIER,
    MetricName.TRANSCRIPT_HEALTH: MetricKind.CATEGORY,
    MetricName.EVIDENCE_FRESHNESS: MetricKind.CATEGORY,
    MetricName.ARTIFACT_COUNT: MetricKind.COUNT,
    MetricName.BLOCKED_LAUNCH_COUNT: MetricKind.COUNT,
}


@dataclass(frozen=True, slots=True)
class DerivedFrom:
    """The revisions a snapshot was computed against.

    Without this a stale snapshot is indistinguishable from a current one, and "metrics
    are recomputable" would be a claim no reader could check.
    """

    run_revision: int
    artifact_index_revision: int


@dataclass(frozen=True, slots=True)
class Metric:
    metric_name: MetricName
    metric_value: float | str | None
    metric_kind: MetricKind
    applicable: bool = True

    def __post_init__(self) -> None:
        if self.metric_kind is not METRIC_KINDS[self.metric_name]:
            raise error(
                ErrorCode.CONFLICT,
                "Metric kind does not match the metric name.",
                "conflict",
                "Build metrics with `metric`, which resolves the kind.",
                metric_name=self.metric_name.value,
            )
        if not self.applicable and self.metric_value is not None:
            raise error(
                ErrorCode.CONFLICT,
                "An inapplicable metric must carry a null value.",
                "conflict",
                "Emit applicable=False with metric_value=None.",
                metric_name=self.metric_name.value,
            )


def metric(
    name: MetricName, value: float | str | None, *, applicable: bool = True
) -> Metric:
    return Metric(name, value if applicable else None, METRIC_KINDS[name], applicable)


def not_applicable(name: MetricName) -> Metric:
    """A metric that does not apply to a run is emitted, never omitted.

    Omission and zero are both misreadings: "no gate wait recorded" is not "waited zero
    seconds", and a consumer that sees neither cannot tell which happened.
    """
    return metric(name, None, applicable=False)


@dataclass(frozen=True, slots=True)
class RuntimeMetricSnapshot:
    run_id: str
    metric_generated_at: datetime
    derived_from: DerivedFrom
    metrics: tuple[Metric, ...]

    def __post_init__(self) -> None:
        names = [m.metric_name for m in self.metrics]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise error(
                ErrorCode.CONFLICT,
                "A metric name appears more than once in one snapshot.",
                "conflict",
                "Emit each metric name at most once.",
                run_id=self.run_id,
            )

    def superseded_by(self, other: RuntimeMetricSnapshot) -> bool:
        """A snapshot at older revisions is superseded, not wrong."""
        return (
            other.derived_from.run_revision >= self.derived_from.run_revision
            and other.derived_from.artifact_index_revision
            >= self.derived_from.artifact_index_revision
            and other.derived_from != self.derived_from
        )

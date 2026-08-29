"""Provider capability reports and the launch guard (F0003-S0002).

The guard rule is one function, `launch_decision`, so "may this launch proceed" has
exactly one answer in the codebase. `wrap` consults it; nothing re-derives it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .enums import (
    CapabilityName,
    CapabilityRequirement,
    FreshnessStatus,
    LaunchDecision,
    ProbeResult,
    ProviderKey,
    ProviderMode,
)


@dataclass(frozen=True, slots=True)
class Capability:
    capability_name: CapabilityName
    capability_requirement: CapabilityRequirement
    probe_result: ProbeResult
    fallback_available: bool = False
    failure_reason: str | None = None
    probe_artifact_id: str | None = None
    probe_duration_ms: int | None = None

    @property
    def satisfied(self) -> bool:
        """A required capability is satisfied by passing, or by an explicit fallback.

        `timeout` is not a pass. S0002 is explicit: a probe that times out blocks launch
        unless the capability is optional — an unanswered probe is not a positive one.
        """
        if self.probe_result is ProbeResult.PASS:
            return True
        return self.fallback_available


def launch_decision(capabilities: tuple[Capability, ...]) -> tuple[LaunchDecision, str | None]:
    """Decide whether a wrapped launch may proceed, and say why when it may not.

    Launch proceeds only when every `required` capability passes or has an explicit
    fallback. Anything else blocks with exit 3, which distinguishes a capability block
    from a policy denial (5) and a provider failure (8).
    """
    required = [c for c in capabilities if c.capability_requirement is CapabilityRequirement.REQUIRED]
    unsatisfied = [c for c in required if not c.satisfied]
    if unsatisfied:
        names = ", ".join(sorted(c.capability_name.value for c in unsatisfied))
        return LaunchDecision.BLOCKED, f"Required capability not available: {names}"
    if any(c.probe_result is not ProbeResult.PASS for c in required):
        return LaunchDecision.ALLOWED_WITH_FALLBACK, None
    return LaunchDecision.ALLOWED, None


def freshness_of(
    report_generated_at: datetime, now: datetime, max_age: timedelta
) -> FreshnessStatus:
    if report_generated_at > now:
        return FreshnessStatus.UNKNOWN
    return (
        FreshnessStatus.FRESH
        if now - report_generated_at <= max_age
        else FreshnessStatus.STALE
    )


@dataclass(frozen=True, slots=True)
class ProviderCapabilityReport:
    provider_key: ProviderKey
    provider_mode: ProviderMode
    report_generated_at: datetime
    launch_decision: LaunchDecision
    capabilities: tuple[Capability, ...]
    provider_cli_path: str | None = None
    provider_version: str | None = None
    freshness_status: FreshnessStatus = FreshnessStatus.FRESH
    blocked_reason: str | None = None

    def __post_init__(self) -> None:
        decision, reason = launch_decision(self.capabilities)
        if decision is not self.launch_decision:
            raise ValueError(
                "launch_decision contradicts the capability set; build reports with `report_for`"
            )
        if decision is LaunchDecision.BLOCKED and not self.blocked_reason:
            raise ValueError("a blocked report must carry blocked_reason")
        del reason


def report_for(
    *,
    provider_key: ProviderKey,
    provider_mode: ProviderMode,
    report_generated_at: datetime,
    capabilities: tuple[Capability, ...],
    provider_cli_path: str | None = None,
    provider_version: str | None = None,
    freshness_status: FreshnessStatus = FreshnessStatus.FRESH,
) -> ProviderCapabilityReport:
    """Build a report with the launch decision derived, never asserted by the caller."""
    decision, reason = launch_decision(capabilities)
    return ProviderCapabilityReport(
        provider_key=provider_key,
        provider_mode=provider_mode,
        report_generated_at=report_generated_at,
        launch_decision=decision,
        capabilities=capabilities,
        provider_cli_path=provider_cli_path,
        provider_version=provider_version,
        freshness_status=freshness_status,
        blocked_reason=reason,
    )

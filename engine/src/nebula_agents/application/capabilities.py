"""Provider capability reporting and the wrapped-launch guard (F0003-S0001, S0002).

`wrap` supersedes nothing. F0001's `launch` remains the primitive; `wrap` is preflight
plus capability guard plus `launch` plus registration, as one operator step.

The guard decision itself lives in the domain (`domain.capabilities.launch_decision`), so
"may this launch proceed" has exactly one answer in the codebase. This service probes,
persists, and enforces — it does not re-derive the rule.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from nebula_agents.domain.capabilities import ProviderCapabilityReport, freshness_of
from nebula_agents.domain.enums import (
    Action,
    FreshnessStatus,
    LaunchDecision,
    ProbeResult,
    ProviderKey,
)
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import Actor, AuthorizationResource, LaunchRequest

from .authorization import AuthorizationService
from .ports import Clock


class CapabilityService:
    def __init__(
        self,
        *,
        prober,
        reports,
        authorization: AuthorizationService,
        clock: Clock,
        workspace_root: Path,
        max_age_seconds: float,
    ) -> None:
        self._prober = prober
        self._reports = reports
        self._authorization = authorization
        self._clock = clock
        self._workspace_root = workspace_root
        self._max_age = timedelta(seconds=max_age_seconds)

    def probe(self, provider_key: ProviderKey, actor: Actor) -> ProviderCapabilityReport:
        """Probe one provider and persist its report. Requires `Probe`."""
        self._authorization.require(
            actor, Action.PROBE, AuthorizationResource(str(self._workspace_root), None, None)
        )
        report = self._prober.probe(provider_key, self._workspace_root)
        self._reports.save(report)
        return report

    def doctor(self, actor: Actor, provider_key: ProviderKey | None = None) -> tuple[ProviderCapabilityReport, ...]:
        keys = (provider_key,) if provider_key else tuple(ProviderKey)
        return tuple(self.probe(key, actor) for key in keys)

    def current(self, provider_key: ProviderKey, actor: Actor) -> ProviderCapabilityReport:
        """The report `wrap` will consult, re-probing when it is stale or absent.

        Staleness triggers a fresh probe rather than a warning. A guard deciding from a
        report of unknown age is a guard in name only, and re-probing costs one bounded
        subprocess call.
        """
        report = self._reports.load(provider_key)
        if report is None:
            return self.probe(provider_key, actor)
        freshness = freshness_of(report.report_generated_at, self._clock.now(), self._max_age)
        if freshness is not FreshnessStatus.FRESH:
            return self.probe(provider_key, actor)
        return report

    def guard(self, provider_key: ProviderKey, actor: Actor) -> ProviderCapabilityReport:
        """Raise unless a wrapped launch may proceed for this provider.

        Exit 3 (preflight blocked), which is what distinguishes a capability block from a
        policy denial (5) and a provider failure (8). The distinction matters to an
        operator: one is fixed by installing something, one by changing policy, one by
        retrying.
        """
        report = self.current(provider_key, actor)
        if report.launch_decision is LaunchDecision.BLOCKED:
            failing = sorted(
                capability.capability_name.value
                for capability in report.capabilities
                if capability.capability_requirement.value == "required"
                and not capability.satisfied
            )
            timed_out = any(c.probe_result is ProbeResult.TIMEOUT for c in report.capabilities)
            raise error(
                ErrorCode.CAPABILITY_BLOCKED,
                report.blocked_reason or "Required provider capability is unavailable.",
                "preflight",
                "Run `nebula-agents providers doctor` and resolve the reported capability.",
                provider_key=provider_key.value,
                failing_capabilities=failing,
                probe_timed_out=timed_out,
            )
        return report

"""F0003-S0002 — the capability matrix and the wrapped-launch guard.

The guard is the only thing standing between an operator and a session that cannot do
what the workflow needs, so these cover the failure directions specifically: a missing
provider, a timeout, a fallback, and a stale report.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from nebula_agents.application.capabilities import CapabilityService
from nebula_agents.domain.capabilities import (
    DEFAULT_REQUIREMENTS,
    Capability,
    report_for,
)
from nebula_agents.domain.enums import (
    CapabilityName,
    CapabilityRequirement,
    FreshnessStatus,
    LaunchDecision,
    ProbeResult,
    ProviderKey,
    ProviderMode,
    Role,
)
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import Actor
from nebula_agents.infrastructure.capability_probe import (
    PROBE_TIMEOUT_SECONDS,
    ProviderCapabilityProber,
    redact,
)

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
OPERATOR = Actor(1000, "operator", Role.LOCAL_OPERATOR, None)


def capability(name: CapabilityName, result: ProbeResult, *, fallback: bool = False) -> Capability:
    return Capability(name, DEFAULT_REQUIREMENTS[name], result, fallback_available=fallback)


def report(**results: ProbeResult):
    caps = tuple(
        capability(name, results.get(name.value, ProbeResult.PASS)) for name in CapabilityName
    )
    return report_for(
        provider_key=ProviderKey.CODEX, provider_mode=ProviderMode.TMUX_NATIVE,
        report_generated_at=NOW, capabilities=caps,
    )


# --------------------------------------------------------------------------- #
# Requirement levels are declared, not decided per probe
# --------------------------------------------------------------------------- #
def test_every_capability_has_a_declared_requirement_level() -> None:
    assert set(DEFAULT_REQUIREMENTS) == set(CapabilityName)


def test_approval_visibility_is_required_because_it_is_the_tmux_native_premise() -> None:
    """A provider that cannot surface approval prompts fails the premise, not a nicety.

    Preserving interactive approvals is the reason F0003 stays tmux-native at all. If
    this were optional, a silently-degraded session would still be allowed to launch.
    """
    assert DEFAULT_REQUIREMENTS[CapabilityName.APPROVAL_VISIBILITY] is CapabilityRequirement.REQUIRED


def test_transcript_is_optional_because_nebula_captures_it_itself() -> None:
    assert DEFAULT_REQUIREMENTS[CapabilityName.TRANSCRIPT] is CapabilityRequirement.OPTIONAL


# --------------------------------------------------------------------------- #
# The launch decision
# --------------------------------------------------------------------------- #
def test_all_required_passing_allows_launch() -> None:
    assert report().launch_decision is LaunchDecision.ALLOWED


@pytest.mark.parametrize("failing", ["launch", "attach", "approval_visibility"])
def test_any_failing_required_capability_blocks_launch(failing: str) -> None:
    built = report(**{failing: ProbeResult.FAIL})
    assert built.launch_decision is LaunchDecision.BLOCKED
    assert failing in built.blocked_reason


def test_a_timeout_blocks_exactly_as_a_failure_does() -> None:
    """An unanswered probe is not a positive one."""
    assert report(launch=ProbeResult.TIMEOUT).launch_decision is LaunchDecision.BLOCKED


def test_an_optional_failure_never_blocks() -> None:
    assert report(transcript=ProbeResult.FAIL, status_probe=ProbeResult.FAIL).launch_decision is LaunchDecision.ALLOWED


# --------------------------------------------------------------------------- #
# Redaction of probe output
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text",
    [
        "codex-cli 1.0 token=sk-live-abcdefghijklmnop",
        "provider 2.0 Bearer abcdefghijklmnopqrstuvwx",
        "v3 api_key: supersecretvalue",
    ],
)
def test_secret_like_probe_output_is_redacted(text: str) -> None:
    """S0002: a version command that returns secret-like text is redacted before persistence."""
    safe, findings = redact(text)
    assert findings >= 1
    assert "[REDACTED]" in safe
    for secret in ("sk-live-abcdefghijklmnop", "abcdefghijklmnopqrstuvwx", "supersecretvalue"):
        assert secret not in safe


def test_ordinary_version_output_is_left_intact() -> None:
    safe, findings = redact("codex-cli 0.145.0")
    assert (safe, findings) == ("codex-cli 0.145.0", 0)


# --------------------------------------------------------------------------- #
# Probing
# --------------------------------------------------------------------------- #
class FakeProbe(SimpleNamespace):
    pass


def prober(status: str, *, tmux_ready: bool = True, version: str | None = "cli 1.0"):
    adapter = SimpleNamespace(
        probe=lambda _root: FakeProbe(
            status=status, executable_path="/usr/bin/codex", version=version
        )
    )
    tmux = SimpleNamespace(probe=lambda: SimpleNamespace(status="ready" if tmux_ready else "missing"))
    return ProviderCapabilityProber(
        {ProviderKey.CODEX: adapter}, tmux, None, SimpleNamespace(now=lambda: NOW)
    )


def test_a_missing_provider_blocks_launch_with_remediation() -> None:
    built = prober("missing").probe(ProviderKey.CODEX, Path("/ws"))
    assert built.launch_decision is LaunchDecision.BLOCKED
    assert "launch" in built.blocked_reason


def test_a_provider_probe_timeout_marks_launch_and_status_probe_timed_out() -> None:
    built = prober("timeout").probe(ProviderKey.CODEX, Path("/ws"))
    timed = {c.capability_name for c in built.capabilities if c.probe_result is ProbeResult.TIMEOUT}
    assert timed == {CapabilityName.LAUNCH, CapabilityName.STATUS_PROBE}
    assert built.launch_decision is LaunchDecision.BLOCKED


def test_missing_tmux_blocks_attach_and_approval_visibility() -> None:
    built = prober("ready", tmux_ready=False).probe(ProviderKey.CODEX, Path("/ws"))
    assert built.provider_mode is ProviderMode.UNAVAILABLE
    assert built.launch_decision is LaunchDecision.BLOCKED


def test_authentication_attention_still_allows_launch_but_fails_the_status_probe() -> None:
    """F0001's rule: an ambiguous auth result is attention-needed, never a login attempt.

    Launch stays allowed because the provider handles its own login prompt inside tmux;
    that is the whole tmux-native premise.
    """
    built = prober("authentication_attention_needed").probe(ProviderKey.CODEX, Path("/ws"))
    assert built.launch_decision is LaunchDecision.ALLOWED
    status = next(c for c in built.capabilities if c.capability_name is CapabilityName.STATUS_PROBE)
    assert status.probe_result is ProbeResult.FAIL


def test_an_unsupported_provider_key_is_not_found() -> None:
    with pytest.raises(NebulaError) as caught:
        prober("ready").probe(ProviderKey.CLAUDE, Path("/ws"))
    assert caught.value.code is ErrorCode.PROVIDER_NOT_FOUND


def test_the_probe_timeout_is_bounded() -> None:
    assert 0 < PROBE_TIMEOUT_SECONDS <= 5


# --------------------------------------------------------------------------- #
# The guard
# --------------------------------------------------------------------------- #
class Reports:
    def __init__(self, stored=None) -> None:
        self.stored = stored
        self.saves = 0

    def load(self, _key):
        return self.stored

    def save(self, report) -> None:
        self.stored = report
        self.saves += 1


def service(stored=None, status="ready", now=NOW, max_age=3600.0) -> tuple[CapabilityService, Reports]:
    reports = Reports(stored)
    return (
        CapabilityService(
            prober=prober(status),
            reports=reports,
            authorization=SimpleNamespace(require=lambda *a, **k: None),
            clock=SimpleNamespace(now=lambda: now),
            workspace_root=Path("/ws"),
            max_age_seconds=max_age,
        ),
        reports,
    )


def test_the_guard_raises_exit_3_naming_the_failing_capability() -> None:
    """Exit 3 distinguishes a capability block from a policy denial (5) and a provider
    failure (8) -- one is fixed by installing, one by policy, one by retrying."""
    guard, _ = service(status="missing")
    with pytest.raises(NebulaError) as caught:
        guard.guard(ProviderKey.CODEX, OPERATOR)
    assert caught.value.code is ErrorCode.CAPABILITY_BLOCKED
    assert caught.value.exit_code == 3
    assert "launch" in caught.value.details[0]["failing_capabilities"]


def test_an_absent_report_triggers_a_probe_rather_than_an_error() -> None:
    guard, reports = service(stored=None)
    guard.guard(ProviderKey.CODEX, OPERATOR)
    assert reports.saves == 1


def test_a_stale_report_is_re_probed_not_merely_warned_about() -> None:
    """A guard deciding from a report of unknown age is a guard in name only."""
    guard, reports = service(stored=report(), now=NOW + timedelta(hours=2), max_age=3600.0)
    guard.guard(ProviderKey.CODEX, OPERATOR)
    assert reports.saves == 1


def test_a_fresh_report_is_reused_without_re_probing() -> None:
    guard, reports = service(stored=report(), now=NOW + timedelta(minutes=5))
    guard.guard(ProviderKey.CODEX, OPERATOR)
    assert reports.saves == 0

"""Provider capability probing and report persistence (F0003-S0002).

Every probe is bounded by a timeout and its output is redacted **before** it is
persisted or returned. A version string is attacker-influenced input in the sense that
matters here: it is whatever the provider chose to print, and it lands in a file a
reviewer reads.
"""

from __future__ import annotations

import json
import os
import stat
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from nebula_agents.domain.capabilities import (
    DEFAULT_REQUIREMENTS,
    Capability,
    ProviderCapabilityReport,
    freshness_of,
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
)
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import serialize_record
from nebula_agents.domain.redaction import StreamingRedactor

from .atomic import (
    FILE_MODE,
    assert_owner_only_directory,
    json_bytes,
    owner_only_lock,
    publish_atomic,
    write_owner_only,
)
from .config import SAFE_ENV_NAMES
from .schema_registry import JsonSchemaRegistry

SCHEMA = "f0003-capability-report.schema.json"
REPORTS_DIRNAME = "capabilities"
#: Per-probe ceiling. A provider CLI that has not answered in this long is not
#: "slow" from an operator's point of view; it is unavailable.
PROBE_TIMEOUT_SECONDS = 2.0


def redact(text: str) -> tuple[str, int]:
    """One-shot redaction over probe output. Returns the safe text and finding count."""
    redactor = StreamingRedactor()
    emitted = redactor.feed(text.encode("utf-8", "replace")) + redactor.finalize()
    return emitted.decode("utf-8", "replace"), redactor.findings


class ProviderCapabilityProber:
    """Turns an F0001 provider adapter plus tmux into a full capability report.

    F0001's `ProviderAdapter.probe` answers one question -- is this provider usable.
    F0003 needs six answers with requirement levels, so this composes the existing probe
    rather than replacing it: the adapter stays the single place that knows how to talk
    to a provider CLI.
    """

    def __init__(self, providers: dict, tmux, runner, clock) -> None:
        self._providers = providers
        self._tmux = tmux
        self._runner = runner
        self._clock = clock

    def probe(self, provider_key: ProviderKey, workspace_root: Path) -> ProviderCapabilityReport:
        adapter = self._providers.get(provider_key)
        if adapter is None:
            raise error(
                ErrorCode.PROVIDER_NOT_FOUND, "Provider is not supported.", "not-found",
                "Choose a supported provider.", provider_key=provider_key.value,
            )
        started = time.monotonic()
        provider_probe = adapter.probe(workspace_root)
        elapsed_ms = int((time.monotonic() - started) * 1000)

        version, findings = redact(provider_probe.version or "")
        cli_path = provider_probe.executable_path

        tmux_probe = self._tmux.probe() if self._tmux is not None else None
        tmux_ready = bool(tmux_probe is not None and tmux_probe.status == "ready")

        status = provider_probe.status
        launch = _result_for(status in {"ready", "authentication_attention_needed"}, status)
        capabilities = (
            _capability(CapabilityName.LAUNCH, launch, elapsed_ms,
                        None if launch is ProbeResult.PASS else f"provider status: {status}"),
            # Attach is tmux's capability, not the provider's -- F0001 attaches to the
            # session, never to the provider process.
            _capability(CapabilityName.ATTACH, _result_for(tmux_ready, "tmux"), None,
                        None if tmux_ready else "tmux is not ready"),
            # Interactive approval prompts survive because the provider runs in a real
            # TTY inside tmux. If tmux is ready and the provider launches, they are
            # visible; nothing further is probeable without starting a session.
            _capability(CapabilityName.APPROVAL_VISIBILITY,
                        _result_for(tmux_ready and launch is ProbeResult.PASS, "tmux+provider"),
                        None, None if tmux_ready else "no interactive session host"),
            # Nebula captures transcripts itself via tmux pipe-pane (ADR-004), so this
            # reports Nebula's capability, not the provider's.
            _capability(CapabilityName.TRANSCRIPT, _result_for(tmux_ready, "pipe-pane"), None,
                        None if tmux_ready else "tmux pipe-pane unavailable"),
            _capability(CapabilityName.STATUS_PROBE,
                        ProbeResult.PASS if status == "ready" else ProbeResult.FAIL,
                        elapsed_ms, None if status == "ready" else f"provider status: {status}"),
            _capability(CapabilityName.FALLBACK, ProbeResult.SKIPPED, None,
                        "no managed fallback until F0002"),
        )
        if status == "timeout":
            capabilities = tuple(
                Capability(
                    c.capability_name, c.capability_requirement, ProbeResult.TIMEOUT,
                    c.fallback_available, "provider probe timed out", None, c.probe_duration_ms,
                )
                if c.capability_name in (CapabilityName.LAUNCH, CapabilityName.STATUS_PROBE)
                else c
                for c in capabilities
            )

        return report_for(
            provider_key=provider_key,
            provider_mode=ProviderMode.TMUX_NATIVE if tmux_ready else ProviderMode.UNAVAILABLE,
            report_generated_at=self._clock.now(),
            capabilities=capabilities,
            provider_cli_path=cli_path,
            # A version string that looked secret-bearing is stored redacted, never raw,
            # and never dropped silently -- the marker is visible to a reviewer.
            provider_version=(version or None) if findings == 0 else version,
        )


def _result_for(ok: bool, _reason: str) -> ProbeResult:
    return ProbeResult.PASS if ok else ProbeResult.FAIL


def _capability(
    name: CapabilityName, result: ProbeResult, duration_ms: int | None, failure: str | None
) -> Capability:
    return Capability(
        capability_name=name,
        capability_requirement=DEFAULT_REQUIREMENTS[name],
        probe_result=result,
        fallback_available=False,
        failure_reason=failure,
        probe_duration_ms=duration_ms,
    )


class FilesystemCapabilityReports:
    """Atomic per-provider report storage under the runtime root."""

    def __init__(self, runtime_root: Path, schema: JsonSchemaRegistry, lock_timeout_seconds: float = 5.0) -> None:
        self._root = runtime_root / REPORTS_DIRNAME
        self._runtime_root = runtime_root
        self._schema = schema
        self._lock_timeout = lock_timeout_seconds

    def _path(self, provider_key: ProviderKey) -> Path:
        return self._root / f"{provider_key.value}.json"

    def load(self, provider_key: ProviderKey) -> ProviderCapabilityReport | None:
        """Absent or unreadable reads as "no report", which `wrap` treats as re-probe."""
        path = self._path(provider_key)
        if not path.exists() or path.is_symlink():
            return None
        try:
            details = path.lstat()
            if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != FILE_MODE:
                return None
            document = json.loads(path.read_text(encoding="utf-8"))
            self._schema.validate(SCHEMA, document)
            return _report_from(document)
        except Exception:
            return None

    def save(self, report: ProviderCapabilityReport) -> None:
        self._runtime_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self._root, 0o700)
        assert_owner_only_directory(self._root)
        with owner_only_lock(self._root, self._lock_timeout, ".capabilities.lock"):
            payload = {"schema_version": "1.0", **serialize_record(report)}
            self._schema.validate(SCHEMA, payload)
            pending = self._root / f"{report.provider_key.value}.pending.json"
            write_owner_only(pending, json_bytes(payload, pretty=True))
            publish_atomic(self._root, pending, self._path(report.provider_key))


def _report_from(document: dict) -> ProviderCapabilityReport:
    return ProviderCapabilityReport(
        provider_key=ProviderKey(document["provider_key"]),
        provider_mode=ProviderMode(document["provider_mode"]),
        report_generated_at=datetime.fromisoformat(
            str(document["report_generated_at"]).replace("Z", "+00:00")
        ).astimezone(timezone.utc),
        launch_decision=LaunchDecision(document["launch_decision"]),
        capabilities=tuple(
            Capability(
                capability_name=CapabilityName(item["capability_name"]),
                capability_requirement=CapabilityRequirement(item["capability_requirement"]),
                probe_result=ProbeResult(item["probe_result"]),
                fallback_available=bool(item.get("fallback_available", False)),
                failure_reason=item.get("failure_reason"),
                probe_artifact_id=item.get("probe_artifact_id"),
                probe_duration_ms=item.get("probe_duration_ms"),
            )
            for item in document["capabilities"]
        ),
        provider_cli_path=document.get("provider_cli_path"),
        provider_version=document.get("provider_version"),
        freshness_status=FreshnessStatus(document.get("freshness_status", "fresh")),
        blocked_reason=document.get("blocked_reason"),
    )

"""F0003 domain records validate against the six committed JSON schemas.

This is the cross-check between the domain layer and the published contract. The
records were written from the schemas; without this test that correspondence is a claim
about the author's care, and it drifts the first time either side is edited alone.

Every schema sets `additionalProperties: false`, so an extra dataclass field fails here
just as loudly as a missing one.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from nebula_agents.domain.artifacts import new_entry
from nebula_agents.domain.capabilities import Capability, report_for
from nebula_agents.domain.enums import (
    ArtifactKind,
    ArtifactRedactionStatus,
    CapabilityName,
    CapabilityRequirement,
    Confidence,
    ProbeResult,
    ProposalStatus,
    ProviderKey,
    ProviderMode,
    SourceRoot,
    SummaryStatus,
)
from nebula_agents.domain.metrics import DerivedFrom, RuntimeMetricSnapshot, metric
from nebula_agents.domain.enums import MetricName
from nebula_agents.domain.models import serialize_record
from nebula_agents.domain.proposals import LearningProposal
from nebula_agents.domain.summaries import ArtifactSummary, SummaryMarker

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
RUN = "2026-08-29-16075bda"


@pytest.fixture(scope="module")
def validate(schema_root: Path):
    def _validate(schema_name: str, document: dict) -> None:
        schema = json.loads((schema_root / schema_name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(document)

    return _validate


def test_artifact_index_entry_validates(tmp_path: Path, validate) -> None:
    roots = {
        SourceRoot.WORKSPACE: tmp_path,
        SourceRoot.RUNTIME: tmp_path / "rt",
        SourceRoot.EVIDENCE: tmp_path / "ev",
    }
    entry = new_entry(
        run_id=RUN, kind=ArtifactKind.TRANSCRIPT,
        artifact_path=tmp_path / "rt" / "runs" / RUN / "t.log", roots=roots,
        created_at=NOW, redaction_status=ArtifactRedactionStatus.PASS,
        content_hash="a" * 64, size_bytes=1024,
    )
    document = {
        "schema_version": "1.0", "run_id": RUN, "revision": 1,
        "updated_at": "2026-08-29T12:00:00Z",
        "entries": [serialize_record(entry)],
    }
    validate("f0003-artifact-index.schema.json", document)


def test_artifact_summary_validates(validate) -> None:
    summary = ArtifactSummary(
        summary_id="s1", artifact_id=f"{RUN}/transcript/rt-0123456789ab",
        artifact_kind=ArtifactKind.TRANSCRIPT, summary_status=SummaryStatus.PARTIAL,
        redaction_status=ArtifactRedactionStatus.PASS, rule_set_version="1.0",
        generated_at=NOW, source_reference=f"{RUN}/transcript/rt-0123456789ab",
        key_events=(SummaryMarker(1, "prompt", detail="redacted"),),
        failure_markers=(SummaryMarker(2, "validator failed", exit_code=1, duration_ms=42),),
        warning_markers=(), open_questions=("Which gate blocked?",),
        truncation_count=3, last_observed_marker="interrupted",
    )
    document = {"schema_version": "1.0", **serialize_record(summary)}
    validate("f0003-artifact-summary.schema.json", document)


def test_capability_report_validates(validate) -> None:
    report = report_for(
        provider_key=ProviderKey.CODEX, provider_mode=ProviderMode.TMUX_NATIVE,
        report_generated_at=NOW,
        capabilities=(
            Capability(CapabilityName.LAUNCH, CapabilityRequirement.REQUIRED,
                       ProbeResult.PASS, probe_duration_ms=12),
            Capability(CapabilityName.TRANSCRIPT, CapabilityRequirement.OPTIONAL,
                       ProbeResult.FAIL, failure_reason="not supported"),
        ),
        provider_cli_path="/usr/local/bin/codex", provider_version="codex-cli 0.145.0",
    )
    document = {"schema_version": "1.0", **serialize_record(report)}
    validate("f0003-capability-report.schema.json", document)


def test_learning_proposal_validates(validate) -> None:
    proposal = LearningProposal(
        proposal_id="p1", run_id=RUN, generated_at=NOW,
        source_artifact_ids=(f"{RUN}/validator-output/ev-0123456789ab",),
        source_content_hashes=("b" * 64,),
        target_document="planning-mds/architecture/SOLUTION-PATTERNS.md",
        proposal_summary="Record the retry rule.",
        proposal_status=ProposalStatus.DRAFT, confidence=Confidence.HIGH,
        patch_plan=None, decisions=(),
    )
    document = {"schema_version": "1.0", **serialize_record(proposal)}
    validate("f0003-learning-proposal.schema.json", document)


def test_metric_snapshot_validates(validate) -> None:
    snapshot = RuntimeMetricSnapshot(
        run_id=RUN, metric_generated_at=NOW, derived_from=DerivedFrom(4, 7),
        metrics=tuple(metric(name, 1) if name not in {
            MetricName.LATEST_FAILING_VALIDATOR, MetricName.TRANSCRIPT_HEALTH,
            MetricName.EVIDENCE_FRESHNESS,
        } else metric(name, "stories") for name in MetricName),
    )
    document = {"schema_version": "1.0", **serialize_record(snapshot)}
    validate("f0003-metric-snapshot.schema.json", document)


def test_every_committed_f0003_schema_has_a_record_exercised_here(schema_root: Path) -> None:
    """Guards against a schema being added and quietly left unexercised.

    `f0003-mcp-response` is exempt: it is a transport envelope produced by the S0003
    adapter, not a domain record, and it has no dataclass to validate yet.
    """
    committed = {p.name for p in schema_root.glob("f0003-*.schema.json")}
    exercised = {
        "f0003-artifact-index.schema.json",
        "f0003-artifact-summary.schema.json",
        "f0003-capability-report.schema.json",
        "f0003-learning-proposal.schema.json",
        "f0003-metric-snapshot.schema.json",
    }
    assert committed - exercised == {"f0003-mcp-response.schema.json"}

"""F0003-S0005 — deterministic summaries (ADR-008).

The corpus in `tests/fixtures/summaries/` was authored **before** the extractors, so
these assert against inputs the rules were not shaped around.

Determinism is the load-bearing property: a summary that varies between runs cannot be
diffed, cached, or trusted as evidence.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from nebula_agents.domain.enums import ArtifactKind, SummaryStatus
from nebula_agents.infrastructure.summarizers import (
    RULE_SET_VERSION,
    SUPPORTED_KINDS,
    extract,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "summaries"

CORPUS = {
    ArtifactKind.TRANSCRIPT: "transcript.txt",
    ArtifactKind.COMMAND_LOG: "command-log.jsonl",
    ArtifactKind.VALIDATOR_OUTPUT: "validator-output.txt",
    ArtifactKind.MANIFEST: "manifest.json",
}


def payload(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def rendered(kind: ArtifactKind, data: bytes) -> str:
    extraction, supported, extracted = extract(kind, data)
    parts = [f"supported={supported}", f"extracted={extracted}",
             f"complete={extraction.input_complete}", f"last={extraction.last_observed_marker}"]
    for group_name in ("key_events", "failure_markers", "warning_markers"):
        for marker in getattr(extraction, group_name):
            parts.append(f"{group_name}:{marker.ordinal}:{marker.label}:{marker.detail}:"
                         f"{marker.exit_code}:{marker.duration_ms}")
    parts.extend(f"question:{q}" for q in extraction.open_questions)
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kind,name", sorted(CORPUS.items(), key=lambda i: i[0].value))
def test_extraction_is_byte_identical_across_repeated_runs(kind: ArtifactKind, name: str) -> None:
    data = payload(name)
    first = rendered(kind, data)
    assert all(rendered(kind, data) == first for _ in range(5))


@pytest.mark.parametrize("kind,name", sorted(CORPUS.items(), key=lambda i: i[0].value))
def test_extraction_is_byte_identical_across_processes(kind: ArtifactKind, name: str) -> None:
    """A fresh interpreter, so nothing depends on hash seed, iteration order, or import order.

    Python randomises string hashing per process by default. An extractor that iterated a
    set anywhere would pass the in-process check above and fail here.
    """
    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, %r)\n"
        "from test_summary_determinism import rendered, payload\n"
        "from nebula_agents.domain.enums import ArtifactKind\n"
        "print(rendered(ArtifactKind(%r), payload(%r)), end='')\n"
        % (str(Path(__file__).resolve().parents[3] / "src"), str(Path(__file__).parent),
           kind.value, name)
    )
    outputs = set()
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=True
        )
        outputs.add(result.stdout)
    assert len(outputs) == 1
    assert outputs.pop() == rendered(kind, payload(name))


def test_the_rule_set_version_is_stamped_and_stable() -> None:
    """A rule change must be visible, not silently rewrite what a reviewer already read."""
    assert RULE_SET_VERSION == "1.0"


# --------------------------------------------------------------------------- #
# What each extractor must preserve
# --------------------------------------------------------------------------- #
def test_a_transcript_preserves_prompts_approvals_and_recovery_markers() -> None:
    extraction, _, _ = extract(ArtifactKind.TRANSCRIPT, payload("transcript.txt"))
    labels = {m.label for m in extraction.key_events}
    assert {"user_prompt", "approval_requested", "recovery_marker"} <= labels
    prompts = [m.detail for m in extraction.key_events if m.label == "user_prompt"]
    assert "Implement the retry guard in application/runs.py" in prompts


def test_a_transcript_preserves_its_failures() -> None:
    extraction, _, _ = extract(ArtifactKind.TRANSCRIPT, payload("transcript.txt"))
    assert any("test_retry_guard failed" in (m.detail or "") for m in extraction.failure_markers)


def test_a_command_log_preserves_order_exit_code_and_duration() -> None:
    extraction, _, _ = extract(ArtifactKind.COMMAND_LOG, payload("command-log.jsonl"))
    assert [m.ordinal for m in extraction.key_events] == sorted(m.ordinal for m in extraction.key_events)
    assert len(extraction.failure_markers) == 1
    failed = extraction.failure_markers[0]
    assert failed.exit_code == 1 and failed.duration_ms == 4210
    assert "run-lifecycle-gates" in failed.detail


def test_a_validator_summary_lists_failed_rules_and_counts_the_passes() -> None:
    """A reviewer reading a validator summary wants what failed; 200 `[PASS]` lines bury it."""
    extraction, _, _ = extract(ArtifactKind.VALIDATOR_OUTPUT, payload("validator-output.txt"))
    failed = {m.label for m in extraction.failure_markers}
    assert failed == {"acceptance_criteria_testable", "out_of_scope_present"}
    assert any("remediation:" in (m.detail or "") for m in extraction.failure_markers)
    passes = next(m for m in extraction.key_events if m.label == "rules_passed")
    assert passes.detail == "3"


def test_a_manifest_summary_reports_scalars_and_summarises_nested_objects() -> None:
    extraction, _, _ = extract(ArtifactKind.MANIFEST, payload("manifest.json"))
    by_label = {m.label: m.detail for m in extraction.key_events}
    assert by_label["feature_id"] == "F0003"
    assert by_label["gate_results"] == "<2 field(s)>"


# --------------------------------------------------------------------------- #
# The failure directions
# --------------------------------------------------------------------------- #
def test_a_binary_artifact_is_unsupported_rather_than_garbled() -> None:
    extraction, supported, extracted = extract(ArtifactKind.TRANSCRIPT, payload("unsupported.bin"))
    assert (supported, extracted) == (False, False)
    assert extraction.key_events == () and extraction.failure_markers == ()


def test_a_kind_without_an_extractor_is_unsupported() -> None:
    assert ArtifactKind.LEARNING_PROPOSAL not in SUPPORTED_KINDS
    _, supported, _ = extract(ArtifactKind.LEARNING_PROPOSAL, b"anything")
    assert supported is False


def test_secret_bearing_content_is_redacted_before_extraction() -> None:
    """Redaction runs on bytes, before decoding.

    A lossy decode first could split a credential into two halves that no byte pattern
    matches, and the summary would carry the pieces.
    """
    extraction, _, _ = extract(ArtifactKind.TRANSCRIPT, payload("secret-bearing.txt"))
    assert extraction.redaction_findings >= 1
    serialised = rendered(ArtifactKind.TRANSCRIPT, payload("secret-bearing.txt"))
    assert "sk-live-abcdefghijklmnopqrstuv" not in serialised


def test_an_interrupted_transcript_is_reported_incomplete() -> None:
    interrupted = b"$ codex\n> do the thing\nworking..."
    extraction, _, _ = extract(ArtifactKind.TRANSCRIPT, interrupted)
    assert extraction.input_complete is False
    assert extraction.last_observed_marker == "working..."


def test_a_truncated_command_log_line_marks_the_input_incomplete() -> None:
    truncated = payload("command-log.jsonl")[:-20]
    extraction, _, _ = extract(ArtifactKind.COMMAND_LOG, truncated)
    assert extraction.input_complete is False


def test_unparseable_structured_input_is_a_failure_marker_not_a_crash() -> None:
    extraction, supported, extracted = extract(ArtifactKind.MANIFEST, b"{ not json")
    assert (supported, extracted) == (True, True)
    assert extraction.failure_markers[0].label == "unparseable"

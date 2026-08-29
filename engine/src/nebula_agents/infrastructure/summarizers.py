"""Rule-based artifact summarizers (F0003-S0005, ADR-008).

**No model call participates in producing a summary.** Extraction is pure functions over
bytes, so identical input yields byte-identical output — a property asserted by fixture,
not assumed. `RULE_SET_VERSION` is stamped on every summary so a future rule change is
visible rather than silently altering what a reviewer reads.

Each extractor answers one question: what would a reviewer need to know from this
artifact without opening it? Everything else is noise, and noise is what gets truncated
first — failure markers are never dropped for size.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from nebula_agents.domain.enums import ArtifactKind
from nebula_agents.domain.models import serialize_record
from nebula_agents.domain.redaction import StreamingRedactor
from nebula_agents.domain.summaries import SummaryMarker

from .atomic import (
    assert_owner_only_directory,
    json_bytes,
    owner_only_lock,
    publish_atomic,
    write_owner_only,
)

#: Bump when an extractor's output changes for unchanged input. Committed summaries
#: record the version that produced them, so a rule change never silently rewrites
#: history.
RULE_SET_VERSION = "1.0"

#: Kinds with a dedicated extractor. Anything else is Unsupported -- reported honestly
#: rather than run through a generic extractor that would produce plausible noise.
SUPPORTED_KINDS = frozenset({
    ArtifactKind.TRANSCRIPT,
    ArtifactKind.COMMAND_LOG,
    ArtifactKind.VALIDATOR_OUTPUT,
    ArtifactKind.MANIFEST,
    ArtifactKind.STATUS,
    ArtifactKind.METRIC,
})


@dataclass(frozen=True, slots=True)
class Extraction:
    key_events: tuple[SummaryMarker, ...]
    failure_markers: tuple[SummaryMarker, ...]
    warning_markers: tuple[SummaryMarker, ...] = ()
    open_questions: tuple[str, ...] = ()
    last_observed_marker: str | None = None
    input_complete: bool = True
    redaction_findings: int = 0


def decode(payload: bytes) -> tuple[str, int, bool]:
    """Redact, then decode. Returns text, redaction findings, and whether it is text.

    Redaction runs on **bytes, before decoding**, because the patterns are byte patterns
    and a lossy decode could split a credential into two harmless-looking halves.
    """
    if b"\x00" in payload[:8192]:
        return "", 0, False
    redactor = StreamingRedactor()
    safe = redactor.feed(payload) + redactor.finalize()
    try:
        return safe.decode("utf-8"), redactor.findings, True
    except UnicodeDecodeError:
        return safe.decode("utf-8", "replace"), redactor.findings, True


_APPROVAL = re.compile(r"\[approval required\]|\(y/n\)", re.IGNORECASE)
_PROMPT = re.compile(r"^>\s+(.+)$")
_FAILURE = re.compile(r"\b(error|failed|failure|traceback|assertionerror)\b", re.IGNORECASE)
_WARNING = re.compile(r"\bwarn(?:ing)?\b", re.IGNORECASE)
_RECOVERY = re.compile(r"\b(recover|reattach|resumed|detached)\b", re.IGNORECASE)
_OPEN_QUESTION = re.compile(r"^\s*(?:TODO|OPEN QUESTION|QUESTION)\s*[:\-]\s*(.+)$", re.IGNORECASE)


def extract_transcript(text: str) -> Extraction:
    """Preserve prompts, approval moments, tool-call attention points, and recovery.

    Everything a reviewer needs to reconstruct *what a human was asked to decide* and
    *what went wrong*, in redacted form. Ordinary output lines are not events.
    """
    key: list[SummaryMarker] = []
    failures: list[SummaryMarker] = []
    warnings: list[SummaryMarker] = []
    questions: list[str] = []
    last: str | None = None
    ordinal = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        last = stripped[:200]
        ordinal += 1
        prompt = _PROMPT.match(stripped)
        if prompt:
            key.append(SummaryMarker(ordinal, "user_prompt", prompt.group(1)[:200]))
        elif _APPROVAL.search(stripped):
            key.append(SummaryMarker(ordinal, "approval_requested", stripped[:200]))
        elif _RECOVERY.search(stripped):
            key.append(SummaryMarker(ordinal, "recovery_marker", stripped[:200]))
        if _FAILURE.search(stripped):
            failures.append(SummaryMarker(ordinal, "failure", stripped[:200]))
        elif _WARNING.search(stripped):
            warnings.append(SummaryMarker(ordinal, "warning", stripped[:200]))
        question = _OPEN_QUESTION.match(stripped)
        if question:
            questions.append(question.group(1)[:200])
    # A transcript that never reached a terminal marker was interrupted; the summary
    # says so rather than presenting a partial run as a finished one.
    complete = bool(text) and _RECOVERY.search(text.splitlines()[-1] if text.splitlines() else "") is not None
    return Extraction(tuple(key), tuple(failures), tuple(warnings), tuple(questions), last, complete)


def extract_command_log(text: str) -> Extraction:
    """Preserve command order, duration, exit code, and every failed command."""
    key: list[SummaryMarker] = []
    failures: list[SummaryMarker] = []
    complete = True
    for ordinal, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            # A truncated final line means the run was cut off mid-write.
            complete = False
            continue
        command = str(entry.get("command", ""))[:200]
        exit_code = entry.get("exit_code")
        duration = entry.get("duration_ms")
        marker = SummaryMarker(
            ordinal, "command", command,
            exit_code=exit_code if isinstance(exit_code, int) else None,
            duration_ms=duration if isinstance(duration, int) else None,
        )
        if isinstance(exit_code, int) and exit_code != 0:
            failures.append(marker)
        else:
            key.append(marker)
    return Extraction(tuple(key), tuple(failures), input_complete=complete)


# `[^\s:]+` rather than `\S+`: greedy \S+ swallows the delimiting colon into the
# rule name, so the summary would report "out_of_scope_present:" as the rule.
_VALIDATOR_RULE = re.compile(r"^\[(PASS|FAIL)\]\s+([^\s:]+)\s*:?\s*(.*)$")
_REMEDIATION = re.compile(r"^\s*remediation\s*:\s*(.+)$", re.IGNORECASE)
_EXIT = re.compile(r"^exit code:\s*(\d+)$", re.IGNORECASE)


def extract_validator_output(text: str) -> Extraction:
    """Preserve command, exit code, pass/fail, failed rule names, and remediation hints.

    Passing rules are counted, not listed: a reviewer reading a validator summary is
    looking for what failed, and 200 lines of `[PASS]` buries it.
    """
    failures: list[SummaryMarker] = []
    key: list[SummaryMarker] = []
    passed = 0
    exit_code: int | None = None
    for ordinal, line in enumerate(text.splitlines(), start=1):
        rule = _VALIDATOR_RULE.match(line.strip())
        if rule:
            if rule.group(1) == "FAIL":
                failures.append(SummaryMarker(ordinal, rule.group(2), rule.group(3)[:200] or None))
            else:
                passed += 1
            continue
        remediation = _REMEDIATION.match(line)
        if remediation and failures:
            last = failures[-1]
            failures[-1] = SummaryMarker(
                last.ordinal, last.label,
                f"{last.detail} | remediation: {remediation.group(1)[:200]}" if last.detail
                else f"remediation: {remediation.group(1)[:200]}",
            )
            continue
        exit_match = _EXIT.match(line.strip())
        if exit_match:
            exit_code = int(exit_match.group(1))
    key.append(SummaryMarker(0, "rules_passed", str(passed)))
    if exit_code is not None:
        key.append(SummaryMarker(1, "exit_code", str(exit_code), exit_code=exit_code))
    return Extraction(tuple(key), tuple(failures))


def extract_structured(text: str) -> Extraction:
    """Manifest, status, and metric artifacts: declared fields and their values.

    Scalars only, sorted by key. Nested objects are summarised by their key count rather
    than flattened, because a flattened manifest is longer than the manifest.
    """
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return Extraction((), (SummaryMarker(1, "unparseable", "document is not valid JSON"),),
                          input_complete=False)
    if not isinstance(document, dict):
        return Extraction((), (SummaryMarker(1, "unexpected_shape", "document is not an object"),))
    key: list[SummaryMarker] = []
    failures: list[SummaryMarker] = []
    for ordinal, name in enumerate(sorted(document), start=1):
        value = document[name]
        if isinstance(value, (str, int, float, bool)) or value is None:
            rendered = str(value)[:200]
        elif isinstance(value, dict):
            rendered = f"<{len(value)} field(s)>"
        else:
            rendered = f"<{len(value)} item(s)>"
        marker = SummaryMarker(ordinal, name, rendered)
        if isinstance(value, str) and value.upper() in {"FAIL", "FAILED", "BLOCKED", "NOT READY"}:
            failures.append(marker)
        else:
            key.append(marker)
    return Extraction(tuple(key), tuple(failures))


EXTRACTORS = {
    ArtifactKind.TRANSCRIPT: extract_transcript,
    ArtifactKind.COMMAND_LOG: extract_command_log,
    ArtifactKind.VALIDATOR_OUTPUT: extract_validator_output,
    ArtifactKind.MANIFEST: extract_structured,
    ArtifactKind.STATUS: extract_structured,
    ArtifactKind.METRIC: extract_structured,
}


def extract(kind: ArtifactKind, payload: bytes) -> tuple[Extraction, bool, bool]:
    """Run the extractor for `kind`. Returns the extraction, supported, and extracted."""
    if kind not in SUPPORTED_KINDS:
        return Extraction((), ()), False, False
    text, findings, is_text = decode(payload)
    if not is_text:
        return Extraction((), (), redaction_findings=findings), False, False
    try:
        result = EXTRACTORS[kind](text)
    except Exception:
        # An extractor fault must leave the artifact indexed with summary_status Failed,
        # never take down the indexing call that produced it.
        return Extraction((), (), redaction_findings=findings), True, False
    return (
        Extraction(
            result.key_events, result.failure_markers, result.warning_markers,
            result.open_questions, result.last_observed_marker, result.input_complete,
            findings,
        ),
        True,
        True,
    )


class RuleBasedSummaryExtractor:
    """The `SummaryExtractor` port, implemented by the rule set in this module."""

    @property
    def rule_set_version(self) -> str:
        return RULE_SET_VERSION

    def extract(self, kind: ArtifactKind, payload: bytes):
        return extract(kind, payload)


class FilesystemSummaryStore:
    """One summary artifact per source artifact, atomic and owner-only."""

    def __init__(self, runs_root: Path, schema, lock_timeout_seconds: float = 5.0) -> None:
        self._runs_root = runs_root
        self._schema = schema
        self._lock_timeout = lock_timeout_seconds

    def relative_path(self, summary_id: str) -> str:
        return f"summaries/{summary_id}.json"

    def save(self, run_id: str, summary) -> None:
        directory = self._runs_root / run_id / "summaries"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        assert_owner_only_directory(directory)
        payload = {"schema_version": "1.0", **serialize_record(summary)}
        self._schema.validate("f0003-artifact-summary.schema.json", payload)
        with owner_only_lock(directory, self._lock_timeout, ".summaries.lock"):
            pending = directory / f"{summary.summary_id}.pending.json"
            write_owner_only(pending, json_bytes(payload, pretty=True))
            publish_atomic(directory, pending, directory / f"{summary.summary_id}.json")

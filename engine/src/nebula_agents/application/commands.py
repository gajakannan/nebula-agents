"""The command facade (F0003-S0007).

Every application operation that writes a record, appends a runtime event, or
otherwise changes run, gate, transcript, artifact, or proposal state is reachable
through this object and only through this object.

The split is a Phase B interface commitment, not an implementation detail: the MCP
presentation adapter is constructed with the *query* facade alone, so no mutating
service is reachable from it. Read-only is a consequence of what was wired in rather
than a promise repeated in each handler (ADR-007).

This facade adds no authorization check and removes none. Every operation continues to
evaluate policy inside the service that owns it, exactly as it did before the split,
and appends the same runtime events with the same payload shapes.
"""

from __future__ import annotations

from dataclasses import dataclass

from .evidence import EvidenceService
from .gates import GateService
from .runs import RunService
from .transcripts import TranscriptService


@dataclass(frozen=True, slots=True)
class CommandService:
    """Aggregates the mutating application services.

    Steps 4 and 6 of the F0003 assembly plan add `capabilities` and `learning` here.
    They are absent rather than stubbed, so the facade never claims a capability that
    does not exist yet.
    """

    runs: RunService
    gates: GateService
    transcripts: TranscriptService
    evidence: EvidenceService

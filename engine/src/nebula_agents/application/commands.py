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

from nebula_agents.domain.models import Actor, LaunchRequest

from .capabilities import CapabilityService
from .evidence import EvidenceService
from .gates import GateService
from .learning import LearningService
from .runs import RunService
from .transcripts import TranscriptService


@dataclass(frozen=True, slots=True)
class CommandService:
    """Aggregates the mutating application services.

    Every mutating F0003 service is now present: evidence indexing and summarization,
    capability probing, and learning-proposal drafting and decision.
    """

    runs: RunService
    gates: GateService
    transcripts: TranscriptService
    evidence: EvidenceService
    capabilities: CapabilityService
    learning: LearningService

    def wrap(self, request: LaunchRequest, actor: Actor):
        """Preflight + capability guard + launch + registration, as one operator step.

        `wrap` supersedes nothing: F0001's `launch` remains the primitive and is called
        unchanged. The only thing `wrap` adds ahead of it is the guard.

        Guard BEFORE launch is the whole point -- a blocked launch must persist no
        session and create no run. `guard` raises exit 3, so control never reaches
        `launch`.
        """
        self.capabilities.guard(request.provider_key, actor)
        return self.runs.launch(request, actor)

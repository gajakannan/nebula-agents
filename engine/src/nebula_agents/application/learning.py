"""Failure-learning proposals (F0003-S0006, ADR-009).

`review` drafts; `decide` records. They are **separate operations with separate
authorization**, because drafting is safe to run automatically and deciding is not. One
capability covering both would let an automated caller approve its own proposals — the
escalation path this split closes by construction rather than by policy text.

Nothing here opens a target document. Applying an accepted proposal is outside F0003's
automated scope.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime

from nebula_agents.domain.enums import (
    Action,
    Confidence,
    ProposalDecisionKind,
    ProposalStatus,
    ReviewerRole,
    SummaryStatus,
)
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import Actor
from nebula_agents.domain.proposals import (
    LearningProposal,
    ProposalDecision,
    authorized_role,
    suppressed_by_rejection,
)
from nebula_agents.domain.transitions import advance

from .runs import commit_authorized, require_authorized, runtime_event

#: What a failure in a given artifact kind suggests correcting, and where.
#:
#: The mapping is deliberately small and explicit. A proposal that cannot name a target
#: from evidence is not drafted at all — inventing one would be the model-generated
#: content ADR-008 excludes, wearing a different hat.
TARGET_BY_KIND = {
    "validator-output": (
        "planning-mds/features/REGISTRY.md",
        "A validator failed repeatedly; the authoring guidance may be unclear.",
    ),
    "command-log": (
        "planning-mds/architecture/SOLUTION-PATTERNS.md",
        "A command failed during the run; the documented procedure may be wrong.",
    ),
    "transcript": (
        "planning-mds/architecture/SOLUTION-PATTERNS.md",
        "The session hit a failure a documented pattern could have prevented.",
    ),
}


class LearningService:
    def __init__(self, *, repository, index, summaries, store, authorization, clock) -> None:
        self._repository = repository
        self._index = index
        self._summaries = summaries
        self._store = store
        self._authorization = authorization
        self._clock = clock

    # ------------------------------------------------------------------ #
    # Drafting
    # ------------------------------------------------------------------ #
    def review(self, run_id: str, actor: Actor, scope: str | None = None) -> tuple[LearningProposal, ...]:
        """Draft proposals from failed or incomplete run evidence.

        A clean run drafts nothing and succeeds. That is a result, not an error: "no
        proposal generated" is the correct answer for a run that went well.
        """
        run = self._repository.load(run_id)
        require_authorized(self._repository, self._authorization, run, actor, Action.DRAFT_PROPOSAL)

        now = self._clock.now()
        document = self._index.load(run_id)
        self._require_usable_evidence(document, run_id)

        existing = {p.proposal_id: p for p in self._store.list(run_id)}
        drafted: list[LearningProposal] = []
        for kind, group in self._failing_groups(run_id, document).items():
            target, rationale = TARGET_BY_KIND[kind]
            hashes = tuple(sorted(h for h in group["hashes"] if h))
            proposal_id = _proposal_id(run_id, target, kind)
            prior = existing.get(proposal_id)
            # Sticky rejection: the same evidence must not be re-raised at a reviewer who
            # already declined it. Changed evidence deserves a fresh look.
            if prior is not None and suppressed_by_rejection(prior, hashes):
                continue
            drafted.append(
                LearningProposal(
                    proposal_id=proposal_id,
                    run_id=run_id,
                    generated_at=now,
                    source_artifact_ids=tuple(sorted(group["artifact_ids"])),
                    target_document=target,
                    proposal_summary=f"{rationale} Evidence: {len(group['artifact_ids'])} artifact(s).",
                    proposal_status=ProposalStatus.DRAFT,
                    source_content_hashes=hashes,
                    confidence=Confidence.HIGH if len(group["artifact_ids"]) > 1 else Confidence.MEDIUM,
                )
            )

        for proposal in drafted:
            self._store.save(run_id, proposal)
        if drafted:
            commit_authorized(
                self._repository, self._authorization,
                expected_revision=run.revision,
                next_record=advance(run, now=now),
                event=runtime_event(
                    run, actor, "ProposalDrafted", now,
                    {
                        "proposal_count": len(drafted),
                        "proposals": [
                            {
                                "proposal_id": p.proposal_id,
                                "target_document": p.target_document,
                                "source_artifact_ids": list(p.source_artifact_ids),
                            }
                            for p in drafted
                        ],
                    },
                ),
                actor=actor, action=Action.DRAFT_PROPOSAL,
            )
        return tuple(drafted)

    def _require_usable_evidence(self, document, run_id: str) -> None:
        """Stale or missing evidence blocks generation until it is resolved.

        Drafting from evidence that may no longer exist produces a proposal a reviewer
        cannot verify, which is worse than no proposal.
        """
        if any(entry.freshness_status.value in {"stale", "missing"} for entry in document.entries):
            raise error(
                ErrorCode.EVIDENCE_STALE,
                "Run evidence is stale or missing; proposals cannot be drafted from it.",
                "gate-blocked",
                "Re-run `evidence index` for this run, then retry.",
                run_id=run_id,
            )

    def _failing_groups(self, run_id: str, document) -> dict:
        """Group failing evidence by artifact kind.

        Multiple failures mapping to one proposal share it, with their artifact ids
        grouped — one proposal per correction, not one per symptom.
        """
        groups: dict[str, dict] = {}
        for entry in document.entries:
            kind = entry.artifact_kind.value
            if kind not in TARGET_BY_KIND or entry.summary_path is None:
                continue
            summary = self._summaries.load(run_id, entry.summary_path)
            if summary is None or not summary.failure_markers:
                continue
            if summary.summary_status is SummaryStatus.BLOCKED:
                continue
            bucket = groups.setdefault(kind, {"artifact_ids": set(), "hashes": set()})
            bucket["artifact_ids"].add(entry.artifact_id)
            bucket["hashes"].add(entry.content_hash)
        return groups

    # ------------------------------------------------------------------ #
    # Deciding
    # ------------------------------------------------------------------ #
    def decide(
        self,
        run_id: str,
        proposal_id: str,
        decision: ProposalDecisionKind,
        actor: Actor,
        reason: str | None = None,
        patch_plan: str | None = None,
    ) -> LearningProposal:
        """Record a decision. Never opens the target document.

        The reviewer role is **derived from the target document and verified against the
        committed policy** — it is not an argument. An earlier revision took it from the
        caller, which meant a `LocalOperator` could pass `--role architect` and decide an
        architecture proposal: the check compared the *declared* role to the required one
        and never asked whether the actor held it. That reopened the escalation path
        ADR-009's draft/decide split exists to close, from the other side.

        Authority comes from `proposal_grants` in the policy file, per target-document
        class, deny by default. Owning the run confers nothing (BLUEPRINT §5.4).
        """
        run = self._repository.load(run_id)
        require_authorized(
            self._repository, self._authorization, run, actor, Action.DECIDE_PROPOSAL
        )
        proposal = self._store.load(run_id, proposal_id)
        if proposal is None:
            raise error(
                ErrorCode.PROPOSAL_NOT_FOUND, "Proposal is not recorded for this run.",
                "not-found", "List proposals with `learn list`.", proposal_id=proposal_id,
            )
        required = authorized_role(proposal.target_document)
        held = self._authorization.decider_roles(actor)
        if required.value not in held:
            raise error(
                ErrorCode.FORBIDDEN,
                "You do not hold the reviewer role that owns this proposal's target.",
                "forbidden",
                f"A decision on {proposal.target_document} requires the "
                f"{required.value} role, granted in policy.json under proposal_grants.",
                proposal_id=proposal_id,
            )
        reviewer_role = required
        now = self._clock.now()
        decided = proposal.decide(
            ProposalDecision(now, decision, reviewer_role, actor.username, reason)
        )
        if patch_plan is not None:
            # Recorded alongside the decision; `accept` still does not open the target.
            decided = replace(decided, patch_plan=patch_plan)
        self._store.save(run_id, decided)
        commit_authorized(
            self._repository, self._authorization,
            expected_revision=run.revision,
            next_record=advance(run, now=now),
            event=runtime_event(
                run, actor, "ProposalDecided", now,
                {
                    "proposal_id": proposal_id,
                    "decision": decision.value,
                    "reviewer_role": reviewer_role.value,
                    "target_document": proposal.target_document,
                    "source_artifact_ids": list(proposal.source_artifact_ids),
                },
            ),
            actor=actor, action=Action.DECIDE_PROPOSAL,
        )
        return decided


def _proposal_id(run_id: str, target: str, kind: str) -> str:
    """Stable across re-review, so re-running does not accumulate duplicates."""
    digest = hashlib.sha256(f"{run_id}|{target}|{kind}".encode("utf-8")).hexdigest()
    return f"p-{digest[:16]}"

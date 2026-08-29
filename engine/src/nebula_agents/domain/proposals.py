"""Learning proposals and their decisions (F0003-S0006, ADR-009).

Three rules shape this module, and each closes a specific hole:

- A proposal is **inert**. It records a suggestion; it never opens the target document.
  Applying an accepted proposal is outside F0003's automated scope.
- A target outside the committed allowlist is refused **at generation**, so `learn
  decide` never evaluates an out-of-allowlist path.
- Rejection is **sticky**, pinned to the source content hashes. A rejected proposal is
  not regenerated unless its source evidence actually changed — otherwise every run
  would re-raise what a reviewer already declined.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import PurePosixPath

from .enums import (
    Confidence,
    ProposalDecisionKind,
    ProposalStatus,
    ReviewerRole,
)
from .errors import ErrorCode, error

#: Target-document classes and the role authorized to decide them.
#:
#: `DecideProposal` is evaluated against the TARGET DOCUMENT, not the run. Owning a run
#: does not confer the right to decide its proposals (BLUEPRINT 5.4).
TARGET_ROLES: dict[str, ReviewerRole] = {
    "planning-mds/security": ReviewerRole.SECURITY,
    "planning-mds/architecture": ReviewerRole.ARCHITECT,
    "agents": ReviewerRole.ARCHITECT,
    "planning-mds/features": ReviewerRole.PRODUCT_MANAGER,
    "planning-mds/operations": ReviewerRole.PRODUCT_MANAGER,
}


def authorized_role(target_document: str) -> ReviewerRole:
    """Resolve who may decide a proposal from its target path, by longest prefix.

    Longest prefix, not first match: `planning-mds/security` must win over a broader
    `planning-mds` entry however the mapping is ordered.
    """
    path = PurePosixPath(target_document)
    matches = [
        (len(PurePosixPath(prefix).parts), role)
        for prefix, role in TARGET_ROLES.items()
        if path.is_relative_to(PurePosixPath(prefix))
    ]
    if not matches:
        raise error(
            ErrorCode.PROPOSAL_TARGET_FORBIDDEN,
            "Proposal target is outside the committed allowlist.",
            "forbidden",
            "Propose against an allowlisted instruction path.",
            target_document=target_document,
        )
    return max(matches)[1]


def assert_target_allowed(target_document: str) -> None:
    """Called at generation. After this, `learn decide` never sees a bad target."""
    if PurePosixPath(target_document).is_absolute() or ".." in PurePosixPath(target_document).parts:
        raise error(
            ErrorCode.PROPOSAL_TARGET_FORBIDDEN,
            "Proposal target must be a workspace-relative path without traversal.",
            "forbidden",
            "Name the target document relative to the workspace root.",
            target_document=target_document,
        )
    authorized_role(target_document)


@dataclass(frozen=True, slots=True)
class ProposalDecision:
    decided_at: datetime
    decision: ProposalDecisionKind
    reviewer_role: ReviewerRole
    reviewer: str | None = None
    decision_reason: str | None = None

    def __post_init__(self) -> None:
        if self.decision.requires_reason and not self.decision_reason:
            raise error(
                ErrorCode.USAGE_ERROR,
                f"--reason is required for {self.decision.value.lower()}.",
                "usage",
                "Re-run learn decide with --reason.",
                decision=self.decision.value,
            )


@dataclass(frozen=True, slots=True)
class LearningProposal:
    proposal_id: str
    run_id: str
    generated_at: datetime
    source_artifact_ids: tuple[str, ...]
    target_document: str
    proposal_summary: str
    proposal_status: ProposalStatus
    decisions: tuple[ProposalDecision, ...] = ()
    source_content_hashes: tuple[str, ...] = ()
    confidence: Confidence | None = None
    patch_plan: str | None = None

    def __post_init__(self) -> None:
        if not self.source_artifact_ids:
            raise error(
                ErrorCode.USAGE_ERROR,
                "A proposal must link to at least one source artifact.",
                "usage",
                "Generate proposals from indexed run evidence.",
                proposal_id=self.proposal_id,
            )
        assert_target_allowed(self.target_document)
        decided_at = [d.decided_at for d in self.decisions]
        if decided_at != sorted(decided_at):
            raise error(
                ErrorCode.CONFLICT,
                "Proposal decisions are not in chronological order.",
                "conflict",
                "Append decisions; never reorder or rewrite them.",
                proposal_id=self.proposal_id,
            )

    def decide(self, decision: ProposalDecision) -> LearningProposal:
        """Append a decision. Append-only: a later decision never rewrites an earlier one.

        The authorization check is the caller's — this asserts only that the recorded
        reviewer role is one that could own this target, so an append cannot fabricate
        an authority the target does not grant.
        """
        expected = authorized_role(self.target_document)
        if decision.reviewer_role is not expected:
            raise error(
                ErrorCode.FORBIDDEN,
                "Reviewer role does not own this proposal's target document.",
                "forbidden",
                f"A decision on {self.target_document} requires the {expected.value} role.",
                proposal_id=self.proposal_id,
            )
        return replace(
            self,
            decisions=(*self.decisions, decision),
            proposal_status=ProposalStatus(decision.decision.value),
        )


def suppressed_by_rejection(
    prior: LearningProposal, source_content_hashes: tuple[str, ...]
) -> bool:
    """Whether a regenerated proposal must be suppressed as already rejected.

    Sticky rejection is pinned to the source content hashes rather than to the proposal
    text: the same evidence must not be re-raised, but changed evidence deserves a fresh
    look. Comparison is order-insensitive because artifact ordering is not meaningful.
    """
    if prior.proposal_status is not ProposalStatus.REJECTED:
        return False
    return set(prior.source_content_hashes) == set(source_content_hashes)

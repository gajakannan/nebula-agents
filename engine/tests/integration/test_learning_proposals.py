"""F0003-S0006 — the learning-proposal workflow end to end (ADR-009).

Checkpoint D. The properties that matter are the ones that keep proposals *inert* and
keep drafting separate from deciding.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from nebula_agents.bootstrap import build_application
from nebula_agents.domain.enums import (
    ProposalDecisionKind,
    ProposalStatus,
    ProviderKey,
    PromptAction,
    ReviewerRole,
)
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import LaunchRequest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "summaries"


@pytest.fixture
def run_with_failures(tmp_path: Path, schema_root: Path):
    ws = tmp_path / "workspace"
    (ws / "planning-mds" / "schemas").mkdir(parents=True)
    for schema in schema_root.glob("f000*-*.json"):
        shutil.copy2(schema, ws / "planning-mds" / "schemas" / schema.name)
    (ws / "planning-mds" / "features" / "F0001-test").mkdir(parents=True)
    evidence = ws / "planning-mds" / "operations" / "evidence"
    evidence.mkdir(parents=True)
    prompts = ws / "agents" / "templates" / "prompts" / "evidence-contract"
    prompts.mkdir(parents=True)
    (prompts / "feature-operator-friendly.md").write_text("FEATURE_ID={F####}\n", encoding="utf-8")

    runtime = tmp_path / "runtime"
    app = build_application(ws, runtime)
    actor = app.current_actor()

    class Provider:
        def build_interactive_argv(self, _r, _p):
            return (str(Path(sys.executable).resolve()), "-c", "pass")

    class Tmux:
        def __init__(self): self.presence = [False, True]
        def has_session(self, _n): return self.presence.pop(0) if len(self.presence) > 1 else self.presence[0]
        def create_session(self, _n, _d): return None

    app.runs._preflight = SimpleNamespace(
        require_ready=lambda *a: SimpleNamespace(
            prompt_contract_path=str(prompts / "feature-operator-friendly.md"))
    )
    app.runs._providers = {ProviderKey.CODEX: Provider()}
    app.runs._tmux = Tmux()
    record = app.runs.launch(
        LaunchRequest("F0001", None, ProviderKey.CODEX, PromptAction.FEATURE, None, None, False), actor
    )
    return SimpleNamespace(app=app, actor=actor, run_id=record.run_id,
                           runtime=runtime, evidence=evidence)


def grant(ctx, *roles: str) -> None:
    """Grant proposal-decision authority in the committed policy, as an operator would.

    Written into policy.json rather than passed as an argument, because that is the whole
    point of the fix: authority comes from the 0600 policy file, not from the caller.
    """
    keys = {"architect": "can_decide_architecture", "security": "can_decide_security",
            "product-manager": "can_decide_planning"}
    path = ctx.runtime / "policy.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["proposal_grants"] = {keys[role]: True for role in roles}
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def with_failing_evidence(ctx, *fixtures: tuple[str, str]):
    paths = []
    for fixture, name in fixtures:
        shutil.copy2(FIXTURES / fixture, ctx.evidence / name)
        paths.append(ctx.evidence / name)
    ctx.app.evidence.index_artifacts(ctx.run_id, paths, ctx.actor)
    ctx.app.evidence.summarize(ctx.run_id, ctx.actor)
    return paths


def test_a_clean_run_drafts_nothing_and_succeeds(run_with_failures) -> None:
    """"No proposal generated" is the correct answer for a run that went well."""
    ctx = run_with_failures
    shutil.copy2(FIXTURES / "manifest.json", ctx.evidence / "m.json")
    ctx.app.evidence.index_artifacts(ctx.run_id, [ctx.evidence / "m.json"], ctx.actor)
    ctx.app.evidence.summarize(ctx.run_id, ctx.actor)
    assert ctx.app.learning.review(ctx.run_id, ctx.actor) == ()


def test_failures_draft_proposals_linked_to_their_source_artifacts(run_with_failures) -> None:
    ctx = run_with_failures
    with_failing_evidence(ctx, ("validator-output.txt", "validator.txt"),
                          ("command-log.jsonl", "commands.log"))

    drafted = ctx.app.learning.review(ctx.run_id, ctx.actor)

    assert len(drafted) == 2
    assert all(p.proposal_status is ProposalStatus.DRAFT for p in drafted)
    assert all(p.source_artifact_ids for p in drafted)
    assert all(p.source_content_hashes for p in drafted)
    # Different evidence kinds route to different targets, and therefore different roles.
    assert len({p.target_document for p in drafted}) == 2


def test_proposals_are_inert_artifacts_on_disk(run_with_failures) -> None:
    """A proposal records a suggestion. It never opens the target document."""
    ctx = run_with_failures
    with_failing_evidence(ctx, ("validator-output.txt", "validator.txt"))
    drafted = ctx.app.learning.review(ctx.run_id, ctx.actor)[0]

    path = ctx.runtime / "runs" / ctx.run_id / "proposals" / f"{drafted.proposal_id}.json"
    assert path.exists() and stat.S_IMODE(path.lstat().st_mode) == 0o600
    # The named target must not have been created or touched anywhere.
    assert not (ctx.runtime / drafted.target_document).exists()


def test_re_reviewing_is_idempotent_rather_than_accumulating(run_with_failures) -> None:
    ctx = run_with_failures
    with_failing_evidence(ctx, ("validator-output.txt", "validator.txt"))
    ctx.app.learning.review(ctx.run_id, ctx.actor)
    ctx.app.learning.review(ctx.run_id, ctx.actor)
    assert len(ctx.app.queries.proposals(ctx.run_id, ctx.actor)) == 1


def test_owning_the_run_does_not_confer_the_right_to_decide(run_with_failures) -> None:
    """The rule a Security Reviewer needs to be able to verify.

    The actor owns the run and holds no proposal grant. Deny by default.
    """
    ctx = run_with_failures
    with_failing_evidence(ctx, ("validator-output.txt", "validator.txt"))
    proposal = ctx.app.learning.review(ctx.run_id, ctx.actor)[0]
    grant(ctx, "architect")

    with pytest.raises(NebulaError) as caught:
        ctx.app.learning.decide(
            ctx.run_id, proposal.proposal_id, ProposalDecisionKind.ACCEPTED, ctx.actor
        )
    assert caught.value.code is ErrorCode.FORBIDDEN
    assert caught.value.exit_code == 5


def test_a_grant_for_one_target_class_does_not_carry_to_another(run_with_failures) -> None:
    """Granted per target-document class, never blanket (BLUEPRINT §5.4).

    This is the regression test for a real finding: an earlier revision took the reviewer
    role from the CALLER, so a LocalOperator could name `architect` and decide an
    architecture proposal. The role is now derived from the target and verified against
    policy.json, so naming it is not possible and holding one class grants only that one.
    """
    ctx = run_with_failures
    with_failing_evidence(ctx, ("validator-output.txt", "validator.txt"),
                          ("command-log.jsonl", "commands.log"))
    drafted = ctx.app.learning.review(ctx.run_id, ctx.actor)
    by_target = {p.target_document: p for p in drafted}
    architecture = by_target["planning-mds/architecture/SOLUTION-PATTERNS.md"]
    planning = by_target["planning-mds/features/REGISTRY.md"]

    grant(ctx, "architect")

    decided = ctx.app.learning.decide(
        ctx.run_id, architecture.proposal_id, ProposalDecisionKind.ACCEPTED, ctx.actor
    )
    assert decided.decisions[0].reviewer_role is ReviewerRole.ARCHITECT

    with pytest.raises(NebulaError) as caught:
        ctx.app.learning.decide(
            ctx.run_id, planning.proposal_id, ProposalDecisionKind.ACCEPTED, ctx.actor
        )
    assert caught.value.code is ErrorCode.FORBIDDEN
    assert "product-manager" in caught.value.remediation


def test_reject_records_a_reason_and_is_append_only(run_with_failures) -> None:
    ctx = run_with_failures
    with_failing_evidence(ctx, ("command-log.jsonl", "commands.log"))
    proposal = ctx.app.learning.review(ctx.run_id, ctx.actor)[0]
    grant(ctx, "architect")

    decided = ctx.app.learning.decide(
        ctx.run_id, proposal.proposal_id, ProposalDecisionKind.REJECTED,
        ctx.actor, reason="documented behaviour is correct",
    )
    assert decided.proposal_status is ProposalStatus.REJECTED
    assert decided.decisions[0].decision_reason == "documented behaviour is correct"

    followed = ctx.app.learning.decide(
        ctx.run_id, proposal.proposal_id, ProposalDecisionKind.ARCHIVED,
        ctx.actor, reason="superseded",
    )
    assert len(followed.decisions) == 2
    assert followed.decisions[0] == decided.decisions[0]


def test_rejection_is_sticky_until_the_source_evidence_changes(run_with_failures) -> None:
    ctx = run_with_failures
    with_failing_evidence(ctx, ("command-log.jsonl", "commands.log"))
    proposal = ctx.app.learning.review(ctx.run_id, ctx.actor)[0]
    grant(ctx, "architect")
    ctx.app.learning.decide(
        ctx.run_id, proposal.proposal_id, ProposalDecisionKind.REJECTED,
        ctx.actor, reason="declined",
    )

    assert ctx.app.learning.review(ctx.run_id, ctx.actor) == ()

    # Changed evidence deserves a fresh look.
    (ctx.evidence / "commands.log").write_text(
        '{"command":"different","exit_code":2,"duration_ms":9}\n', encoding="utf-8"
    )
    ctx.app.evidence.index_artifacts(ctx.run_id, [ctx.evidence / "commands.log"], ctx.actor)
    ctx.app.evidence.summarize(ctx.run_id, ctx.actor)
    assert len(ctx.app.learning.review(ctx.run_id, ctx.actor)) == 1


def test_accept_records_the_decision_without_opening_the_target(run_with_failures) -> None:
    """Applying an accepted proposal is outside F0003's automated scope."""
    ctx = run_with_failures
    with_failing_evidence(ctx, ("command-log.jsonl", "commands.log"))
    proposal = ctx.app.learning.review(ctx.run_id, ctx.actor)[0]
    grant(ctx, "architect")

    decided = ctx.app.learning.decide(
        ctx.run_id, proposal.proposal_id, ProposalDecisionKind.ACCEPTED,
        ctx.actor, patch_plan="add a retry note to §7",
    )
    assert decided.proposal_status is ProposalStatus.ACCEPTED
    assert decided.patch_plan == "add a retry note to §7"


def test_stale_evidence_blocks_drafting_until_it_is_resolved(run_with_failures) -> None:
    """A proposal drawn from evidence a reviewer cannot open is worse than none."""
    ctx = run_with_failures
    paths = with_failing_evidence(ctx, ("command-log.jsonl", "commands.log"))
    paths[0].unlink()
    ctx.app.evidence.index_artifacts(ctx.run_id, paths, ctx.actor)

    with pytest.raises(NebulaError) as caught:
        ctx.app.learning.review(ctx.run_id, ctx.actor)
    assert caught.value.code is ErrorCode.EVIDENCE_STALE
    assert caught.value.exit_code == 7


def test_drafting_and_deciding_each_append_one_audit_event(run_with_failures) -> None:
    ctx = run_with_failures
    with_failing_evidence(ctx, ("command-log.jsonl", "commands.log"))
    proposal = ctx.app.learning.review(ctx.run_id, ctx.actor)[0]
    grant(ctx, "architect")
    ctx.app.learning.decide(
        ctx.run_id, proposal.proposal_id, ProposalDecisionKind.EDITED,
        ctx.actor,
    )

    events = [
        json.loads(line)
        for line in (ctx.runtime / "runs" / ctx.run_id / "events.jsonl")
        .read_text(encoding="utf-8").splitlines()
    ]
    drafted = [e for e in events if e["event_type"] == "ProposalDrafted"]
    decided = [e for e in events if e["event_type"] == "ProposalDecided"]
    assert len(drafted) == 1 and len(decided) == 1
    assert decided[0]["payload"]["reviewer_role"] == "architect"
    assert decided[0]["payload"]["target_document"] == proposal.target_document


def test_deciding_an_unknown_proposal_is_not_found(run_with_failures) -> None:
    ctx = run_with_failures
    with pytest.raises(NebulaError) as caught:
        ctx.app.learning.decide(
            ctx.run_id, "p-0000000000000000", ProposalDecisionKind.ACCEPTED,
            ctx.actor,
        )
    assert caught.value.code is ErrorCode.PROPOSAL_NOT_FOUND

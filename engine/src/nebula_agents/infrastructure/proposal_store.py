"""Learning-proposal storage (F0003-S0006, ADR-009).

One atomic JSON document per proposal under the run, written with the ADR-002 discipline
the other stores share.

Proposals are **inert artifacts**. Nothing here opens, reads, or writes a target
document — this store persists a suggestion and the decisions recorded against it, and
that is the whole of its authority.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from nebula_agents.domain.enums import Confidence, ProposalDecisionKind, ProposalStatus, ReviewerRole
from nebula_agents.domain.models import serialize_record
from nebula_agents.domain.proposals import LearningProposal, ProposalDecision

from .atomic import (
    FILE_MODE,
    assert_owner_only_directory,
    json_bytes,
    owner_only_lock,
    publish_atomic,
    write_owner_only,
)
from .schema_registry import JsonSchemaRegistry

SCHEMA = "f0003-learning-proposal.schema.json"
PROPOSALS_DIRNAME = "proposals"


class FilesystemProposalStore:
    def __init__(self, runs_root: Path, schema: JsonSchemaRegistry, lock_timeout_seconds: float = 5.0) -> None:
        self._runs_root = runs_root
        self._schema = schema
        self._lock_timeout = lock_timeout_seconds

    def _directory(self, run_id: str) -> Path:
        return self._runs_root / run_id / PROPOSALS_DIRNAME

    def list(self, run_id: str) -> tuple[LearningProposal, ...]:
        """An absent directory reads as no proposals. A read never creates it."""
        directory = self._directory(run_id)
        if not directory.is_dir() or directory.is_symlink():
            return ()
        found = []
        for path in sorted(directory.glob("*.json")):
            proposal = self._load_path(path)
            if proposal is not None:
                found.append(proposal)
        return tuple(found)

    def load(self, run_id: str, proposal_id: str) -> LearningProposal | None:
        return self._load_path(self._directory(run_id) / f"{proposal_id}.json")

    def _load_path(self, path: Path) -> LearningProposal | None:
        if not path.is_file() or path.is_symlink():
            return None
        try:
            details = path.lstat()
            if details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != FILE_MODE:
                return None
            document = json.loads(path.read_text(encoding="utf-8"))
            self._schema.validate(SCHEMA, document)
            return _proposal_from(document)
        except Exception:
            return None

    def save(self, run_id: str, proposal: LearningProposal) -> None:
        directory = self._directory(run_id)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        assert_owner_only_directory(directory)
        payload = {"schema_version": "1.0", **serialize_record(proposal)}
        self._schema.validate(SCHEMA, payload)
        with owner_only_lock(directory, self._lock_timeout, ".proposals.lock"):
            pending = directory / f"{proposal.proposal_id}.pending.json"
            write_owner_only(pending, json_bytes(payload, pretty=True))
            publish_atomic(directory, pending, directory / f"{proposal.proposal_id}.json")


def _parsed(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _proposal_from(document: dict) -> LearningProposal:
    return LearningProposal(
        proposal_id=str(document["proposal_id"]),
        run_id=str(document["run_id"]),
        generated_at=_parsed(document["generated_at"]),
        source_artifact_ids=tuple(document["source_artifact_ids"]),
        target_document=str(document["target_document"]),
        proposal_summary=str(document["proposal_summary"]),
        proposal_status=ProposalStatus(document["proposal_status"]),
        decisions=tuple(
            ProposalDecision(
                decided_at=_parsed(item["decided_at"]),
                decision=ProposalDecisionKind(item["decision"]),
                reviewer_role=ReviewerRole(item["reviewer_role"]),
                reviewer=item.get("reviewer"),
                decision_reason=item.get("decision_reason"),
            )
            for item in document.get("decisions", [])
        ),
        source_content_hashes=tuple(document.get("source_content_hashes", [])),
        confidence=Confidence(document["confidence"]) if document.get("confidence") else None,
        patch_plan=document.get("patch_plan"),
    )

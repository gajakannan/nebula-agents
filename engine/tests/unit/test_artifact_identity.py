"""F0003-S0004 — artifact identity, root selection, and containment (ADR-006).

Checkpoint B of the assembly plan lives here. The rule these tests defend is that
identity derives from *location within a named approved root*, because that is what
stays constant across re-index, restart, and a moved runtime directory.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from nebula_agents.domain.artifacts import (
    DIGEST_LENGTH,
    ArtifactIndexEntry,
    admit,
    content_digest,
    derive_artifact_id,
    new_entry,
    resolve_owning_root,
    retrieval_policy_for,
)
from nebula_agents.domain.enums import (
    ArtifactKind,
    ArtifactRedactionStatus,
    FreshnessStatus,
    RedactionStatus,
    RetrievalPolicy,
    SourceRoot,
    artifact_redaction_of,
)
from nebula_agents.domain.errors import ErrorCode, NebulaError

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
RUN = "2026-08-29-16075bda"


def nested_roots(base: Path) -> dict[SourceRoot, Path]:
    """The real-world layout: runtime and evidence both INSIDE the workspace.

    This is the configuration that makes longest-match load-bearing — a fixed root
    order would resolve every artifact to `workspace`.
    """
    return {
        SourceRoot.WORKSPACE: base,
        SourceRoot.RUNTIME: base / ".nebula-agents" / "runtime",
        SourceRoot.EVIDENCE: base / "planning-mds" / "operations" / "evidence",
    }


# --------------------------------------------------------------------------- #
# Root selection
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        (".nebula-agents/runtime/runs/X/artifacts.json", SourceRoot.RUNTIME),
        ("planning-mds/operations/evidence/runs/X/commands.log", SourceRoot.EVIDENCE),
        ("engine/src/nebula_agents/bootstrap.py", SourceRoot.WORKSPACE),
    ],
)
def test_longest_match_selects_the_owning_root(
    tmp_path: Path, relative: str, expected: SourceRoot
) -> None:
    roots = nested_roots(tmp_path)
    root, base = resolve_owning_root(tmp_path / relative, roots)
    assert root is expected
    assert base == roots[expected]


def test_root_selection_is_independent_of_mapping_order(tmp_path: Path) -> None:
    """Longest match, not first match: reversing the mapping changes nothing."""
    roots = nested_roots(tmp_path)
    reversed_roots = dict(reversed(list(roots.items())))
    target = tmp_path / ".nebula-agents" / "runtime" / "runs" / "X" / "run.json"
    assert resolve_owning_root(target, roots) == resolve_owning_root(target, reversed_roots)


def test_runtime_root_outside_the_workspace_still_resolves(tmp_path: Path) -> None:
    """NEBULA_AGENTS_RUNTIME_DIR can move the runtime root out of the workspace."""
    roots = {
        SourceRoot.WORKSPACE: tmp_path / "workspace",
        SourceRoot.RUNTIME: tmp_path / "elsewhere" / "runtime",
        SourceRoot.EVIDENCE: tmp_path / "workspace" / "evidence",
    }
    root, _ = resolve_owning_root(tmp_path / "elsewhere" / "runtime" / "runs" / "r.json", roots)
    assert root is SourceRoot.RUNTIME


def test_identical_roots_break_the_tie_runtime_over_evidence_over_workspace(
    tmp_path: Path,
) -> None:
    """The tiebreak is only reachable when two roots resolve to the same path."""
    same = tmp_path / "shared"
    assert (
        resolve_owning_root(
            same / "a.log",
            {SourceRoot.WORKSPACE: same, SourceRoot.EVIDENCE: same, SourceRoot.RUNTIME: same},
        )[0]
        is SourceRoot.RUNTIME
    )
    assert (
        resolve_owning_root(
            same / "a.log", {SourceRoot.WORKSPACE: same, SourceRoot.EVIDENCE: same}
        )[0]
        is SourceRoot.EVIDENCE
    )


def test_path_outside_every_root_is_a_policy_violation_not_a_crash(tmp_path: Path) -> None:
    with pytest.raises(NebulaError) as caught:
        resolve_owning_root(Path("/etc/passwd"), nested_roots(tmp_path))
    assert caught.value.code is ErrorCode.PATH_DENIED
    assert caught.value.exit_code == 5


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #
def test_artifact_id_shape_matches_the_contract(tmp_path: Path) -> None:
    artifact_id = derive_artifact_id(
        RUN,
        ArtifactKind.TRANSCRIPT,
        tmp_path / ".nebula-agents" / "runtime" / "runs" / "X" / "t.log",
        nested_roots(tmp_path),
    )
    run_id, kind, tail = artifact_id.split("/")
    root_key, digest = tail.split("-")
    assert (run_id, kind, root_key) == (RUN, "transcript", "rt")
    assert len(digest) == DIGEST_LENGTH == 12
    assert all(c in "0123456789abcdef" for c in digest)


def test_identity_is_stable_when_the_runtime_root_moves(tmp_path: Path) -> None:
    """The whole point of root-relative identity.

    The same artifact at the same position inside a relocated runtime root keeps its
    ID. Identity that embedded an absolute path would change here, and every recorded
    reference to it would dangle.
    """
    def ident(base: Path) -> str:
        roots = {
            SourceRoot.WORKSPACE: base / "ws",
            SourceRoot.RUNTIME: base / "rt",
            SourceRoot.EVIDENCE: base / "ws" / "ev",
        }
        return derive_artifact_id(
            RUN, ArtifactKind.COMMAND_LOG, base / "rt" / "runs" / "X" / "c.log", roots
        )

    assert ident(tmp_path / "first") == ident(tmp_path / "second")


def test_reindexing_the_same_path_is_idempotent(tmp_path: Path) -> None:
    roots = nested_roots(tmp_path)
    path = tmp_path / "planning-mds" / "operations" / "evidence" / "runs" / "X" / "m.json"
    first = new_entry(
        run_id=RUN, kind=ArtifactKind.MANIFEST, artifact_path=path, roots=roots,
        created_at=NOW, redaction_status=ArtifactRedactionStatus.PASS,
    )
    second = new_entry(
        run_id=RUN, kind=ArtifactKind.MANIFEST, artifact_path=path, roots=roots,
        created_at=NOW, redaction_status=ArtifactRedactionStatus.PASS,
    )
    assert first == second
    assert admit(admit({}, first), second) == {first.artifact_id: first}


def test_duplicate_content_keeps_distinct_ids_linked_by_hash(tmp_path: Path) -> None:
    """Content hash is an attribute, not identity — which is why this works."""
    roots = nested_roots(tmp_path)
    payload = b"identical bytes"
    entries = [
        new_entry(
            run_id=RUN, kind=ArtifactKind.STATUS,
            artifact_path=tmp_path / "planning-mds" / "operations" / "evidence" / name,
            roots=roots, created_at=NOW,
            redaction_status=ArtifactRedactionStatus.PASS,
            content_hash=content_digest(payload),
        )
        for name in ("a.json", "b.json")
    ]
    assert entries[0].artifact_id != entries[1].artifact_id
    assert entries[0].content_hash == entries[1].content_hash


def test_digest_collision_raises_conflict_and_never_overwrites(tmp_path: Path) -> None:
    roots = nested_roots(tmp_path)
    entry = new_entry(
        run_id=RUN, kind=ArtifactKind.STATUS,
        artifact_path=tmp_path / "planning-mds" / "operations" / "evidence" / "a.json",
        roots=roots, created_at=NOW, redaction_status=ArtifactRedactionStatus.PASS,
    )
    # Same ID, different source path: a truncated-digest collision.
    collided = replace(entry, source_path="planning-mds/operations/evidence/other.json")
    with pytest.raises(NebulaError) as caught:
        admit({entry.artifact_id: entry}, collided)
    assert caught.value.code is ErrorCode.DIGEST_COLLISION
    assert caught.value.exit_code == 6


# --------------------------------------------------------------------------- #
# Retrieval policy and freshness
# --------------------------------------------------------------------------- #
def test_failed_redaction_forces_blocked_even_when_also_missing() -> None:
    """`Blocked` outranks `Missing`: one reads as recoverable, the other must not."""
    assert (
        retrieval_policy_for(ArtifactRedactionStatus.FAIL, FreshnessStatus.MISSING)
        is RetrievalPolicy.BLOCKED
    )


def test_entry_rejects_a_retrieval_policy_that_contradicts_its_state(tmp_path: Path) -> None:
    with pytest.raises(NebulaError):
        ArtifactIndexEntry(
            artifact_id="x", run_id=RUN, artifact_kind=ArtifactKind.STATUS,
            source_root=SourceRoot.EVIDENCE, source_path="a.json", created_at=NOW,
            redaction_status=ArtifactRedactionStatus.FAIL,
            retrieval_policy=RetrievalPolicy.LOCAL_ONLY,   # contradicts FAIL
        )


def test_a_missing_artifact_keeps_its_entry_and_id(tmp_path: Path) -> None:
    entry = new_entry(
        run_id=RUN, kind=ArtifactKind.TRANSCRIPT,
        artifact_path=tmp_path / ".nebula-agents" / "runtime" / "t.log",
        roots=nested_roots(tmp_path), created_at=NOW,
        redaction_status=ArtifactRedactionStatus.PASS,
    )
    gone = entry.marked_missing()
    assert gone.artifact_id == entry.artifact_id
    assert gone.freshness_status is FreshnessStatus.MISSING
    assert gone.retrieval_policy is RetrievalPolicy.MISSING


def test_artifact_redaction_mapping_is_total() -> None:
    """A new F0001 RedactionStatus member without a mapping fails here.

    The two vocabularies are deliberately separate — merging them would change an F0001
    record shape, which contract 1.1 forbids — so the bridge between them must be total.
    """
    for status in RedactionStatus:
        assert isinstance(artifact_redaction_of(status), ArtifactRedactionStatus)

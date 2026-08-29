"""F0003-S0004 — the artifact index end to end, against a real filesystem.

Checkpoint B's durability half. The unit tests cover identity arithmetic; these cover
what happens when the index meets a real disk: atomic publish, optimistic concurrency,
a corrupt file, and the audit event that indexing must append.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from nebula_agents.bootstrap import build_application
from nebula_agents.domain.enums import (
    ArtifactKind,
    ArtifactRedactionStatus,
    FreshnessStatus,
    ProviderKey,
    PromptAction,
    RetrievalPolicy,
    SourceRoot,
)
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import LaunchRequest

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def workspace(tmp_path: Path, schema_root: Path) -> Path:
    root = tmp_path / "workspace"
    target = root / "planning-mds" / "schemas"
    target.mkdir(parents=True)
    for schema in schema_root.glob("f000*-*.json"):
        shutil.copy2(schema, target / schema.name)
    (root / "planning-mds" / "features" / "F0001-test").mkdir(parents=True)
    (root / "planning-mds" / "operations" / "evidence").mkdir(parents=True)
    prompts = root / "agents" / "templates" / "prompts" / "evidence-contract"
    prompts.mkdir(parents=True)
    (prompts / "feature-operator-friendly.md").write_text("FEATURE_ID={F####}\n", encoding="utf-8")
    return root


@pytest.fixture
def launched(workspace: Path, tmp_path: Path):
    """A real run, launched through the real service, with a fake provider and tmux."""
    application = build_application(workspace, tmp_path / "runtime")
    actor = application.current_actor()

    class Provider:
        def build_interactive_argv(self, workspace_root, prompt_text):
            return (str(Path(sys.executable).resolve()), "-c", "pass")

    class Tmux:
        def __init__(self) -> None:
            self.presence = [False, True]

        def has_session(self, _name: str) -> bool:
            return self.presence.pop(0) if len(self.presence) > 1 else self.presence[0]

        def create_session(self, _name: str, descriptor: Path) -> None:
            return None

    prompt = workspace / "agents" / "templates" / "prompts" / "evidence-contract" / "feature-operator-friendly.md"
    application.runs._preflight = SimpleNamespace(
        require_ready=lambda *a: SimpleNamespace(prompt_contract_path=str(prompt))
    )
    application.runs._providers = {ProviderKey.CODEX: Provider()}
    application.runs._tmux = Tmux()
    record = application.runs.launch(
        LaunchRequest("F0001", None, ProviderKey.CODEX, PromptAction.FEATURE, None, None, False),
        actor,
    )
    return application, actor, record.run_id, tmp_path / "runtime"


def index_path(runtime: Path, run_id: str) -> Path:
    return runtime / "runs" / run_id / "artifacts.json"


def test_indexing_writes_an_owner_only_atomic_index(launched, workspace: Path) -> None:
    application, actor, run_id, runtime = launched
    artifact = workspace / "planning-mds" / "operations" / "evidence" / "commands.log"
    artifact.write_text("one\ntwo\n", encoding="utf-8")

    entries = application.evidence.index_artifacts(run_id, [artifact], actor)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.source_root is SourceRoot.EVIDENCE
    assert entry.artifact_kind is ArtifactKind.COMMAND_LOG
    assert entry.artifact_id.startswith(f"{run_id}/command-log/ev-")
    assert entry.content_hash and len(entry.content_hash) == 64
    assert entry.size_bytes == 8

    path = index_path(runtime, run_id)
    assert stat.S_IMODE(path.lstat().st_mode) == 0o600
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["revision"] == 1 and len(document["entries"]) == 1
    assert not (runtime / "runs" / run_id / "artifacts.pending.json").exists()


def test_reindexing_is_idempotent_and_is_the_recovery_path(launched, workspace: Path) -> None:
    """Losing the index costs a re-index, never evidence — so re-indexing must be safe."""
    application, actor, run_id, runtime = launched
    artifact = workspace / "planning-mds" / "operations" / "evidence" / "commands.log"
    artifact.write_text("one\n", encoding="utf-8")

    first = application.evidence.index_artifacts(run_id, [artifact], actor)
    second = application.evidence.index_artifacts(run_id, [artifact], actor)

    assert [e.artifact_id for e in first] == [e.artifact_id for e in second]
    document = json.loads(index_path(runtime, run_id).read_text(encoding="utf-8"))
    assert len(document["entries"]) == 1
    assert document["revision"] == 2  # the projection advanced; the entry did not duplicate


def test_an_artifact_outside_every_approved_root_is_refused(launched, tmp_path: Path) -> None:
    application, actor, run_id, _ = launched
    outside = tmp_path / "outside.log"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(NebulaError) as caught:
        application.evidence.index_artifacts(run_id, [outside], actor)
    assert caught.value.code is ErrorCode.PATH_DENIED
    assert caught.value.exit_code == 5


def test_a_symlink_escaping_an_approved_root_is_refused(launched, workspace: Path, tmp_path: Path) -> None:
    """Symlinks are resolved BEFORE containment, never after.

    Checked after the fact, the link's own path sits inside an approved root and the
    read would follow it straight out.
    """
    application, actor, run_id, _ = launched
    secret = tmp_path / "outside-secret.log"
    secret.write_text("secret", encoding="utf-8")
    link = workspace / "planning-mds" / "operations" / "evidence" / "innocent.log"
    link.symlink_to(secret)
    with pytest.raises(NebulaError) as caught:
        application.evidence.index_artifacts(run_id, [link], actor)
    assert caught.value.code is ErrorCode.PATH_DENIED


def test_a_missing_artifact_is_indexed_as_missing_rather_than_crashing(launched, workspace: Path) -> None:
    application, actor, run_id, _ = launched
    absent = workspace / "planning-mds" / "operations" / "evidence" / "never-written.log"
    entry = application.evidence.index_artifacts(run_id, [absent], actor)[0]
    assert entry.freshness_status is FreshnessStatus.MISSING
    assert entry.retrieval_policy is RetrievalPolicy.MISSING
    assert entry.content_hash is None


def test_indexing_appends_one_audit_event_carrying_every_artifact(launched, workspace: Path) -> None:
    """BLUEPRINT 5.3: indexing creates a runtime event, because it changes review evidence."""
    application, actor, run_id, runtime = launched
    evidence_root = workspace / "planning-mds" / "operations" / "evidence"
    paths = []
    for name in ("a.log", "b.log"):
        (evidence_root / name).write_text(name, encoding="utf-8")
        paths.append(evidence_root / name)

    application.evidence.index_artifacts(run_id, paths, actor)

    events = [
        json.loads(line)
        for line in (runtime / "runs" / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    indexed = [e for e in events if e["event_type"] == "ArtifactIndexed"]
    assert len(indexed) == 1
    assert indexed[0]["payload"]["artifact_count"] == 2
    recorded = {a["artifact_id"] for a in indexed[0]["payload"]["artifacts"]}
    assert len(recorded) == 2
    assert all("retrieval_policy" in a for a in indexed[0]["payload"]["artifacts"])


def test_reads_append_no_event_and_create_no_index(launched, tmp_path: Path) -> None:
    application, actor, run_id, runtime = launched
    before = (runtime / "runs" / run_id / "events.jsonl").read_text(encoding="utf-8")
    assert application.queries.artifacts(run_id, actor) == ()
    assert not index_path(runtime, run_id).exists()
    assert (runtime / "runs" / run_id / "events.jsonl").read_text(encoding="utf-8") == before


def test_a_corrupt_index_is_preserved_and_rebuilt(launched, workspace: Path) -> None:
    """The index is a projection: one bad file must not make a run unindexable."""
    application, actor, run_id, runtime = launched
    artifact = workspace / "planning-mds" / "operations" / "evidence" / "a.log"
    artifact.write_text("a", encoding="utf-8")
    application.evidence.index_artifacts(run_id, [artifact], actor)

    path = index_path(runtime, run_id)
    path.write_text("{ not json", encoding="utf-8")
    os.chmod(path, 0o600)

    assert application.queries.artifacts(run_id, actor) == ()
    preserved = list((runtime / "runs" / run_id).glob("artifacts.json.corrupt-*"))
    assert len(preserved) == 1
    # and the run can be indexed again
    entries = application.evidence.index_artifacts(run_id, [artifact], actor)
    assert len(entries) == 1


def test_show_resolves_by_id_and_reports_an_unknown_id_as_not_found(launched, workspace: Path) -> None:
    application, actor, run_id, _ = launched
    artifact = workspace / "planning-mds" / "operations" / "evidence" / "a.log"
    artifact.write_text("a", encoding="utf-8")
    entry = application.evidence.index_artifacts(run_id, [artifact], actor)[0]

    assert application.queries.artifact(entry.artifact_id, actor) == entry

    with pytest.raises(NebulaError) as caught:
        application.queries.artifact(f"{run_id}/transcript/rt-000000000000", actor)
    assert caught.value.code is ErrorCode.ARTIFACT_NOT_FOUND
    assert caught.value.exit_code == 4

    with pytest.raises(NebulaError) as caught:
        application.queries.artifact("not-an-id", actor)
    assert caught.value.exit_code == 2


def test_a_stale_revision_commit_is_rejected(launched, workspace: Path) -> None:
    application, actor, run_id, runtime = launched
    artifact = workspace / "planning-mds" / "operations" / "evidence" / "a.log"
    artifact.write_text("a", encoding="utf-8")
    application.evidence.index_artifacts(run_id, [artifact], actor)

    index = application.commands.evidence._index
    with pytest.raises(NebulaError) as caught:
        index.commit(run_id=run_id, expected_revision=0, entries=(), now=NOW)
    assert caught.value.code is ErrorCode.STALE_REVISION

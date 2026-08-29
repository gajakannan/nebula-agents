"""F0003-S0005 — `evidence summarize` end to end.

The unit and contract tests cover extraction. These cover what summarizing does to the
run: summary artifacts on disk, the index updated with paths and resolved redaction
status, and one audit event.
"""

from __future__ import annotations

import json
import shutil
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from nebula_agents.bootstrap import build_application
from nebula_agents.domain.enums import (
    ArtifactKind,
    ArtifactRedactionStatus,
    ProviderKey,
    PromptAction,
    RetrievalPolicy,
    SummaryStatus,
)
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import LaunchRequest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "summaries"


@pytest.fixture
def launched(tmp_path: Path, schema_root: Path):
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
    return app, actor, record.run_id, runtime, evidence


def place(evidence: Path, fixture: str, name: str) -> Path:
    target = evidence / name
    shutil.copy2(FIXTURES / fixture, target)
    return target


def test_summarize_writes_artifacts_and_updates_the_index(launched) -> None:
    app, actor, run_id, runtime, evidence = launched
    artifact = place(evidence, "command-log.jsonl", "commands.log")
    indexed = app.evidence.index_artifacts(run_id, [artifact], actor)[0]
    assert indexed.summary_path is None
    assert indexed.redaction_status is ArtifactRedactionStatus.PENDING

    summaries = app.evidence.summarize(run_id, actor)

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.artifact_id == indexed.artifact_id
    assert summary.summary_status is SummaryStatus.PASS
    assert summary.rule_set_version == "1.0"
    assert len(summary.failure_markers) == 1

    path = runtime / "runs" / run_id / "summaries" / f"{summary.summary_id}.json"
    assert path.exists() and stat.S_IMODE(path.lstat().st_mode) == 0o600
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema_version"] == "1.0"

    updated = app.queries.artifact(indexed.artifact_id, actor)
    assert updated.summary_path == f"summaries/{summary.summary_id}.json"
    assert updated.redaction_status is ArtifactRedactionStatus.PASS
    assert updated.retrieval_policy is RetrievalPolicy.LOCAL_ONLY


def test_summarizing_is_deterministic_across_repeated_calls(launched) -> None:
    app, actor, run_id, runtime, evidence = launched
    artifact = place(evidence, "validator-output.txt", "validator.txt")
    app.evidence.index_artifacts(run_id, [artifact], actor)

    first = app.evidence.summarize(run_id, actor)[0]
    path = runtime / "runs" / run_id / "summaries" / f"{first.summary_id}.json"
    before = path.read_text(encoding="utf-8")

    second = app.evidence.summarize(run_id, actor)[0]
    after = path.read_text(encoding="utf-8")

    assert first.summary_id == second.summary_id  # derived from the artifact id
    # `generated_at` is the only field allowed to move between runs.
    assert json.loads(before) | {"generated_at": None} == json.loads(after) | {"generated_at": None}


def test_a_binary_artifact_summarizes_as_unsupported_and_stays_indexed(launched) -> None:
    app, actor, run_id, _, evidence = launched
    artifact = place(evidence, "unsupported.bin", "blob.bin")
    indexed = app.evidence.index_artifacts(
        run_id, [artifact], actor, kinds={artifact: ArtifactKind.TRANSCRIPT}
    )[0]

    summary = app.evidence.summarize(run_id, actor)[0]

    assert summary.summary_status is SummaryStatus.UNSUPPORTED
    assert app.queries.artifact(indexed.artifact_id, actor) is not None


def test_a_missing_source_artifact_summarizes_as_partial_not_a_crash(launched) -> None:
    app, actor, run_id, _, evidence = launched
    artifact = evidence / "never-written.log"
    app.evidence.index_artifacts(run_id, [artifact], actor)
    summary = app.evidence.summarize(run_id, actor)[0]
    assert summary.summary_status in {SummaryStatus.PARTIAL, SummaryStatus.FAILED}


def test_summarize_appends_one_audit_event_naming_the_rule_set(launched) -> None:
    app, actor, run_id, runtime, evidence = launched
    app.evidence.index_artifacts(run_id, [place(evidence, "manifest.json", "m.json")], actor)
    app.evidence.summarize(run_id, actor)

    events = [
        json.loads(line)
        for line in (runtime / "runs" / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    summarized = [e for e in events if e["event_type"] == "ArtifactSummarized"]
    assert len(summarized) == 1
    assert summarized[0]["payload"]["rule_set_version"] == "1.0"
    assert summarized[0]["payload"]["summary_count"] == 1


def test_summarizing_one_artifact_by_id_leaves_the_others_alone(launched) -> None:
    app, actor, run_id, _, evidence = launched
    first = place(evidence, "manifest.json", "one.json")
    second = place(evidence, "command-log.jsonl", "two.log")
    entries = app.evidence.index_artifacts(run_id, [first, second], actor)

    produced = app.evidence.summarize(run_id, actor, artifact_id=entries[0].artifact_id)

    assert len(produced) == 1
    untouched = app.queries.artifact(entries[1].artifact_id, actor)
    assert untouched.summary_path is None


def test_summarizing_an_unindexed_artifact_is_not_found(launched) -> None:
    app, actor, run_id, _, _ = launched
    with pytest.raises(NebulaError) as caught:
        app.evidence.summarize(run_id, actor, artifact_id=f"{run_id}/transcript/rt-000000000000")
    assert caught.value.code is ErrorCode.ARTIFACT_NOT_FOUND

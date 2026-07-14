from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nebula_agents.infrastructure import watcher as watcher_module
from nebula_agents.domain.enums import (
    ArtifactStatus,
    DecisionKind,
    GateStatus,
    PromptAction,
    ProviderKey,
    RedactionStatus,
    Role,
    RunStatus,
    TranscriptStatus,
    ValidatorKey,
)
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import (
    Actor,
    GateDecision,
    GateSnapshot,
    ProcessResult,
    RunRecord,
    TranscriptState,
)
from nebula_agents.infrastructure.watcher import (
    AllowlistedValidatorRunner,
    PollingEvidenceWatcher,
)


NOW = datetime(2026, 7, 13, 18, 0, tzinfo=UTC)


class Clock:
    def now(self):
        return NOW


def _run(workspace: Path, evidence_root: Path | None) -> RunRecord:
    return RunRecord(
        "1.0",
        0,
        "2026-07-13-deadbeef",
        "F0001",
        None,
        ProviderKey.CODEX,
        "nebula-F0001-deadbeef",
        str(workspace),
        str(workspace / "prompt.md"),
        PromptAction.FEATURE,
        RunStatus.ACTIVE,
        Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR),
        str(evidence_root) if evidence_root else None,
        GateSnapshot("G1", GateStatus.PENDING, False, (), None),
        None,
        (),
        TranscriptState(TranscriptStatus.DISABLED, RedactionStatus.NOT_RUN, None, None, 0),
        str(workspace / "runtime" / "events.jsonl"),
        1,
        NOW,
        NOW,
        NOW,
    )


def test_watcher_classifies_available_missing_malformed_and_denied_paths(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    evidence = workspace / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "available.md").write_text("ok", encoding="utf-8")
    (evidence / "valid.json").write_text('{"ok": true}', encoding="utf-8")
    (evidence / "invalid.json").write_text("{", encoding="utf-8")
    (evidence / "valid.yaml").write_text("status: ready\n", encoding="utf-8")
    (evidence / "invalid.yaml").write_text(
        "status: [unterminated\n", encoding="utf-8"
    )
    (evidence / "valid.md").write_text("# Evidence\n\nready\n", encoding="utf-8")
    (evidence / "invalid.md").write_text(
        "---\ntitle: unterminated front matter\n", encoding="utf-8"
    )
    (evidence / "directory").mkdir()
    observations = PollingEvidenceWatcher(Clock()).observe_once(
        _run(workspace, evidence),
        (
            "available.md",
            "valid.json",
            "invalid.json",
            "valid.yaml",
            "invalid.yaml",
            "valid.md",
            "invalid.md",
            "directory",
            "missing.md",
            "",
            "/absolute/path",
            "../escape.md",
        ),
    )
    by_path = {item.relative_path: item for item in observations}
    assert by_path["available.md"].status is ArtifactStatus.AVAILABLE
    assert by_path["available.md"].size_bytes == 2
    assert by_path["valid.json"].status is ArtifactStatus.AVAILABLE
    assert by_path["invalid.json"].status is ArtifactStatus.MALFORMED
    assert by_path["valid.yaml"].status is ArtifactStatus.AVAILABLE
    assert by_path["invalid.yaml"].status is ArtifactStatus.MALFORMED
    assert by_path["valid.md"].status is ArtifactStatus.AVAILABLE
    assert by_path["invalid.md"].status is ArtifactStatus.MALFORMED
    assert by_path["directory"].status is ArtifactStatus.MALFORMED
    assert by_path["missing.md"].status is ArtifactStatus.MISSING
    assert by_path["<invalid>"].status is ArtifactStatus.DENIED
    assert by_path["/absolute/path"].status is ArtifactStatus.DENIED
    assert by_path["../escape.md"].status is ArtifactStatus.DENIED
    assert all(item.observed_at == NOW for item in observations)


def test_watcher_uses_workspace_when_evidence_root_is_not_created(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "STATUS.md").write_text("ready", encoding="utf-8")
    observation = PollingEvidenceWatcher(Clock()).observe_once(
        _run(workspace, None), ("STATUS.md",)
    )[0]
    assert observation.status is ArtifactStatus.AVAILABLE


def test_watcher_denies_symlink_that_resolves_outside_evidence_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    evidence = workspace / "evidence"
    evidence.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    (evidence / "link.md").symlink_to(outside)
    observation = PollingEvidenceWatcher(Clock()).observe_once(
        _run(workspace, evidence), ("link.md",)
    )[0]
    assert observation.status is ArtifactStatus.DENIED


def test_watcher_rejects_symlinked_canonical_evidence_run_root(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    runs_root = workspace / "planning-mds" / "operations" / "evidence" / "runs"
    runs_root.mkdir(parents=True)
    outside = tmp_path / "outside-evidence"
    outside.mkdir()
    linked = runs_root / "2026-07-13-deadbeef"
    linked.symlink_to(outside, target_is_directory=True)
    run = _run(workspace, linked)
    watcher = PollingEvidenceWatcher(Clock())

    assert watcher._discover_root(run) is None
    reconciliation = watcher.reconcile(run)
    assert reconciliation.evidence_root == str(linked)
    assert reconciliation.gate.status is GateStatus.BLOCKED
    assert reconciliation.gate.evidence_ready is False
    assert reconciliation.error_category == "evidence-root-denied"


def test_watcher_classifies_permission_and_other_os_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    evidence = workspace / "evidence"
    evidence.mkdir(parents=True)
    denied = evidence / "denied.md"
    malformed = evidence / "malformed.md"
    denied.write_text("x", encoding="utf-8")
    malformed.write_text("x", encoding="utf-8")
    original_stat = Path.stat

    def fake_stat(path: Path, *args, **kwargs):
        if path == denied:
            raise PermissionError("denied")
        if path == malformed:
            raise OSError("I/O")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)
    observations = PollingEvidenceWatcher(Clock()).observe_once(
        _run(workspace, evidence), ("denied.md", "malformed.md")
    )
    assert observations[0].status is ArtifactStatus.DENIED
    assert observations[1].status is ArtifactStatus.MALFORMED


def test_watcher_retains_last_known_size_and_deduplicates_unchanged_observation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    evidence = workspace / "evidence"
    evidence.mkdir(parents=True)
    artifact = evidence / "report.md"
    artifact.write_text("ready", encoding="utf-8")
    watcher = PollingEvidenceWatcher(Clock())
    run = _run(workspace, evidence)

    available = watcher.observe_once(run, ("report.md",))[0]
    artifact.unlink()
    missing = watcher.observe_once(
        replace(run, artifacts=(available,)), ("report.md",)
    )[0]
    unchanged = watcher.observe_once(
        replace(run, artifacts=(missing,)), ("report.md",)
    )[0]

    assert available.status is ArtifactStatus.AVAILABLE
    assert available.size_bytes == 5
    assert missing.status is ArtifactStatus.MISSING
    assert missing.size_bytes == 5
    assert unchanged is missing


def test_descriptor_bound_observation_is_stable_during_path_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    evidence = workspace / "evidence"
    evidence.mkdir(parents=True)
    artifact = evidence / "report.json"
    artifact.write_text('{"version": "validated"}', encoding="utf-8")
    original_read = watcher_module.os.read
    replaced = False

    def replace_after_read(file_descriptor: int, count: int) -> bytes:
        nonlocal replaced
        payload = original_read(file_descriptor, count)
        if payload and not replaced:
            replacement = evidence / "replacement.json"
            replacement.write_text("{", encoding="utf-8")
            replacement.replace(artifact)
            replaced = True
        return payload

    monkeypatch.setattr(watcher_module.os, "read", replace_after_read)
    watcher = PollingEvidenceWatcher(Clock())
    run = _run(workspace, evidence)

    stable = watcher.observe_once(run, ("report.json",))[0]
    monkeypatch.setattr(watcher_module.os, "read", original_read)
    replaced_observation = watcher.observe_once(run, ("report.json",))[0]

    assert stable.status is ArtifactStatus.AVAILABLE
    assert replaced_observation.status is ArtifactStatus.MALFORMED


def test_production_reconciliation_watches_all_lifecycle_and_gate_artifacts(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    evidence = (
        workspace
        / "planning-mds"
        / "operations"
        / "evidence"
        / "runs"
        / "2026-07-14-remediate"
    )
    evidence.mkdir(parents=True)
    (evidence / "evidence-manifest.json").write_text(
        json.dumps({"feature_id": "F0001", "status": "in-progress"}),
        encoding="utf-8",
    )

    reconciliation = PollingEvidenceWatcher(Clock()).reconcile(
        _run(workspace, evidence)
    )
    observed_paths = {item.relative_path for item in reconciliation.artifacts}

    assert {
        "evidence-manifest.json",
        "commands.log",
        "lifecycle-gates.log",
        "action-context.md",
        "artifact-trace.md",
        "g0-assembly-plan-validation.md",
        "g1-runtime-preflight.md",
        "g2-self-review.md",
        "test-execution-report.md",
        "coverage-report.md",
        "deployability-check.md",
        "code-review-report.md",
        "security-review-report.md",
        "gate-decisions.md",
        "signoff-ledger.md",
        "feature-action-execution.md",
        "kg-reconciliation.md",
        "pm-closeout.md",
    } <= observed_paths
    assert next(
        item
        for item in reconciliation.artifacts
        if item.relative_path == "g1-runtime-preflight.md"
    ).status is ArtifactStatus.MISSING


def test_watcher_discovers_newest_active_matching_evidence_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    runs_root = workspace / "planning-mds" / "operations" / "evidence" / "runs"
    runs_root.mkdir(parents=True)
    watcher = PollingEvidenceWatcher(Clock())

    def manifest(name: str, document: object, timestamp: int) -> Path:
        path = runs_root / name / "evidence-manifest.json"
        path.parent.mkdir()
        path.write_text(json.dumps(document), encoding="utf-8")
        os.utime(path, ns=(timestamp, timestamp))
        return path

    old = manifest(
        "old",
        {"feature_id": "F0001", "status": "draft"},
        10,
    )
    newest = manifest(
        "newest",
        {"feature_id": "F0001", "status": "in-progress"},
        20,
    )
    manifest("wrong-feature", {"feature_id": "F9999", "status": "draft"}, 30)
    manifest("closed", {"feature_id": "F0001", "status": "complete"}, 40)
    malformed = runs_root / "malformed" / "evidence-manifest.json"
    malformed.parent.mkdir()
    malformed.write_text("{", encoding="utf-8")
    oversized = runs_root / "oversized" / "evidence-manifest.json"
    oversized.parent.mkdir()
    oversized.write_text("x" * 1_048_577, encoding="utf-8")
    symlink = runs_root / "symlink" / "evidence-manifest.json"
    symlink.parent.mkdir()
    symlink.symlink_to(old)

    assert watcher._discover_root(_run(workspace, None)) == newest.parent.resolve()
    assert watcher._discover_root(_run(workspace, newest.parent)) == newest.parent.resolve()


def test_watcher_gate_selection_handles_missing_malformed_and_passed_results(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    evidence = workspace / "evidence"
    evidence.mkdir(parents=True)
    run = _run(workspace, evidence)

    assert PollingEvidenceWatcher._gate_for_manifest(None, run) == (
        "G0",
        ("evidence-manifest.json", "g0-assembly-plan-validation.md"),
    )
    (evidence / "evidence-manifest.json").write_text("{", encoding="utf-8")
    assert PollingEvidenceWatcher._gate_for_manifest(evidence, run)[0] == "G0"

    (evidence / "evidence-manifest.json").write_text(
        json.dumps(
            {
                "gate_results": {
                    "assembly_plan_validation": {"result": "passed"},
                    "runtime_preflight": {"result": "APPROVED"},
                }
            }
        ),
        encoding="utf-8",
    )
    gate_id, requirements = PollingEvidenceWatcher._gate_for_manifest(evidence, run)
    assert gate_id == "G2"
    assert requirements == (
        "evidence-manifest.json",
        "g2-self-review.md",
        "test-execution-report.md",
        "coverage-report.md",
        "deployability-check.md",
    )


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        ("PASS", True),
        ("PASSED", True),
        ("APPROVED WITH RECOMMENDATIONS", True),
        ("FAIL", False),
        ("PENDING", False),
        (None, False),
    ],
)
def test_watcher_semantic_readiness_uses_manifest_verdict_not_file_presence(
    tmp_path: Path, verdict: str | None, expected: bool
) -> None:
    workspace = tmp_path / "workspace"
    evidence = (
        workspace
        / "planning-mds"
        / "operations"
        / "evidence"
        / "runs"
        / "2026-07-13-deadbeef"
    )
    evidence.mkdir(parents=True)
    document: dict[str, object] = {
        "feature_id": "F0001",
        "status": "in-progress",
        "gate_results": {},
    }
    if verdict is not None:
        document["gate_results"] = {
            "runtime_preflight": {"result": verdict}
        }
    (evidence / "evidence-manifest.json").write_text(
        json.dumps(document), encoding="utf-8"
    )
    # The artifact exists in every case; only its governed verdict varies.
    (evidence / "g1-runtime-preflight.md").write_text("present", encoding="utf-8")

    ready = PollingEvidenceWatcher(Clock()).semantic_gate_ready(
        _run(workspace, evidence), "G1"
    )

    assert ready is expected


@pytest.mark.parametrize("gate_id", ["", "G", "Gx", "1", "G99"])
def test_watcher_semantic_readiness_fails_closed_for_unknown_gate_ids(
    tmp_path: Path, gate_id: str
) -> None:
    workspace = tmp_path / "workspace"
    evidence = workspace / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "evidence-manifest.json").write_text(
        json.dumps({"feature_id": "F0001", "status": "in-progress"}),
        encoding="utf-8",
    )
    assert (
        PollingEvidenceWatcher(Clock()).semantic_gate_ready(
            _run(workspace, evidence), gate_id
        )
        is False
    )


def test_watcher_reconcile_updates_root_readiness_and_decision_scope(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    evidence = (
        workspace
        / "planning-mds"
        / "operations"
        / "evidence"
        / "runs"
        / "run-new"
    )
    evidence.mkdir(parents=True)
    (evidence / "evidence-manifest.json").write_text(
        json.dumps(
            {
                "feature_id": "F0001",
                "status": "in-progress",
                "gate_results": {
                    "assembly_plan_validation": {"result": "PASS"}
                },
            }
        ),
        encoding="utf-8",
    )
    preflight = evidence / "g1-runtime-preflight.md"
    preflight.write_text("ready", encoding="utf-8")
    decision = GateDecision(
        DecisionKind.HOLD,
        "verify",
        _run(workspace, None).owner,
        NOW,
        0,
    )
    run = replace(
        _run(workspace, None),
        gate=GateSnapshot("G1", GateStatus.PENDING, False, (), decision),
    )
    watcher = PollingEvidenceWatcher(Clock())

    available_but_unverified = watcher.reconcile(run)
    assert available_but_unverified.evidence_root == str(evidence.resolve())
    assert available_but_unverified.gate.gate_id == "G1"
    assert available_but_unverified.gate.status is GateStatus.BLOCKED
    assert available_but_unverified.gate.evidence_ready is False
    assert available_but_unverified.gate.decision is decision
    by_path = {
        item.relative_path: item for item in available_but_unverified.artifacts
    }
    assert by_path["evidence-manifest.json"].status is ArtifactStatus.AVAILABLE
    assert by_path["g1-runtime-preflight.md"].status is ArtifactStatus.AVAILABLE
    assert by_path["g2-self-review.md"].status is ArtifactStatus.MISSING
    assert available_but_unverified.gate.required_evidence == (
        "evidence-manifest.json",
        "g1-runtime-preflight.md",
    )

    preflight.unlink()
    blocked = watcher.reconcile(
        replace(run, artifacts=available_but_unverified.artifacts)
    )
    assert blocked.gate.status is GateStatus.BLOCKED
    assert blocked.gate.evidence_ready is False
    assert blocked.artifacts[1].status is ArtifactStatus.MISSING
    assert blocked.artifacts[1].size_bytes == len("ready")

    stale_decision = watcher.reconcile(
        replace(run, gate=replace(run.gate, gate_id="G0"))
    )
    assert stale_decision.gate.decision is None


class Process:
    def __init__(self, result: ProcessResult) -> None:
        self.result = result
        self.calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def run(self, argv, **kwargs):
        self.calls.append((tuple(argv), kwargs))
        return self.result


def _validator_workspace(root: Path) -> dict[ValidatorKey, Path]:
    (root / "planning-mds" / "features" / "F0001-feature").mkdir(
        parents=True
    )
    scripts = {
        ValidatorKey.STORIES: root
        / "agents"
        / "product-manager"
        / "scripts"
        / "validate-stories.py",
        ValidatorKey.TRACKERS: root
        / "agents"
        / "product-manager"
        / "scripts"
        / "validate-trackers.py",
        ValidatorKey.TEMPLATES: root
        / "agents"
        / "scripts"
        / "validate_templates.py",
    }
    for script in scripts.values():
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("raise SystemExit(0)\n", encoding="utf-8")
        script.chmod(0o600)
    return scripts


@pytest.mark.parametrize(
    ("key", "script", "template"),
    [
        (
            ValidatorKey.STORIES,
            "validate-stories.py",
            "python3 validate-stories.py --product-root {workspace} {feature}",
        ),
        (
            ValidatorKey.TRACKERS,
            "validate-trackers.py",
            "python3 validate-trackers.py --product-root {workspace} --skip-feature-evidence",
        ),
        (
            ValidatorKey.TEMPLATES,
            "validate_templates.py",
            "python3 validate_templates.py",
        ),
    ],
)
def test_validator_runner_uses_committed_argv_allowlist(
    tmp_path: Path, key: ValidatorKey, script: str, template: str
) -> None:
    scripts = _validator_workspace(tmp_path)
    process = Process(ProcessResult("python3", 0, "passed", "", 12))
    result = AllowlistedValidatorRunner(process, Clock()).run(
        key,
        workspace_root=tmp_path,
        feature_id="F0001",
        run_id="2026-07-13-deadbeef",
        timeout_seconds=120,
    )
    argv, kwargs = process.calls[0]
    assert argv[0] == "python3"
    assert argv[1].startswith("/proc/self/fd/")
    assert scripts[key].name == script
    assert kwargs["cwd"] == Path(f"/proc/self/fd/{kwargs['pass_fds'][0]}")
    assert kwargs["timeout_seconds"] == 120
    assert kwargs["pass_fds"]
    if key is ValidatorKey.STORIES:
        root_option = argv.index("--story-root-fd")
        assert int(argv[root_option + 1]) in kwargs["pass_fds"]
    else:
        assert "--story-root-fd" not in argv
    assert result.validator_key is key
    assert result.exit_code == 0
    assert result.summary == "passed"
    assert result.artifact_path is None
    assert result.command_template == template
    assert str(tmp_path) not in result.command_template


def test_validator_runner_bounds_combined_summary_and_returns_existing_artifact(
    tmp_path: Path,
) -> None:
    _validator_workspace(tmp_path)
    artifact = (
        tmp_path
        / "planning-mds"
        / "operations"
        / "evidence"
        / "runs"
        / "2026-07-13-deadbeef"
        / "artifacts"
        / "tests"
        / "validator-stories.log"
    )
    artifact.parent.mkdir(parents=True)
    artifact.write_text("details", encoding="utf-8")
    process = Process(ProcessResult("python3", 1, "x" * 3000, "y" * 3000, 42))
    result = AllowlistedValidatorRunner(process, Clock()).run(
        ValidatorKey.STORIES,
        workspace_root=tmp_path,
        feature_id="F0001",
        run_id="2026-07-13-deadbeef",
        timeout_seconds=120,
    )
    assert len(result.summary) == 4000
    assert result.summary.endswith("...")
    assert result.artifact_path == str(artifact)
    assert result.completed_at == NOW


def test_validator_runner_executes_opened_script_after_path_replacement(
    tmp_path: Path,
) -> None:
    scripts = _validator_workspace(tmp_path)
    governed_script = scripts[ValidatorKey.STORIES]
    original_payload = governed_script.read_bytes()

    class ReplacingProcess(Process):
        def run(self, argv, **kwargs):
            replacement = governed_script.with_suffix(".replacement")
            replacement.write_text("raise SystemExit(91)\n", encoding="utf-8")
            replacement.chmod(0o600)
            replacement.replace(governed_script)
            script_fd = int(str(argv[1]).rsplit("/", 1)[1])
            assert os.pread(script_fd, len(original_payload), 0) == original_payload
            return super().run(argv, **kwargs)

    process = ReplacingProcess(ProcessResult("python3", 0, "passed", "", 12))

    result = AllowlistedValidatorRunner(process, Clock()).run(
        ValidatorKey.STORIES,
        workspace_root=tmp_path,
        feature_id="F0001",
        run_id="2026-07-13-deadbeef",
        timeout_seconds=120,
    )

    assert result.exit_code == 0
    assert governed_script.read_text(encoding="utf-8") == "raise SystemExit(91)\n"


def test_validator_runner_rejects_symlinked_feature_root_before_execution(
    tmp_path: Path,
) -> None:
    features = tmp_path / "planning-mds" / "features"
    features.mkdir(parents=True)
    outside = tmp_path / "outside-feature"
    outside.mkdir()
    (features / "F0001-linked").symlink_to(outside, target_is_directory=True)
    process = Process(ProcessResult("python3", 0, "passed", "", 12))
    runner = AllowlistedValidatorRunner(process, Clock())

    with pytest.raises(NebulaError) as caught:
        runner.run(
            ValidatorKey.STORIES,
            workspace_root=tmp_path,
            feature_id="F0001",
            run_id="2026-07-13-deadbeef",
            timeout_seconds=120,
        )

    assert caught.value.code is ErrorCode.PATH_DENIED
    assert process.calls == []


@pytest.mark.parametrize(
    ("key", "relative_script"),
    [
        (ValidatorKey.STORIES, "agents/product-manager/scripts/validate-stories.py"),
        (ValidatorKey.TRACKERS, "agents/product-manager/scripts/validate-trackers.py"),
        (ValidatorKey.TEMPLATES, "agents/scripts/validate_templates.py"),
    ],
)
def test_validator_runner_rejects_symlinked_allowlisted_script(
    tmp_path: Path, key: ValidatorKey, relative_script: str
) -> None:
    (tmp_path / "planning-mds" / "features" / "F0001-feature").mkdir(
        parents=True
    )
    outside = tmp_path / "outside-validator.py"
    outside.write_text("raise SystemExit(0)\n", encoding="utf-8")
    script = tmp_path / relative_script
    script.parent.mkdir(parents=True, exist_ok=True)
    script.symlink_to(outside)
    process = Process(ProcessResult("python3", 0, "passed", "", 12))

    with pytest.raises(NebulaError) as caught:
        AllowlistedValidatorRunner(process, Clock()).run(
            key,
            workspace_root=tmp_path,
            feature_id="F0001",
            run_id="2026-07-13-deadbeef",
            timeout_seconds=120,
        )

    assert caught.value.code is ErrorCode.PATH_DENIED
    assert process.calls == []

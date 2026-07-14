from __future__ import annotations

import os
from pathlib import Path

import pytest

from nebula_agents.application.preflight import PreflightService
from nebula_agents.domain.enums import PromptAction, ProviderKey
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import Probe


class Clock:
    def __init__(self, value) -> None:
        self.value = value

    def now(self):
        return self.value


class Tmux:
    def __init__(self, status: str = "ready") -> None:
        self.status = status

    def probe(self) -> Probe:
        return Probe("tmux", self.status, "/usr/bin/tmux" if self.status == "ready" else None, "tmux 3.4" if self.status == "ready" else None)


class Provider:
    def __init__(self, key: ProviderKey, status: str = "ready") -> None:
        self.key = key
        self.status = status
        self.probed: list[Path] = []

    def probe(self, workspace_root: Path) -> Probe:
        self.probed.append(workspace_root)
        return Probe(self.key.value, self.status, f"/usr/bin/{self.key.value}" if self.status == "ready" else None, "1.0" if self.status == "ready" else None)


class Schema:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def validate(self, name, document) -> None:
        self.calls.append((name, document))


def _service(fixed_now, *, tmux="ready", codex="ready", claude="ready"):
    schema = Schema()
    providers = {
        ProviderKey.CODEX: Provider(ProviderKey.CODEX, codex),
        ProviderKey.CLAUDE: Provider(ProviderKey.CLAUDE, claude),
    }
    return (
        PreflightService(clock=Clock(fixed_now), tmux=Tmux(tmux), providers=providers, schema=schema),
        schema,
        providers,
    )


def test_ready_preflight_is_read_only_and_validates_creatable_runtime_contract(
    workspace: Path, fixed_now
) -> None:
    service, schema, providers = _service(fixed_now)
    result = service.run(workspace, provider_hint=ProviderKey.CODEX, prompt_action=PromptAction.FEATURE)
    assert result.overall_status == "ready"
    assert Path(result.workspace_root).is_absolute()
    assert not Path(result.runtime_dir).exists()
    runtime_check = next(
        check for check in result.checks if check.key == "runtime_directory"
    )
    assert runtime_check.status == "ready"
    assert "first authorized mutation" in runtime_check.message
    assert result.prompt_contract_path is not None
    assert result.prompt_contract_path.endswith("feature-operator-friendly.md")
    assert result.planning_docs_path == str((workspace / "planning-mds").resolve())
    assert result.missing_paths == ()
    assert [probe.key for probe in result.providers] == ["codex"]
    assert providers[ProviderKey.CODEX].probed == [workspace.resolve()]
    assert providers[ProviderKey.CLAUDE].probed == []
    assert schema.calls[0][0] == "f0001-preflight-result.schema.json"


@pytest.mark.parametrize(
    ("tmux", "provider", "overall"),
    [
        ("missing", "ready", "blocked"),
        ("ready", "missing", "blocked"),
        ("ready", "authentication_attention_needed", "authentication_attention_needed"),
        ("ready", "timeout", "blocked"),
    ],
)
def test_preflight_classifies_missing_and_attention_states(
    workspace: Path, fixed_now, tmux: str, provider: str, overall: str
) -> None:
    service, _, _ = _service(fixed_now, tmux=tmux, codex=provider)
    result = service.run(workspace, provider_hint=ProviderKey.CODEX)
    assert result.overall_status == overall


def test_preflight_reports_missing_governed_workspace(tmp_path: Path, fixed_now) -> None:
    service, _, _ = _service(fixed_now)
    result = service.run(
        tmp_path,
        provider_hint=ProviderKey.CODEX,
        prompt_action=PromptAction.FEATURE,
    )
    assert result.overall_status == "blocked"
    assert next(check for check in result.checks if check.key == "workspace_contract").status == "missing"
    assert result.planning_docs_path is None
    assert result.missing_paths == tuple(
        str((tmp_path / relative).resolve())
        for relative in (
            "planning-mds",
            "planning-mds/features",
            "agents/templates/prompts/evidence-contract",
            "agents/templates/prompts/evidence-contract/feature-operator-friendly.md",
        )
    )
    assert all(Path(path).is_absolute() for path in result.missing_paths)


def test_preflight_rejects_symlinked_prompt_leaf(tmp_path: Path, fixed_now) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "planning-mds" / "features").mkdir(parents=True)
    prompt_root = (
        workspace / "agents" / "templates" / "prompts" / "evidence-contract"
    )
    prompt_root.mkdir(parents=True)
    outside = tmp_path / "outside-prompt.md"
    outside.write_text("untrusted", encoding="utf-8")
    (prompt_root / "feature-operator-friendly.md").symlink_to(outside)
    service, _, _ = _service(fixed_now)

    result = service.run(
        workspace,
        provider_hint=ProviderKey.CODEX,
        prompt_action=PromptAction.FEATURE,
    )

    assert result.overall_status == "blocked"
    assert result.prompt_contract_path is None
    assert result.missing_paths == (
        str(
            workspace
            / "agents/templates/prompts/evidence-contract/feature-operator-friendly.md"
        ),
    )


def test_preflight_denies_unsafe_existing_runtime_directory(
    workspace: Path, fixed_now
) -> None:
    runtime = workspace / "unsafe-runtime"
    runtime.mkdir(mode=0o755)
    runtime.chmod(0o755)
    service, _, _ = _service(fixed_now)
    result = service.run(workspace, runtime_dir_override=runtime, provider_hint=ProviderKey.CODEX)
    assert result.overall_status == "denied"
    assert next(check for check in result.checks if check.key == "runtime_directory").status == "denied"


def test_require_ready_raises_stable_preflight_error(workspace: Path, fixed_now) -> None:
    service, _, _ = _service(fixed_now, tmux="missing")
    with pytest.raises(NebulaError) as caught:
        service.require_ready(workspace, None, ProviderKey.CODEX, PromptAction.FEATURE)
    assert caught.value.code is ErrorCode.PREFLIGHT_BLOCKED
    assert caught.value.exit_code == 3

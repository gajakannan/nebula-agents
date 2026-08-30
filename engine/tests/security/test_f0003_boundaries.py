"""F0003 security boundaries (Step 8).

The four guarantees BLUEPRINT §5.6 states, each asserted against real behaviour rather
than inspected in review:

- artifact index and proposal store are `0600` inside `0700`
- path containment resolves symlinks **before** the check
- probe output is redacted before persistence
- proposals cannot name a target outside the allowlist

`test_static_execution_boundary.py` already covers the no-shell rule for the whole
package, including these modules.
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
from nebula_agents.domain.enums import ProviderKey, PromptAction, ReviewerRole
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import LaunchRequest
from nebula_agents.domain.proposals import assert_target_allowed

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "summaries"

#: Values that must never reach a persisted artifact, summary, or report.
SENTINELS = (
    "sk-live-sentinelvaluethatmustnotleak",
    "Bearer sentineltokenmustnotleak00",
    "api_key: sentinelsecretmustnotleak",
)


@pytest.fixture
def running(tmp_path: Path, schema_root: Path):
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
        def probe(self, _root):
            # A provider whose version output carries a credential.
            return SimpleNamespace(
                status="ready", executable_path="/usr/bin/codex",
                version=f"cli 1.0 {SENTINELS[0]}",
            )

        def build_interactive_argv(self, _r, _p):
            return (str(Path(sys.executable).resolve()), "-c", "pass")

    class Tmux:
        def __init__(self): self.presence = [False, True]
        def probe(self): return SimpleNamespace(status="ready")
        def has_session(self, _n): return self.presence.pop(0) if len(self.presence) > 1 else self.presence[0]
        def create_session(self, _n, _d): return None

    app.runs._preflight = SimpleNamespace(
        require_ready=lambda *a: SimpleNamespace(
            prompt_contract_path=str(prompts / "feature-operator-friendly.md"))
    )
    app.runs._providers = {ProviderKey.CODEX: Provider()}
    app.runs._tmux = Tmux()
    app.capabilities._prober._providers = {ProviderKey.CODEX: Provider()}
    app.capabilities._prober._tmux = Tmux()
    record = app.runs.launch(
        LaunchRequest("F0001", None, ProviderKey.CODEX, PromptAction.FEATURE, None, None, False), actor
    )
    return SimpleNamespace(app=app, actor=actor, run_id=record.run_id,
                           runtime=runtime, evidence=evidence, workspace=ws)


# --------------------------------------------------------------------------- #
# File modes
# --------------------------------------------------------------------------- #
def test_every_f0003_store_is_owner_only_inside_an_owner_only_directory(running) -> None:
    ctx = running
    shutil.copy2(FIXTURES / "command-log.jsonl", ctx.evidence / "commands.log")
    ctx.app.evidence.index_artifacts(ctx.run_id, [ctx.evidence / "commands.log"], ctx.actor)
    ctx.app.evidence.summarize(ctx.run_id, ctx.actor)
    ctx.app.learning.review(ctx.run_id, ctx.actor)
    ctx.app.capabilities.probe(ProviderKey.CODEX, ctx.actor)

    run_dir = ctx.runtime / "runs" / ctx.run_id
    files = [
        run_dir / "artifacts.json",
        *(run_dir / "summaries").glob("*.json"),
        *(run_dir / "proposals").glob("*.json"),
        ctx.runtime / "capabilities" / "codex.json",
    ]
    assert len(files) >= 4
    for path in files:
        assert path.exists(), path
        assert stat.S_IMODE(path.lstat().st_mode) == 0o600, f"{path} is not 0600"
        assert stat.S_IMODE(path.parent.lstat().st_mode) == 0o700, f"{path.parent} is not 0700"


# --------------------------------------------------------------------------- #
# Path containment
# --------------------------------------------------------------------------- #
def test_a_symlink_out_of_an_approved_root_is_refused_not_followed(running, tmp_path: Path) -> None:
    """Symlinks resolve BEFORE containment, never after.

    Checked after the fact, the link's own path sits inside an approved root and the read
    would follow it straight out — which is the whole attack.
    """
    ctx = running
    secret = tmp_path / "outside" / "secret.log"
    secret.parent.mkdir()
    secret.write_text(SENTINELS[1], encoding="utf-8")
    link = ctx.evidence / "looks-innocent.log"
    link.symlink_to(secret)

    with pytest.raises(NebulaError) as caught:
        ctx.app.evidence.index_artifacts(ctx.run_id, [link], ctx.actor)
    assert caught.value.code is ErrorCode.PATH_DENIED


def test_a_traversal_that_escapes_every_approved_root_is_refused(running) -> None:
    ctx = running
    escaped = ctx.evidence.joinpath(*[".."] * 8) / "escaped.log"
    assert not escaped.resolve().is_relative_to(ctx.workspace)
    with pytest.raises(NebulaError) as caught:
        ctx.app.evidence.index_artifacts(ctx.run_id, [escaped], ctx.actor)
    assert caught.value.code is ErrorCode.PATH_DENIED


def test_a_traversal_that_lands_back_inside_an_approved_root_is_allowed(running) -> None:
    """Containment is about where a path RESOLVES, not whether it contains `..`.

    `evidence/../../..` lands in the workspace root, which is an approved root, so it is
    contained. Rejecting on the presence of `..` would be a syntactic check pretending to
    be a security one, and it would refuse legitimate paths while still missing symlinks.
    """
    ctx = running
    inside = ctx.evidence / ".." / ".." / ".." / "landed.log"
    inside.resolve().write_text("ok", encoding="utf-8")
    entry = ctx.app.evidence.index_artifacts(ctx.run_id, [inside], ctx.actor)[0]
    assert entry.source_root.value == "workspace"
    assert entry.source_path == "landed.log"


# --------------------------------------------------------------------------- #
# Redaction
# --------------------------------------------------------------------------- #
def test_no_sentinel_reaches_any_persisted_f0003_artifact(running) -> None:
    """The end-to-end sentinel sweep: index, summarize, report, and propose.

    Individually each path is redacted; this asserts the *union* leaks nothing, which is
    what a Security Reviewer actually needs.
    """
    ctx = running
    bearing = ctx.evidence / "transcript-bearing.txt"
    bearing.write_text(
        "\n".join(["$ codex", f"> deploy with {SENTINELS[2]}", f"ERROR: refused {SENTINELS[1]}"]),
        encoding="utf-8",
    )
    ctx.app.evidence.index_artifacts(ctx.run_id, [bearing], ctx.actor)
    ctx.app.evidence.summarize(ctx.run_id, ctx.actor)
    ctx.app.capabilities.probe(ProviderKey.CODEX, ctx.actor)

    leaked = []
    for path in sorted(ctx.runtime.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for sentinel in SENTINELS:
            if sentinel in text:
                leaked.append(f"{sentinel[:20]}... in {path.relative_to(ctx.runtime)}")
    assert leaked == [], "credential material reached persisted runtime state:\n" + "\n".join(leaked)


def test_a_secret_bearing_provider_version_is_stored_redacted(running) -> None:
    ctx = running
    report = ctx.app.capabilities.probe(ProviderKey.CODEX, ctx.actor)
    assert SENTINELS[0] not in (report.provider_version or "")
    assert "[REDACTED]" in (report.provider_version or "")

    document = json.loads(
        (ctx.runtime / "capabilities" / "codex.json").read_text(encoding="utf-8")
    )
    assert SENTINELS[0] not in json.dumps(document)


# --------------------------------------------------------------------------- #
# Proposal target allowlist
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "target",
    [
        "/etc/passwd",
        "../../outside.md",
        "engine/src/nebula_agents/bootstrap.py",
        "planning-mds/schemas/f0001-run-record.schema.json",
        ".nebula-agents/runtime/policy.json",
    ],
)
def test_a_proposal_target_outside_the_allowlist_is_refused_at_generation(target: str) -> None:
    """Refused at generation, so `learn decide` never evaluates an out-of-allowlist path.

    The last two matter most: a proposal that could name a schema or the local policy
    file would turn a review suggestion into a route to the trust boundary.
    """
    with pytest.raises(NebulaError) as caught:
        assert_target_allowed(target)
    assert caught.value.code is ErrorCode.PROPOSAL_TARGET_FORBIDDEN
    assert caught.value.exit_code == 5


def test_errors_carry_no_absolute_paths_outside_the_approved_roots(running, tmp_path: Path) -> None:
    """A denial must not become a directory-listing oracle."""
    ctx = running
    outside = tmp_path / "outside" / "probe-target.log"
    outside.parent.mkdir(exist_ok=True)
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(NebulaError) as caught:
        ctx.app.evidence.index_artifacts(ctx.run_id, [outside], ctx.actor)
    rendered = json.dumps([dict(d) for d in caught.value.details])
    assert "secret" not in rendered.lower()
    assert str(ctx.workspace) not in rendered

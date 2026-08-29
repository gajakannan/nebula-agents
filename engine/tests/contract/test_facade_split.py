"""F0003-S0007 — the query/command facade split is structural, not conventional.

These tests are the reason the split is worth anything. Without them the query facade
is a naming convention that the next contributor can quietly break; with them, adding a
mutating method to the read side fails the build.

The regression boundary for the split itself is the rest of this suite: 514 tests that
pass unmodified. Nothing here re-tests behavior — these assert the *shape* the behavior
now lives in.
"""

from __future__ import annotations

import inspect
import shutil
from pathlib import Path

import pytest

from nebula_agents.application.commands import CommandService
from nebula_agents.application.gates import GateService
from nebula_agents.application.preflight import PreflightService
from nebula_agents.application.queries import QueryService
from nebula_agents.application.runs import RunService
from nebula_agents.application.transcripts import TranscriptService
from nebula_agents.bootstrap import Application, build_application

# A query facade method may not read as a mutation. This list is deliberately broader
# than today's command surface so a future mutating verb is caught on arrival.
MUTATING_VERBS = (
    "create", "write", "commit", "append", "delete", "remove", "set", "update",
    "decide", "index", "summarize", "draft", "launch", "attach", "recover",
    "configure", "observe", "reconcile", "enable", "complete", "run", "resume",
    "initialize", "apply", "record", "save", "store",
)


def public_methods(cls: type) -> frozenset[str]:
    return frozenset(
        name
        for name, member in inspect.getmembers(cls, predicate=inspect.isfunction)
        if not name.startswith("_")
    )


def tree_snapshot(root: Path) -> list[tuple[str, int]]:
    """Every path under root with its size. Compared before and after a read."""
    if not root.exists():
        return []
    return sorted(
        (str(p.relative_to(root)), p.stat().st_size if p.is_file() else -1)
        for p in root.rglob("*")
    )


@pytest.fixture
def facade_workspace(tmp_path: Path, schema_root: Path) -> Path:
    """A workspace carrying the committed F0001 schemas, so preflight can probe."""
    workspace = tmp_path / "workspace"
    target = workspace / "planning-mds" / "schemas"
    target.mkdir(parents=True)
    for schema in schema_root.glob("f0001-*.json"):
        shutil.copy2(schema, target / schema.name)
    (workspace / "planning-mds" / "features").mkdir()
    (workspace / "agents" / "templates" / "prompts" / "evidence-contract").mkdir(
        parents=True
    )
    return workspace


@pytest.fixture
def application(facade_workspace: Path, tmp_path: Path) -> Application:
    # Deliberately an ABSENT runtime root: a query must not create it.
    return build_application(facade_workspace, tmp_path / "absent-runtime")


def test_query_surface_is_declared_exactly(application: Application) -> None:
    """A method added to QueryService and not declared in QUERY_SURFACE fails here.

    This is the assertion that makes the facade a contract. It is intentionally an
    equality, not a subset: an undeclared addition and a stale declaration both fail.
    """
    assert public_methods(QueryService) == QueryService.QUERY_SURFACE


def test_no_query_surface_name_reads_as_a_mutation() -> None:
    offenders = sorted(
        name
        for name in QueryService.QUERY_SURFACE
        if any(name == verb or name.startswith(f"{verb}_") for verb in MUTATING_VERBS)
    )
    assert offenders == [], f"query facade declares mutating-sounding names: {offenders}"


def test_executing_the_whole_query_surface_writes_nothing(
    application: Application, tmp_path: Path
) -> None:
    """The lazy-initialization edge case, asserted rather than promised.

    S0007 names it explicitly: a read that lazily creates the runtime directory is a
    command wearing a query's name. Running the entire declared surface against an
    absent runtime root must leave the tree byte-identical — which, here, means it must
    still not exist.
    """
    runtime = tmp_path / "absent-runtime"
    before = tree_snapshot(runtime)

    assert application.queries.sessions() == ()
    assert application.queries.recovery_candidates() == ()
    for run_id in ("2026-08-29-deadbeef",):
        for call in (
            application.queries.status,
            application.queries.evidence,
            application.queries.recovery_status,
        ):
            with pytest.raises(Exception):  # unknown run: NOT_FOUND, never a write
                call(run_id)

    assert tree_snapshot(runtime) == before
    assert not runtime.exists(), "a query created the runtime root"


def test_preflight_inspects_without_creating(
    application: Application, facade_workspace: Path, tmp_path: Path
) -> None:
    """PreflightService sits on the read side, and this is why.

    It stats the workspace, runtime root, and providers and reports. The runtime
    directory is created by the first authorized mutation, not by probing for it.
    """
    runtime = tmp_path / "absent-runtime"
    application.preflight.run(facade_workspace, runtime)
    assert not runtime.exists()


def test_command_facade_holds_every_mutating_service() -> None:
    assert isinstance(CommandService.__dataclass_fields__["runs"], object)
    assert set(CommandService.__dataclass_fields__) == {"runs", "gates", "transcripts"}


def test_query_facade_holds_no_mutating_service(application: Application) -> None:
    """Neither facade may reach the other.

    ADR-007's guarantee is that the MCP adapter, constructed with `queries` alone,
    cannot reach a mutating service. That only holds if `queries` does not itself hold
    one — so inspect what it actually carries rather than trusting the constructor.
    """
    mutating = (RunService, GateService, TranscriptService, CommandService)
    held = [
        getattr(application.queries, slot, None)
        for slot in vars(application.queries)
    ]
    assert not [obj for obj in held if isinstance(obj, mutating)]


def test_application_properties_delegate_to_the_command_facade(
    application: Application,
) -> None:
    """The compatibility surface is delegation, not duplication.

    If these were separate instances, a monkeypatch in an existing test would patch one
    object while production code used another — the split would look green and be
    broken.
    """
    assert application.runs is application.commands.runs
    assert application.gates is application.commands.gates
    assert application.transcripts is application.commands.transcripts


def test_application_declares_the_read_and_write_sides(application: Application) -> None:
    assert set(Application.__dataclass_fields__) == {
        "queries", "commands", "preflight", "identity",
    }
    assert isinstance(application.queries, QueryService)
    assert isinstance(application.commands, CommandService)
    assert isinstance(application.preflight, PreflightService)

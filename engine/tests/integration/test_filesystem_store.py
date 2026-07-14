from __future__ import annotations

import json
import fcntl
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from nebula_agents.domain.enums import (
    GateStatus,
    PromptAction,
    ProviderKey,
    RedactionStatus,
    Role,
    RunStatus,
    TranscriptStatus,
)
from nebula_agents.domain.errors import ErrorCode, NebulaError
from nebula_agents.domain.models import (
    Actor,
    GateSnapshot,
    RunRecord,
    RuntimeEvent,
    TranscriptState,
)
from nebula_agents.infrastructure.filesystem_store import FilesystemRunRepository
from nebula_agents.infrastructure.schema_registry import JsonSchemaRegistry


NOW = datetime(2026, 7, 13, 18, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 13, 18, 1, tzinfo=UTC)
CORRELATION = UUID("6fddeba4-7f25-4bf1-a298-70c095235f4f")
RUN_ID = "2026-07-13-deadbeef"
ACTOR = Actor(os.getuid(), "operator", Role.LOCAL_OPERATOR)


def _record(
    runtime: Path,
    *,
    revision: int = 0,
    sequence: int = 1,
    status: RunStatus = RunStatus.LAUNCHING,
    updated_at: datetime = NOW,
) -> RunRecord:
    return RunRecord(
        "1.0",
        revision,
        RUN_ID,
        "F0001",
        None,
        ProviderKey.CODEX,
        "nebula-F0001-deadbeef",
        "/workspace",
        "/workspace/feature-operator-friendly.md",
        PromptAction.FEATURE,
        status,
        ACTOR,
        None,
        GateSnapshot(None, GateStatus.UNKNOWN, False, (), None),
        None,
        (),
        TranscriptState(TranscriptStatus.DISABLED, RedactionStatus.NOT_RUN, None, None, 0),
        str(runtime / "runs" / RUN_ID / "events.jsonl"),
        sequence,
        NOW,
        updated_at,
        None,
    )


def _event(sequence: int, event_type: str, *, run_id: str = RUN_ID) -> RuntimeEvent:
    return RuntimeEvent("1.0", run_id, sequence, event_type, LATER if sequence > 1 else NOW, ACTOR, CORRELATION, {})


@pytest.fixture
def repository(tmp_path: Path, schema_root: Path) -> FilesystemRunRepository:
    return FilesystemRunRepository(tmp_path / "runtime", JsonSchemaRegistry(schema_root))


def _created(repository: FilesystemRunRepository) -> RunRecord:
    record = _record(repository.runtime_root)
    return repository.create(record, _event(1, "LaunchRequested"))


def _committed(repository: FilesystemRunRepository) -> RunRecord:
    current = _created(repository)
    next_record = replace(
        current,
        revision=1,
        last_event_sequence=2,
        status=RunStatus.ACTIVE,
        updated_at=LATER,
        last_seen_at=LATER,
    )
    return repository.commit(
        expected_revision=0,
        next_record=next_record,
        event=_event(2, "RunLaunched"),
    )


def test_create_persists_private_schema_valid_snapshot_and_event(
    repository: FilesystemRunRepository,
) -> None:
    expected = _created(repository)
    run_root = repository.run_directory(RUN_ID)
    assert repository.load(RUN_ID) == expected
    assert run_root.stat().st_mode & 0o777 == 0o700
    assert (run_root / "run.json").stat().st_mode & 0o777 == 0o600
    assert (run_root / "events.jsonl").stat().st_mode & 0o777 == 0o600
    event = json.loads((run_root / "events.jsonl").read_text(encoding="utf-8"))
    assert event["event_type"] == "LaunchRequested"
    assert event["sequence"] == 1


def test_commit_is_revision_checked_and_preserves_backup(
    repository: FilesystemRunRepository,
) -> None:
    committed = _committed(repository)
    assert repository.load(RUN_ID) == committed
    assert (repository.run_directory(RUN_ID) / "run.json.bak").is_file()
    with pytest.raises(NebulaError) as caught:
        repository.commit(
            expected_revision=0,
            next_record=replace(committed, revision=2, last_event_sequence=3),
            event=_event(3, "SessionAttached"),
        )
    assert caught.value.code is ErrorCode.STALE_REVISION


def test_list_is_read_only_and_filters_status(repository: FilesystemRunRepository) -> None:
    _committed(repository)
    before = (repository.run_directory(RUN_ID) / "events.jsonl").read_bytes()
    assert [record.run_id for record in repository.list()] == [RUN_ID]
    assert repository.list(RunStatus.ACTIVE)[0].run_id == RUN_ID
    assert repository.list(RunStatus.FAILED) == ()
    assert (repository.run_directory(RUN_ID) / "events.jsonl").read_bytes() == before


def test_duplicate_and_invalid_run_ids_fail_before_state_overwrite(
    repository: FilesystemRunRepository,
) -> None:
    _created(repository)
    with pytest.raises(NebulaError) as duplicate:
        repository.create(_record(repository.runtime_root), _event(1, "LaunchRequested"))
    assert duplicate.value.code is ErrorCode.CONFLICT
    with pytest.raises(NebulaError) as invalid:
        repository.run_directory("../../escape")
    assert invalid.value.code is ErrorCode.USAGE_ERROR


def test_load_rejects_non_private_snapshot_mode(repository: FilesystemRunRepository) -> None:
    _created(repository)
    snapshot = repository.run_directory(RUN_ID) / "run.json"
    snapshot.chmod(0o644)
    with pytest.raises(NebulaError) as caught:
        repository.load(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_CORRUPT


def test_load_rejects_symlink_snapshot_even_when_target_is_valid(
    repository: FilesystemRunRepository,
) -> None:
    _created(repository)
    snapshot = repository.run_directory(RUN_ID) / "run.json"
    target = snapshot.with_name("run.real.json")
    snapshot.rename(target)
    snapshot.symlink_to(target)
    with pytest.raises(NebulaError) as caught:
        repository.load(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_CORRUPT


def test_recovery_replays_contiguous_event_suffix_after_corrupt_latest_snapshot(
    repository: FilesystemRunRepository,
) -> None:
    expected = _committed(repository)
    snapshot = repository.run_directory(RUN_ID) / "run.json"
    snapshot.write_text("{corrupt", encoding="utf-8")
    snapshot.chmod(0o600)
    recovered = repository.recover(RUN_ID)
    assert recovered == expected
    assert repository.load(RUN_ID) == expected


def test_recovery_rejects_event_from_different_run(repository: FilesystemRunRepository) -> None:
    _created(repository)
    events = repository.run_directory(RUN_ID) / "events.jsonl"
    document = json.loads(events.read_text(encoding="utf-8"))
    document["run_id"] = "2026-07-13-feedface"
    events.write_text(json.dumps(document) + "\n", encoding="utf-8")
    events.chmod(0o600)
    with pytest.raises(NebulaError) as caught:
        repository.recover(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_CORRUPT


def test_recovery_rejects_noncontiguous_event_stream(
    repository: FilesystemRunRepository,
) -> None:
    _created(repository)
    events = repository.run_directory(RUN_ID) / "events.jsonl"
    with events.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "schema_version": "1.0",
            "run_id": RUN_ID,
            "sequence": 3,
            "event_type": "SessionAttached",
            "occurred_at": "2026-07-13T18:02:00Z",
            "actor": {"uid": os.getuid(), "username": "operator", "role": "LocalOperator", "display_label": None},
            "correlation_id": str(CORRELATION),
            "payload": {},
        }) + "\n")
    with pytest.raises(NebulaError) as caught:
        repository.recover(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_CORRUPT


def test_load_missing_and_list_skip_corrupt_snapshot(
    repository: FilesystemRunRepository,
) -> None:
    with pytest.raises(NebulaError) as missing:
        repository.load(RUN_ID)
    assert missing.value.code is ErrorCode.RUN_NOT_FOUND
    _created(repository)
    snapshot = repository.run_directory(RUN_ID) / "run.json"
    snapshot.write_text("[]", encoding="utf-8")
    snapshot.chmod(0o600)
    assert repository.list() == ()


def test_corrupt_snapshot_remains_discoverable_as_recovery_candidate(
    repository: FilesystemRunRepository,
) -> None:
    expected = _committed(repository)
    snapshot = repository.run_directory(RUN_ID) / "run.json"
    snapshot.write_text("{corrupt", encoding="utf-8")
    snapshot.chmod(0o600)

    assert repository.list() == ()
    candidates = repository.list_recoverable()

    assert len(candidates) == 1
    assert candidates[0].record == expected
    assert candidates[0].last_audit_event is not None
    assert candidates[0].last_audit_event.sequence == 2
    assert candidates[0].last_audit_event.event_type == "RunLaunched"
    assert candidates[0].last_audit_event.occurred_at == LATER


def test_create_and_commit_reject_inconsistent_state_event_pairs(
    repository: FilesystemRunRepository, schema_root: Path,
) -> None:
    invalid_initial = replace(_record(repository.runtime_root), revision=1)
    with pytest.raises(NebulaError) as initial:
        repository.create(invalid_initial, _event(1, "LaunchRequested"))
    assert initial.value.code is ErrorCode.STATE_CORRUPT

    other = FilesystemRunRepository(
        repository.runtime_root.parent / "other-runtime",
        JsonSchemaRegistry(schema_root),
    )
    current = _created(other)
    invalid_next = replace(current, revision=4, last_event_sequence=2)
    with pytest.raises(NebulaError) as revision:
        other.commit(
            expected_revision=0,
            next_record=invalid_next,
            event=_event(2, "RunLaunched"),
        )
    assert revision.value.code is ErrorCode.STATE_CORRUPT
    mismatched_next = replace(current, revision=1, last_event_sequence=2)
    with pytest.raises(NebulaError) as event:
        other.commit(
            expected_revision=0,
            next_record=mismatched_next,
            event=_event(3, "RunLaunched"),
        )
    assert event.value.code is ErrorCode.STATE_CORRUPT


def test_commit_and_recover_missing_run_are_stable_not_found(
    repository: FilesystemRunRepository,
) -> None:
    record = _record(repository.runtime_root, revision=1, sequence=2)
    with pytest.raises(NebulaError) as commit:
        repository.commit(
            expected_revision=0,
            next_record=record,
            event=_event(2, "RunLaunched"),
        )
    assert commit.value.code is ErrorCode.RUN_NOT_FOUND
    with pytest.raises(NebulaError) as recover:
        repository.recover(RUN_ID)
    assert recover.value.code is ErrorCode.RUN_NOT_FOUND


def test_missing_run_error_lists_only_twenty_newest_valid_available_ids(
    repository: FilesystemRunRepository,
) -> None:
    repository.initialize()
    available = [f"2026-07-13-{number:08x}" for number in range(25)]
    for run_id in available:
        repository.run_directory(run_id).mkdir(mode=0o700)
    (repository.runtime_root / "runs" / "not-a-run").mkdir()
    (repository.runtime_root / "runs" / "2026-07-13-ffffffff").write_text(
        "not a directory", encoding="utf-8"
    )

    with pytest.raises(NebulaError) as caught:
        repository.load("2026-07-13-feedface")

    assert caught.value.code is ErrorCode.RUN_NOT_FOUND
    assert caught.value.details == (
        {
            "run_id": "2026-07-13-feedface",
            "available_run_ids": sorted(available, reverse=True)[:20],
        },
    )


def test_lock_contention_maps_to_timeout_without_mutation(
    tmp_path: Path, schema_root: Path
) -> None:
    repository = FilesystemRunRepository(
        tmp_path / "runtime", JsonSchemaRegistry(schema_root), lock_timeout_seconds=0
    )
    current = _created(repository)
    lock_path = repository.run_directory(RUN_ID) / ".lock"
    fd = os.open(lock_path, os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(NebulaError) as caught:
            repository.commit(
                expected_revision=0,
                next_record=replace(current, revision=1, last_event_sequence=2),
                event=_event(2, "RunLaunched"),
            )
        assert caught.value.code is ErrorCode.STATE_LOCK_TIMEOUT
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@pytest.mark.parametrize("unsafe", ["symlink", "mode"])
def test_recovery_rejects_unsafe_event_log(
    repository: FilesystemRunRepository, unsafe: str
) -> None:
    _created(repository)
    events = repository.run_directory(RUN_ID) / "events.jsonl"
    if unsafe == "symlink":
        target = events.with_name("events.real.jsonl")
        events.rename(target)
        events.symlink_to(target)
    else:
        events.chmod(0o644)
    with pytest.raises(NebulaError) as caught:
        repository.recover(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_CORRUPT


def test_recovery_rejects_when_every_state_image_is_corrupt(
    repository: FilesystemRunRepository,
) -> None:
    _created(repository)
    run_root = repository.run_directory(RUN_ID)
    for path in run_root.glob("*.json"):
        path.write_text("{corrupt", encoding="utf-8")
        path.chmod(0o600)
    with pytest.raises(NebulaError) as caught:
        repository.recover(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_CORRUPT


def test_recovery_rejects_state_images_ahead_of_event_history(
    repository: FilesystemRunRepository,
) -> None:
    _created(repository)
    run_root = repository.run_directory(RUN_ID)
    for path in (run_root / "run.json", run_root / "state-00000001.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        document["last_event_sequence"] = 2
        path.write_text(json.dumps(document), encoding="utf-8")
        path.chmod(0o600)
    with pytest.raises(NebulaError) as caught:
        repository.recover(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_CORRUPT


def test_recovery_rejects_contiguous_suffix_without_matching_state_image(
    repository: FilesystemRunRepository,
) -> None:
    _committed(repository)
    run_root = repository.run_directory(RUN_ID)
    (run_root / "state-00000002.json").unlink()
    (run_root / "run.json").write_text("{corrupt", encoding="utf-8")
    (run_root / "run.json").chmod(0o600)
    with pytest.raises(NebulaError) as caught:
        repository.recover(RUN_ID)
    assert caught.value.code is ErrorCode.STATE_CORRUPT


def test_recovery_preserves_invalid_pending_file_for_inspection(
    repository: FilesystemRunRepository,
) -> None:
    expected = _created(repository)
    run_root = repository.run_directory(RUN_ID)
    pending = run_root / "pending.json"
    pending.write_text("{corrupt", encoding="utf-8")
    pending.chmod(0o600)
    assert repository.recover(RUN_ID) == expected
    assert not pending.exists()
    preserved = tuple(run_root.glob("pending.corrupt-*.json"))
    assert len(preserved) == 1
    assert preserved[0].read_text(encoding="utf-8") == "{corrupt"

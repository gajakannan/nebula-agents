"""Tests for tracker_merge.py — tracker-table three-way merge (F0006-S0002)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "kg"))

import merge3  # noqa: E402
from tracker_merge import (  # noqa: E402
    TrackerFormatError,
    merge_tracker_documents,
    tracker_semantic_diff,
)


BASE_REGISTRY = """# Feature Registry

**Next Available Feature Number:** F0041

## Planned (Reserved IDs)

| Feature ID | Name | Status | Phase | Folder |
|------------|------|--------|-------|--------|
| F0008 | Broker Insights | Planned | MVP | `F0008-broker-insights/` |
| F0021 | Communication Hub | Planned | MVP | `F0021-communication-hub/` |

## Archived Features

| Feature ID | Name | Archived Date | Folder |
|------------|------|---------------|--------|
| F0023 | Global Search | 2026-06-20 | `archive/F0023-global-search/` |
| F0019 | Quoting | 2026-06-03 | `archive/F0019-quoting/` |
"""

BASE_ROADMAP = """# Feature Roadmap (Now / Next / Later)

## Next

| Feature | Phase | Why Next |
|---------|-------|----------|
| [F0037 — Access Scoping](./F0037-access/README.md) | MVP+ | Deferred scope. |
| [F0022 — Work Queues](./F0022-queues/README.md) | MVP | Routing. |
| [F0021 — Communication Hub](./F0021-comms/README.md) | MVP | System of record. |

## Completed

| Feature | Phase | Completion State |
|---------|-------|------------------|
| [F0023 — Global Search](./archive/F0023-global-search/README.md) | MVP | Done and archived (2026-06-20) |

## Notes

- Base note one.
- Base note two.
"""


def merge_registry(base: str, ours: str, theirs: str):
    return merge_tracker_documents(base, ours, theirs, "REGISTRY.md")


def merge_roadmap(base: str, ours: str, theirs: str):
    return merge_tracker_documents(base, ours, theirs, "ROADMAP.md")


# ── row union and ordering ───────────────────────────────────────


def test_independent_row_union_archived_newest_first_id_desc_tiebreak() -> None:
    ours = BASE_REGISTRY.replace(
        "| F0023 | Global Search | 2026-06-20 | `archive/F0023-global-search/` |",
        "| F0038 | Neuron Shell | 2026-07-02 | `archive/F0038-neuron/` |\n"
        "| F0023 | Global Search | 2026-06-20 | `archive/F0023-global-search/` |",
    )
    theirs = BASE_REGISTRY.replace(
        "| F0021 | Communication Hub | Planned | MVP | `F0021-communication-hub/` |\n", ""
    ).replace(
        "| F0023 | Global Search | 2026-06-20 | `archive/F0023-global-search/` |",
        "| F0021 | Communication Hub | 2026-07-02 | `archive/F0021-comms/` |\n"
        "| F0023 | Global Search | 2026-06-20 | `archive/F0023-global-search/` |",
    )
    result = merge_registry(BASE_REGISTRY, ours, theirs)
    assert result.conflicts == []
    lines = [l for l in result.merged_text.splitlines() if l.startswith("| F00")]
    archived = [l for l in lines if "archive/" in l]
    # same archive date -> feature-ID-descending: F0038 above F0021, then by date
    assert [l.split("|")[1].strip() for l in archived] == ["F0038", "F0021", "F0023", "F0019"]


def test_same_row_divergence_is_pm_conflict_and_blocks() -> None:
    ours = BASE_REGISTRY.replace(
        "| F0021 | Communication Hub | Planned | MVP |",
        "| F0021 | Communication Hub | In Progress | MVP |",
    )
    theirs = BASE_REGISTRY.replace(
        "| F0021 | Communication Hub | Planned | MVP |",
        "| F0021 | Communication Hub | Blocked | MVP |",
    )
    result = merge_registry(BASE_REGISTRY, ours, theirs)
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.kind == "DivergentUpdate"
    assert conflict.record_id == "F0021"
    assert "Status" in conflict.field
    assert conflict.owning_role == "product-manager"
    assert conflict.ours == "In Progress" and conflict.theirs == "Blocked"


def test_delete_vs_update_row() -> None:
    ours = BASE_REGISTRY.replace(
        "| F0008 | Broker Insights | Planned | MVP | `F0008-broker-insights/` |\n", ""
    )
    theirs = BASE_REGISTRY.replace(
        "| F0008 | Broker Insights | Planned | MVP |",
        "| F0008 | Broker Insights | In Progress | MVP |",
    )
    result = merge_registry(BASE_REGISTRY, ours, theirs)
    assert [c.kind for c in result.conflicts] == ["DeleteVsUpdate"]
    assert result.conflicts[0].record_id == "F0008"


def test_counter_merges_to_max() -> None:
    ours = BASE_REGISTRY.replace("F0041", "F0042")
    theirs = BASE_REGISTRY.replace("F0041", "F0044")
    result = merge_registry(BASE_REGISTRY, ours, theirs)
    assert result.conflicts == []
    assert "**Next Available Feature Number:** F0044" in result.merged_text


def test_section_move_conflict() -> None:
    """Same feature moved to different exclusive sections on the two sides."""
    ours = BASE_ROADMAP.replace(
        "| [F0021 — Communication Hub](./F0021-comms/README.md) | MVP | System of record. |\n", ""
    ).replace(
        "| [F0023 — Global Search](./archive/F0023-global-search/README.md) | MVP | Done and archived (2026-06-20) |",
        "| [F0023 — Global Search](./archive/F0023-global-search/README.md) | MVP | Done and archived (2026-06-20) |\n"
        "| [F0021 — Communication Hub](./archive/F0021-comms/README.md) | MVP | Done and archived (2026-07-02) |",
    )
    theirs = BASE_ROADMAP  # theirs keeps F0021 in Next, ours moved it to Completed
    # make theirs also *touch* F0021's row so both sides changed it
    theirs = theirs.replace(
        "| [F0021 — Communication Hub](./F0021-comms/README.md) | MVP | System of record. |",
        "| [F0021 — Communication Hub](./F0021-comms/README.md) | MVP | Comm system of record. |",
    )
    result = merge_roadmap(BASE_ROADMAP, ours, theirs)
    kinds = {c.kind for c in result.conflicts}
    assert "DeleteVsUpdate" in kinds or any(
        c.record_id == "F0021" and "section" in (c.field or "") for c in result.conflicts
    )


def test_clean_section_move_merges() -> None:
    """One side moves a feature Next -> Completed; other side untouched."""
    ours = BASE_ROADMAP.replace(
        "| [F0021 — Communication Hub](./F0021-comms/README.md) | MVP | System of record. |\n", ""
    ).replace(
        "| [F0023 — Global Search](./archive/F0023-global-search/README.md) | MVP | Done and archived (2026-06-20) |",
        "| [F0021 — Communication Hub](./archive/F0021-comms/README.md) | MVP | Done and archived (2026-07-02) |\n"
        "| [F0023 — Global Search](./archive/F0023-global-search/README.md) | MVP | Done and archived (2026-06-20) |",
    )
    result = merge_roadmap(BASE_ROADMAP, ours, BASE_ROADMAP)
    assert result.conflicts == []
    next_block = result.merged_text.split("## Next")[1].split("## Completed")[0]
    completed_block = result.merged_text.split("## Completed")[1]
    assert "F0021" not in next_block
    assert "F0021" in completed_block


def test_manual_order_both_prepend_weaves_ours_first() -> None:
    """Both sides prepend to Completed -> ours' row first (the published F0038-above-F0021 rule)."""
    ours = BASE_ROADMAP.replace(
        "| [F0023 — Global Search](./archive/F0023-global-search/README.md) | MVP | Done and archived (2026-06-20) |",
        "| [F0038 — Neuron Shell](./archive/F0038-neuron/README.md) | Neuron | Done and archived (2026-07-02) |\n"
        "| [F0023 — Global Search](./archive/F0023-global-search/README.md) | MVP | Done and archived (2026-06-20) |",
    )
    theirs = BASE_ROADMAP.replace(
        "| [F0021 — Communication Hub](./F0021-comms/README.md) | MVP | System of record. |\n", ""
    ).replace(
        "| [F0023 — Global Search](./archive/F0023-global-search/README.md) | MVP | Done and archived (2026-06-20) |",
        "| [F0021 — Communication Hub](./archive/F0021-comms/README.md) | MVP | Done and archived (2026-07-02) |\n"
        "| [F0023 — Global Search](./archive/F0023-global-search/README.md) | MVP | Done and archived (2026-06-20) |",
    )
    result = merge_roadmap(BASE_ROADMAP, ours, theirs)
    assert result.conflicts == []
    completed = [
        l for l in result.merged_text.split("## Completed")[1].splitlines() if l.startswith("| [")
    ]
    ids = [l.split("—")[0].split("[")[1].strip() for l in completed]
    assert ids == ["F0038", "F0021", "F0023"]


def test_manual_order_double_reorder_conflicts() -> None:
    next_rows = [
        "| [F0037 — Access Scoping](./F0037-access/README.md) | MVP+ | Deferred scope. |",
        "| [F0022 — Work Queues](./F0022-queues/README.md) | MVP | Routing. |",
        "| [F0021 — Communication Hub](./F0021-comms/README.md) | MVP | System of record. |",
    ]
    ours = BASE_ROADMAP.replace(
        "\n".join(next_rows), "\n".join([next_rows[2], next_rows[0], next_rows[1]])
    )
    theirs = BASE_ROADMAP.replace(
        "\n".join(next_rows), "\n".join([next_rows[1], next_rows[2], next_rows[0]])
    )
    result = merge_roadmap(BASE_ROADMAP, ours, theirs)
    assert any(c.kind == "OrderedListConflict" for c in result.conflicts)


# ── structure and prose ──────────────────────────────────────────


def test_column_structure_mismatch_conflicts() -> None:
    theirs = BASE_REGISTRY.replace(
        "| Feature ID | Name | Status | Phase | Folder |",
        "| Feature ID | Name | Status | Phase | Folder | Owner |",
    ).replace(
        "|------------|------|--------|-------|--------|",
        "|------------|------|--------|-------|--------|-------|",
    )
    result = merge_registry(BASE_REGISTRY, BASE_REGISTRY, theirs)
    assert any("column structure" in c.message for c in result.conflicts)


def test_prose_double_append_merges() -> None:
    ours = BASE_ROADMAP.replace("- Base note two.", "- Base note two.\n- Ours note.")
    theirs = BASE_ROADMAP.replace("- Base note two.", "- Base note two.\n- Theirs note.")
    result = merge_roadmap(BASE_ROADMAP, ours, theirs)
    assert result.conflicts == []
    assert "- Ours note." in result.merged_text
    assert "- Theirs note." in result.merged_text


def test_prose_divergence_conflicts_to_pm() -> None:
    ours = BASE_ROADMAP.replace("- Base note one.", "- Ours rewrote this.")
    theirs = BASE_ROADMAP.replace("- Base note one.", "- Theirs rewrote this.")
    result = merge_roadmap(BASE_ROADMAP, ours, theirs)
    assert len(result.conflicts) == 1
    assert result.conflicts[0].owning_role == "product-manager"


def test_unknown_tracker_fails_loudly() -> None:
    with pytest.raises(TrackerFormatError, match="no tracker merge configuration"):
        merge_tracker_documents("# X\n", "# X\n", "# X\n", "BLUEPRINT.md")


def test_unkeyed_row_fails_loudly() -> None:
    bad = BASE_REGISTRY.replace("| F0008 |", "| (unnumbered) |")
    with pytest.raises(TrackerFormatError, match="no identifiable feature ID"):
        merge_registry(bad, bad, bad)


# ── rendering and CLI ────────────────────────────────────────────


def test_rendering_idempotent() -> None:
    once = merge_registry(BASE_REGISTRY, BASE_REGISTRY, BASE_REGISTRY).merged_text
    twice = merge_registry(once, once, once).merged_text
    assert once == twice
    road_once = merge_roadmap(BASE_ROADMAP, BASE_ROADMAP, BASE_ROADMAP).merged_text
    road_twice = merge_roadmap(road_once, road_once, road_once).merged_text
    assert road_once == road_twice


def test_semantic_diff_rows() -> None:
    changed = BASE_REGISTRY.replace(
        "| F0021 | Communication Hub | Planned | MVP |",
        "| F0021 | Communication Hub | In Progress | MVP |",
    )
    diff = tracker_semantic_diff(BASE_REGISTRY, changed, "REGISTRY.md")
    assert diff["changed"] == ["Planned (Reserved IDs)[F0021]"]
    assert diff["added"] == [] and diff["removed"] == []


def test_cli_story_index_rejected(tmp_path: Path) -> None:
    target = tmp_path / "STORY-INDEX.md"
    target.write_text("# Story Index\n", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        merge3.main([str(target), "--base", str(target), "--ours", str(target), "--theirs", str(target)])
    assert excinfo.value.code == 2


def test_cli_tracker_merge_all_or_nothing(tmp_path: Path) -> None:
    base = tmp_path / "base.md"
    ours = tmp_path / "REGISTRY.md"
    theirs = tmp_path / "theirs.md"
    base.write_text(BASE_REGISTRY, encoding="utf-8")
    ours.write_text(
        BASE_REGISTRY.replace(
            "| F0021 | Communication Hub | Planned | MVP |",
            "| F0021 | Communication Hub | In Progress | MVP |",
        ),
        encoding="utf-8",
    )
    theirs.write_text(
        BASE_REGISTRY.replace(
            "| F0021 | Communication Hub | Planned | MVP |",
            "| F0021 | Communication Hub | Blocked | MVP |",
        ),
        encoding="utf-8",
    )
    report = tmp_path / "report.json"
    code = merge3.main(
        [str(ours), "--base", str(base), "--ours", str(ours), "--theirs", str(theirs), "--json", str(report)]
    )
    assert code == 1
    assert "In Progress" in ours.read_text(encoding="utf-8")  # unchanged
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["result"] == "conflicts"
    assert payload["conflicts"][0]["owning_role"] == "product-manager"


def test_cli_tracker_clean_merge_writes(tmp_path: Path) -> None:
    base = tmp_path / "base.md"
    ours = tmp_path / "REGISTRY.md"
    theirs = tmp_path / "theirs.md"
    base.write_text(BASE_REGISTRY, encoding="utf-8")
    ours.write_text(BASE_REGISTRY, encoding="utf-8")
    theirs.write_text(BASE_REGISTRY.replace("F0041", "F0043"), encoding="utf-8")
    code = merge3.main([str(ours), "--base", str(base), "--ours", str(ours), "--theirs", str(theirs)])
    assert code == 0
    assert "**Next Available Feature Number:** F0043" in ours.read_text(encoding="utf-8")

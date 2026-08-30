"""Tests for tracker_gen.py — REGISTRY/ROADMAP generation from feature shards (F0006-S0007)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "kg"))

import tracker_gen  # noqa: E402
from tracker_gen import TrackerGenError  # noqa: E402


# ── the round-trip gate: regenerating the committed trackers is zero-diff ──
def test_zero_diff_regeneration():
    assert tracker_gen.check() == [], "tracker regions drifted from the shards"


def test_double_generate_stable():
    a = tracker_gen.generate(write=False)
    b = tracker_gen.generate(write=False)
    assert a == b


# ── placement + counts ──
def test_every_feature_in_exactly_one_registry_table_and_roadmap_section():
    feats = tracker_gen.load_features()
    for f in feats:
        placements = [n for n, s in tracker_gen.REGISTRY_TABLES.items() if s["select"](f)]
        assert len(placements) == 1, (f["id"], placements)
        sections = [n for n, s in tracker_gen.ROADMAP_TABLES.items() if s["select"](f)]
        assert len(sections) == 1, (f["id"], sections)


def test_registry_table_derivation_rules():
    # A shard may omit `registry_section`, in which case placement is derived.
    # Replaces a hard-coded per-table count snapshot that went stale on every
    # feature registration or archive, and that exercised no logic.
    derive = tracker_gen._registry_table
    assert derive({"status": "superseded", "superseded_by": "feature:F0006"}) == "retired"
    assert derive({"status": "done", "retired_date": "2026-01-01"}) == "retired"
    assert derive({"status": "archived-done", "archived_date": "2026-01-01"}) == "archived"
    assert derive({"status": "planned"}) == "planned"
    assert derive({"status": "planned-provisional"}) == "planned"
    assert derive({"status": "in-progress"}) == "active"
    assert derive({"status": "done"}) == "active"
    # Retirement outranks archival when a shard carries both dates.
    assert derive({"retired_date": "2026-01-01", "archived_date": "2026-02-01"}) == "retired"
    # An explicit section always wins over the derived placement.
    assert derive({"status": "planned", "registry_section": "Active"}) == "active"


def test_next_available_feature_number():
    # REGISTRY.md's Numbering Rules: ids are sequential and never reused. Assert that
    # contract rather than a literal id, which goes stale on every new registration.
    feats = tracker_gen.load_features()
    taken = {tracker_gen._id_num(f) for f in feats}
    reg = tracker_gen.generate(write=False)["REGISTRY.md"]
    match = re.search(r"\*\*Next Available Feature Number:\*\* F(\d{4})", reg)
    assert match, "REGISTRY.md must publish a next-available feature number"
    nxt = int(match.group(1))
    assert nxt not in taken, f"F{nxt:04d} is already registered"
    assert nxt > max(taken), "next-available number must never reuse a retired id"


# ── ordering ──
def test_archived_is_date_desc_id_desc():
    feats = tracker_gen.load_features()
    spec = tracker_gen.REGISTRY_TABLES["registry:archived"]
    rows = sorted((f for f in feats if spec["select"](f)), key=spec["key"], reverse=spec["reverse"])
    keys = [(f["archived_date"], tracker_gen._id_num(f)) for f in rows]
    assert keys == sorted(keys, reverse=True)


def test_roadmap_rows_are_ordered_by_roadmap_order():
    """`render_table` orders rows by `roadmap_order` within a section.

    Injects synthetic features rather than reading the live repository. Two earlier
    versions of this test were worthless and both are worth naming:

    - The original pinned "F0003 before F0002" across every roadmap row. That held only
      while both sat in `Next`, and broke the moment F0003 was archived into `Completed` --
      a legitimate data change, not a regression.
    - Its first replacement read the GENERATED output and asserted it was sorted. The
      generator sorts, so that assertion could never fail; inverting a shard's
      `roadmap_order` left it green.

    Feeding `render_table` an out-of-order list is the only version that fails when the
    sort is removed.
    """
    spec = tracker_gen.ROADMAP_TABLES["roadmap:later"]
    features = [
        {"id": "feature:F9002", "name": "Second", "path": "p/F9002-b",
         "roadmap_section": "Later", "roadmap_order": 2, "status": "planned", "rationale": ""},
        {"id": "feature:F9001", "name": "First", "path": "p/F9001-a",
         "roadmap_section": "Later", "roadmap_order": 1, "status": "planned", "rationale": ""},
    ]
    rendered = tracker_gen.render_table(spec, features)
    assert rendered.index("F9001") < rendered.index("F9002")

    # And the ordering is driven by roadmap_order, not by input or id order.
    for f in features:
        f["roadmap_order"] = 3 - f["roadmap_order"]
    flipped = tracker_gen.render_table(spec, features)
    assert flipped.index("F9002") < flipped.index("F9001")


# ── fenced-region integrity ──
def test_missing_marker_fails():
    with pytest.raises(TrackerGenError, match="exactly one begin/end"):
        tracker_gen._replace_region("no markers here", "registry:active", "body", "REGISTRY.md")


def test_duplicated_marker_fails():
    txt = ("<!-- generated:begin x -->\na\n<!-- generated:end x -->\n"
           "<!-- generated:begin x -->\nb\n<!-- generated:end x -->")
    with pytest.raises(TrackerGenError, match="exactly one begin/end"):
        tracker_gen._replace_region(txt, "x", "body", "REGISTRY.md")


def test_replace_region_only_touches_between_markers():
    txt = "before\n<!-- generated:begin x -->\nOLD\n<!-- generated:end x -->\nafter"
    out = tracker_gen._replace_region(txt, "x", "NEW", "F.md")
    assert out == "before\n<!-- generated:begin x -->\nNEW\n<!-- generated:end x -->\nafter"


def test_prose_outside_regions_untouched():
    import re
    generated = tracker_gen.generate(write=False)
    for basename, text in generated.items():
        committed = (tracker_gen.FEATURES_DIR / basename).read_text(encoding="utf-8")
        # strip every generated region from both; the remaining prose must be identical
        region = re.compile(r"<!-- generated:begin .*? -->\n.*?\n<!-- generated:end .*? -->", re.DOTALL)
        assert region.sub("", committed) == region.sub("", text)

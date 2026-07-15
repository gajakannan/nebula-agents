"""Tests for tracker_gen.py — REGISTRY/ROADMAP generation from feature shards (F0006-S0007)."""
from __future__ import annotations

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


def test_registry_placement_counts():
    feats = tracker_gen.load_features()
    counts = {n: sum(1 for f in feats if s["select"](f)) for n, s in tracker_gen.REGISTRY_TABLES.items()}
    assert counts == {"registry:active": 2, "registry:retired": 1,
                      "registry:planned": 3, "registry:archived": 1}


def test_next_available_feature_number():
    reg = tracker_gen.generate(write=False)["REGISTRY.md"]
    assert "**Next Available Feature Number:** F0008" in reg


# ── ordering ──
def test_archived_is_date_desc_id_desc():
    feats = tracker_gen.load_features()
    spec = tracker_gen.REGISTRY_TABLES["registry:archived"]
    rows = sorted((f for f in feats if spec["select"](f)), key=spec["key"], reverse=spec["reverse"])
    keys = [(f["archived_date"], tracker_gen._id_num(f)) for f in rows]
    assert keys == sorted(keys, reverse=True)


def test_roadmap_uses_captured_order():
    reg = tracker_gen.generate(write=False)["ROADMAP.md"]
    # Next section authored order: F0003, then F0002.
    next_ids = [ln.split("[")[1][:5] for ln in reg.splitlines()
                if ln.startswith("| [F") and "roadmap" not in ln]
    assert next_ids.index("F0003") < next_ids.index("F0002")


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

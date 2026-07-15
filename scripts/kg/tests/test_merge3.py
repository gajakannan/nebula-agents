"""Tests for merge3.py — three-way semantic KG merge (F0006-S0001)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "kg"))

import merge3  # noqa: E402
from kg_common import canonical_dump, canonicalize_document  # noqa: E402


BASE_DOC = {
    "version": 0,
    "status": "seed",
    "entities": [
        {"id": "entity:alpha", "label": "Alpha", "source_docs": ["docs/a.md"]},
        {"id": "entity:beta", "label": "Beta", "source_docs": ["docs/b.md"]},
    ],
    "capabilities": [
        {"id": "capability:reporting", "label": "Reporting", "related_nodes": ["entity:alpha"]},
    ],
    "workflows": [
        {
            "id": "workflow:intake",
            "label": "Intake",
            "states": [
                {"id": "state:intake:new", "transitions_to": ["state:intake:review"]},
                {"id": "state:intake:review", "transitions_to": ["state:intake:done"]},
                {"id": "state:intake:done", "transitions_to": []},
            ],
        }
    ],
}


def write_doc(path: Path, doc: dict, *, scramble: bool = False) -> Path:
    """Write a doc as YAML; `scramble` re-serializes with different formatting."""
    if scramble:
        text = yaml.dump(doc, sort_keys=True, default_flow_style=True, allow_unicode=False)
    else:
        text = yaml.dump(doc, sort_keys=False)
    path.write_text(text, encoding="utf-8")
    return path


def run_merge(
    tmp_path: Path,
    base: dict,
    ours: dict,
    theirs: dict,
    *,
    target_name: str = "canonical-nodes.yaml",
    scramble_theirs: bool = False,
    extra_args: list[str] | None = None,
) -> tuple[int, Path, dict]:
    target = tmp_path / target_name
    write_doc(target, ours)
    base_path = write_doc(tmp_path / "base.yaml", base)
    ours_path = write_doc(tmp_path / "ours.yaml", ours)
    theirs_path = write_doc(tmp_path / "theirs.yaml", theirs, scramble=scramble_theirs)
    report = tmp_path / "report.json"
    argv = [
        str(target),
        "--base",
        str(base_path),
        "--ours",
        str(ours_path),
        "--theirs",
        str(theirs_path),
        "--json",
        str(report),
        *(extra_args or []),
    ]
    code = merge3.main(argv)
    payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
    return code, target, payload


def deep(doc: dict) -> dict:
    return json.loads(json.dumps(doc))


# ── canonicalization ─────────────────────────────────────────────


def test_canonicalization_idempotent() -> None:
    once = canonical_dump(BASE_DOC)
    twice = canonical_dump(yaml.safe_load(once))
    assert once == twice


def test_canonicalization_preserves_ordered_fields() -> None:
    canonical = canonicalize_document(BASE_DOC)
    states = canonical["workflows"][0]["states"]
    assert [s["id"] for s in states] == [
        "state:intake:new",
        "state:intake:review",
        "state:intake:done",
    ]


def test_canonicalization_sorts_records_and_scalar_lists() -> None:
    doc = {
        "entities": [
            {"id": "entity:zeta", "source_docs": ["z.md", "a.md", "a.md"]},
            {"id": "entity:alpha", "source_docs": ["b.md"]},
        ]
    }
    canonical = canonicalize_document(doc)
    assert [e["id"] for e in canonical["entities"]] == ["entity:alpha", "entity:zeta"]
    assert canonical["entities"][1]["source_docs"] == ["a.md", "z.md"]


# ── convergence ──────────────────────────────────────────────────


def test_reserialization_plus_additions_converges(tmp_path: Path) -> None:
    """The PR #47 shape: theirs is a re-dump of base plus new nodes; ours has its own change."""
    ours = deep(BASE_DOC)
    ours["entities"][0]["label"] = "Alpha Prime"  # ours-only change
    theirs = deep(BASE_DOC)
    theirs["entities"].append({"id": "entity:gamma", "label": "Gamma"})

    code, target, payload = run_merge(tmp_path, BASE_DOC, ours, theirs, scramble_theirs=True)
    assert code == 0
    assert payload["result"] == "clean"
    merged = yaml.safe_load(target.read_text(encoding="utf-8"))
    ids = [e["id"] for e in merged["entities"]]
    assert ids == ["entity:alpha", "entity:beta", "entity:gamma"]
    assert merged["entities"][0]["label"] == "Alpha Prime"


def test_identical_addition_on_both_sides_converges(tmp_path: Path) -> None:
    addition = {"id": "entity:gamma", "label": "Gamma"}
    ours = deep(BASE_DOC)
    ours["entities"].append(deep(addition))
    theirs = deep(BASE_DOC)
    theirs["entities"].append(deep(addition))

    code, target, payload = run_merge(tmp_path, BASE_DOC, ours, theirs)
    assert code == 0
    merged = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert sum(1 for e in merged["entities"] if e["id"] == "entity:gamma") == 1


def test_field_level_recursion_merges_disjoint_field_changes(tmp_path: Path) -> None:
    ours = deep(BASE_DOC)
    ours["entities"][0]["label"] = "Alpha Prime"
    theirs = deep(BASE_DOC)
    theirs["entities"][0]["notes"] = "annotated"

    code, target, _ = run_merge(tmp_path, BASE_DOC, ours, theirs)
    assert code == 0
    merged = yaml.safe_load(target.read_text(encoding="utf-8"))
    alpha = merged["entities"][0]
    assert alpha["label"] == "Alpha Prime"
    assert alpha["notes"] == "annotated"


def test_scalar_list_set_union_with_deletion(tmp_path: Path) -> None:
    ours = deep(BASE_DOC)
    ours["entities"][0]["source_docs"] = ["docs/a.md", "docs/extra.md"]  # add
    theirs = deep(BASE_DOC)
    theirs["entities"][0]["source_docs"] = []  # remove docs/a.md

    code, target, _ = run_merge(tmp_path, BASE_DOC, ours, theirs)
    assert code == 0
    merged = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert merged["entities"][0]["source_docs"] == ["docs/extra.md"]


# ── typed conflicts ──────────────────────────────────────────────


def test_divergent_update_conflict_blocks_write(tmp_path: Path) -> None:
    ours = deep(BASE_DOC)
    ours["entities"][0]["label"] = "Alpha Ours"
    theirs = deep(BASE_DOC)
    theirs["entities"][0]["label"] = "Alpha Theirs"

    code, target, payload = run_merge(tmp_path, BASE_DOC, ours, theirs)
    assert code == 1
    kinds = [c["kind"] for c in payload["conflicts"]]
    assert kinds == ["DivergentUpdate"]
    conflict = payload["conflicts"][0]
    assert conflict["record_id"] == "entity:alpha"
    assert "label" in conflict["field"]
    assert conflict["owning_role"] == "architect"
    assert conflict["ours"] == "Alpha Ours"
    assert conflict["theirs"] == "Alpha Theirs"
    # all-or-nothing: target still holds the pre-merge (ours) content
    assert yaml.safe_load(target.read_text(encoding="utf-8"))["entities"][0]["label"] == "Alpha Ours"


def test_divergent_insert_conflict(tmp_path: Path) -> None:
    ours = deep(BASE_DOC)
    ours["entities"].append({"id": "entity:gamma", "label": "Gamma One"})
    theirs = deep(BASE_DOC)
    theirs["entities"].append({"id": "entity:gamma", "label": "Gamma Two"})

    code, _, payload = run_merge(tmp_path, BASE_DOC, ours, theirs)
    assert code == 1
    assert [c["kind"] for c in payload["conflicts"]] == ["DivergentInsert"]
    assert payload["conflicts"][0]["record_id"] == "entity:gamma"


def test_delete_vs_update_conflict(tmp_path: Path) -> None:
    ours = deep(BASE_DOC)
    ours["entities"] = [e for e in ours["entities"] if e["id"] != "entity:beta"]
    theirs = deep(BASE_DOC)
    theirs["entities"][1]["label"] = "Beta Updated"

    code, _, payload = run_merge(tmp_path, BASE_DOC, ours, theirs)
    assert code == 1
    assert [c["kind"] for c in payload["conflicts"]] == ["DeleteVsUpdate"]
    assert payload["conflicts"][0]["record_id"] == "entity:beta"


def test_ordered_list_conflict_on_double_reorder(tmp_path: Path) -> None:
    ours = deep(BASE_DOC)
    ours["workflows"][0]["states"] = list(reversed(ours["workflows"][0]["states"]))
    theirs = deep(BASE_DOC)
    states = theirs["workflows"][0]["states"]
    theirs["workflows"][0]["states"] = [states[1], states[0], states[2]]

    code, _, payload = run_merge(tmp_path, BASE_DOC, ours, theirs)
    assert code == 1
    assert "OrderedListConflict" in [c["kind"] for c in payload["conflicts"]]


def test_ordered_list_one_side_change_adopted(tmp_path: Path) -> None:
    ours = deep(BASE_DOC)
    theirs = deep(BASE_DOC)
    theirs["workflows"][0]["states"].append({"id": "state:intake:archived", "transitions_to": []})

    code, target, _ = run_merge(tmp_path, BASE_DOC, ours, theirs)
    assert code == 0
    merged = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert [s["id"] for s in merged["workflows"][0]["states"]][-1] == "state:intake:archived"


def test_pm_owned_conflict_routes_to_product_manager(tmp_path: Path) -> None:
    base = {
        "features": [{"id": "feature:F0900", "path": "planning-mds/features/F0900-x", "status": "planned"}]
    }
    ours = deep(base)
    ours["features"][0]["status"] = "in-progress"
    theirs = deep(base)
    theirs["features"][0]["status"] = "archived-done"

    code, _, payload = run_merge(
        tmp_path, base, ours, theirs, target_name="feature-mappings.yaml"
    )
    assert code == 1
    assert payload["conflicts"][0]["owning_role"] == "product-manager"


# ── graph-level checks ───────────────────────────────────────────


def test_orphan_edge_when_sibling_still_references_deleted_node(tmp_path: Path) -> None:
    sibling = {
        "features": [
            {"id": "feature:F0900", "path": "p", "status": "planned", "affects": ["entity:beta"]}
        ]
    }
    write_doc(tmp_path / "feature-mappings.yaml", sibling)

    ours = deep(BASE_DOC)
    theirs = deep(BASE_DOC)
    theirs["entities"] = [e for e in theirs["entities"] if e["id"] != "entity:beta"]

    code, _, payload = run_merge(tmp_path, BASE_DOC, ours, theirs)
    assert code == 1
    orphans = [c for c in payload["conflicts"] if c["kind"] == "OrphanEdge"]
    assert orphans and orphans[0]["record_id"] == "entity:beta"


def test_unique_violation_across_lists(tmp_path: Path) -> None:
    base = {
        "coverage": {
            "excluded_features": [{"id": "feature:F0900", "path": "p", "reason": "pending"}]
        },
        "features": [],
    }
    ours = deep(base)
    ours["features"] = [{"id": "feature:F0900", "path": "p", "status": "planned"}]
    theirs = deep(base)

    code, _, payload = run_merge(
        tmp_path, base, ours, theirs, target_name="feature-mappings.yaml"
    )
    assert code == 1
    assert "UniqueViolation" in [c["kind"] for c in payload["conflicts"]]


def test_semantic_duplicate_warning_is_non_blocking(tmp_path: Path) -> None:
    ours = deep(BASE_DOC)
    theirs = deep(BASE_DOC)
    theirs["capabilities"].append({"id": "capability:reporting-v2", "label": "reporting"})

    code, _, payload = run_merge(tmp_path, BASE_DOC, ours, theirs)
    assert code == 0
    assert any(w["kind"] == "SemanticDuplicateWarning" for w in payload["warnings"])


def test_object_form_edge_refs_are_not_record_definitions(tmp_path: Path) -> None:
    """`depends_on: [{id:, provenance:}]` is a reference, not a definition —
    it must not collide with the real record of the same id (PR #47 replay bug)."""
    base = {
        "features": [
            {"id": "feature:F0900", "path": "p", "status": "planned"},
            {
                "id": "feature:F0901",
                "path": "q",
                "status": "planned",
                "depends_on": [{"id": "feature:F0900", "provenance": "inferred", "confidence": 0.6}],
            },
        ]
    }
    ours = deep(base)
    theirs = deep(base)
    theirs["features"][1]["status"] = "in-progress"

    code, _, payload = run_merge(
        tmp_path, base, ours, theirs, target_name="feature-mappings.yaml"
    )
    assert code == 0
    assert payload["conflicts"] == []


def test_orphan_check_sees_object_form_refs(tmp_path: Path) -> None:
    sibling = {
        "features": [
            {
                "id": "feature:F0900",
                "path": "p",
                "status": "planned",
                "depends_on": [{"id": "entity:beta", "provenance": "inferred", "confidence": 0.9}],
            }
        ]
    }
    write_doc(tmp_path / "feature-mappings.yaml", sibling)

    ours = deep(BASE_DOC)
    theirs = deep(BASE_DOC)
    theirs["entities"] = [e for e in theirs["entities"] if e["id"] != "entity:beta"]

    code, _, payload = run_merge(tmp_path, BASE_DOC, ours, theirs)
    assert code == 1
    orphans = [c for c in payload["conflicts"] if c["kind"] == "OrphanEdge"]
    assert orphans and orphans[0]["record_id"] == "entity:beta"


# ── guards, validation, exit codes ───────────────────────────────


def test_generated_file_rejected(tmp_path: Path) -> None:
    target = tmp_path / "symbol-index.yaml"
    write_doc(target, {"symbols": []})
    with pytest.raises(SystemExit) as excinfo:
        merge3.main([str(target), "--base", str(target), "--ours", str(target), "--theirs", str(target)])
    assert excinfo.value.code == 2


def test_duplicate_id_in_input_is_hard_error(tmp_path: Path) -> None:
    bad = deep(BASE_DOC)
    bad["entities"].append(deep(bad["entities"][0]))
    with pytest.raises(SystemExit) as excinfo:
        run_merge(tmp_path, bad, BASE_DOC, BASE_DOC)
    assert excinfo.value.code == 2


def test_missing_side_is_usage_error(tmp_path: Path) -> None:
    target = write_doc(tmp_path / "canonical-nodes.yaml", BASE_DOC)
    with pytest.raises(SystemExit) as excinfo:
        merge3.main([str(target), "--base", str(target)])
    assert excinfo.value.code == 2


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    ours = deep(BASE_DOC)
    theirs = deep(BASE_DOC)
    theirs["entities"].append({"id": "entity:gamma", "label": "Gamma"})

    code, target, payload = run_merge(
        tmp_path, BASE_DOC, ours, theirs, extra_args=["--dry-run"]
    )
    assert code == 0
    assert payload["output"] is None
    merged = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert all(e["id"] != "entity:gamma" for e in merged["entities"])


def test_full_validate_rolls_back_on_constraint_violation(tmp_path: Path) -> None:
    ours = deep(BASE_DOC)
    theirs = deep(BASE_DOC)
    theirs["entities"].append({"id": "entity:gamma", "label": "Gamma"})

    original = canonical_dump(ours)
    target = tmp_path / "canonical-nodes.yaml"
    target.write_text(original, encoding="utf-8")

    code, target, payload = run_merge(
        tmp_path,
        BASE_DOC,
        ours,
        theirs,
        extra_args=["--full-validate", "--validate-cmd", "false"],
    )
    assert code == 1
    assert [c["kind"] for c in payload["conflicts"]] == ["ConstraintViolation"]
    # rolled back to the pre-merge bytes
    merged = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert all(e["id"] != "entity:gamma" for e in merged["entities"])


def test_full_validate_keeps_output_when_validator_passes(tmp_path: Path) -> None:
    ours = deep(BASE_DOC)
    theirs = deep(BASE_DOC)
    theirs["entities"].append({"id": "entity:gamma", "label": "Gamma"})

    code, target, _ = run_merge(
        tmp_path,
        BASE_DOC,
        ours,
        theirs,
        extra_args=["--full-validate", "--validate-cmd", "true"],
    )
    assert code == 0
    merged = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert any(e["id"] == "entity:gamma" for e in merged["entities"])


def test_output_is_deterministic(tmp_path: Path) -> None:
    ours = deep(BASE_DOC)
    ours["entities"][0]["label"] = "Alpha Prime"
    theirs = deep(BASE_DOC)
    theirs["entities"].append({"id": "entity:gamma", "label": "Gamma"})

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    _, target_a, _ = run_merge(tmp_path / "a", BASE_DOC, ours, theirs, scramble_theirs=True)
    _, target_b, _ = run_merge(tmp_path / "b", BASE_DOC, ours, theirs)
    assert target_a.read_text(encoding="utf-8") == target_b.read_text(encoding="utf-8")


# ── semantic diff mode ───────────────────────────────────────────


def test_semantic_diff_reserialization_is_no_change(tmp_path: Path) -> None:
    old = write_doc(tmp_path / "old.yaml", BASE_DOC)
    new = write_doc(tmp_path / "new.yaml", deep(BASE_DOC), scramble=True)
    target = tmp_path / "canonical-nodes.yaml"
    write_doc(target, BASE_DOC)
    code = merge3.main([str(target), "--semantic-diff", str(old), str(new)])
    assert code == 0


def test_semantic_diff_detects_record_change(tmp_path: Path) -> None:
    changed = deep(BASE_DOC)
    changed["entities"][0]["label"] = "Alpha Prime"
    old = write_doc(tmp_path / "old.yaml", BASE_DOC)
    new = write_doc(tmp_path / "new.yaml", changed)
    target = tmp_path / "canonical-nodes.yaml"
    write_doc(target, BASE_DOC)
    code = merge3.main([str(target), "--semantic-diff", str(old), str(new)])
    assert code == 1

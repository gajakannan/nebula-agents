"""Tests for compile.py + kg_common.resolve_doc_ref — deterministic KG compiler (F0006-S0005)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "kg"))

import compile as kgc  # noqa: E402
import kg_common  # noqa: E402
from kg_common import DocRefError, resolve_doc_ref  # noqa: E402

FIXTURES = REPO_ROOT / "scripts" / "kg" / "tests" / "fixtures" / "compile"
SRC = FIXTURES / "kg-source"
GOLDEN = FIXTURES / "golden"


def write(root: Path, rel: str, content: str) -> Path:
    p = root / "kg-source" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ── determinism + golden ────────────────────────────────────────────────────
def test_double_compile_byte_identical():
    a = kgc.render(kgc.compile_sources(SRC, exist_root=None))
    b = kgc.render(kgc.compile_sources(SRC, exist_root=None))
    assert a == b


def test_compile_matches_golden():
    rendered = kgc.render(kgc.compile_sources(SRC, exist_root=None))
    for name, text in rendered.items():
        assert text == (GOLDEN / name).read_text(encoding="utf-8"), f"{name} drifted from golden"
    # golden set and rendered set agree exactly
    assert set(rendered) == {p.name for p in GOLDEN.glob("*.yaml")}


def test_compile_is_path_independent(tmp_path):
    # Copy the fixture tree to a different location; output must be identical (cross-machine proxy).
    import shutil
    dst = tmp_path / "elsewhere" / "kg-source"
    shutil.copytree(SRC, dst)
    here = kgc.render(kgc.compile_sources(SRC, exist_root=None))
    there = kgc.render(kgc.compile_sources(dst, exist_root=None))
    assert here == there


def test_ontology_mirror_is_verbatim():
    rendered = kgc.render(kgc.compile_sources(SRC, exist_root=None))
    assert rendered["solution-ontology.yaml"] == (SRC / "ontology" / "solution-ontology.yaml").read_text(encoding="utf-8")


# ── projection semantics ─────────────────────────────────────────────────────
def test_logical_ref_resolved_in_projection():
    res = kgc.compile_sources(SRC, exist_root=None)
    cap = next(r for r in res.projections["canonical-nodes.yaml"]["capabilities"] if r["id"] == "capability:dashboard-home")
    assert "planning-mds/features/F0099-example/README.md" in cap["source_docs"]
    assert not any(d.startswith("F0099/") for d in cap["source_docs"])


def test_feature_mappings_excludes_presentation_fields():
    res = kgc.compile_sources(SRC, exist_root=None)
    feat = next(f for f in res.projections["feature-mappings.yaml"]["features"] if f["id"] == "feature:F0099")
    assert set(feat) <= {"id", "status", "path", "affects", "uses_schema", "governed_by",
                         "uses_api_contract", "depends_on", "supersedes", "superseded_by"}
    for presentation in ("name", "phase", "roadmap_section", "rationale", "archived_date", "completion_state"):
        assert presentation not in feat


def test_stories_expanded_with_feature_key():
    res = kgc.compile_sources(SRC, exist_root=None)
    stories = res.projections["feature-mappings.yaml"]["stories"]
    ids = {s["id"] for s in stories}
    assert {"story:F0099-S0001", "story:F0099-S0002"} <= ids
    for s in stories:
        assert s["feature"] == "feature:F0099"


# ── analysis ─────────────────────────────────────────────────────────────────
def test_duplicate_id_is_hard_error(tmp_path):
    write(tmp_path, "nodes/capabilities/a.yaml", "id: capability:x\nlabel: A\n")
    write(tmp_path, "nodes/capabilities/b.yaml", "id: capability:x\nlabel: B\n")
    res = kgc.compile_sources(tmp_path / "kg-source", exist_root=None)
    assert not res.ok
    assert any("duplicate id `capability:x`" in e for e in res.errors)


def test_name_similarity_advisory_then_strict(tmp_path):
    write(tmp_path, "nodes/capabilities/a.yaml", "id: capability:x\nlabel: Same Name\n")
    write(tmp_path, "nodes/capabilities/b.yaml", "id: capability:y\nlabel: Same Name\n")
    advisory = kgc.compile_sources(tmp_path / "kg-source", exist_root=None, strict=False)
    assert advisory.ok and any("name-similarity" in w for w in advisory.warnings)
    strict = kgc.compile_sources(tmp_path / "kg-source", exist_root=None, strict=True)
    assert not strict.ok and any("name-similarity" in e for e in strict.errors)


def test_binding_overlap_flagged(tmp_path):
    write(tmp_path, "nodes/capabilities/a.yaml", "id: capability:x\nlabel: X\n")
    write(tmp_path, "nodes/capabilities/y.yaml", "id: capability:y\nlabel: Y\n")
    write(tmp_path, "bindings/b.yaml",
          "node_bindings:\n"
          "  - id: capability:x\n    paths:\n      backend:\n        - engine/Shared.cs\n"
          "  - id: capability:y\n    paths:\n      backend:\n        - engine/Shared.cs\n")
    res = kgc.compile_sources(tmp_path / "kg-source", exist_root=None, strict=False)
    assert any("binding-overlap" in w and "engine/Shared.cs" in w for w in res.warnings)


def test_suppression_ledger_clears_finding(tmp_path):
    write(tmp_path, "nodes/capabilities/a.yaml", "id: capability:x\nlabel: Same Name\n")
    write(tmp_path, "nodes/capabilities/b.yaml", "id: capability:y\nlabel: Same Name\n")
    write(tmp_path, "exclusions/suppressions.yaml",
          "suppressions:\n  - kind: name-similarity\n    ids: [capability:x, capability:y]\n"
          "    rationale: Distinct concepts that share a display name.\n")
    # Suppressed even under --strict; recorded in `suppressed`, not errors/warnings.
    res = kgc.compile_sources(tmp_path / "kg-source", exist_root=None, strict=True)
    assert res.ok
    assert not any("name-similarity" in e for e in res.errors)
    assert any("name-similarity" in s and "Distinct concepts" in s for s in res.suppressed)


def test_suppression_without_rationale_does_not_suppress(tmp_path):
    write(tmp_path, "nodes/capabilities/a.yaml", "id: capability:x\nlabel: Same Name\n")
    write(tmp_path, "nodes/capabilities/b.yaml", "id: capability:y\nlabel: Same Name\n")
    write(tmp_path, "exclusions/suppressions.yaml",
          "suppressions:\n  - kind: name-similarity\n    ids: [capability:x, capability:y]\n")
    res = kgc.compile_sources(tmp_path / "kg-source", exist_root=None, strict=False)
    assert any("name-similarity" in w for w in res.warnings)


# ── --check + all-or-nothing ─────────────────────────────────────────────────
def test_check_detects_no_drift_and_drift(tmp_path):
    out = tmp_path / "kg"
    out.mkdir()
    res = kgc.compile_sources(SRC, exist_root=None)
    kgc.write_projections(res, out)
    assert kgc.check_projections(res, out) == []          # freshly written → no drift
    (out / "canonical-nodes.yaml").write_text("hand edit\n", encoding="utf-8")
    assert "canonical-nodes.yaml" in kgc.check_projections(res, out)


def test_all_or_nothing_writes_nothing_on_error(tmp_path):
    write(tmp_path, "nodes/capabilities/a.yaml", "id: capability:x\nlabel: A\n")
    write(tmp_path, "nodes/capabilities/b.yaml", "id: capability:x\nlabel: B\n")  # duplicate → error
    out = tmp_path / "kg"
    out.mkdir()
    rc = kgc.main(["--source", str(tmp_path / "kg-source"), "--out", str(out)])
    assert rc == 1
    assert list(out.iterdir()) == []  # nothing written


def test_empty_source_is_noop(tmp_path):
    (tmp_path / "kg-source").mkdir()
    (tmp_path / "kg-source" / "README.md").write_text("no shards yet\n", encoding="utf-8")
    out = tmp_path / "kg"
    out.mkdir()
    (out / "canonical-nodes.yaml").write_text("REAL GRAPH — must not be clobbered\n", encoding="utf-8")
    rc = kgc.main(["--source", str(tmp_path / "kg-source"), "--out", str(out)])
    assert rc == 0
    assert (out / "canonical-nodes.yaml").read_text(encoding="utf-8") == "REAL GRAPH — must not be clobbered\n"


def test_strip_generated_at(tmp_path):
    f = tmp_path / "decisions-index.yaml"
    f.write_text("version: 0\ngenerated_at: '2026-07-06T04:57:16+00:00'\nnodes: []\n", encoding="utf-8")
    kgc.strip_generated_at(f)
    text = f.read_text(encoding="utf-8")
    assert "generated_at" not in text
    assert "version: 0" in text and "nodes: []" in text
    kgc.strip_generated_at(f)  # idempotent
    assert "generated_at" not in f.read_text(encoding="utf-8")


# ── resolver matrix (F0005 acceptance), hermetic ─────────────────────────────
@pytest.fixture
def repo(tmp_path):
    (tmp_path / "planning-mds/features/F0007-live/docs").mkdir(parents=True)
    (tmp_path / "planning-mds/features/F0007-live/README.md").write_text("x", encoding="utf-8")
    (tmp_path / "planning-mds/features/archive/F0007-live/README.md").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "planning-mds/features/archive/F0007-live/README.md").write_text("x", encoding="utf-8")
    (tmp_path / "planning-mds/architecture").mkdir(parents=True)
    (tmp_path / "planning-mds/architecture/adr.md").write_text("x", encoding="utf-8")
    return tmp_path


def test_resolver_live(repo):
    fp = {"feature:F0007": "planning-mds/features/F0007-live"}
    assert resolve_doc_ref("F0007/README.md", fp, exist_root=repo) == "planning-mds/features/F0007-live/README.md"


def test_resolver_archive_flip(repo):
    # Same ref + shard content; only the feature path differs live↔archive; both resolve + exist.
    live = resolve_doc_ref("F0007/README.md", {"feature:F0007": "planning-mds/features/F0007-live"}, exist_root=repo)
    arch = resolve_doc_ref("F0007/README.md", {"feature:F0007": "planning-mds/features/archive/F0007-live"}, exist_root=repo)
    assert live == "planning-mds/features/F0007-live/README.md"
    assert arch == "planning-mds/features/archive/F0007-live/README.md"


def test_resolver_stable_root_passthrough(repo):
    assert resolve_doc_ref("planning-mds/architecture/adr.md", {}, exist_root=repo) == "planning-mds/architecture/adr.md"


def test_resolver_unknown_feature(repo):
    with pytest.raises(DocRefError, match="unknown feature"):
        resolve_doc_ref("F0404/README.md", {}, exist_root=repo)


def test_resolver_missing_file(repo):
    fp = {"feature:F0007": "planning-mds/features/F0007-live"}
    with pytest.raises(DocRefError, match="does not exist"):
        resolve_doc_ref("F0007/nope.md", fp, exist_root=repo)


def test_resolver_malformed_empty_remainder(repo):
    with pytest.raises(DocRefError, match="empty path"):
        resolve_doc_ref("F0007/", {"feature:F0007": "planning-mds/features/F0007-live"}, exist_root=repo)


def test_resolver_physical_feature_path_rejected(repo):
    with pytest.raises(DocRefError, match="physical feature-doc path"):
        resolve_doc_ref("planning-mds/features/F0007-live/README.md", {}, exist_root=repo)


def test_resolver_unrecognized(repo):
    with pytest.raises(DocRefError, match="unrecognized"):
        resolve_doc_ref("some/random/path.md", {}, exist_root=repo)

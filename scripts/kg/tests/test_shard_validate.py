"""Tests for shard_validate.py — kg-source shard schema + ownership contract (F0006-S0004)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "kg"))

import shard_validate  # noqa: E402
from shard_validate import (  # noqa: E402
    classify_directory,
    validate_paths,
    validate_shard_file,
)

FIXTURES = REPO_ROOT / "scripts" / "kg" / "tests" / "fixtures" / "kg-source"


def write_shard(tmp_path: Path, relpath: str, content: str) -> Path:
    """Create tmp_path/kg-source/<relpath> so the validator's directory classifier resolves it."""
    p = tmp_path / "kg-source" / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def errors_for(tmp_path: Path, relpath: str, content: str) -> list[str]:
    return validate_shard_file(write_shard(tmp_path, relpath, content)).errors


def assert_has(errors: list[str], needle: str) -> None:
    assert any(needle in e for e in errors), f"expected an error containing {needle!r}; got {errors}"


# 1 — happy path: the committed node + binding + feature fixtures all validate.
def test_valid_fixture_tree_passes():
    report = validate_paths([FIXTURES])
    assert report.ok, report.errors


def test_individual_valid_shards_pass(tmp_path):
    ok = errors_for(
        tmp_path,
        "nodes/capabilities/example.yaml",
        "id: capability:example\nlabel: Example\nrelated_nodes:\n  - entity:account\n",
    )
    assert ok == []


# 2 — kind ≠ directory.
def test_kind_directory_disagreement_fails(tmp_path):
    errs = errors_for(tmp_path, "nodes/entities/wrong.yaml", "id: capability:oops\nlabel: Oops\n")
    assert_has(errs, "grammar for directory 'nodes/entities'")


# 3 — physical feature-doc ref fails with the logical-form hint.
def test_physical_feature_docref_fails_with_hint(tmp_path):
    errs = errors_for(
        tmp_path,
        "nodes/capabilities/c.yaml",
        "id: capability:c\nlabel: C\nsource_docs:\n"
        "  - planning-mds/features/archive/F0035-session-continuity/F0035-S0004-auth.md\n",
    )
    assert_has(errs, "logical form")
    assert_has(errs, "F0035/")


# 4 — one-concept-per-file rule.
def test_bundle_in_one_per_file_dir_fails(tmp_path):
    errs = errors_for(
        tmp_path,
        "nodes/capabilities/two.yaml",
        "capabilities:\n  - id: capability:a\n    label: A\n  - id: capability:b\n    label: B\n",
    )
    assert_has(errs, "one concept per file")


def test_malformed_multi_key_file_fails(tmp_path):
    errs = errors_for(tmp_path, "nodes/entities/bad.yaml", "label: no id here\nnotes: stray\n")
    assert_has(errs, "single concept")


def test_bundle_allowed_in_thin_dir_passes(tmp_path):
    errs = errors_for(
        tmp_path,
        "nodes/endpoints/endpoints.yaml",
        "endpoints:\n  - id: endpoint:a\n    label: GET /a\n    method: GET\n    route: /a\n",
    )
    assert errs == []


# 5 — files outside a mapped directory.
def test_unmapped_directory_fails(tmp_path):
    errs = errors_for(tmp_path, "random/x.yaml", "id: capability:x\nlabel: X\n")
    assert_has(errs, "outside a mapped kg-source directory")


def test_unknown_node_kind_directory_fails(tmp_path):
    errs = errors_for(tmp_path, "nodes/widgets/x.yaml", "id: capability:x\nlabel: X\n")
    assert_has(errs, "outside a mapped kg-source directory")


# 6 — ID grammar (good + bad).
def test_bad_id_grammar_fails(tmp_path):
    errs = errors_for(tmp_path, "nodes/entities/e.yaml", "id: entity:Bad_Slug\nlabel: E\n")
    assert_has(errs, "grammar")


def test_api_contract_prefix_grammar(tmp_path):
    # api_contract kind uses the `api:` prefix, not `api_contract:`.
    good = errors_for(tmp_path, "nodes/api_contracts/rest.yaml", "id: api:nebula-rest\nlabel: REST\npath: planning-mds/api/nebula-api.yaml\n")
    assert good == []
    bad = errors_for(tmp_path, "nodes/api_contracts/bad.yaml", "id: api_contract:nebula\nlabel: REST\npath: planning-mds/api/nebula-api.yaml\n")
    assert_has(bad, "grammar")


# 7 — references are IDs only.
def test_reference_with_path_fails(tmp_path):
    errs = errors_for(
        tmp_path,
        "nodes/capabilities/c.yaml",
        "id: capability:c\nlabel: C\nrelated_nodes:\n  - planning-mds/features/F0001/README.md\n",
    )
    assert_has(errs, "never a path")


def test_reference_unknown_kind_fails(tmp_path):
    errs = errors_for(
        tmp_path,
        "nodes/capabilities/c.yaml",
        "id: capability:c\nlabel: C\nrelated_nodes:\n  - widget:foo\n",
    )
    assert_has(errs, "unknown reference kind")


# 8 — feature base-required fields still enforced; presentation conditional-requires relaxed (S0006).
def test_feature_missing_base_required_fails(tmp_path):
    # name + roadmap_section are base-required; a bare feature record fails.
    errs = errors_for(tmp_path, "features/F0100.yaml", "id: feature:F0100\nstatus: planned\n")
    assert any("name" in e for e in errs) and any("roadmap_section" in e for e in errs), errs


def test_feature_presentation_conditionals_relaxed(tmp_path):
    # S0006 relaxed the strict conditional-requires (rationale/retired_date/archived_date) because the
    # real graph has legitimate edge cases (superseded+archived, etc.). Completeness is enforced at
    # render time (S0007). These best-effort-populated shards validate.
    for name, body in (
        ("F0101", "status: in-progress\nphase: P\nroadmap_section: Now\n"),                  # no rationale
        ("F0102", "status: superseded\nroadmap_section: Abandoned\nsuperseded_by: feature:F0103\n"),  # no retired_date
        ("F0104", "status: archived-done\nphase: P\nroadmap_section: Completed\ncompletion_state: Done.\n"),  # no archived_date
    ):
        errs = errors_for(tmp_path, f"features/{name}.yaml",
                          f"id: feature:{name}\nname: Ex\npath: planning-mds/features/{name}-ex\n{body}")
        assert errs == [], (name, errs)


# 8b — feature story block (D3): valid stories pass; malformed story id / path-ref fail.
def test_feature_with_valid_stories_passes(tmp_path):
    errs = errors_for(
        tmp_path,
        "features/F0104.yaml",
        "id: feature:F0104\nname: Ex\npath: planning-mds/features/F0104-ex\n"
        "status: in-progress\nphase: P\nroadmap_section: Now\nrationale: why\n"
        "story_mappings:\n  - id: story:F0104-S0001\n    path: planning-mds/features/F0104-ex/s1.md\n"
        "    affects:\n      - capability:dashboard-home\n",
    )
    assert errs == []


def test_feature_bad_story_id_fails(tmp_path):
    errs = errors_for(
        tmp_path,
        "features/F0105.yaml",
        "id: feature:F0105\nname: Ex\npath: planning-mds/features/F0105-ex\n"
        "status: in-progress\nphase: P\nroadmap_section: Now\nrationale: why\n"
        "story_mappings:\n  - id: F0105-S0001\n    path: planning-mds/features/F0105-ex/s1.md\n",
    )
    assert errs, "expected a schema/grammar error for the malformed story id"


def test_feature_story_ref_must_be_id(tmp_path):
    errs = errors_for(
        tmp_path,
        "features/F0106.yaml",
        "id: feature:F0106\nname: Ex\npath: planning-mds/features/F0106-ex\n"
        "status: in-progress\nphase: P\nroadmap_section: Now\nrationale: why\n"
        "story_mappings:\n  - id: story:F0106-S0001\n    path: planning-mds/features/F0106-ex/s1.md\n"
        "    affects:\n      - planning-mds/features/x\n",
    )
    assert_has(errs, "never a path")


# 9 — unparseable YAML / missing id.
def test_unparseable_yaml_fails(tmp_path):
    errs = errors_for(tmp_path, "nodes/entities/broken.yaml", "id: entity:x\n  : : : bad\n- also")
    assert errs, "expected a parse error"


def test_record_missing_id_fails(tmp_path):
    errs = errors_for(
        tmp_path,
        "nodes/endpoints/endpoints.yaml",
        "endpoints:\n  - label: no id\n    method: GET\n    route: /a\n",
    )
    assert_has(errs, "missing a string `id`")


# 10 — binding globs syntactically valid.
def test_binding_invalid_glob_fails(tmp_path):
    errs = errors_for(
        tmp_path,
        "bindings/b.yaml",
        "id: capability:x\npaths:\n  backend:\n    - engine/[bad.cs\n",
    )
    assert_has(errs, "valid glob")


def test_binding_valid_paths_pass(tmp_path):
    errs = errors_for(
        tmp_path,
        "bindings/b.yaml",
        "id: capability:x\npaths:\n  backend:\n    - engine/src/Foo.cs\n  tests:\n    - engine/tests/*.cs\n",
    )
    assert errs == []


# 11 — ownership map covers every directory (each resolves to exactly one primary owner).
@pytest.mark.parametrize(
    "relpath,owner",
    [
        ("nodes/capabilities/x.yaml", "architect"),
        ("nodes/schemas/x.yaml", "architect"),
        ("policies/x.yaml", "architect"),
        ("bindings/x.yaml", "architect"),
        ("features/F0001.yaml", "product-manager"),
        ("exclusions/x.yaml", "product-manager"),
        ("ontology/solution-ontology.yaml", "architect"),
    ],
)
def test_every_directory_resolves_to_one_owner(tmp_path, relpath, owner):
    dc = classify_directory(write_shard(tmp_path, relpath, "id: x\n"))
    assert dc is not None and dc.owner == owner


def test_cosign_encoded_on_primary_scope(tmp_path):
    pol = classify_directory(write_shard(tmp_path, "policies/x.yaml", "id: x\n"))
    exc = classify_directory(write_shard(tmp_path, "exclusions/x.yaml", "id: x\n"))
    ont = classify_directory(write_shard(tmp_path, "ontology/x.yaml", "id: x\n"))
    assert "security" in pol.cosign
    assert "architect" in exc.cosign
    assert "product-manager" in ont.cosign


def test_unmapped_directory_has_no_owner(tmp_path):
    assert classify_directory(write_shard(tmp_path, "random/x.yaml", "id: x\n")) is None

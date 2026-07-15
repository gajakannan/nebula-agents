from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "kg"))

import lookup  # noqa: E402
from kg_common import load_bundle  # noqa: E402


@pytest.fixture(scope="module")
def bundle() -> dict[str, object]:
    return load_bundle()


def _lookup_target(
    bundle: dict[str, object],
    *,
    tier: int,
    fields: str = "full",
    target: str = "F0001",
    allow_missing: bool = False,
) -> dict[str, object]:
    return lookup.lookup_by_target(
        target,
        bundle,
        tier=tier,
        fields=fields,
        allow_missing=allow_missing,
    )


def _find_node(entries: list[dict[str, object]], node_id: str) -> dict[str, object]:
    return next(entry for entry in entries if entry["id"] == node_id)


def test_tier_1_returns_ids_and_labels_only(bundle: dict[str, object]) -> None:
    payload = _lookup_target(bundle, tier=1)

    capability = _find_node(payload["affects"], "capability:local-run-registry")
    assert capability == {
        "id": "capability:local-run-registry",
        "label": "Local run registry",
    }

    schema = _find_node(payload["uses_schema"], "schema:f0001-run-record")
    assert schema == {"id": "schema:f0001-run-record", "label": "F0001 run record"}


def test_tier_2_adds_summary_without_source_docs(bundle: dict[str, object]) -> None:
    payload = _lookup_target(bundle, tier=2)

    capability = _find_node(payload["affects"], "capability:local-run-registry")
    assert "notes" in capability
    assert "source_docs" not in capability


def test_tier_3_adds_source_docs_without_reading_file_contents(bundle: dict[str, object]) -> None:
    payload = _lookup_target(bundle, tier=3)

    capability = _find_node(payload["affects"], "capability:local-run-registry")
    assert capability["source_docs"] == [
        "planning-mds/architecture/decisions/ADR-002-f0001-runtime-persistence.md",
        "planning-mds/features/F0001-tmux-native-agent-cockpit/F0001-S0003-run-registry-and-evidence-watchers.md",
    ]
    assert all(isinstance(path, str) and "/" in path for path in capability["source_docs"])
    assert "Persists typed run state" not in capability["source_docs"][0]


def test_tier_4_matches_prechange_behavior(bundle: dict[str, object]) -> None:
    scope = lookup.feature_or_story_by_id("feature:F0001", bundle["mappings"])
    assert scope is not None
    scope["_kind"] = "feature"

    expected = lookup.build_scope_payload(scope, bundle)
    actual = _lookup_target(bundle, tier=4)
    assert actual == expected


def test_allow_missing_returns_unmapped_payload() -> None:
    result = subprocess.run(
        ["python3", "scripts/kg/lookup.py", "F9999", "--allow-missing"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "feature_id": "F9999",
        "scope": None,
        "reason": "unmapped",
        "hints": [
            "Feature has no mapping in feature-mappings.yaml; proceed file-centric; seed stub before Phase B"
        ],
    }


def test_allow_missing_unset_preserves_legacy_error() -> None:
    result = subprocess.run(
        ["python3", "scripts/kg/lookup.py", "F9999"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Unknown target: F9999" in result.stderr


def test_untested_lookup_is_node_scoped(bundle: dict[str, object]) -> None:
    symbols_by_id = bundle["symbols_by_id"]
    target_node = next(
        sym["node"]
        for sym in symbols_by_id.values()
        if sym.get("kind") in {"method", "function"}
        and sym.get("visibility") in {None, "public", "internal", "export"}
        and not sym.get("is_test")
        and not any(
            symbols_by_id.get(caller_id, {}).get("is_test")
            for caller_id in sym.get("callers", []) or []
        )
    )

    payload = lookup.lookup_untested(target_node, bundle)

    assert payload is not None
    assert payload["query"] == {"kind": "untested", "node": target_node}
    assert payload["untested_count"] == len(payload["untested"])
    assert payload["untested_count"] >= 1
    assert {entry["node"] for entry in payload["untested"]} == {target_node}


def test_fields_ids_strip_rationale_and_source_docs(bundle: dict[str, object]) -> None:
    payload = _lookup_target(bundle, tier=3, fields="ids")

    capability = _find_node(payload["affects"], "capability:local-run-registry")
    assert capability == {
        "id": "capability:local-run-registry",
        "label": "Local run registry",
    }


def test_hint_emission_fires_on_ambiguous_fixture(
    bundle: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_scope = {
        "id": "feature:F9998",
        "path": "planning-mds/features/F9998-fixture",
        "status": "draft",
        "affects": [
            {
                "id": "entity:submission",
                "provenance": "ambiguous",
            }
        ],
    }

    monkeypatch.setattr(
        lookup,
        "feature_or_story_by_id",
        lambda normalized, mappings: dict(fixture_scope) if normalized == "feature:F9998" else None,
    )

    payload = lookup.lookup_by_target(
        "F9998",
        bundle,
        tier=1,
        fields="full",
        allow_missing=False,
    )

    assert payload["hints"] == [
        "1 ambiguous nodes detected (entity:submission) -- consider --tier 3 or open source_docs directly"
    ]

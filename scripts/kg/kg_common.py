#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import json
import math
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "PyYAML is required for scripts/kg tooling. Install it with `pip install pyyaml`."
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[2]
KG_DIR = REPO_ROOT / "planning-mds" / "knowledge-graph"
FEATURES_DIR = REPO_ROOT / "planning-mds" / "features"
DEFAULT_TELEMETRY_PATH = REPO_ROOT / ".kg-state" / "telemetry.jsonl"
_DEFAULT_RUN_ID: str | None = None
WILDCARD_RE = re.compile(r"[*?\[]")
FEATURE_ID_RE = re.compile(r"^feature:F\d{4}$")
STORY_ID_RE = re.compile(r"^story:F\d{4}-S\d{4}$")
BARE_FEATURE_ID_RE = re.compile(r"^F\d{4}$")
BARE_STORY_ID_RE = re.compile(r"^F\d{4}-S\d{4}$")

SECTION_TYPES = {
    "entities": "entity",
    "glossary_terms": "glossary_term",
    "workflows": "workflow",
    "capabilities": "capability",
    "endpoints": "endpoint",
    "ui_routes": "ui_route",
    "events": "event",
    "config_keys": "config_key",
    "migrations": "migration",
    "roles": "role",
    "policy_rules": "policy_rule",
    "evidence": "evidence",
    "adrs": "adr",
    "schemas": "schema",
    "api_contracts": "api_contract",
}

REF_FIELDS = (
    "affects",
    "governed_by",
    "uses_schema",
    "uses_api_contract",
    "depends_on",
    "restricted_to_role",
    "enforced_by_policy",
    "workflow_states",
    "validated_by",
    "supersedes",
)

VALID_PROVENANCE = {"extracted", "inferred", "ambiguous"}
TELEMETRY_ENV_VARS = {
    "action": "NEBULA_ACTION",
    "feature_id": "NEBULA_FEATURE_ID",
    "mode": "NEBULA_MODE",
    "gate": "NEBULA_GATE",
    "topic": "NEBULA_TOPIC",
    "source": "NEBULA_SOURCE",  # e.g. "mcp" — set by the MCP server so eval.py can split MCP vs CLI
}


def edge_ref_id(ref: str | dict[str, Any]) -> str:
    """Extract the node ID from an edge reference (bare string or object)."""
    if isinstance(ref, str):
        return ref
    return ref["id"]


def edge_ref_provenance(ref: str | dict[str, Any]) -> dict[str, Any] | None:
    """Extract provenance info from an edge reference, or None if bare string."""
    if isinstance(ref, str):
        return None
    prov = ref.get("provenance")
    if prov is None:
        return None
    result: dict[str, Any] = {"provenance": prov}
    if prov == "inferred":
        result["confidence"] = ref.get("confidence", 0.5)
    return result


def edge_ref_ids(refs: list[Any]) -> list[str]:
    """Extract node IDs from a list of edge references (bare strings or objects)."""
    return [edge_ref_id(r) for r in refs]


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing required file: {repo_relative(path)}") from exc
    except yaml.YAMLError as exc:
        raise SystemExit(f"Failed to parse YAML: {repo_relative(path)}: {exc}") from exc

    return data or {}


def repo_relative(path: Path | str) -> str:
    resolved = Path(path)
    if resolved.is_absolute():
        resolved = resolved.resolve()
        try:
            resolved = resolved.relative_to(REPO_ROOT)
        except ValueError:
            return resolved.as_posix()
    return resolved.as_posix()


def normalize_repo_path(path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        candidate = candidate.resolve()
        try:
            candidate = candidate.relative_to(REPO_ROOT)
        except ValueError:
            return candidate.as_posix()
    return candidate.as_posix()


def has_wildcards(pattern: str) -> bool:
    return bool(WILDCARD_RE.search(pattern))


def expand_declared_pattern(pattern: str) -> list[str]:
    normalized = normalize_repo_path(pattern)
    if has_wildcards(normalized):
        return sorted(
            repo_relative(path)
            for path in REPO_ROOT.glob(normalized)
            if path.exists()
        )

    candidate = REPO_ROOT / normalized
    return [normalized] if candidate.exists() else []


def normalize_target_id(target: str) -> str:
    stripped = target.strip()
    if BARE_FEATURE_ID_RE.fullmatch(stripped):
        return f"feature:{stripped}"
    if BARE_STORY_ID_RE.fullmatch(stripped):
        return f"story:{stripped}"
    return stripped


def build_bundle(
    ontology: Mapping[str, Any],
    canonical: Mapping[str, Any],
    mappings: Mapping[str, Any],
    code_index: Mapping[str, Any],
    symbols: Mapping[str, Any] | None = None,
    decisions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_nodes = flatten_canonical_nodes(canonical)
    mapping_nodes = flatten_mapping_nodes(mappings)
    all_nodes = {**canonical_nodes, **mapping_nodes}
    bindings = build_binding_index(code_index)
    symbol_indexes = build_symbol_indexes(symbols or {})
    decision_indexes = build_decision_indexes(decisions or {})

    return {
        "ontology": dict(ontology),
        "canonical": dict(canonical),
        "mappings": dict(mappings),
        "code_index": dict(code_index),
        "canonical_nodes": canonical_nodes,
        "mapping_nodes": mapping_nodes,
        "all_nodes": all_nodes,
        "bindings": bindings,
        "symbols": dict(symbols or {}),
        "symbols_by_id": symbol_indexes["by_id"],
        "symbols_by_node": symbol_indexes["by_node"],
        "symbols_by_name": symbol_indexes["by_name"],
        "symbols_by_file": symbol_indexes["by_file"],
        "decisions": dict(decisions or {}),
        "decisions_by_file": decision_indexes["by_file"],
        "decisions_by_symbol": decision_indexes["by_symbol"],
        "decisions_by_node": decision_indexes["by_node"],
    }


def load_bundle() -> dict[str, Any]:
    ontology = load_yaml(KG_DIR / "solution-ontology.yaml")
    canonical = load_yaml(KG_DIR / "canonical-nodes.yaml")
    mappings = load_yaml(KG_DIR / "feature-mappings.yaml")
    code_index = load_yaml(KG_DIR / "code-index.yaml")
    symbols_path = KG_DIR / "symbol-index.yaml"
    symbols = load_yaml(symbols_path) if symbols_path.exists() else {}
    decisions_path = KG_DIR / "decisions-index.yaml"
    decisions = load_yaml(decisions_path) if decisions_path.exists() else {}
    return build_bundle(ontology, canonical, mappings, code_index, symbols, decisions)


def build_symbol_indexes(symbols: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Build flat lookup indexes over the symbol layer.

    The returned dict has four indexes:
    - by_id: {symbol_id -> symbol dict}
    - by_node: {canonical_node_id -> [symbol dicts]}
    - by_name: {symbol_name -> [symbol dicts]}
    - by_file: {repo_relative_path -> [symbol dicts]}
    """
    by_id: dict[str, dict[str, Any]] = {}
    by_node: dict[str, list[dict[str, Any]]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    by_file: dict[str, list[dict[str, Any]]] = {}

    for entry in symbols.get("symbols", []) or []:
        sid = entry.get("id")
        if not sid:
            continue
        by_id[sid] = entry
        node = entry.get("node")
        if node:
            by_node.setdefault(node, []).append(entry)
        name = entry.get("name")
        if name:
            by_name.setdefault(name, []).append(entry)
        file_rel = entry.get("file")
        if file_rel:
            by_file.setdefault(file_rel, []).append(entry)

    return {
        "by_id": by_id,
        "by_node": by_node,
        "by_name": by_name,
        "by_file": by_file,
    }


def build_decision_indexes(decisions: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Build lookup indexes over inline decision markers."""
    by_file: dict[str, list[dict[str, Any]]] = {}
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    by_node: dict[str, list[dict[str, Any]]] = {}

    for entry in decisions.get("decisions", []) or []:
        file_rel = entry.get("file")
        if file_rel:
            by_file.setdefault(file_rel, []).append(entry)
        symbol_id = entry.get("resolved_symbol")
        if symbol_id:
            by_symbol.setdefault(symbol_id, []).append(entry)
        node_id = entry.get("resolved_node")
        if node_id:
            by_node.setdefault(node_id, []).append(entry)

    for index in (by_file, by_symbol, by_node):
        for values in index.values():
            values.sort(key=lambda item: (item.get("file", ""), item.get("line", 0)))

    return {
        "by_file": by_file,
        "by_symbol": by_symbol,
        "by_node": by_node,
    }


def match_symbols_for_node(
    node_id: str, bundle: Mapping[str, Any]
) -> list[dict[str, Any]]:
    return list(bundle.get("symbols_by_node", {}).get(node_id, []))


def match_symbols_for_path(
    path: str, bundle: Mapping[str, Any]
) -> list[dict[str, Any]]:
    normalized = normalize_repo_path(path)
    return list(bundle.get("symbols_by_file", {}).get(normalized, []))


def match_symbol_by_name(
    name: str, bundle: Mapping[str, Any], node_id: str | None = None
) -> list[dict[str, Any]]:
    matches = list(bundle.get("symbols_by_name", {}).get(name, []))
    if node_id:
        matches = [m for m in matches if m.get("node") == node_id]
    return matches


def get_symbol_by_id(
    symbol_id: str, bundle: Mapping[str, Any]
) -> dict[str, Any] | None:
    return bundle.get("symbols_by_id", {}).get(symbol_id)


def match_decisions_for_path(
    path: str, bundle: Mapping[str, Any]
) -> list[dict[str, Any]]:
    normalized = normalize_repo_path(path)
    return list(bundle.get("decisions_by_file", {}).get(normalized, []))


def match_decisions_for_symbol(
    symbol_id: str, bundle: Mapping[str, Any]
) -> list[dict[str, Any]]:
    return list(bundle.get("decisions_by_symbol", {}).get(symbol_id, []))


def match_decisions_for_node(
    node_id: str, bundle: Mapping[str, Any]
) -> list[dict[str, Any]]:
    return list(bundle.get("decisions_by_node", {}).get(node_id, []))


def flatten_canonical_nodes(canonical: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}

    for section, node_type in SECTION_TYPES.items():
        for item in canonical.get(section, []):
            node = dict(item)
            node["_kind"] = node_type
            nodes[node["id"]] = node

            if section == "workflows":
                for state in item.get("states", []):
                    state_node = dict(state)
                    state_node["_kind"] = "workflow_state"
                    state_node["belongs_to_workflow"] = item["id"]
                    nodes[state_node["id"]] = state_node

    return nodes


def flatten_mapping_nodes(mappings: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}

    for item in mappings.get("features", []):
        node = dict(item)
        node["_kind"] = "feature"
        nodes[node["id"]] = node

    for item in mappings.get("coverage", {}).get("excluded_features", []):
        node = dict(item)
        node["_kind"] = "feature"
        node["excluded"] = True
        nodes[node["id"]] = node

    for item in mappings.get("stories", []):
        node = dict(item)
        node["_kind"] = "story"
        nodes[node["id"]] = node

    return nodes


def _collect_patterns(value: Any, labels: list[str] | None = None) -> list[dict[str, str]]:
    labels = labels or []
    collected: list[dict[str, str]] = []

    if isinstance(value, str):
        collected.append(
            {
                "bucket": ".".join(labels) if labels else "paths",
                "pattern": normalize_repo_path(value),
            }
        )
        return collected

    if isinstance(value, list):
        for item in value:
            collected.extend(_collect_patterns(item, labels))
        return collected

    if isinstance(value, dict):
        for key, child in value.items():
            collected.extend(_collect_patterns(child, [*labels, key]))
        return collected

    return collected


def build_binding_index(code_index: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    bindings: dict[str, dict[str, Any]] = {}

    for entry in code_index.get("node_bindings", []):
        binding = dict(entry)
        binding["declared_paths"] = _collect_patterns(binding.get("paths", {}))
        bindings[binding["id"]] = binding

    return bindings


def resolve_node(node_id: str, bundle: Mapping[str, Any]) -> dict[str, Any] | None:
    node = bundle["all_nodes"].get(node_id)
    if node is None:
        return None

    resolved = dict(node)
    binding = bundle["bindings"].get(node_id)
    if binding:
        resolved["code_paths"] = binding.get("paths", {})
    return resolved


def resolve_refs(ref_ids: Iterable[str], bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for ref_id in ref_ids:
        node = resolve_node(ref_id, bundle)
        if node is not None:
            resolved.append(node)
    return resolved


# ---------------------------------------------------------------------------
# Logical feature-doc references (F0006-S0005 / absorbs F0005)
# ---------------------------------------------------------------------------
# A shard authors doc refs move-invariantly: `F####/rel/path.md` resolves through
# the owning feature shard's `path:` at compile time, so archiving a feature (one
# `path:` edit) repoints every ref with zero shard changes. Stable-root refs (docs
# that do not move with a feature) pass through physical.

LOGICAL_DOC_REF_RE = re.compile(r"^F(\d{4})/(.*)$")
STABLE_ROOT_PREFIXES: tuple[str, ...] = (
    "planning-mds/architecture/",
    "planning-mds/api/",
    "planning-mds/schemas/",
    "planning-mds/security/",
    "planning-mds/domain/",
    "engine/",
    "experience/",
)


class DocRefError(ValueError):
    """A shard doc ref could not be resolved (unknown feature, missing file, or malformed)."""


def resolve_doc_ref(
    ref: str,
    feature_paths: Mapping[str, str],
    *,
    exist_root: Path | None = REPO_ROOT,
) -> str:
    """Resolve a shard doc ref to a physical repo-relative path.

    - ``F####/rel`` → ``<feature path>/rel`` (feature path from ``feature_paths``,
      keyed by ``feature:F####``); existence-checked under ``exist_root`` when given.
    - a stable-root physical ref → returned unchanged (validated to exist when a root is given).
    - anything else (physical ``planning-mds/features/…`` path, unknown feature, empty
      remainder, missing file) → :class:`DocRefError`.
    """
    if not isinstance(ref, str) or not ref:
        raise DocRefError(f"doc ref must be a non-empty string, got {ref!r}")

    m = LOGICAL_DOC_REF_RE.match(ref)
    if m:
        remainder = m.group(2).strip()
        if not remainder:
            raise DocRefError(f"malformed logical ref '{ref}': empty path after F{m.group(1)}/")
        feature_id = f"feature:F{m.group(1)}"
        base = feature_paths.get(feature_id)
        if base is None:
            raise DocRefError(f"logical ref '{ref}' names unknown feature {feature_id}")
        resolved = f"{base.rstrip('/')}/{remainder}"
        if exist_root is not None and not (exist_root / resolved).exists():
            raise DocRefError(f"logical ref '{ref}' resolves to '{resolved}', which does not exist")
        return resolved

    if ref.startswith("planning-mds/features/"):
        raise DocRefError(
            f"physical feature-doc path '{ref}' is not allowed in a shard; use the logical "
            f"`F####/rel` form so archive moves need no shard edit"
        )

    if ref.startswith(STABLE_ROOT_PREFIXES):
        if exist_root is not None and not (exist_root / ref).exists():
            raise DocRefError(f"stable-root ref '{ref}' does not exist")
        return ref

    raise DocRefError(
        f"unrecognized doc ref '{ref}': expected a logical `F####/rel` ref or a stable-root path "
        f"({', '.join(STABLE_ROOT_PREFIXES)})"
    )


def iter_feature_dirs() -> list[str]:
    feature_dirs: list[str] = []
    for path in sorted(FEATURES_DIR.glob("*")):
        if path.is_dir() and path.name != "archive":
            feature_dirs.append(repo_relative(path))

    archive_dir = FEATURES_DIR / "archive"
    if archive_dir.exists():
        for path in sorted(archive_dir.glob("*")):
            if path.is_dir():
                feature_dirs.append(repo_relative(path))

    return feature_dirs


def excluded_feature_paths(mappings: Mapping[str, Any]) -> set[str]:
    coverage = mappings.get("coverage", {})
    return {
        normalize_repo_path(item["path"])
        for item in coverage.get("excluded_features", [])
        if item.get("path")
    }


def match_bindings_for_path(path: str, bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    normalized = normalize_repo_path(path)
    matches: list[dict[str, Any]] = []

    for binding in bundle["bindings"].values():
        matched = [
            entry
            for entry in binding.get("declared_paths", [])
            if fnmatch.fnmatch(normalized, entry["pattern"])
        ]
        if matched:
            entry = dict(binding)
            entry["matched_patterns"] = matched
            matches.append(entry)

    return sorted(matches, key=lambda item: item["id"])


def collect_referenced_node_ids(bundle: Mapping[str, Any]) -> set[str]:
    """Set of canonical node ids that any other artifact references.

    Counts every outgoing reference channel: feature/story REF_FIELDS edges,
    `feature` parent on stories, canonical `related_nodes`/`allowed_roles`,
    `rationale.adr` entries, and workflow-state `transitions_to`. Excluded
    coverage entries are not crawled — an excluded feature should not pin
    canonical nodes to "referenced" status.
    """
    canonical = bundle["canonical"]
    mappings = bundle["mappings"]

    referenced: set[str] = set()

    for section_name in ("features", "stories"):
        for item in mappings.get(section_name, []):
            for field in REF_FIELDS:
                referenced.update(edge_ref_ids(item.get(field, [])))
            feature_ref = item.get("feature")
            if feature_ref:
                referenced.add(feature_ref)

    for section in SECTION_TYPES:
        for item in canonical.get(section, []):
            referenced.update(item.get("related_nodes", []))
            referenced.update(item.get("allowed_roles", []))
            for rationale in item.get("rationale", []):
                if isinstance(rationale, dict) and rationale.get("adr"):
                    referenced.add(rationale["adr"])
            if section == "workflows":
                for state in item.get("states", []):
                    referenced.update(state.get("transitions_to", []))

    return referenced


def related_mapping_entries(
    node_ids: Iterable[str],
    mappings: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    wanted = set(node_ids)
    features: list[dict[str, Any]] = []
    stories: list[dict[str, Any]] = []

    for item in mappings.get("features", []):
        refs = set()
        for field in REF_FIELDS:
            refs.update(edge_ref_ids(item.get(field, [])))
        if refs.intersection(wanted):
            features.append(dict(item))

    for item in mappings.get("stories", []):
        refs = {item.get("feature")} if item.get("feature") else set()
        for field in REF_FIELDS:
            refs.update(edge_ref_ids(item.get(field, [])))
        if refs.intersection(wanted):
            stories.append(dict(item))

    features.sort(key=lambda item: item["id"])
    stories.sort(key=lambda item: item["id"])
    return features, stories


def planning_scope_for_path(path: str, mappings: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_repo_path(path)

    for story in mappings.get("stories", []):
        if normalize_repo_path(story.get("path", "")) == normalized:
            return {"story": dict(story)}

    for feature in mappings.get("features", []):
        feature_path = normalize_repo_path(feature.get("path", ""))
        if normalized == feature_path or normalized.startswith(f"{feature_path}/"):
            return {"feature": dict(feature)}

    return {}


def feature_or_story_by_id(target_id: str, mappings: Mapping[str, Any]) -> dict[str, Any] | None:
    if FEATURE_ID_RE.fullmatch(target_id):
        for item in mappings.get("features", []):
            if item["id"] == target_id:
                return dict(item)
    if STORY_ID_RE.fullmatch(target_id):
        for item in mappings.get("stories", []):
            if item["id"] == target_id:
                return dict(item)
    return None


def id_patterns_by_type(ontology: Mapping[str, Any]) -> dict[str, str]:
    return {
        item["type"]: item["pattern"]
        for item in ontology.get("id_patterns", [])
        if item.get("type") and item.get("pattern")
    }


def type_regex_map() -> dict[str, re.Pattern[str]]:
    slug = r"[a-z0-9]+(?:-[a-z0-9]+)*"
    return {
        "entity": re.compile(rf"^entity:{slug}$"),
        "workflow": re.compile(rf"^workflow:{slug}$"),
        "workflow_state": re.compile(rf"^state:{slug}:{slug}$"),
        "schema": re.compile(rf"^schema:{slug}$"),
        "capability": re.compile(rf"^capability:{slug}$"),
        "role": re.compile(rf"^role:{slug}$"),
        "policy_rule": re.compile(rf"^policy_rule:{slug}$"),
        "api_contract": re.compile(rf"^api:{slug}$"),
        "adr": re.compile(rf"^adr:[a-z0-9]+(?:-[a-z0-9]+)*$"),
        "feature": re.compile(r"^feature:F\d{4}$"),
        "story": re.compile(r"^story:F\d{4}-S\d{4}$"),
    }


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def telemetry_context_from_env() -> dict[str, str | None]:
    """Read the shared Nebula telemetry context from environment variables.

    Supported environment variables:
    - NEBULA_ACTION
    - NEBULA_FEATURE_ID
    - NEBULA_MODE
    - NEBULA_GATE
    - NEBULA_TOPIC
    """
    return {
        field: os.getenv(env_name) or None
        for field, env_name in TELEMETRY_ENV_VARS.items()
    }


def estimate_tokens(value: Any) -> int:
    """Best-effort token estimate for telemetry budgeting.

    This intentionally stays lightweight and deterministic so CLIs can emit
    comparable telemetry without depending on a tokenizer package.
    """
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return max(1, math.ceil(len(serialized) / 4))


def _default_run_id() -> str:
    global _DEFAULT_RUN_ID
    if _DEFAULT_RUN_ID is None:
        _DEFAULT_RUN_ID = str(uuid.uuid4())
    return _DEFAULT_RUN_ID


def emit_telemetry(
    telemetry_file: Path | None,
    run_id: str | None,
    tool: str,
    event: dict[str, Any],
) -> None:
    """Append a single JSONL telemetry event.

    When `telemetry_file` is None, the event is written to the repo-default
    path `{REPO_ROOT}/.kg-state/telemetry.jsonl`. When `run_id` is None, a
    per-process uuid4 is generated and reused so all events from one script
    invocation share a correlation ID.
    """
    used_default_path = telemetry_file is None
    if used_default_path:
        telemetry_file = DEFAULT_TELEMETRY_PATH
    if run_id is None:
        run_id = _default_run_id()

    payload = {
        "ts": now_iso(),
        "run_id": run_id,
        "tool": tool,
        **telemetry_context_from_env(),
        "payload": event,
    }

    try:
        telemetry_file.parent.mkdir(parents=True, exist_ok=True)
        with telemetry_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
            handle.flush()
    except OSError:
        # Telemetry must never crash a caller. Errors on the default path are
        # silently dropped (e.g., read-only checkout); errors on an explicit
        # path bubble up so the caller sees the misconfiguration.
        if not used_default_path:
            raise


def main_exception(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


# ──────────────────────────────────────────────────────────────
# Canonical serialization (F0006-S0001)
#
# One serializer for the curated KG files so that two semantically
# identical documents are byte-identical on disk. merge3.py compares and
# emits canonical form; the Phase-B compiler reuses the same functions.
# ──────────────────────────────────────────────────────────────

# Keys emitted first, in this order, on every mapping; remaining keys follow
# alphabetically. A single global list keeps ordering decidable without
# per-file schemas.
CANONICAL_KEY_PRIORITY: tuple[str, ...] = (
    "version",
    "status",
    "coverage_note",
    "id",
    "label",
    "name",
    "title",
    "feature",
    "path",
    "kind",
    "reason",
)

# List fields whose element order is semantic. They are never sorted at
# canonicalization, and merge3 refuses to auto-merge divergent reorders.
# Every other list is set-like: canonicalization sorts (and de-duplicates
# scalars); merge3 unions.
ORDERED_LIST_FIELDS: frozenset[str] = frozenset({"states", "transitions_to", "rules"})

# Generated projections — never merge inputs, never canonicalization targets.
GENERATED_KG_BASENAMES: frozenset[str] = frozenset(
    {
        "symbol-index.yaml",
        "coverage-report.yaml",
        "unbound-but-referenced.yaml",
        "decisions-index.yaml",
    }
)


def is_record_list(value: Any) -> bool:
    """A non-empty list whose every element is a mapping carrying an `id`."""
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, dict) and "id" in item for item in value)
    )


def _is_scalar_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        item is None or isinstance(item, (str, int, float, bool)) for item in value
    )


def scalar_sort_key(value: Any) -> tuple[str, str]:
    return (type(value).__name__, str(value))


def _ordered_keys(mapping: Mapping[str, Any]) -> list[str]:
    priority = [key for key in CANONICAL_KEY_PRIORITY if key in mapping]
    rest = sorted(key for key in mapping if key not in CANONICAL_KEY_PRIORITY)
    return [*priority, *rest]


def canonicalize_document(value: Any, field: str | None = None) -> Any:
    """Return a semantically equal copy in canonical structural form.

    Canonical form: mapping keys priority-then-alphabetical; record lists
    sorted by `id`; scalar lists de-duplicated and sorted — except fields in
    ORDERED_LIST_FIELDS, which keep authored order. Idempotent:
    canonicalize(canonicalize(x)) == canonicalize(x).
    """
    if isinstance(value, dict):
        return {
            key: canonicalize_document(value[key], field=key)
            for key in _ordered_keys(value)
        }
    if isinstance(value, list):
        items = [canonicalize_document(item, field=field) for item in value]
        if field in ORDERED_LIST_FIELDS:
            return items
        if is_record_list(value):
            return sorted(items, key=lambda item: str(item["id"]))
        if _is_scalar_list(value):
            deduped = list(dict.fromkeys(items))
            return sorted(deduped, key=scalar_sort_key)
        return items
    return value


class _CanonicalDumper(yaml.SafeDumper):
    """SafeDumper with block-sequence indentation matching the curated files."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):  # noqa: FBT001, FBT002
        return super().increase_indent(flow, False)


def canonical_dump(data: Any) -> str:
    """Serialize to the canonical YAML byte form (stable across machines)."""
    return yaml.dump(
        canonicalize_document(data),
        Dumper=_CanonicalDumper,
        sort_keys=False,
        allow_unicode=True,
        width=100,
        default_flow_style=False,
    )


def canonical_equal(a: Any, b: Any) -> bool:
    """Semantic equality: equal after canonicalization."""
    return canonicalize_document(a) == canonicalize_document(b)

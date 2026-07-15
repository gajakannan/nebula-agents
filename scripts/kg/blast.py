#!/usr/bin/env python3
"""Compute blast radius for a file path or canonical node ID.

Given a starting point (repo file, ontology node, or feature/story), walk
the knowledge graph to enumerate all impacted surfaces: features, stories,
code bindings, Casbin policy rules, endpoints, UI routes, and migrations.

Usage:
    python3 scripts/kg/blast.py entity:submission
    python3 scripts/kg/blast.py --file engine/src/Nebula.Domain/Entities/Submission.cs
    python3 scripts/kg/blast.py F0007
    python3 scripts/kg/blast.py entity:renewal --compact
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from kg_common import (
    REF_FIELDS,
    edge_ref_id,
    edge_ref_ids,
    edge_ref_provenance,
    emit_telemetry,
    estimate_tokens,
    expand_declared_pattern,
    get_symbol_by_id,
    load_bundle,
    match_bindings_for_path,
    match_symbol_by_name,
    match_symbols_for_node,
    normalize_target_id,
    related_mapping_entries,
    repo_relative,
)

LOW_CONFIDENCE_THRESHOLD = 0.5


def node_ids_for_file(path: str, bundle: dict[str, Any]) -> set[str]:
    """Find all canonical node IDs bound to a file path via code-index."""
    return {m["id"] for m in match_bindings_for_path(path, bundle)}


def canonical_refs_from_mapping(node: dict[str, Any]) -> set[str]:
    """For a feature/story node, gather all canonical node IDs it references."""
    refs: set[str] = set()
    for field in REF_FIELDS:
        refs.update(edge_ref_ids(node.get(field, [])))
    return refs


def classify_mapping_edges(node: dict[str, Any]) -> tuple[str, int]:
    """Inspect edge provenance on a feature/story node.

    Returns (confidence_band, ambiguous_count) using the same vocabulary as
    scripts/kg/lookup.py so telemetry stays comparable across tools.
    """
    ambiguous_ids: set[str] = set()
    low = False
    medium = False
    for field in REF_FIELDS:
        for ref in node.get(field, []):
            prov = edge_ref_provenance(ref)
            if prov is None:
                continue
            provenance = prov.get("provenance")
            confidence = prov.get("confidence")
            if provenance == "ambiguous":
                ambiguous_ids.add(edge_ref_id(ref))
            elif provenance == "inferred":
                if isinstance(confidence, (int, float)) and confidence < LOW_CONFIDENCE_THRESHOLD:
                    low = True
                else:
                    medium = True
    if ambiguous_ids:
        return "ambiguous", len(ambiguous_ids)
    if low:
        return "low", 0
    if medium:
        return "medium", 0
    return "high", 0


def one_hop_neighbors(node_id: str, bundle: dict[str, Any]) -> set[str]:
    """Collect node IDs reachable in one hop via ref fields."""
    neighbors: set[str] = set()
    node = bundle["all_nodes"].get(node_id)
    if not node:
        return neighbors

    for field in REF_FIELDS:
        neighbors.update(edge_ref_ids(node.get(field, [])))

    if node.get("_kind") == "workflow":
        for state in node.get("states", []):
            neighbors.add(state["id"])

    wf_id = node.get("belongs_to_workflow")
    if wf_id:
        neighbors.add(wf_id)

    return neighbors


def symbol_call_neighbors(node_id: str, bundle: dict[str, Any]) -> set[str]:
    """Canonical nodes reached via symbol-level call edges from this node.

    Aggregates ``callers`` and ``callees`` for every symbol bound to
    ``node_id`` and resolves each edge back to its canonical node(s) by
    rebinding the callee's declared file path against ``code-index.yaml``.

    The symbol id prefix is not authoritative — files often bind to several
    canonical nodes via overlapping globs, and the prefix the extractor
    chose is only one of them. Walking the file through ``match_bindings_
    for_path`` recovers the full neighbor set so canonical entities surface
    a real structural reach when their ontology ``REF_FIELDS`` are sparse.
    """
    neighbors: set[str] = set()
    file_to_node_ids_cache: dict[str, set[str]] = {}
    for sym in match_symbols_for_node(node_id, bundle):
        for edge_id in sym.get("callers", []) + sym.get("callees", []):
            target = get_symbol_by_id(edge_id, bundle)
            if target is None:
                continue
            tgt_file = target.get("file")
            if not tgt_file:
                continue
            bound = file_to_node_ids_cache.get(tgt_file)
            if bound is None:
                bound = {
                    b["id"] for b in match_bindings_for_path(tgt_file, bundle)
                }
                file_to_node_ids_cache[tgt_file] = bound
            neighbors |= bound - {node_id}
    return neighbors


def find_related_policy_rules(
    node_ids: set[str], bundle: dict[str, Any]
) -> list[str]:
    """Find policy_rule nodes whose related_nodes intersect with node_ids."""
    rules: list[str] = []
    for rule in bundle["canonical"].get("policy_rules", []):
        related = set(rule.get("related_nodes", []))
        if related.intersection(node_ids):
            rules.append(rule["id"])
    return sorted(rules)


def flatten_paths(obj: Any) -> list[str]:
    """Recursively collect all string paths from a nested dict/list."""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, list):
        result: list[str] = []
        for item in obj:
            result.extend(flatten_paths(item))
        return result
    if isinstance(obj, dict):
        result = []
        for v in obj.values():
            result.extend(flatten_paths(v))
        return result
    return []


def resolve_patterns(patterns: list[str]) -> list[str]:
    """Expand glob patterns to actual file paths."""
    resolved: list[str] = []
    for pattern in patterns:
        resolved.extend(expand_declared_pattern(pattern))
    return sorted(set(resolved))


def build_blast_report(
    starting_ids: set[str],
    bundle: dict[str, Any],
    query: dict[str, Any],
) -> dict[str, Any]:
    """Build the full blast radius report."""

    # One-hop expansion from starting nodes — combines ontology refs with
    # symbol-level call edges so canonical entities (whose outbound REF_FIELDS
    # are typically empty) still surface a real neighbor count.
    neighbor_ids: set[str] = set()
    for node_id in starting_ids:
        neighbor_ids |= one_hop_neighbors(node_id, bundle)
        neighbor_ids |= symbol_call_neighbors(node_id, bundle)
    neighbor_ids -= starting_ids

    all_impacted = starting_ids | neighbor_ids

    # Features and stories that reference direct nodes
    features, stories = related_mapping_entries(starting_ids, bundle["mappings"])

    # Indirect features/stories via neighbor nodes
    indirect_features, indirect_stories = related_mapping_entries(
        neighbor_ids, bundle["mappings"]
    )
    direct_feature_ids = {f["id"] for f in features}
    direct_story_ids = {s["id"] for s in stories}
    indirect_features = [
        f for f in indirect_features if f["id"] not in direct_feature_ids
    ]
    indirect_stories = [
        s for s in indirect_stories if s["id"] not in direct_story_ids
    ]

    # Code bindings for direct nodes
    direct_bindings: dict[str, dict[str, Any]] = {}
    for node_id in sorted(starting_ids):
        binding = bundle["bindings"].get(node_id)
        if binding:
            direct_bindings[node_id] = binding.get("paths", {})

    # Policy rules: nodes in impacted set + reverse lookup via related_nodes
    policy_rules_from_type = sorted(
        nid
        for nid in all_impacted
        if bundle["all_nodes"].get(nid, {}).get("_kind") == "policy_rule"
    )
    policy_rules_from_related = find_related_policy_rules(starting_ids, bundle)
    for feat in features:
        policy_rules_from_related.extend(edge_ref_ids(feat.get("enforced_by_policy", [])))
    policy_rules = sorted(
        set(policy_rules_from_type) | set(policy_rules_from_related)
    )

    # Categorize all impacted nodes by type
    impacted_by_type: dict[str, list[str]] = {}
    for nid in sorted(all_impacted):
        node = bundle["all_nodes"].get(nid)
        if node:
            kind = node.get("_kind", "unknown")
            impacted_by_type.setdefault(kind, []).append(nid)

    # Resolved file paths
    all_patterns: list[str] = []
    for paths_obj in direct_bindings.values():
        all_patterns.extend(flatten_paths(paths_obj))
    resolved_files = resolve_patterns(all_patterns)

    return {
        "query": query,
        "direct_nodes": sorted(starting_ids),
        "neighbor_nodes": sorted(neighbor_ids),
        "impacted_by_type": impacted_by_type,
        "features": [
            {"id": f["id"], "path": f.get("path"), "status": f.get("status")}
            for f in features
        ],
        "stories": [{"id": s["id"], "path": s.get("path")} for s in stories],
        "indirect_features": [
            {"id": f["id"], "path": f.get("path"), "status": f.get("status")}
            for f in indirect_features
        ],
        "indirect_stories": [
            {"id": s["id"], "path": s.get("path")} for s in indirect_stories
        ],
        "policy_rules": policy_rules,
        "code_bindings": direct_bindings,
        "resolved_files": resolved_files,
        "summary": {
            "direct_node_count": len(starting_ids),
            "neighbor_node_count": len(neighbor_ids),
            "feature_count": len(features),
            "indirect_feature_count": len(indirect_features),
            "story_count": len(stories),
            "indirect_story_count": len(indirect_stories),
            "policy_rule_count": len(policy_rules),
            "resolved_file_count": len(resolved_files),
        },
    }


def build_symbol_blast(
    starting_symbols: list[dict[str, Any]],
    bundle: dict[str, Any],
    query: dict[str, Any],
) -> dict[str, Any]:
    """Blast radius for a symbol entry. Walks one hop of caller/callee edges
    and reports the reached symbols, canonical nodes, and files."""
    visited: dict[str, dict[str, Any]] = {}
    direct_ids: list[str] = []
    for sym in starting_symbols:
        sid = sym["id"]
        if sid in visited:
            continue
        visited[sid] = sym
        direct_ids.append(sid)

    reached_ids: list[str] = []
    for sym in starting_symbols:
        for edge_id in sym.get("callers", []) + sym.get("callees", []):
            target = get_symbol_by_id(edge_id, bundle)
            if target is None:
                continue
            if edge_id in visited:
                continue
            visited[edge_id] = target
            reached_ids.append(edge_id)

    nodes_touched = sorted({s["node"] for s in visited.values() if s.get("node")})
    files_touched = sorted({s["file"] for s in visited.values() if s.get("file")})

    def brief(s: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": s["id"],
            "name": s.get("name"),
            "kind": s.get("kind"),
            "container": s.get("container"),
            "node": s.get("node"),
            "file": s.get("file"),
            "line": s.get("line"),
        }

    return {
        "query": query,
        "direct_symbols": [brief(s) for s in starting_symbols],
        "callers": [
            brief(get_symbol_by_id(cid, bundle))
            for s in starting_symbols
            for cid in s.get("callers", [])
            if get_symbol_by_id(cid, bundle) is not None
        ],
        "callees": [
            brief(get_symbol_by_id(cid, bundle))
            for s in starting_symbols
            for cid in s.get("callees", [])
            if get_symbol_by_id(cid, bundle) is not None
        ],
        "nodes_touched": nodes_touched,
        "files_touched": files_touched,
        "summary": {
            "direct_symbol_count": len(direct_ids),
            "reached_symbol_count": len(reached_ids),
            "node_count": len(nodes_touched),
            "file_count": len(files_touched),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute blast radius for a file, canonical node ID, or symbol."
    )
    parser.add_argument(
        "target",
        nargs="?",
        help=(
            "Node ID (entity:submission), feature (F0007), story (F0007-S0003), "
            "or symbol ID (symbol:entity-submission:submission-service.transition-async)"
        ),
    )
    parser.add_argument(
        "--file",
        dest="file_path",
        help="Repo file path (e.g. engine/src/Nebula.Domain/Entities/Submission.cs)",
    )
    parser.add_argument(
        "--symbol",
        dest="symbol_name",
        help="Symbol name (e.g. TransitionAsync). Walks symbol-level call edges.",
    )
    parser.add_argument(
        "--node",
        dest="symbol_node",
        help="Scope --symbol blast to one canonical node id.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Output summary only, omit resolved file lists.",
    )
    parser.add_argument("--run-id", default=None, help="Correlation ID stamped onto emitted telemetry.")
    parser.add_argument(
        "--telemetry-file",
        type=Path,
        default=None,
        help="Append one JSONL telemetry event for this invocation.",
    )
    args = parser.parse_args()

    modes = sum(bool(x) for x in (args.target, args.file_path, args.symbol_name))
    if modes == 0:
        parser.error("Provide a node ID, --file, or --symbol.")
    if modes > 1:
        parser.error("Use only one of: node ID, --file, --symbol.")

    bundle = load_bundle()

    confidence_band = "high"
    ambiguous_count = 0

    # --symbol mode: name-based symbol blast
    if args.symbol_name:
        matches = match_symbol_by_name(args.symbol_name, bundle, node_id=args.symbol_node)
        if not matches:
            print(f"No symbols named: {args.symbol_name}", file=sys.stderr)
            return 1
        query = {"symbol_name": args.symbol_name, "node": args.symbol_node}
        report = build_symbol_blast(matches, bundle, query)
        if args.compact:
            json.dump(report["summary"], sys.stdout, indent=2)
        else:
            json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        emit_telemetry(
            args.telemetry_file,
            args.run_id,
            "blast",
            {
                "query": query,
                "nodes_returned": report["nodes_touched"],
                "nodes_count": report["summary"]["node_count"],
                "symbols_returned": [s["id"] for s in report["direct_symbols"]],
                "symbol_count": report["summary"]["direct_symbol_count"],
                "reached_symbol_count": report["summary"]["reached_symbol_count"],
                "file_count": report["summary"]["file_count"],
                "empty_scope": not report["direct_symbols"],
                "ambiguous_count": 0,
                "hint_emitted": False,
                "confidence_band": "high",
                "tokens_estimated": estimate_tokens(report if not args.compact else report["summary"]),
            },
        )
        return 0

    # symbol id passed as positional target
    if args.target and args.target.startswith("symbol:"):
        sym = get_symbol_by_id(args.target, bundle)
        if sym is None:
            print(f"Unknown symbol id: {args.target}", file=sys.stderr)
            return 1
        query = {"symbol_id": args.target}
        report = build_symbol_blast([sym], bundle, query)
        if args.compact:
            json.dump(report["summary"], sys.stdout, indent=2)
        else:
            json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        emit_telemetry(
            args.telemetry_file,
            args.run_id,
            "blast",
            {
                "query": query,
                "nodes_returned": report["nodes_touched"],
                "nodes_count": report["summary"]["node_count"],
                "symbols_returned": [s["id"] for s in report["direct_symbols"]],
                "symbol_count": report["summary"]["direct_symbol_count"],
                "reached_symbol_count": report["summary"]["reached_symbol_count"],
                "file_count": report["summary"]["file_count"],
                "empty_scope": False,
                "ambiguous_count": 0,
                "hint_emitted": False,
                "confidence_band": "high",
                "tokens_estimated": estimate_tokens(report if not args.compact else report["summary"]),
            },
        )
        return 0

    if args.file_path:
        starting_ids = node_ids_for_file(args.file_path, bundle)
        if not starting_ids:
            print(f"No KG bindings found for: {args.file_path}", file=sys.stderr)
            return 1
        query = {"file": repo_relative(args.file_path)}
    else:
        normalized = normalize_target_id(args.target)
        node = bundle["all_nodes"].get(normalized)
        if node is None:
            print(f"Unknown node: {args.target}", file=sys.stderr)
            return 1

        if node.get("_kind") in ("feature", "story"):
            starting_ids = canonical_refs_from_mapping(node)
            if not starting_ids:
                starting_ids = {normalized}
            confidence_band, ambiguous_count = classify_mapping_edges(node)
            query = {
                "feature_or_story": normalized,
                "affected_canonical_nodes": sorted(starting_ids),
            }
        else:
            starting_ids = {normalized}
            query = {"node": normalized}

    report = build_blast_report(starting_ids, bundle, query)

    if args.compact:
        json.dump(report["summary"], sys.stdout, indent=2)
    else:
        json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")

    emit_telemetry(
        args.telemetry_file,
        args.run_id,
        "blast",
        {
            "query": query,
            "nodes_returned": report["direct_nodes"],
            "nodes_count": len(report["direct_nodes"]),
            "neighbor_nodes": report["neighbor_nodes"],
            "policy_rule_count": report["summary"]["policy_rule_count"],
            "resolved_file_count": report["summary"]["resolved_file_count"],
            "empty_scope": not report["direct_nodes"],
            "ambiguous_count": ambiguous_count,
            "hint_emitted": False,
            "confidence_band": confidence_band,
            "tokens_estimated": estimate_tokens(report if not args.compact else report["summary"]),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

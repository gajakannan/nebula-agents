#!/usr/bin/env python3
"""Compute PageRank over the knowledge graph to surface hub nodes.

Builds a directed graph from canonical-nodes.yaml and feature-mappings.yaml
edges, runs iterative PageRank, and outputs a ranked report. Hub ("god")
nodes are the ones most connected across features, schemas, policies, and
code bindings — they indicate where ABAC coverage, test coverage, and
architectural attention matter most.

Usage:
    python3 scripts/kg/pagerank.py
    python3 scripts/kg/pagerank.py --top 20
    python3 scripts/kg/pagerank.py --type entity
    python3 scripts/kg/pagerank.py --yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from typing import Any

import yaml

from kg_common import (
    KG_DIR,
    REF_FIELDS,
    SECTION_TYPES,
    edge_ref_ids,
    load_bundle,
)


def build_graph(bundle: dict[str, Any]) -> dict[str, set[str]]:
    """Build a directed adjacency list from all KG edges.

    Edge direction follows reference semantics: if feature F0006 affects
    entity:submission, the edge is F0006 → submission.  Nodes that receive
    many incoming edges rank highest — they are the hubs the graph depends on.
    """
    all_nodes = bundle["all_nodes"]
    canonical = bundle["canonical"]
    mappings = bundle["mappings"]

    graph: dict[str, set[str]] = defaultdict(set)

    # Ensure every known node appears as a key even with no outgoing edges
    for node_id in all_nodes:
        graph.setdefault(node_id, set())

    # --- canonical-nodes.yaml edges ---

    for section in SECTION_TYPES:
        for item in canonical.get(section, []):
            node_id = item["id"]

            # related_nodes (bidirectional association)
            for target in item.get("related_nodes", []):
                if target in all_nodes:
                    graph[node_id].add(target)
                    graph[target].add(node_id)

            # allowed_roles on policy_rules
            for role_id in item.get("allowed_roles", []):
                if role_id in all_nodes:
                    graph[node_id].add(role_id)

            # rationale ADR references
            for entry in item.get("rationale", []):
                adr_ref = entry.get("adr")
                if adr_ref and adr_ref in all_nodes:
                    graph[node_id].add(adr_ref)

            # Workflow states
            if section == "workflows":
                for state in item.get("states", []):
                    state_id = state["id"]
                    # state belongs to workflow
                    graph[state_id].add(node_id)
                    graph[node_id].add(state_id)
                    # transitions
                    for target in state.get("transitions_to", []):
                        if target in all_nodes:
                            graph[state_id].add(target)

    # --- feature-mappings.yaml edges ---

    for section_name in ("features", "stories"):
        for item in mappings.get(section_name, []):
            node_id = item["id"]

            # story → feature
            feature_ref = item.get("feature")
            if feature_ref and feature_ref in all_nodes:
                graph[node_id].add(feature_ref)

            # All REF_FIELDS: feature/story → target node
            for field in REF_FIELDS:
                for target in edge_ref_ids(item.get(field, [])):
                    if target in all_nodes:
                        graph[node_id].add(target)

    return graph


def compute_pagerank(
    graph: dict[str, set[str]],
    damping: float = 0.85,
    iterations: int = 100,
    tolerance: float = 1e-8,
) -> dict[str, float]:
    """Iterative PageRank over a directed graph."""
    nodes = list(graph.keys())
    n = len(nodes)
    if n == 0:
        return {}

    rank: dict[str, float] = {node: 1.0 / n for node in nodes}

    # Build reverse adjacency (incoming edges)
    incoming: dict[str, list[str]] = defaultdict(list)
    out_degree: dict[str, int] = {}
    for node in nodes:
        out_degree[node] = len(graph[node])
        for target in graph[node]:
            incoming[target].append(node)

    base = (1.0 - damping) / n

    for _ in range(iterations):
        new_rank: dict[str, float] = {}
        # Collect rank from dangling nodes (no outgoing edges)
        dangling_sum = sum(rank[node] for node in nodes if out_degree[node] == 0)

        for node in nodes:
            incoming_sum = sum(
                rank[src] / out_degree[src]
                for src in incoming.get(node, [])
                if out_degree[src] > 0
            )
            new_rank[node] = base + damping * (incoming_sum + dangling_sum / n)

        # Check convergence
        diff = sum(abs(new_rank[node] - rank[node]) for node in nodes)
        rank = new_rank
        if diff < tolerance:
            break

    return rank


def build_report(
    rank: dict[str, float],
    bundle: dict[str, Any],
    graph: dict[str, set[str]],
    top_n: int | None = None,
    filter_type: str | None = None,
) -> list[dict[str, Any]]:
    """Build a ranked report with node metadata."""
    all_nodes = bundle["all_nodes"]

    # Build in-degree map
    in_degree: dict[str, int] = defaultdict(int)
    for node, targets in graph.items():
        for target in targets:
            in_degree[target] += 1

    entries: list[dict[str, Any]] = []
    for node_id, score in rank.items():
        node = all_nodes.get(node_id, {})
        kind = node.get("_kind", "unknown")

        if filter_type and kind != filter_type:
            continue

        entry: dict[str, Any] = {
            "id": node_id,
            "label": node.get("label", node_id),
            "type": kind,
            "pagerank": round(score, 8),
            "in_degree": in_degree.get(node_id, 0),
            "out_degree": len(graph.get(node_id, set())),
        }

        # Include code binding count if present
        binding = bundle["bindings"].get(node_id)
        if binding:
            entry["code_binding_patterns"] = len(binding.get("declared_paths", []))

        entries.append(entry)

    entries.sort(key=lambda e: e["pagerank"], reverse=True)

    if top_n:
        entries = entries[:top_n]

    # Add rank position
    for i, entry in enumerate(entries, 1):
        entry["rank"] = i

    return entries


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute PageRank over the knowledge graph to surface hub nodes."
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Number of top-ranked nodes to display (default: 30, 0 for all).",
    )
    parser.add_argument(
        "--type",
        dest="filter_type",
        default=None,
        help="Filter results to a single node type (e.g. entity, capability, endpoint).",
    )
    parser.add_argument(
        "--yaml",
        dest="output_yaml",
        action="store_true",
        help="Output as YAML instead of JSON.",
    )
    parser.add_argument(
        "--damping",
        type=float,
        default=0.85,
        help="PageRank damping factor (default: 0.85).",
    )
    args = parser.parse_args()

    bundle = load_bundle()
    graph = build_graph(bundle)
    rank = compute_pagerank(graph, damping=args.damping)

    top_n = args.top if args.top > 0 else None
    report = build_report(rank, bundle, graph, top_n=top_n, filter_type=args.filter_type)

    total_nodes = len(rank)
    total_edges = sum(len(targets) for targets in graph.values())

    output = {
        "summary": {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "damping_factor": args.damping,
            "showing": len(report),
        },
        "rankings": report,
    }

    if args.output_yaml:
        yaml.safe_dump(output, sys.stdout, sort_keys=False, allow_unicode=False)
    else:
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

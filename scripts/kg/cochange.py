#!/usr/bin/env python3
"""Discover git co-change edges between canonical nodes.

Analyzes git history to find files that frequently change together, maps them
to canonical node IDs via code-index.yaml bindings, and surfaces:

1. Node co-change pairs — canonical nodes whose bound files change together,
   ranked by frequency.  Structural relationships the static ontology can't see.
2. Coverage gap candidates — files that frequently co-change with bound files
   but have no code-index binding themselves.

Usage:
    python3 scripts/kg/cochange.py
    python3 scripts/kg/cochange.py --months 3 --min-commits 2
    python3 scripts/kg/cochange.py --coverage-gaps
    python3 scripts/kg/cochange.py --yaml
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

import yaml

from kg_common import (
    REPO_ROOT,
    load_bundle,
    match_bindings_for_path,
    repo_relative,
)


def git_commits_with_files(months: int) -> list[list[str]]:
    """Parse git log into a list of commits, each a list of changed file paths."""
    cmd = [
        "git", "log",
        f"--since={months} months ago",
        "--no-merges",
        "--format=>>>%H",
        "--name-only",
        "--diff-filter=AMRC",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    if result.returncode != 0:
        raise SystemExit(f"git log failed: {result.stderr.strip()}")

    commits: list[list[str]] = []
    current: list[str] = []

    for line in result.stdout.splitlines():
        if line.startswith(">>>"):
            if current:
                commits.append(current)
            current = []
        elif line.strip():
            current.append(line.strip())

    if current:
        commits.append(current)

    return commits


def build_file_to_nodes(bundle: dict[str, Any], all_files: set[str]) -> dict[str, list[str]]:
    """Map each file path to the canonical node IDs it binds to."""
    mapping: dict[str, list[str]] = {}
    for filepath in all_files:
        matches = match_bindings_for_path(filepath, bundle)
        if matches:
            mapping[filepath] = [m["id"] for m in matches]
    return mapping


def build_node_to_files(file_to_nodes: dict[str, list[str]]) -> dict[str, set[str]]:
    """Invert the file→nodes map to get each node's bound files."""
    node_files: dict[str, set[str]] = defaultdict(set)
    for filepath, node_ids in file_to_nodes.items():
        for node_id in node_ids:
            node_files[node_id].add(filepath)
    return node_files


def compute_cochanges(
    commits: list[list[str]],
    file_to_nodes: dict[str, list[str]],
    min_commits: int,
    all_nodes: dict[str, Any] | None = None,
    exclude_types: set[str] | None = None,
) -> dict[str, Any]:
    """Compute node-level and file-level co-change statistics."""

    # Build node→files map for shared-file detection
    node_files = build_node_to_files(file_to_nodes)

    # --- Node co-change pairs ---
    node_pair_commits: Counter[tuple[str, str]] = Counter()
    node_commit_count: Counter[str] = Counter()

    for files in commits:
        # Collect unique nodes touched in this commit
        nodes_in_commit: set[str] = set()
        for f in files:
            for node_id in file_to_nodes.get(f, []):
                nodes_in_commit.add(node_id)

        for node_id in nodes_in_commit:
            node_commit_count[node_id] += 1

        # Count each pair of distinct nodes
        for a, b in combinations(sorted(nodes_in_commit), 2):
            node_pair_commits[(a, b)] += 1

    # Filter to pairs above threshold, skipping trivial shared-file pairs
    node_pairs: list[dict[str, Any]] = []
    for (a, b), count in node_pair_commits.most_common():
        if count < min_commits:
            break

        # Skip pairs where nodes share all or most binding files —
        # they co-change trivially because they bind to overlapping files.
        # Covers: identical sets, subsets, and high-overlap (>80%) pairs.
        files_a = node_files.get(a, set())
        files_b = node_files.get(b, set())
        if files_a and files_b:
            overlap = len(files_a & files_b)
            smaller = min(len(files_a), len(files_b))
            if overlap / smaller > 0.8:
                continue

        # Skip pairs involving excluded node types
        if exclude_types and all_nodes:
            type_a = all_nodes.get(a, {}).get("_kind", "")
            type_b = all_nodes.get(b, {}).get("_kind", "")
            if type_a in exclude_types or type_b in exclude_types:
                continue

        pct_of_a = round(count / node_commit_count[a] * 100, 1) if node_commit_count[a] else 0
        pct_of_b = round(count / node_commit_count[b] * 100, 1) if node_commit_count[b] else 0
        node_pairs.append({
            "nodes": [a, b],
            "co_commits": count,
            "pct_of_first": pct_of_a,
            "pct_of_second": pct_of_b,
        })

    # --- Coverage gap candidates ---
    # Files that co-change with bound files but have no binding themselves
    all_files_in_commits: set[str] = set()
    for files in commits:
        all_files_in_commits.update(files)

    bound_files = set(file_to_nodes.keys())
    unbound_files = all_files_in_commits - bound_files

    # Filter to code files only (skip planning docs, configs, etc.)
    code_prefixes = ("engine/", "experience/", "neuron/")
    code_extensions = {".cs", ".ts", ".tsx", ".js", ".jsx", ".py", ".yaml", ".json"}
    unbound_code_files = {
        f for f in unbound_files
        if any(f.startswith(p) for p in code_prefixes)
        and Path(f).suffix in code_extensions
    }

    # Count how often each unbound code file co-appears with any bound file
    unbound_cochange: Counter[str] = Counter()
    unbound_partners: dict[str, set[str]] = defaultdict(set)

    for files in commits:
        file_set = set(files)
        bound_in_commit = file_set & bound_files
        unbound_in_commit = file_set & unbound_code_files

        if bound_in_commit and unbound_in_commit:
            # Map bound files to their nodes for context
            nodes_in_commit: set[str] = set()
            for f in bound_in_commit:
                for node_id in file_to_nodes.get(f, []):
                    nodes_in_commit.add(node_id)

            for uf in unbound_in_commit:
                unbound_cochange[uf] += 1
                unbound_partners[uf].update(nodes_in_commit)

    coverage_gaps: list[dict[str, Any]] = []
    for filepath, count in unbound_cochange.most_common():
        if count < min_commits:
            break
        coverage_gaps.append({
            "file": filepath,
            "co_commits_with_bound": count,
            "co_change_nodes": sorted(unbound_partners[filepath]),
        })

    return {
        "node_pairs": node_pairs,
        "node_commit_counts": dict(node_commit_count.most_common()),
        "coverage_gaps": coverage_gaps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover git co-change edges between canonical nodes."
    )
    parser.add_argument(
        "--months",
        type=int,
        default=6,
        help="Look back N months in git history (default: 6).",
    )
    parser.add_argument(
        "--min-commits",
        type=int,
        default=2,
        help="Minimum co-change commits to report a pair (default: 2).",
    )
    parser.add_argument(
        "--coverage-gaps",
        action="store_true",
        help="Include coverage gap candidates in output.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Show top N node pairs (default: 30, 0 for all).",
    )
    parser.add_argument(
        "--exclude-type",
        dest="exclude_types",
        action="append",
        default=[],
        help="Exclude node type from pairs (repeatable, e.g. --exclude-type policy_rule --exclude-type role).",
    )
    parser.add_argument(
        "--yaml",
        dest="output_yaml",
        action="store_true",
        help="Output as YAML instead of JSON.",
    )
    args = parser.parse_args()

    bundle = load_bundle()
    commits = git_commits_with_files(args.months)

    # Collect all unique files across all commits
    all_files: set[str] = set()
    for files in commits:
        all_files.update(files)

    file_to_nodes = build_file_to_nodes(bundle, all_files)
    exclude = set(args.exclude_types) if args.exclude_types else None
    results = compute_cochanges(
        commits, file_to_nodes, args.min_commits,
        all_nodes=bundle["all_nodes"], exclude_types=exclude,
    )

    node_pairs = results["node_pairs"]
    if args.top > 0:
        node_pairs = node_pairs[:args.top]

    output: dict[str, Any] = {
        "summary": {
            "months_analyzed": args.months,
            "total_commits": len(commits),
            "unique_files": len(all_files),
            "bound_files": len(file_to_nodes),
            "unbound_files": len(all_files) - len(file_to_nodes),
            "node_pairs_found": len(results["node_pairs"]),
            "min_commits_threshold": args.min_commits,
        },
        "node_co_changes": node_pairs,
    }

    if args.coverage_gaps:
        output["coverage_gaps"] = results["coverage_gaps"]

    if args.output_yaml:
        yaml.safe_dump(output, sys.stdout, sort_keys=False, allow_unicode=False)
    else:
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

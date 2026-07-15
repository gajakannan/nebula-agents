#!/usr/bin/env python3
"""Output KG routing hints for a file or directory path.

Agent-agnostic CLI tool. Given a repo-relative path, looks up code-index
bindings and outputs a compact summary of matched nodes, features, stories,
and Casbin policy rules.

Usage:
    python3 scripts/kg/hint.py engine/src/Nebula.Domain/Entities/Submission.cs
    python3 scripts/kg/hint.py engine/src/Nebula.Domain/Entities
    python3 scripts/kg/hint.py experience/src/features/renewals
    python3 scripts/kg/hint.py --json engine/src/Nebula.Domain/Entities/Renewal.cs

Exit code is always 0 (advisory). Produces no output when no bindings match.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from kg_common import (
    KG_DIR,
    emit_telemetry,
    estimate_tokens,
    load_bundle,
    load_yaml,
    match_bindings_for_path,
    match_symbol_by_name,
    match_symbols_for_path,
    normalize_repo_path,
    related_mapping_entries,
)


SYMBOL_PREVIEW_LIMIT = 10
HOTSPOT_RANK_THRESHOLD = 5

_HOTSPOT_CACHE: dict[str, dict[str, Any]] | None = None


def _hotspots_by_node() -> dict[str, dict[str, Any]]:
    """Lazy-load Phase 3 hotspot fields from coverage-report.yaml.

    Missing report or missing fields → empty dict (Phase 3 is additive).
    """
    global _HOTSPOT_CACHE
    if _HOTSPOT_CACHE is not None:
        return _HOTSPOT_CACHE
    report_path = KG_DIR / "coverage-report.yaml"
    if not report_path.exists():
        _HOTSPOT_CACHE = {}
        return _HOTSPOT_CACHE
    report = load_yaml(report_path) or {}
    canonical = report.get("freshness", {}).get("canonical", {}) or {}
    out: dict[str, dict[str, Any]] = {}
    for node_id, entry in canonical.items():
        rank = entry.get("hotspot_rank")
        if rank is None:
            continue
        out[node_id] = {
            "hotspot_rank": rank,
            "primary_owner": entry.get("primary_owner"),
            "bus_factor_flag": bool(entry.get("bus_factor_flag")),
        }
    _HOTSPOT_CACHE = out
    return out


def _hotspot_label(node_ids: list[str]) -> str | None:
    """Compact one-line hotspot annotation for hint output.

    Returns None when no node hits the threshold or carries a bus-factor flag.
    """
    by_node = _hotspots_by_node()
    flagged: list[tuple[str, dict[str, Any]]] = []
    for nid in node_ids:
        info = by_node.get(nid)
        if not info:
            continue
        if info["hotspot_rank"] <= HOTSPOT_RANK_THRESHOLD or info["bus_factor_flag"]:
            flagged.append((nid, info))
    if not flagged:
        return None
    parts: list[str] = []
    for nid, info in flagged:
        rank = info["hotspot_rank"]
        markers: list[str] = []
        if rank <= HOTSPOT_RANK_THRESHOLD:
            markers.append(f"hotspot ▲ rank {rank}")
        if info["bus_factor_flag"]:
            owner = info.get("primary_owner") or "unknown"
            markers.append(f"bus-factor ⚠ {owner}")
        parts.append(f"{nid}: {', '.join(markers)}")
    return "  Risk: " + "; ".join(parts)


def find_policy_rules_for_nodes(
    node_ids: list[str], bundle: dict[str, Any]
) -> list[str]:
    """Find policy_rule nodes whose related_nodes mention any of node_ids."""
    wanted = set(node_ids)
    rules: list[str] = []
    for rule in bundle["canonical"].get("policy_rules", []):
        related = set(rule.get("related_nodes", []))
        if related.intersection(wanted):
            rules.append(rule["id"])
    return sorted(rules)


def match_path(normalized: str, bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Match a path against code-index bindings, handling files and directories."""
    matches = match_bindings_for_path(normalized, bundle)

    # If no direct match and path looks like a directory, try prefix matching
    if not matches and not Path(normalized).suffix:
        prefix = normalized.rstrip("/") + "/"
        for binding in bundle["bindings"].values():
            for entry in binding.get("declared_paths", []):
                if entry["pattern"].startswith(prefix):
                    matches.append(binding)
                    break
        seen: set[str] = set()
        deduped = []
        for m in matches:
            if m["id"] not in seen:
                seen.add(m["id"])
                deduped.append(m)
        matches = deduped

    return matches


def format_text(
    path: str,
    node_ids: list[str],
    features: list[dict[str, Any]],
    stories: list[dict[str, Any]],
    policy_rules: list[str],
    symbols: list[dict[str, Any]],
) -> str:
    """Format KG hints as compact human-readable text."""
    lines = [f"[KG] {path} -> {', '.join(node_ids)}"]

    if features:
        feat_parts = [f["id"] for f in features[:6]]
        lines.append(f"  Features: {', '.join(feat_parts)}")

    if stories:
        story_parts = [s["id"] for s in stories[:8]]
        suffix = f" (+{len(stories) - 8} more)" if len(stories) > 8 else ""
        lines.append(f"  Stories: {', '.join(story_parts)}{suffix}")

    if policy_rules:
        lines.append(f"  Casbin: {', '.join(policy_rules[:6])}")

    if symbols:
        preview = symbols[:SYMBOL_PREVIEW_LIMIT]
        more = len(symbols) - len(preview)
        labels = [_format_symbol_label(s) for s in preview]
        suffix = f" (+{more} more)" if more > 0 else ""
        lines.append(f"  Symbols: {', '.join(labels)}{suffix}")

    hotspot_line = _hotspot_label(node_ids)
    if hotspot_line:
        lines.append(hotspot_line)

    lines.append(
        "  Tip: `python3 scripts/kg/blast.py --file <path>` for full blast radius"
    )
    return "\n".join(lines)


def _format_symbol_label(symbol: dict[str, Any]) -> str:
    container = symbol.get("container")
    name = symbol.get("name") or "?"
    line = symbol.get("line")
    base = f"{container}.{name}" if container else name
    return f"{base}:L{line}" if line else base


def hint_symbol(name: str, bundle: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Compact text for a symbol-name hint plus the matched records.

    Empty-match output stays terse; the caller is expected to consult
    `lookup.py --symbol` for richer detail.
    """
    matches = match_symbol_by_name(name, bundle)
    if not matches:
        return f"[KG] symbol '{name}' -> no matches in symbol-index.yaml", []
    lines = [f"[KG] symbol '{name}' -> {len(matches)} match(es)"]
    for symbol in matches[:SYMBOL_PREVIEW_LIMIT]:
        node = symbol.get("node", "?")
        file_rel = symbol.get("file", "?")
        line = symbol.get("line", 0)
        container = symbol.get("container")
        label = f"{container}.{name}" if container else name
        lines.append(f"  {node} :: {label}  {file_rel}:{line}")
    if len(matches) > SYMBOL_PREVIEW_LIMIT:
        lines.append(f"  (+{len(matches) - SYMBOL_PREVIEW_LIMIT} more — see lookup.py --symbol)")
    lines.append("  Tip: `python3 scripts/kg/lookup.py --symbol <name>` for callers/callees")
    return "\n".join(lines), matches


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Output KG routing hints for a file or directory path."
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Repo-relative file or directory path",
    )
    parser.add_argument(
        "--symbol",
        dest="symbol_name",
        help="Look up a symbol by source name and emit a compact hint.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output as JSON instead of human-readable text.",
    )
    parser.add_argument("--run-id", default=None, help="Correlation ID stamped onto emitted telemetry.")
    parser.add_argument(
        "--telemetry-file",
        type=Path,
        default=None,
        help="Append one JSONL telemetry event for this invocation.",
    )
    args = parser.parse_args()

    if not args.path and not args.symbol_name:
        parser.error("Provide a path or --symbol.")
    if args.path and args.symbol_name:
        parser.error("Use either a path or --symbol, not both.")

    try:
        bundle = load_bundle()
    except SystemExit:
        return 0

    if args.symbol_name:
        text, symbol_matches = hint_symbol(args.symbol_name, bundle)
        if args.as_json:
            payload = {
                "symbol": args.symbol_name,
                "matches": [
                    {
                        "id": s["id"],
                        "name": s.get("name"),
                        "node": s.get("node"),
                        "file": s.get("file"),
                        "line": s.get("line"),
                        "container": s.get("container"),
                        "kind": s.get("kind"),
                    }
                    for s in symbol_matches
                ],
            }
            json.dump(payload, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            print(text)
        emit_telemetry(
            args.telemetry_file,
            args.run_id,
            "hint",
            {
                "query_symbol": args.symbol_name,
                "symbols_returned": [s["id"] for s in symbol_matches],
                "symbols_count": len(symbol_matches),
                "nodes_returned": sorted({s["node"] for s in symbol_matches if s.get("node")}),
                "nodes_count": len({s.get("node") for s in symbol_matches if s.get("node")}),
                "empty_scope": not symbol_matches,
                "ambiguous_count": 0,
                "hint_emitted": True,
                "confidence_band": "high" if symbol_matches else "low",
                "tokens_estimated": estimate_tokens(symbol_matches or {}),
            },
        )
        return 0

    normalized = normalize_repo_path(args.path)

    if normalized.count("/") < 2:
        return 0

    matches = match_path(normalized, bundle)
    if not matches:
        emit_telemetry(
            args.telemetry_file,
            args.run_id,
            "hint",
            {
                "path": normalized,
                "nodes_returned": [],
                "nodes_count": 0,
                "empty_scope": True,
                "ambiguous_count": 0,
                "hint_emitted": False,
                "confidence_band": "low",
                "tokens_estimated": 1,
            },
        )
        return 0

    node_ids = [m["id"] for m in matches]
    features, stories = related_mapping_entries(node_ids, bundle["mappings"])
    policy_rules = find_policy_rules_for_nodes(node_ids, bundle)
    symbols = match_symbols_for_path(normalized, bundle)

    hotspot_annotations = {
        nid: info
        for nid, info in (
            (nid, _hotspots_by_node().get(nid)) for nid in node_ids
        )
        if info
    }

    if args.as_json:
        payload = {
            "path": normalized,
            "nodes": node_ids,
            "features": [f["id"] for f in features],
            "stories": [s["id"] for s in stories],
            "policy_rules": policy_rules,
            "symbols": [
                {
                    "id": s["id"],
                    "name": s.get("name"),
                    "kind": s.get("kind"),
                    "container": s.get("container"),
                    "line": s.get("line"),
                }
                for s in symbols
            ],
        }
        if hotspot_annotations:
            payload["hotspots"] = hotspot_annotations
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(format_text(normalized, node_ids, features, stories, policy_rules, symbols))

    emit_telemetry(
        args.telemetry_file,
        args.run_id,
        "hint",
        {
            "path": normalized,
            "nodes_returned": node_ids,
            "nodes_count": len(node_ids),
            "feature_ids": [f["id"] for f in features],
            "story_ids": [s["id"] for s in stories],
            "policy_rule_ids": policy_rules,
            "symbols_returned": [s["id"] for s in symbols],
            "symbols_count": len(symbols),
            "empty_scope": False,
            "ambiguous_count": 0,
            "hint_emitted": False,
            "confidence_band": "high",
            "tokens_estimated": estimate_tokens(
                {
                    "path": normalized,
                    "nodes": node_ids,
                    "features": [f["id"] for f in features],
                    "stories": [s["id"] for s in stories],
                    "policy_rules": policy_rules,
                    "symbols": [s["id"] for s in symbols],
                }
            ),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

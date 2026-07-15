#!/usr/bin/env python3
"""Report symbol-level dead-code candidates from the symbol layer.

Wraps the reachability traversal in scripts/kg/symbols.py:

    entry points  := bound symbols on endpoint/ui_route canonical nodes
                  +  symbols matching framework name suffixes (*Handler, *Plugin, ...)
                  +  symbols in hosted-service / worker / background-service files
    reachable     := entry points + everything reachable via `callees` (BFS)
    candidate     := unreachable symbol with confidence >= --min-confidence

Confidence is a coarse heuristic (see symbols._score_dead_code) tuned to bias
toward false negatives (missing a candidate) over false positives. Per
solution-ontology.yaml.authority.precedence, raw source remains authoritative —
this report is a routing aid for release-readiness cleanup, not a removal
verdict.

Usage:
    python3 scripts/kg/dead-code.py
    python3 scripts/kg/dead-code.py --safe-only            # only confidence >= 0.85
    python3 scripts/kg/dead-code.py --min-confidence 0.8
    python3 scripts/kg/dead-code.py --node entity:customer
    python3 scripts/kg/dead-code.py --format text
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from kg_common import emit_telemetry, estimate_tokens, load_bundle
from symbols import (
    DEFAULT_ENTRY_NODE_KINDS,
    SYMBOL_INDEX_PATH,
    find_dead_code_candidates,
    load_symbol_records,
)


SAFE_ONLY_THRESHOLD = 0.85
DEFAULT_MIN_CONFIDENCE = 0.7


def render_text(candidates: list[dict[str, Any]], reachability_summary: dict[str, Any]) -> str:
    lines = [
        f"Dead-code candidates: {len(candidates)} "
        f"(reachability: {reachability_summary['reachable']}/{reachability_summary['total']} "
        f"symbols reached from {reachability_summary['entry_points']} entry points)",
    ]
    if not candidates:
        lines.append("(none)")
        return "\n".join(lines)
    for c in candidates:
        lines.append(
            f"- {c['symbol_id']}  conf={c['confidence']:.2f}  "
            f"{c['kind']} {c['name']} ({c['visibility']}) "
            f"@ {c['file']}:{c['line']}"
        )
        for reason in c["reasons"]:
            lines.append(f"    · {reason}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report symbol-level dead-code candidates from the symbol layer. "
            "Conservative thresholds; raw source remains authoritative."
        )
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_MIN_CONFIDENCE,
        help=f"Minimum confidence to report (default: {DEFAULT_MIN_CONFIDENCE}).",
    )
    parser.add_argument(
        "--safe-only",
        action="store_true",
        help=(
            f"Shortcut for --min-confidence {SAFE_ONLY_THRESHOLD}. "
            "Reports only the highest-confidence candidates."
        ),
    )
    parser.add_argument(
        "--node",
        action="append",
        default=[],
        help="Restrict report to one or more canonical node ids (repeatable).",
    )
    parser.add_argument(
        "--entry-kind",
        action="append",
        default=[],
        choices=sorted(DEFAULT_ENTRY_NODE_KINDS | {"event", "capability"}),
        help=(
            "Override the canonical node kinds treated as entry points "
            "(repeatable). Defaults: " + ", ".join(sorted(DEFAULT_ENTRY_NODE_KINDS))
            + ". Use this when a product treats events or capabilities as "
            "first-party entry points."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("json", "text", "yaml"),
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--fail-on-find",
        action="store_true",
        help="Exit non-zero if any candidate at >= --min-confidence is reported.",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--telemetry-file", type=Path, default=None)
    args = parser.parse_args()

    if not SYMBOL_INDEX_PATH.exists():
        print(
            "symbol-index.yaml not found "
            "(run python3 scripts/kg/symbols.py first)",
            file=sys.stderr,
        )
        return 2

    min_confidence = SAFE_ONLY_THRESHOLD if args.safe_only else args.min_confidence
    entry_node_kinds = (
        frozenset(args.entry_kind) if args.entry_kind else DEFAULT_ENTRY_NODE_KINDS
    )

    bundle = load_bundle()
    records = load_symbol_records()

    if args.node:
        wanted = set(args.node)
        records = [r for r in records if r.node in wanted]

    reachability, candidates = find_dead_code_candidates(
        records,
        bundle,
        min_confidence=min_confidence,
        entry_node_kinds=entry_node_kinds,
    )

    candidate_dicts = [c.to_dict() for c in candidates]
    reach_total = len(reachability)
    reach_count = sum(1 for r in reachability.values() if r.reachable)
    entry_count = sum(1 for r in reachability.values() if r.entry_point)
    reachability_summary = {
        "total": reach_total,
        "reachable": reach_count,
        "entry_points": entry_count,
        "unreachable": reach_total - reach_count,
    }

    payload: dict[str, Any] = {
        "version": 0,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "min_confidence": min_confidence,
        "entry_node_kinds": sorted(entry_node_kinds),
        "reachability": reachability_summary,
        "candidates": candidate_dicts,
    }

    if args.format == "json":
        json.dump(payload, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    elif args.format == "yaml":
        yaml.safe_dump(payload, sys.stdout, sort_keys=False, allow_unicode=False)
    else:
        print(render_text(candidate_dicts, reachability_summary))

    nodes_returned = sorted({c["node"] for c in candidate_dicts})
    emit_telemetry(
        args.telemetry_file,
        args.run_id,
        "dead-code",
        {
            "candidates_count": len(candidate_dicts),
            "reachable_count": reach_count,
            "entry_point_count": entry_count,
            "total_symbols": reach_total,
            "min_confidence": min_confidence,
            "nodes_returned": nodes_returned,
            "nodes_count": len(nodes_returned),
            "empty_scope": not candidate_dicts,
            "ambiguous_count": 0,
            "hint_emitted": False,
            "confidence_band": "high" if candidate_dicts else "low",
            "tokens_estimated": estimate_tokens(payload),
        },
    )

    if args.fail_on_find and candidate_dicts:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Aggregate KG signals into a single 0-10 risk score for a node/file/symbol.

The risk layer is a pre-flight check, not source of truth: it combines existing
Phase 1-3 signals (blast radius, hotspot, cochange, ownership concentration,
test gap) into one number plus reviewer recommendations. Raw artifacts and
human judgement still win per ``solution-ontology.yaml.authority.precedence``.

Signals (each clamped 0.0-1.0):

- ``blast_count``            — neighbor + direct node count from blast.py,
  normalized against ``BLAST_SATURATION``.
- ``hotspot_score``          — Phase 3 hotspot score (0.0-1.0) for the
  primary node. Read from ``coverage-report.yaml`` when available, otherwise
  computed live via ``compute_hotspots``.
- ``cochange_density``       — share of the node's recent commits that also
  touched a partner canonical node (hidden coupling).
- ``ownership_concentration``— ``primary_owner_pct / 100`` for the primary
  node; ``bus_factor_flag`` pushes this towards 1.0.
- ``test_gap``               — 1.0 when no bound test files exist; otherwise
  ``max(0, 1 - test_files / impl_files)``.

The score is a weighted sum (weights documented in
``agents/architect/references/risk-scoring-guide.md``) rounded to an integer
0-10. Bands:

- 0-3  routine
- 4-6  elevated
- 7-8  high      (reviewer gate: second reviewer)
- 9-10 critical  (build gate: workstate decision required before merge)

Usage:
    python3 scripts/kg/risk.py entity:submission
    python3 scripts/kg/risk.py --file engine/src/Nebula.Domain/Entities/Submission.cs
    python3 scripts/kg/risk.py --symbol TransitionAsync --node entity:submission
    python3 scripts/kg/risk.py entity:submission --reason
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from blast import build_blast_report, build_symbol_blast, node_ids_for_file
from cochange import (
    build_file_to_nodes,
    compute_cochanges,
    git_commits_with_files,
)
from hotspots import DEFAULT_MONTHS, compute_hotspots
from kg_common import (
    KG_DIR,
    emit_telemetry,
    estimate_tokens,
    expand_declared_pattern,
    get_symbol_by_id,
    load_bundle,
    load_yaml,
    match_symbol_by_name,
    normalize_target_id,
    repo_relative,
)


# Signal weights — must sum to 10 so the weighted sum lands in 0-10.
WEIGHTS = {
    "blast_count": 2.0,
    "hotspot_score": 3.0,
    "cochange_density": 1.5,
    "ownership_concentration": 1.5,
    "test_gap": 2.0,
}
BLAST_SATURATION = 20  # neighbor + direct node count that saturates blast signal
COCHANGE_MIN_COMMITS = 2
# Distinct co-change partners that saturate the signal. 40 leaves meaningful
# differentiation in repos where most active nodes share 80+ partners; lower
# values collapse the signal to 1.0 across the active tier. Products with
# tighter coupling baselines may override via a product-local ADR.
COCHANGE_PARTNER_SATURATION = 40
COCHANGE_DEFAULT_MONTHS = 6
BUS_FACTOR_THRESHOLD = 80
TEST_BUCKET_TOKEN = "test"  # matches "tests", "test" buckets after lowercasing


def clamp01(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def band_for_score(score: int) -> str:
    if score <= 3:
        return "routine"
    if score <= 6:
        return "elevated"
    if score <= 8:
        return "high"
    return "critical"


def load_coverage_hotspots() -> dict[str, dict[str, Any]]:
    """Return ``freshness.canonical`` block from ``coverage-report.yaml`` or {}."""
    path = KG_DIR / "coverage-report.yaml"
    if not path.exists():
        return {}
    payload = load_yaml(path)
    freshness = payload.get("freshness") or {}
    canonical = freshness.get("canonical") or {}
    return canonical if isinstance(canonical, dict) else {}


def gather_hotspot_signals(
    node_ids: list[str],
    bundle: dict[str, Any],
    months: int,
) -> dict[str, dict[str, Any]]:
    """Pull hotspot/ownership signals for the requested nodes.

    Prefers ``coverage-report.yaml`` for cost; falls back to live
    ``compute_hotspots`` when the report is missing or a node isn't covered.
    """
    coverage = load_coverage_hotspots()
    needed = [nid for nid in node_ids if nid not in coverage]
    live: dict[str, dict[str, Any]] = {}
    if needed:
        live = compute_hotspots(bundle, months=months)

    result: dict[str, dict[str, Any]] = {}
    for nid in node_ids:
        record = coverage.get(nid) or live.get(nid) or {}
        result[nid] = {
            "hotspot_rank": record.get("hotspot_rank"),
            "hotspot_score": record.get("hotspot_score") or 0.0,
            "primary_owner": record.get("primary_owner"),
            "primary_owner_pct": record.get("primary_owner_pct") or 0,
            "bus_factor_flag": bool(record.get("bus_factor_flag")),
            "last_modified": record.get("last_modified"),
        }
    return result


def gather_cochange_signal(
    node_ids: list[str],
    bundle: dict[str, Any],
    months: int,
) -> dict[str, dict[str, Any]]:
    """Compute per-node co-change density and partner list."""
    commits = git_commits_with_files(months)
    all_files: set[str] = set()
    for files in commits:
        all_files.update(files)
    file_to_nodes = build_file_to_nodes(bundle, all_files)
    results = compute_cochanges(
        commits, file_to_nodes, COCHANGE_MIN_COMMITS, all_nodes=bundle["all_nodes"]
    )

    by_node: dict[str, dict[str, Any]] = {
        nid: {"partners": []} for nid in node_ids
    }
    for pair in results["node_pairs"]:
        a, b = pair["nodes"]
        co = pair["co_commits"]
        for nid, other in ((a, b), (b, a)):
            if nid in by_node:
                by_node[nid]["partners"].append({"node": other, "co_commits": co})

    commit_counts = results["node_commit_counts"]
    for nid, info in by_node.items():
        info["partners"].sort(key=lambda p: (-p["co_commits"], p["node"]))
        density = clamp01(len(info["partners"]) / COCHANGE_PARTNER_SATURATION)
        info["density"] = round(density, 2)
        info["partner_count"] = len(info["partners"])
        info["node_commit_count"] = commit_counts.get(nid, 0)
    return by_node


def collect_files_by_bucket(binding: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (test_files, impl_files) resolved from a binding's declared paths.

    A declared pattern's bucket is the dotted key path (e.g. ``backend.tests``
    or ``frontend.feature``). Anything whose final segment contains ``test`` is
    counted as a test path.
    """
    test_files: set[str] = set()
    impl_files: set[str] = set()
    for entry in binding.get("declared_paths", []):
        bucket = (entry.get("bucket") or "").lower()
        leaf = bucket.rsplit(".", 1)[-1]
        resolved = expand_declared_pattern(entry["pattern"])
        if TEST_BUCKET_TOKEN in leaf:
            test_files.update(resolved)
        else:
            impl_files.update(resolved)
    return sorted(test_files), sorted(impl_files)


def compute_test_gap(
    node_ids: list[str], bundle: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Per-node test_gap signal driven by code-index buckets."""
    by_node: dict[str, dict[str, Any]] = {}
    for nid in node_ids:
        binding = bundle["bindings"].get(nid) or {}
        test_files, impl_files = collect_files_by_bucket(binding)
        if not impl_files:
            gap = 0.0
        elif not test_files:
            gap = 1.0
        else:
            gap = clamp01(1.0 - len(test_files) / len(impl_files))
        by_node[nid] = {
            "test_files": len(test_files),
            "impl_files": len(impl_files),
            "test_gap": round(gap, 2),
        }
    return by_node


def signals_for_node(
    node_id: str,
    blast_summary: dict[str, Any],
    hotspot: dict[str, Any],
    cochange: dict[str, Any],
    test_gap: dict[str, Any],
) -> dict[str, float]:
    """Combine raw inputs into the five normalized signals."""
    direct = blast_summary.get("direct_node_count", 0)
    neighbor = blast_summary.get("neighbor_node_count", 0)
    blast = clamp01((direct + neighbor) / BLAST_SATURATION)
    hotspot_score = clamp01(float(hotspot.get("hotspot_score") or 0.0))
    cochange_density = clamp01(float(cochange.get("density") or 0.0))
    ownership = clamp01((hotspot.get("primary_owner_pct") or 0) / 100.0)
    gap = clamp01(float(test_gap.get("test_gap") or 0.0))
    return {
        "blast_count": round(blast, 2),
        "hotspot_score": round(hotspot_score, 2),
        "cochange_density": round(cochange_density, 2),
        "ownership_concentration": round(ownership, 2),
        "test_gap": round(gap, 2),
    }


def score_signals(signals: dict[str, float]) -> int:
    weighted = sum(WEIGHTS[name] * signals.get(name, 0.0) for name in WEIGHTS)
    return max(0, min(10, round(weighted)))


def build_recommendations(
    score: int,
    signals: dict[str, float],
    hotspot: dict[str, Any],
    test_gap: dict[str, Any],
    cochange: dict[str, Any],
) -> list[str]:
    recs: list[str] = []
    if score >= 9:
        recs.append(
            "kg.risk ≥ 9 — treat as critical; require senior reviewer plus "
            "`workstate.py decision --topic risk-acknowledgement` before merge."
        )
    elif score >= 7:
        recs.append("kg.risk ≥ 7 — additional reviewer required before merge.")
    if signals["hotspot_score"] >= 0.80 or (hotspot.get("hotspot_rank") or 99) <= 5:
        recs.append(
            f"Hotspot gate: hotspot_score {signals['hotspot_score']:.2f}, "
            f"rank {hotspot.get('hotspot_rank')} — second-reviewer evidence required "
            "(see agents/architect/references/hotspot-review-guide.md)."
        )
    if hotspot.get("bus_factor_flag"):
        owner = hotspot.get("primary_owner") or "primary_owner"
        recs.append(
            f"Bus-factor: loop in {owner} for explicit PR acknowledgement "
            f"(primary_owner_pct={hotspot.get('primary_owner_pct')})."
        )
    if signals["test_gap"] >= 0.5:
        recs.append(
            f"Test gap: {test_gap.get('test_files', 0)} test file(s) vs "
            f"{test_gap.get('impl_files', 0)} impl file(s) — add coverage before merge."
        )
    if signals["cochange_density"] >= 0.5:
        partners = ", ".join(
            f"{p['node']} ({p['co_commits']}×)" for p in cochange.get("partners", [])[:3]
        ) or "see cochange.py"
        recs.append(
            f"Hidden coupling: co-change density {signals['cochange_density']:.2f}; "
            f"inspect partners: {partners}."
        )
    if signals["blast_count"] >= 0.5:
        recs.append(
            "Wide blast radius — run `blast.py` and walk downstream nodes "
            "before merging."
        )
    return recs


def resolve_targets(
    args: argparse.Namespace, bundle: dict[str, Any]
) -> tuple[list[str], dict[str, Any], str]:
    """Return (node_ids, query, mode) for the requested target.

    Modes: ``symbol``, ``file``, ``node``. Symbol mode also returns a single
    canonical node (the symbol's ``node`` field).
    """
    if args.symbol_name:
        matches = match_symbol_by_name(args.symbol_name, bundle, node_id=args.symbol_node)
        if not matches:
            raise SystemExit(f"No symbols named: {args.symbol_name}")
        node_ids = sorted({s["node"] for s in matches if s.get("node")})
        query = {
            "symbol_name": args.symbol_name,
            "node": args.symbol_node,
            "matched_symbols": [s["id"] for s in matches],
        }
        return node_ids, query, "symbol"

    if args.target and args.target.startswith("symbol:"):
        sym = get_symbol_by_id(args.target, bundle)
        if sym is None:
            raise SystemExit(f"Unknown symbol id: {args.target}")
        node_ids = [sym["node"]] if sym.get("node") else []
        query = {"symbol_id": args.target, "matched_symbols": [args.target]}
        return node_ids, query, "symbol"

    if args.file_path:
        node_ids = sorted(node_ids_for_file(args.file_path, bundle))
        if not node_ids:
            raise SystemExit(f"No KG bindings found for: {args.file_path}")
        return node_ids, {"file": repo_relative(args.file_path)}, "file"

    if not args.target:
        raise SystemExit("Provide a node ID, --file, or --symbol.")

    normalized = normalize_target_id(args.target)
    node = bundle["all_nodes"].get(normalized)
    if node is None:
        raise SystemExit(f"Unknown node: {args.target}")
    if node.get("_kind") not in {None} and node.get("_kind") in {"feature", "story"}:
        # Risk score is meaningful per canonical node; mapping nodes get
        # decomposed into their canonical refs by the caller's blast pass.
        from blast import canonical_refs_from_mapping

        node_ids = sorted(canonical_refs_from_mapping(node)) or [normalized]
        query = {
            "feature_or_story": normalized,
            "canonical_nodes": node_ids,
        }
    else:
        node_ids = [normalized]
        query = {"node": normalized}
    return node_ids, query, "node"


def blast_summary_for(
    starting_ids: list[str],
    mode: str,
    bundle: dict[str, Any],
    symbol_query: dict[str, Any] | None,
) -> dict[str, Any]:
    if mode == "symbol":
        # When the entry is a symbol, walk caller/callee edges and reuse the
        # symbol blast summary structure.
        sym_ids = (symbol_query or {}).get("matched_symbols", [])
        starting_symbols = [
            s for s in (get_symbol_by_id(sid, bundle) for sid in sym_ids) if s is not None
        ]
        report = build_symbol_blast(starting_symbols, bundle, symbol_query or {})
        summary = report["summary"]
        return {
            "direct_node_count": summary.get("node_count", 0),
            "neighbor_node_count": summary.get("reached_symbol_count", 0),
            "policy_rule_count": 0,
            "resolved_file_count": summary.get("file_count", 0),
            "feature_count": 0,
        }
    report = build_blast_report(set(starting_ids), bundle, {})
    return report["summary"]


def build_report(
    node_ids: list[str],
    query: dict[str, Any],
    mode: str,
    bundle: dict[str, Any],
    months: int,
) -> dict[str, Any]:
    blast_summary = blast_summary_for(node_ids, mode, bundle, query)
    hotspots = gather_hotspot_signals(node_ids, bundle, months=months)
    cochanges = gather_cochange_signal(node_ids, bundle, months=months)
    test_gaps = compute_test_gap(node_ids, bundle)

    per_node: list[dict[str, Any]] = []
    for nid in node_ids:
        signals = signals_for_node(
            nid,
            blast_summary,
            hotspots.get(nid, {}),
            cochanges.get(nid, {}),
            test_gaps.get(nid, {}),
        )
        score = score_signals(signals)
        per_node.append(
            {
                "node": nid,
                "score": score,
                "band": band_for_score(score),
                "signals": signals,
                "raw": {
                    "blast": blast_summary,
                    "hotspot": hotspots.get(nid, {}),
                    "cochange": cochanges.get(nid, {}),
                    "test_gap": test_gaps.get(nid, {}),
                },
            }
        )

    per_node.sort(key=lambda item: (-item["score"], item["node"]))
    primary = per_node[0] if per_node else None

    recommendations: list[str] = []
    if primary:
        recommendations = build_recommendations(
            primary["score"],
            primary["signals"],
            primary["raw"]["hotspot"],
            primary["raw"]["test_gap"],
            primary["raw"]["cochange"],
        )

    return {
        "query": query,
        "mode": mode,
        "score": primary["score"] if primary else 0,
        "band": primary["band"] if primary else "routine",
        "signals": primary["signals"] if primary else {},
        "raw": primary["raw"] if primary else {},
        "primary_node": primary["node"] if primary else None,
        "per_node": per_node,
        "reviewer_recommendations": recommendations,
        "weights": WEIGHTS,
    }


def render_reason(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(
        f"Risk score: {report['score']}/10 ({report['band']}) "
        f"for {report['primary_node'] or report['query']}"
    )
    lines.append("")
    lines.append("Signals (weighted contribution to score):")
    for name, weight in WEIGHTS.items():
        value = report["signals"].get(name, 0.0)
        lines.append(f"  - {name:24s} {value:0.2f} × {weight} = {value * weight:0.2f}")
    raw = report.get("raw", {})
    hotspot = raw.get("hotspot", {})
    cochange = raw.get("cochange", {})
    test_gap = raw.get("test_gap", {})
    blast = raw.get("blast", {})
    lines.append("")
    lines.append("Raw inputs:")
    lines.append(
        f"  - blast: direct={blast.get('direct_node_count', 0)} "
        f"neighbor={blast.get('neighbor_node_count', 0)} "
        f"files={blast.get('resolved_file_count', 0)}"
    )
    lines.append(
        f"  - hotspot_rank={hotspot.get('hotspot_rank')} "
        f"owner={hotspot.get('primary_owner')} "
        f"pct={hotspot.get('primary_owner_pct')}% "
        f"bus_factor={hotspot.get('bus_factor_flag')}"
    )
    lines.append(
        f"  - cochange: density={cochange.get('density', 0.0)} "
        f"partners={len(cochange.get('partners', []))} "
        f"node_commits={cochange.get('node_commit_count', 0)}"
    )
    lines.append(
        f"  - tests: {test_gap.get('test_files', 0)} test / "
        f"{test_gap.get('impl_files', 0)} impl"
    )
    recs = report.get("reviewer_recommendations") or []
    if recs:
        lines.append("")
        lines.append("Reviewer recommendations:")
        for rec in recs:
            lines.append(f"  - {rec}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate KG signals into a 0-10 risk score for a canonical "
            "node, file, or symbol. Pre-flight check; raw artifacts remain "
            "authoritative per solution-ontology.yaml.authority.precedence."
        )
    )
    parser.add_argument(
        "target",
        nargs="?",
        help=(
            "Canonical node id (entity:submission), feature/story id (F0007 "
            "/ F0007-S0003), or symbol id (symbol:...)."
        ),
    )
    parser.add_argument(
        "--file",
        dest="file_path",
        help="Repo file path; resolves to one or more bound canonical nodes.",
    )
    parser.add_argument(
        "--symbol",
        dest="symbol_name",
        help="Symbol name (e.g. TransitionAsync); requires symbol-index.yaml.",
    )
    parser.add_argument(
        "--node",
        dest="symbol_node",
        help="Scope --symbol lookups to one canonical node id.",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=DEFAULT_MONTHS,
        help=(
            f"Look back N months for hotspot/cochange signals (default: {DEFAULT_MONTHS})."
        ),
    )
    parser.add_argument(
        "--reason",
        action="store_true",
        help="Emit a human-readable narrative instead of JSON.",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--telemetry-file", type=Path, default=None)
    args = parser.parse_args()

    modes = sum(bool(x) for x in (args.target, args.file_path, args.symbol_name))
    if modes == 0:
        parser.error("Provide a node id, --file, or --symbol.")
    if modes > 1:
        parser.error("Use only one of: positional target, --file, --symbol.")

    bundle = load_bundle()
    node_ids, query, mode = resolve_targets(args, bundle)
    report = build_report(node_ids, query, mode, bundle, months=args.months)

    if args.reason:
        sys.stdout.write(render_reason(report) + "\n")
    else:
        json.dump(report, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")

    emit_telemetry(
        args.telemetry_file,
        args.run_id,
        "risk",
        {
            "query": query,
            "mode": mode,
            "nodes_returned": node_ids,
            "nodes_count": len(node_ids),
            "score": report["score"],
            "band": report["band"],
            "recommendation_count": len(report["reviewer_recommendations"]),
            "empty_scope": not node_ids,
            "ambiguous_count": 0,
            "hint_emitted": False,
            "confidence_band": "high" if node_ids else "low",
            "tokens_estimated": estimate_tokens(report),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

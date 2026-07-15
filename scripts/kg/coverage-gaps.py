#!/usr/bin/env python3
"""coverage-gaps: projection over unbound-but-referenced.yaml.

Surfaces invocations that originate in files outside code-index.yaml
bindings but target bound symbols — the same data validate.py
--check-coverage-gaps gates on. Default exclusions filter out test
files where the test is the source, migrations, scripts/, and tools/
so the first run doesn't drown reviewers; opt back in with
--include-excluded.

Usage:
    python3 scripts/kg/coverage-gaps.py                  # by source file (default)
    python3 scripts/kg/coverage-gaps.py --by-target      # group by bound symbol
    python3 scripts/kg/coverage-gaps.py --include-excluded
    python3 scripts/kg/coverage-gaps.py --exclude 'engine/sandbox/**'
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import yaml

from kg_common import KG_DIR, emit_telemetry, estimate_tokens

SIDECAR_PATH = KG_DIR / "unbound-but-referenced.yaml"

DEFAULT_EXCLUDES = (
    "**/tests/**",
    "**/test/**",
    "**/*Tests.cs",
    "**/*Test.cs",
    "**/*.test.ts",
    "**/*.test.tsx",
    "**/*.test.js",
    "**/*.test.jsx",
    "**/*.spec.ts",
    "**/*.spec.tsx",
    "**/*.spec.js",
    "**/*.spec.jsx",
    "**/migrations/**",
    "scripts/**",
    "tools/**",
)


def _matches_any(path: str, patterns: Iterable[str]) -> str | None:
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return pat
    return None


def load_sidecar(path: Path) -> dict[str, Any] | None:
    """Read the sidecar. Returns None when missing — caller warns and exits 0
    per memo §1 ("degrade gracefully if the file is absent")."""
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SystemExit(
            f"coverage-gaps: {path} is not a mapping (got {type(data).__name__})"
        )
    return data


def filter_invocations(
    invocations: list[dict[str, Any]], excludes: tuple[str, ...]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split invocations into (kept, excluded) by source_file glob match."""
    kept: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for inv in invocations:
        src = inv.get("source_file", "")
        matched = _matches_any(src, excludes)
        if matched is None:
            kept.append(inv)
        else:
            excluded.append({**inv, "excluded_by": matched})
    return kept, excluded


def _target_key(inv: dict[str, Any]) -> tuple[str, str]:
    """Stable key for an invocation's target — supports both shapes
    (resolved `target_symbol` and unresolved `target_name`/`target_container`).
    """
    sym = inv.get("target_symbol")
    if sym:
        return ("symbol", sym)
    container = inv.get("target_container") or ""
    name = inv.get("target_name") or ""
    return ("name", f"{container}.{name}")


def _target_label(inv: dict[str, Any]) -> dict[str, Any]:
    """Compact target descriptor for output."""
    sym = inv.get("target_symbol")
    if sym:
        return {"target_symbol": sym, "target_node": inv.get("target_node")}
    return {
        "target_name": inv.get("target_name"),
        "target_container": inv.get("target_container"),
        "target_node": inv.get("target_node"),
        "unresolved": True,
    }


def group_by_source(invocations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_file: dict[str, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    for inv in invocations:
        src = inv.get("source_file", "")
        tkey = _target_key(inv)
        bucket = by_file[src].setdefault(
            tkey,
            {**_target_label(inv), "lines": []},
        )
        line = inv.get("source_line")
        if line is not None:
            bucket["lines"].append(line)

    out: list[dict[str, Any]] = []
    for src in sorted(by_file):
        targets = []
        for target in by_file[src].values():
            target["lines"] = sorted(set(target["lines"]))
            targets.append(target)
        targets.sort(
            key=lambda t: (
                t.get("target_node") or "",
                t.get("target_symbol") or t.get("target_name") or "",
            )
        )
        out.append(
            {
                "source_file": src,
                "invocations": sum(len(t["lines"]) for t in targets),
                "targets": targets,
            }
        )
    return out


def group_by_target(invocations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_target: dict[tuple[str, str], dict[str, Any]] = {}
    for inv in invocations:
        tkey = _target_key(inv)
        entry = by_target.setdefault(
            tkey,
            {**_target_label(inv), "sources": {}},
        )
        src = inv.get("source_file", "")
        src_bucket = entry["sources"].setdefault(src, [])
        line = inv.get("source_line")
        if line is not None:
            src_bucket.append(line)

    out: list[dict[str, Any]] = []
    for entry in by_target.values():
        sources = []
        for src, lines in entry["sources"].items():
            sources.append({"source_file": src, "lines": sorted(set(lines))})
        sources.sort(key=lambda s: s["source_file"])
        entry["sources"] = sources
        entry["invocations"] = sum(len(s["lines"]) for s in sources)
        out.append(entry)

    out.sort(
        key=lambda t: (
            t.get("target_node") or "",
            t.get("target_symbol") or t.get("target_name") or "",
        )
    )
    return out


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"generated_at: {payload.get('generated_at')}",
        f"total_invocations: {payload['totals']['raw']}",
        f"after exclusions: {payload['totals']['after_filter']}  "
        f"(excluded: {payload['totals']['excluded']})",
        "",
    ]
    if payload["mode"] == "by-source":
        lines.append(f"source files ({len(payload['source_files'])}):")
        for entry in payload["source_files"]:
            lines.append(f"  - {entry['source_file']}  ({entry['invocations']} call(s))")
            for t in entry["targets"]:
                tag = t.get("target_symbol") or (
                    f"{t.get('target_container')}.{t.get('target_name')} [unresolved]"
                )
                lines.append(
                    f"      -> {tag}  [{t.get('target_node')}]  lines={t['lines']}"
                )
    else:
        lines.append(f"targets ({len(payload['targets'])}):")
        for t in payload["targets"]:
            tag = t.get("target_symbol") or (
                f"{t.get('target_container')}.{t.get('target_name')} [unresolved]"
            )
            lines.append(
                f"  - {tag}  [{t.get('target_node')}]  ({t['invocations']} call(s))"
            )
            for s in t["sources"]:
                lines.append(f"      from {s['source_file']}  lines={s['lines']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Projection over unbound-but-referenced.yaml. Raw artifacts "
            "remain authoritative; this is a routing aid."
        )
    )
    parser.add_argument(
        "--by-target",
        action="store_true",
        help="Group by bound symbol instead of by source file.",
    )
    parser.add_argument(
        "--include-excluded",
        action="store_true",
        help="Disable default exclusions (tests-as-source, migrations, scripts/, tools/).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="Additional source-file glob to exclude (repeatable).",
    )
    parser.add_argument(
        "--format",
        choices=("json", "yaml", "text"),
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--sidecar",
        type=Path,
        default=SIDECAR_PATH,
        help=f"Override sidecar path (default: {SIDECAR_PATH}).",
    )
    parser.add_argument(
        "--run-id",
        help="Correlation ID stamped onto emitted telemetry.",
    )
    parser.add_argument(
        "--telemetry-file",
        type=Path,
        help="Append one JSONL telemetry event for this invocation.",
    )
    args = parser.parse_args()

    sidecar = load_sidecar(args.sidecar)

    if sidecar is None:
        sys.stderr.write(
            f"coverage-gaps: {args.sidecar} not found; nothing to project. "
            "Run scripts/kg/symbols.py to regenerate the symbol layer.\n"
        )
        event = {
            "mode": "by-target" if args.by_target else "by-source",
            "raw_invocations": 0,
            "after_filter": 0,
            "excluded": 0,
            "nodes_returned": [],
            "nodes_count": 0,
            "empty_scope": True,
            "missing_sidecar": True,
            "confidence_band": "low",
            "tokens_estimated": 0,
        }
        emit_telemetry(args.telemetry_file, args.run_id, "coverage-gaps", event)
        return 0

    excludes: tuple[str, ...] = tuple(args.exclude)
    if not args.include_excluded:
        excludes = (*DEFAULT_EXCLUDES, *excludes)

    invocations = sidecar.get("invocations") or []
    kept, excluded = filter_invocations(invocations, excludes)

    nodes_returned = sorted(
        {inv["target_node"] for inv in kept if inv.get("target_node")}
    )
    empty_scope = not kept

    payload: dict[str, Any] = {
        "mode": "by-target" if args.by_target else "by-source",
        "version": sidecar.get("version"),
        "generated_at": sidecar.get("generated_at"),
        "summary_source": sidecar.get("summary"),
        "totals": {
            "raw": len(invocations),
            "after_filter": len(kept),
            "excluded": len(excluded),
        },
        "exclusions_applied": list(excludes),
        "affected_nodes": nodes_returned,
        "telemetry": {
            "tokens_estimated": 0,
            "confidence_band": "low" if empty_scope else "high",
        },
    }

    if args.by_target:
        payload["targets"] = group_by_target(kept)
    else:
        payload["source_files"] = group_by_source(kept)

    payload["telemetry"]["tokens_estimated"] = estimate_tokens(payload)

    event = {
        "mode": payload["mode"],
        "raw_invocations": len(invocations),
        "after_filter": len(kept),
        "excluded": len(excluded),
        "nodes_returned": nodes_returned,
        "nodes_count": len(nodes_returned),
        "empty_scope": empty_scope,
        "missing_sidecar": False,
        "confidence_band": payload["telemetry"]["confidence_band"],
        "tokens_estimated": payload["telemetry"]["tokens_estimated"],
    }
    emit_telemetry(args.telemetry_file, args.run_id, "coverage-gaps", event)

    if args.format == "json":
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif args.format == "yaml":
        yaml.safe_dump(payload, sys.stdout, sort_keys=False)
    else:
        sys.stdout.write(render_text(payload))

    return 0


if __name__ == "__main__":
    sys.exit(main())

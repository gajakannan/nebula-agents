#!/usr/bin/env python3
"""diff-impact: compute the symbol-graph blast radius of a git range.

Reads the diff for `<git-range>`, maps changed line ranges to symbols via
the `line`/`end_line` rule (memo §2), walks `callers` transitively up to
`--depth` hops, and reports the canonical nodes affected.

Usage:
    python3 scripts/kg/diff-impact.py origin/main..HEAD
    python3 scripts/kg/diff-impact.py HEAD~5..HEAD --depth 3
    python3 scripts/kg/diff-impact.py abc123 --format yaml
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import yaml

from kg_common import (
    REPO_ROOT,
    emit_telemetry,
    estimate_tokens,
    load_bundle,
    repo_relative,
)

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,(?P<count>\d+))? @@")
DEFAULT_DEPTH = 2


def run_git(args: list[str]) -> str:
    """Run a git command from the repo root; return stdout (text)."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} exited {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


def validate_range(range_: str) -> None:
    """Ensure the range is something git can resolve before doing more work."""
    try:
        run_git(["rev-list", "--max-count=1", range_])
    except RuntimeError as exc:
        raise SystemExit(f"diff-impact: cannot resolve git range '{range_}': {exc}")


def changed_files(range_: str) -> list[dict[str, str]]:
    """Return per-path change records with status and (for renames) old path.

    Status codes: M (modified), A (added), D (deleted), R (renamed),
    C (copied), T (type change). Renames include `from_path`; everything
    else has `path` only.
    """
    out = run_git(["diff", "--name-status", "--find-renames", "-z", range_])
    tokens = out.split("\0")
    records: list[dict[str, str]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if not tok:
            i += 1
            continue
        status = tok[0]
        if status in ("R", "C"):
            from_path = tokens[i + 1]
            to_path = tokens[i + 2]
            records.append(
                {
                    "status": status,
                    "from_path": from_path,
                    "path": to_path,
                    "similarity": tok[1:],
                }
            )
            i += 3
        else:
            records.append({"status": status, "path": tokens[i + 1]})
            i += 2
    return records


def hunk_ranges(range_: str, path: str) -> list[tuple[int, int]]:
    """Parse `+START,COUNT` hunks from `git diff --unified=0` for one path.

    Returns `[start, end)` line ranges on the *new* side. Pure-deletion hunks
    (count=0) are dropped — they have no new lines to map to symbols.
    """
    out = run_git(["diff", "--unified=0", range_, "--", path])
    ranges: list[tuple[int, int]] = []
    for line in out.splitlines():
        m = HUNK_RE.match(line)
        if not m:
            continue
        start = int(m.group("start"))
        count = int(m.group("count") or 1)
        if count == 0:
            continue
        ranges.append((start, start + count))
    return ranges


def symbols_in_ranges(
    file_path: str,
    ranges: list[tuple[int, int]],
    symbols_by_file: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Symbols in `file_path` whose `[line, end_line]` intersects any range.

    Falls back to approach A from memo §2 — next-symbol.line as the end —
    when `end_line` is absent on a record (legacy entries during rollout).
    """
    file_syms = symbols_by_file.get(file_path) or []
    if not file_syms:
        return []

    # Build per-symbol [start, end] inclusive line spans.
    ordered = sorted(file_syms, key=lambda s: s.get("line") or 0)
    spans: list[tuple[int, int, dict[str, Any]]] = []
    for idx, sym in enumerate(ordered):
        start = sym.get("line") or 0
        end = sym.get("end_line")
        if end is None:
            # Fallback approach A: run to the next symbol's start - 1, or EOF.
            if idx + 1 < len(ordered):
                end = max(start, (ordered[idx + 1].get("line") or start) - 1)
            else:
                end = 10**9  # EOF sentinel
        spans.append((start, end, sym))

    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hunk_start, hunk_end in ranges:
        for span_start, span_end, sym in spans:
            if span_start < hunk_end and hunk_start <= span_end:
                sid = sym.get("id")
                if sid and sid not in seen:
                    seen.add(sid)
                    matched.append(sym)
    return matched


def walk_callers(
    seed_ids: list[str],
    symbols_by_id: dict[str, dict[str, Any]],
    max_depth: int,
) -> list[dict[str, Any]]:
    """BFS over `callers` edges starting from `seed_ids`.

    Returns one record per *new* symbol reached, with the minimum hop count
    at which it was discovered. Seeds themselves are not included — only
    upstream callers are.
    """
    if max_depth <= 0:
        return []

    discovered: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque()
    seen_seeds = set(seed_ids)
    for sid in seed_ids:
        for caller in symbols_by_id.get(sid, {}).get("callers", []) or []:
            if caller in seen_seeds:
                continue
            if caller not in discovered or discovered[caller] > 1:
                discovered[caller] = 1
                queue.append((caller, 1))

    while queue:
        cur_id, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for caller in symbols_by_id.get(cur_id, {}).get("callers", []) or []:
            if caller in seen_seeds:
                continue
            if caller not in discovered or discovered[caller] > depth + 1:
                discovered[caller] = depth + 1
                queue.append((caller, depth + 1))

    results: list[dict[str, Any]] = []
    for sid, hops in sorted(discovered.items(), key=lambda kv: (kv[1], kv[0])):
        sym = symbols_by_id.get(sid)
        node = sym.get("node") if sym else None
        results.append({"id": sid, "node": node, "hops": hops})
    return results


_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    s = re.sub(r"(?<!^)(?=[A-Z])", "-", value).lower()
    return _SLUG_NON_ALNUM.sub("-", s).strip("-")


def derive_pre_rename_id(
    to_id: str, from_path: str, to_path: str
) -> tuple[str | None, bool]:
    """Best-effort pre-rename id derivation for whole-file renames.

    Substitutes the to-file's stem slug with the from-file's stem slug
    inside `to_id`. Returns (candidate_id, unresolved_pre_rename). When the
    substitution doesn't change the id (e.g., the file stem slug wasn't
    part of the id container), we return None and mark unresolved — the
    reviewer matches by hand per memo §3.
    """
    from_stem = _slug(Path(from_path).stem)
    to_stem = _slug(Path(to_path).stem)
    if not from_stem or not to_stem or from_stem == to_stem:
        return None, True
    if to_stem not in to_id:
        return None, True
    candidate = to_id.replace(to_stem, from_stem)
    if candidate == to_id:
        return None, True
    return candidate, False


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"range: {payload['range']}",
        f"depth: {payload['depth']}",
        "",
        f"changed symbols ({len(payload['changed_symbols'])}):",
    ]
    for entry in payload["changed_symbols"]:
        rename = f"  (renamed from {entry['rename']['from_id'] or '?'})" if entry.get("rename") else ""
        lines.append(f"  - {entry['id']}  [{entry['node']}]{rename}")
    lines.append("")
    lines.append(f"blast symbols ({len(payload['blast_symbols'])}):")
    for entry in payload["blast_symbols"]:
        lines.append(f"  - hop {entry['hops']}: {entry['id']}  [{entry['node']}]")
    lines.append("")
    lines.append(f"affected nodes ({len(payload['affected_nodes'])}):")
    for node in payload["affected_nodes"]:
        lines.append(f"  - {node}")
    if payload.get("renames"):
        lines.append("")
        lines.append(f"renames ({len(payload['renames'])}):")
        for r in payload["renames"]:
            lines.append(
                f"  - {r['from_path']} -> {r['to_path']} "
                f"(from_id={r['from_id'] or '?'}, to_id={r['to_id']}, "
                f"unresolved_pre_rename={r['unresolved_pre_rename']})"
            )
    if payload.get("unresolved_paths"):
        lines.append("")
        lines.append("unresolved paths (no current symbol coverage):")
        for p in payload["unresolved_paths"]:
            lines.append(f"  - {p}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compute symbol-graph blast radius for a git range. "
            "Raw artifacts remain the source of truth; this is a routing aid."
        )
    )
    parser.add_argument(
        "range",
        help="Any string `git diff` accepts (e.g. origin/main..HEAD, HEAD~5..HEAD, <sha>).",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=DEFAULT_DEPTH,
        help=f"Number of caller hops to walk (default: {DEFAULT_DEPTH}).",
    )
    parser.add_argument(
        "--format",
        choices=("json", "yaml", "text"),
        default="json",
        help="Output format (default: json).",
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

    if args.depth < 0:
        parser.error("--depth must be >= 0.")

    validate_range(args.range)
    bundle = load_bundle()
    symbols_by_file = bundle["symbols_by_file"]
    symbols_by_id = bundle["symbols_by_id"]

    files = changed_files(args.range)

    changed_records: list[dict[str, Any]] = []
    seen_changed_ids: set[str] = set()
    rename_entries: list[dict[str, Any]] = []
    unresolved_paths: list[str] = []

    for fr in files:
        status = fr["status"]
        path = fr["path"]

        if status == "D":
            # Pure deletion — no current symbols to attribute to.
            unresolved_paths.append(path)
            continue

        # Compute changed line ranges. Added files: entire file is "changed",
        # but unified=0 still gives a +1,N hunk so this falls out naturally.
        try:
            ranges = hunk_ranges(args.range, path)
        except RuntimeError:
            unresolved_paths.append(path)
            continue

        if not ranges:
            continue

        matched = symbols_in_ranges(path, ranges, symbols_by_file)
        if not matched and (status in ("M", "A", "T")):
            if path in symbols_by_file:
                # File is bound but no symbol overlapped — note but don't error.
                unresolved_paths.append(path)
            else:
                unresolved_paths.append(path)

        for sym in matched:
            sid = sym["id"]
            if sid in seen_changed_ids:
                continue
            seen_changed_ids.add(sid)

            rename_info: dict[str, Any] | None = None
            if status in ("R", "C"):
                from_id, unresolved = derive_pre_rename_id(
                    sid, fr["from_path"], path
                )
                rename_info = {"from_id": from_id, "unresolved_pre_rename": unresolved}

            changed_records.append(
                {
                    "id": sid,
                    "node": sym.get("node"),
                    "file": sym.get("file"),
                    "rename": rename_info,
                }
            )

        if status in ("R", "C"):
            for sym in matched:
                from_id, unresolved = derive_pre_rename_id(
                    sym["id"], fr["from_path"], path
                )
                rename_entries.append(
                    {
                        "from_path": fr["from_path"],
                        "to_path": path,
                        "from_id": from_id,
                        "to_id": sym["id"],
                        "unresolved_pre_rename": unresolved,
                    }
                )

    seed_ids = [r["id"] for r in changed_records]
    blast = walk_callers(seed_ids, symbols_by_id, args.depth)

    affected_nodes = sorted(
        {r["node"] for r in changed_records if r.get("node")}
        | {b["node"] for b in blast if b.get("node")}
    )

    empty_scope = not changed_records
    confidence_band = "low" if empty_scope else "high"

    payload: dict[str, Any] = {
        "range": args.range,
        "depth": args.depth,
        "changed_symbols": changed_records,
        "blast_symbols": blast,
        "affected_nodes": affected_nodes,
        "renames": rename_entries,
        "unresolved_paths": unresolved_paths,
        "source_precedence": bundle["ontology"]["authority"]["precedence"],
        "telemetry": {
            "tokens_estimated": 0,  # filled below
            "confidence_band": confidence_band,
        },
    }
    payload["telemetry"]["tokens_estimated"] = estimate_tokens(payload)

    event = {
        "range": args.range,
        "depth": args.depth,
        "changed_symbols_count": len(changed_records),
        "blast_symbols_count": len(blast),
        "nodes_returned": affected_nodes,
        "nodes_count": len(affected_nodes),
        "renames_count": len(rename_entries),
        "unresolved_paths_count": len(unresolved_paths),
        "empty_scope": empty_scope,
        "confidence_band": confidence_band,
        "tokens_estimated": payload["telemetry"]["tokens_estimated"],
    }
    emit_telemetry(args.telemetry_file, args.run_id, "diff-impact", event)

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

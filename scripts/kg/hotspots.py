#!/usr/bin/env python3
"""Compute git-derived hotspot, ownership, and bus-factor signals per canonical node.

Reads git history (filtered for significant commits — no merges, no diff-of-zero
entries, no commits whose entire footprint is lockfile bumps), maps each touched
file back to canonical nodes via code-index bindings, and emits Phase 3
freshness fields:

- ``hotspot_rank``     — 1 = hottest node in the product (descending by score).
- ``hotspot_score``    — normalized 0.0–1.0; raw score is
  ``Σ commits_per_bound_file × decay(180-day half-life) × file_count``.
- ``primary_owner``    — author with most line-touches (insertions + deletions
  via ``git log --numstat``).
- ``primary_owner_pct``— integer percentage of touched lines attributed to
  ``primary_owner``.
- ``bus_factor_flag``  — true when ``primary_owner_pct > 80``.
- ``last_modified``    — latest significant-commit date among bound files.

The hotspot layer is NOT authoritative. Raw source files win per
``solution-ontology.yaml.authority.precedence``. These signals are routing
aids for reviewers, architects, and security.

Usage:
    python3 scripts/kg/hotspots.py
    python3 scripts/kg/hotspots.py --months 6
    python3 scripts/kg/hotspots.py --node entity:customer
    python3 scripts/kg/hotspots.py --yaml

``validate.py --write-coverage-report`` calls ``compute_hotspots`` as a library
and merges the result into ``coverage-report.yaml.freshness.canonical``.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from kg_common import (
    REPO_ROOT,
    emit_telemetry,
    estimate_tokens,
    load_bundle,
    match_bindings_for_path,
)


HALF_LIFE_DAYS = 180
DECAY_RATE = math.log(2) / HALF_LIFE_DAYS
DEFAULT_MONTHS = 12
BUS_FACTOR_THRESHOLD = 80
LOCKFILE_NAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
    "Gemfile.lock",
}


def collect_commits(months: int) -> list[dict[str, Any]]:
    """Return significant commits with per-file numstat.

    Each commit: {sha, ts: datetime, email, file_lines: [(path, lines_changed)]}.
    Renames are followed via ``-M`` so ownership history survives moves.
    """
    cmd = [
        "git",
        "log",
        f"--since={months} months ago",
        "--no-merges",
        "--numstat",
        "-M",
        "--diff-filter=AMRC",
        "--format=>>>%H|%aI|%ae",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if proc.returncode != 0:
        raise SystemExit(f"git log failed: {proc.stderr.strip()}")

    commits: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in proc.stdout.splitlines():
        if line.startswith(">>>"):
            if current and current["file_lines"]:
                commits.append(current)
            sha, ts_iso, email = line[3:].split("|", 2)
            current = {
                "sha": sha,
                "ts": datetime.fromisoformat(ts_iso),
                "email": email,
                "file_lines": [],
            }
            continue
        if not line.strip() or current is None:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        adds, dels, fpath = parts[0], parts[1], parts[2]
        # numstat reports "-\t-\t<binary>" for binary files; skip them.
        if adds == "-" or dels == "-":
            continue
        try:
            lines_changed = int(adds) + int(dels)
        except ValueError:
            continue
        # Rename payloads can look like "foo => bar" or "{old => new}". The
        # post-rename path is what we want for ownership and freshness.
        if " => " in fpath:
            fpath = _post_rename_path(fpath)
        current["file_lines"].append((fpath, lines_changed))

    if current and current["file_lines"]:
        commits.append(current)

    return [c for c in commits if _is_significant(c)]


def _post_rename_path(raw: str) -> str:
    """Resolve ``foo/{old => new}/bar.cs`` → ``foo/new/bar.cs``."""
    if "{" in raw and " => " in raw:
        before, _, after = raw.partition("{")
        inner, _, tail = after.partition("}")
        _, _, new_part = inner.partition(" => ")
        return f"{before}{new_part}{tail}".replace("//", "/")
    if " => " in raw:
        _, _, new = raw.partition(" => ")
        return new.strip()
    return raw


def _is_significant(commit: dict[str, Any]) -> bool:
    files = [f for f, _ in commit["file_lines"]]
    if not files:
        return False
    if all(Path(f).name in LOCKFILE_NAMES for f in files):
        return False
    return True


def _days_between(ts: datetime, now: datetime) -> float:
    return max(0.0, (now - ts).total_seconds() / 86400.0)


def compute_hotspots(
    bundle: dict[str, Any],
    months: int = DEFAULT_MONTHS,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """Compute Phase 3 freshness fields keyed by canonical node id.

    Library entry point used by ``validate.py --write-coverage-report``.
    """
    now = now or datetime.now(UTC)
    commits = collect_commits(months)

    # Cache file → [node_id] to avoid re-matching the same path many times.
    file_to_nodes: dict[str, list[str]] = {}
    touched_files: set[str] = set()
    for commit in commits:
        for fpath, _ in commit["file_lines"]:
            touched_files.add(fpath)
    for fpath in touched_files:
        matches = match_bindings_for_path(fpath, bundle)
        if matches:
            file_to_nodes[fpath] = [m["id"] for m in matches]

    decayed_per_file: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    author_lines: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    last_modified: dict[str, datetime] = {}

    for commit in commits:
        age_days = _days_between(commit["ts"], now)
        weight = math.exp(-DECAY_RATE * age_days)
        for fpath, lines_changed in commit["file_lines"]:
            node_ids = file_to_nodes.get(fpath)
            if not node_ids:
                continue
            for nid in node_ids:
                decayed_per_file[nid][fpath] += weight
                author_lines[nid][commit["email"]] += lines_changed
                if nid not in last_modified or commit["ts"] > last_modified[nid]:
                    last_modified[nid] = commit["ts"]

    raw_scores: dict[str, float] = {}
    for nid, per_file in decayed_per_file.items():
        raw_scores[nid] = sum(per_file.values()) * len(per_file)

    max_score = max(raw_scores.values(), default=0.0)
    ranked = sorted(raw_scores.items(), key=lambda kv: (-kv[1], kv[0]))
    rank_by_node = {nid: idx + 1 for idx, (nid, _) in enumerate(ranked)}

    result: dict[str, dict[str, Any]] = {}
    for nid, raw in raw_scores.items():
        touches = author_lines.get(nid, {})
        total = sum(touches.values())
        primary_owner: str | None = None
        primary_pct = 0
        if total > 0:
            primary_owner, top_lines = max(touches.items(), key=lambda kv: (kv[1], kv[0]))
            primary_pct = round(100 * top_lines / total)
        ts = last_modified.get(nid)
        result[nid] = {
            "hotspot_rank": rank_by_node[nid],
            "hotspot_score": round(raw / max_score, 2) if max_score > 0 else 0.0,
            "primary_owner": primary_owner,
            "primary_owner_pct": primary_pct,
            "bus_factor_flag": primary_pct > BUS_FACTOR_THRESHOLD,
            "last_modified": ts.date().isoformat() if ts else None,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute hotspot/ownership/bus-factor signals per canonical node."
    )
    parser.add_argument(
        "--months",
        type=int,
        default=DEFAULT_MONTHS,
        help=f"Look back N months in git history (default: {DEFAULT_MONTHS}).",
    )
    parser.add_argument(
        "--node",
        dest="node_filter",
        help="Restrict output to a single canonical node id.",
    )
    parser.add_argument(
        "--yaml",
        dest="as_yaml",
        action="store_true",
        help="Emit YAML instead of JSON.",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--telemetry-file", type=Path, default=None)
    args = parser.parse_args()

    bundle = load_bundle()
    signals = compute_hotspots(bundle, months=args.months)
    if args.node_filter:
        signals = {k: v for k, v in signals.items() if k == args.node_filter}

    payload = {
        "version": 0,
        "summary": {
            "months_analyzed": args.months,
            "nodes_with_signals": len(signals),
            "bus_factor_count": sum(1 for v in signals.values() if v["bus_factor_flag"]),
        },
        "signals": signals,
    }

    if args.as_yaml:
        yaml.safe_dump(payload, sys.stdout, sort_keys=False, allow_unicode=False)
    else:
        json.dump(payload, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")

    emit_telemetry(
        args.telemetry_file,
        args.run_id,
        "hotspots",
        {
            "nodes_returned": sorted(signals.keys()),
            "nodes_count": len(signals),
            "bus_factor_count": payload["summary"]["bus_factor_count"],
            "months_analyzed": args.months,
            "empty_scope": not signals,
            "ambiguous_count": 0,
            "hint_emitted": False,
            "confidence_band": "high" if signals else "low",
            "tokens_estimated": estimate_tokens(payload),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

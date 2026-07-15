#!/usr/bin/env python3
"""Generate decisions-index.yaml from inline decision markers.

Walks only implementation files declared in code-index.yaml. The resulting
decisions-index.yaml is a retrieval aid for local code rationale; raw source,
ADRs, and canonical node rationale remain authoritative.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from kg_common import (
    KG_DIR,
    REPO_ROOT,
    emit_telemetry,
    estimate_tokens,
    expand_declared_pattern,
    load_bundle,
    match_symbols_for_path,
    normalize_repo_path,
)


DECISIONS_INDEX_PATH = KG_DIR / "decisions-index.yaml"
SUPPORTED_EXTENSIONS = {".cs", ".ts", ".tsx", ".py"}
KINDS = {"WHY", "DECISION", "TRADEOFF", "SUPERSEDES"}
LINE_MARKER_RE = re.compile(
    r"(?:^|\s)(?://|#)\s*(WHY|DECISION|TRADEOFF|SUPERSEDES):\s*(.+?)\s*$",
    re.IGNORECASE,
)
BARE_MARKER_RE = re.compile(
    r"^(WHY|DECISION|TRADEOFF|SUPERSEDES):\s*(.+?)\s*$",
    re.IGNORECASE,
)
JSDOC_MARKER_RE = re.compile(
    r"^@(?P<tag>why|decision|tradeoff|supersedes)\b\s*:?\s*(?P<text>.+?)\s*$",
    re.IGNORECASE,
)
ADR_REF_RE = re.compile(
    r"\b(?:ADR[-\s:]?|adr:)([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)\b",
    re.IGNORECASE,
)
SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class DecisionRecord:
    id: str
    file: str
    line: int
    kind: str
    text: str
    resolved_node: str | None
    resolved_symbol: str | None = None
    candidate_nodes: list[str] | None = None
    supersedes_adr: str | None = None

    def to_index_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {k: v for k, v in payload.items() if v not in (None, [], {})}


def slug(value: str) -> str:
    stem = Path(value).with_suffix("").as_posix().lower()
    cleaned = SLUG_RE.sub("-", stem).strip("-")
    return cleaned or "root"


def decision_id(file_rel: str, line: int, kind: str, seen: set[str]) -> str:
    base = f"decision:{slug(file_rel)}-l{line}-{kind.lower()}"
    candidate = base
    suffix = 2
    while candidate in seen:
        candidate = f"{base}-{suffix}"
        suffix += 1
    seen.add(candidate)
    return candidate


def declared_code_files(bundle: dict[str, Any]) -> dict[str, set[str]]:
    """Return repo-relative implementation files mapped to bound node IDs."""
    files: dict[str, set[str]] = {}
    for binding in bundle["bindings"].values():
        node_id = binding["id"]
        for entry in binding.get("declared_paths", []):
            for rel in expand_declared_pattern(entry["pattern"]):
                normalized = normalize_repo_path(rel)
                path = REPO_ROOT / normalized
                if path.suffix not in SUPPORTED_EXTENSIONS or not path.is_file():
                    continue
                files.setdefault(normalized, set()).add(node_id)
    return files


def strip_block_prefix(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("/**"):
        stripped = stripped[3:].strip()
    elif stripped.startswith("/*"):
        stripped = stripped[2:].strip()
    if stripped.endswith("*/"):
        stripped = stripped[:-2].strip()
    if stripped.startswith("*"):
        stripped = stripped[1:].strip()
    return stripped


def extract_marker(line: str) -> tuple[str, str] | None:
    match = LINE_MARKER_RE.search(line)
    if match:
        return match.group(1).upper(), match.group(2).strip()

    stripped = line.strip()
    if not stripped.startswith(("/*", "*")):
        return None

    cleaned = strip_block_prefix(line)
    match = BARE_MARKER_RE.match(cleaned)
    if match:
        return match.group(1).upper(), match.group(2).strip()

    match = JSDOC_MARKER_RE.match(cleaned)
    if match:
        return match.group("tag").upper(), match.group("text").strip()

    return None


def extract_adr_ref(text: str) -> str | None:
    match = ADR_REF_RE.search(text)
    if not match:
        return None
    return f"adr:{match.group(1).lower()}"


def nearest_symbol(
    file_rel: str,
    line: int,
    node_ids: set[str],
    bundle: dict[str, Any],
) -> dict[str, Any] | None:
    symbols = [
        symbol
        for symbol in match_symbols_for_path(file_rel, bundle)
        if not node_ids or symbol.get("node") in node_ids
    ]
    if not symbols:
        return None

    symbols.sort(key=lambda item: item.get("line") or 0)
    before = [s for s in symbols if isinstance(s.get("line"), int) and s["line"] <= line]
    after = [s for s in symbols if isinstance(s.get("line"), int) and s["line"] > line]

    near_after = after[0] if after and after[0]["line"] - line <= 3 else None
    if near_after and (not before or line - before[-1]["line"] > 8):
        return near_after
    if before:
        return before[-1]
    return near_after


def collect_decisions(
    bundle: dict[str, Any],
    *,
    node_filter: set[str] | None = None,
) -> list[DecisionRecord]:
    file_nodes = declared_code_files(bundle)
    records: list[DecisionRecord] = []
    seen_ids: set[str] = set()

    for file_rel, node_ids in sorted(file_nodes.items()):
        if node_filter and not node_ids.intersection(node_filter):
            continue
        path = REPO_ROOT / file_rel
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue

        for index, line in enumerate(lines, start=1):
            marker = extract_marker(line)
            if marker is None:
                continue
            kind, text = marker
            if kind not in KINDS or not text:
                continue

            symbol = nearest_symbol(file_rel, index, node_ids, bundle)
            resolved_symbol = symbol.get("id") if symbol else None
            resolved_node = (
                symbol.get("node")
                if symbol and symbol.get("node")
                else sorted(node_ids)[0]
                if node_ids
                else None
            )
            candidates = sorted(node_ids) if len(node_ids) > 1 and not symbol else None
            supersedes_adr = extract_adr_ref(text) if kind == "SUPERSEDES" else None

            records.append(
                DecisionRecord(
                    id=decision_id(file_rel, index, kind, seen_ids),
                    file=file_rel,
                    line=index,
                    kind=kind,
                    text=text,
                    resolved_node=resolved_node,
                    resolved_symbol=resolved_symbol,
                    candidate_nodes=candidates,
                    supersedes_adr=supersedes_adr,
                )
            )

    return records


def summarize(records: list[DecisionRecord]) -> dict[str, Any]:
    by_kind = {kind: 0 for kind in sorted(KINDS)}
    nodes: set[str] = set()
    symbols = 0
    ambiguous = 0
    for record in records:
        by_kind[record.kind] = by_kind.get(record.kind, 0) + 1
        if record.resolved_node:
            nodes.add(record.resolved_node)
        if record.resolved_symbol:
            symbols += 1
        if record.candidate_nodes:
            ambiguous += 1
    return {
        "total_decisions": len(records),
        "by_kind": by_kind,
        "resolved_node_count": len(nodes),
        "resolved_symbol_count": symbols,
        "ambiguous_count": ambiguous,
    }


def write_decisions_index(records: list[DecisionRecord], summary: dict[str, Any]) -> None:
    payload = {
        "version": 0,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "summary": summary,
        "decisions": [
            record.to_index_dict()
            for record in sorted(records, key=lambda item: (item.file, item.line, item.kind))
        ],
    }
    DECISIONS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    DECISIONS_INDEX_PATH.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate decisions-index.yaml from inline WHY/DECISION/TRADEOFF/"
            "SUPERSEDES markers in code-index-bound files."
        )
    )
    parser.add_argument(
        "--node",
        action="append",
        default=[],
        help="Restrict extraction to one or more canonical node IDs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary without writing decisions-index.yaml.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the generated payload as JSON-like YAML.",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--telemetry-file", type=Path, default=None)
    args = parser.parse_args()

    bundle = load_bundle()
    node_filter = set(args.node) if args.node else None
    records = collect_decisions(bundle, node_filter=node_filter)
    summary = summarize(records)

    if not args.dry_run:
        write_decisions_index(records, summary)

    if args.json:
        yaml.safe_dump(
            {
                "summary": summary,
                "decisions": [record.to_index_dict() for record in records],
            },
            sys.stdout,
            sort_keys=False,
            allow_unicode=False,
        )
    else:
        print(f"Decision markers: {summary['total_decisions']}")
        for kind, count in sorted(summary["by_kind"].items()):
            print(f"  {kind.lower():10} {count:>5}")
        print(f"  resolved nodes   {summary['resolved_node_count']:>5}")
        print(f"  resolved symbols {summary['resolved_symbol_count']:>5}")

    nodes_returned = sorted(
        {record.resolved_node for record in records if record.resolved_node}
    )
    telemetry_payload = {
        "summary": summary,
        "nodes_returned": nodes_returned,
    }
    emit_telemetry(
        args.telemetry_file,
        args.run_id,
        "decisions",
        {
            "nodes_returned": nodes_returned,
            "nodes_count": len(nodes_returned),
            "decisions_count": summary["total_decisions"],
            "empty_scope": summary["total_decisions"] == 0,
            "ambiguous_count": summary["ambiguous_count"],
            "hint_emitted": False,
            "confidence_band": "low"
            if summary["total_decisions"] == 0
            else "ambiguous"
            if summary["ambiguous_count"]
            else "high",
            "tokens_estimated": estimate_tokens(telemetry_payload),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

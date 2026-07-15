#!/usr/bin/env python3
"""Three-way semantic merge for curated knowledge-graph YAML (F0006-S0001).

Merges base/ours/theirs versions of one curated KG file by semantic record
ID instead of by line. Identical content in different serialization
converges to zero conflicts; real divergence surfaces as typed conflicts
routed to the owning role. Output is all-or-nothing: either the canonically
serialized merged file is written, or nothing is written and a conflict
report (text + optional JSON) is emitted.

Usage:
  merge3.py TARGET --base REF_OR_PATH --ours REF_OR_PATH --theirs REF_OR_PATH
            [--output PATH] [--json PATH] [--dry-run]
            [--full-validate] [--validate-cmd CMD]
  merge3.py TARGET --semantic-diff OLD NEW [--json PATH]

Inputs may be file paths or git refs (resolved as `git show REF:<target>`).
Exit codes: 0 = clean merge / no semantic diff; 1 = conflicts, constraint
violation, or semantic differences; 2 = usage or input-data error.

Generated projections (symbol-index, coverage-report, unbound-but-referenced,
decisions-index) are never merge inputs — regenerate them instead.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kg_common import (  # noqa: E402
    GENERATED_KG_BASENAMES,
    ORDERED_LIST_FIELDS,
    REF_FIELDS,
    REPO_ROOT,
    canonical_dump,
    canonicalize_document,
    is_record_list,
    repo_relative,
    scalar_sort_key,
    yaml,
)

_MISSING = object()


def _die(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(EXIT_USAGE)

# Field names whose string values reference node ids (used by the orphan-edge
# check). Record-list `id` fields are definitions, not references — except in
# code-index, where a binding's `id` refers to a canonical node.
REF_SCAN_FIELDS = frozenset(REF_FIELDS) | {
    "related_nodes",
    "allowed_roles",
    "transitions_to",
    "feature",
    "adr",
    "belongs_to_workflow",
}

CURATED_BASENAMES = ("canonical-nodes.yaml", "feature-mappings.yaml", "code-index.yaml")

EXIT_CLEAN = 0
EXIT_CONFLICTS = 1
EXIT_USAGE = 2


@dataclass
class Conflict:
    kind: str
    record_id: str | None
    field: str | None
    base: Any
    ours: Any
    theirs: Any
    owning_role: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "record_id": self.record_id,
            "field": self.field,
            "base": self.base,
            "ours": self.ours,
            "theirs": self.theirs,
            "owning_role": self.owning_role,
            "message": self.message,
        }


@dataclass
class MergeResult:
    merged: Any
    conflicts: list[Conflict] = dataclass_field(default_factory=list)
    warnings: list[dict[str, Any]] = dataclass_field(default_factory=list)
    stats: dict[str, int] = dataclass_field(default_factory=dict)


def _owning_role(record_id: str | None, path: str, target_basename: str) -> str:
    if "excluded_features" in path:
        return "product-manager+architect"
    rid = record_id or ""
    if rid.startswith(("feature:", "story:")) or re.fullmatch(r"F\d{4}", rid):
        return "product-manager"
    if rid:
        return "architect"
    if target_basename == "feature-mappings.yaml" or target_basename.endswith(".md"):
        return "product-manager"  # trackers are PM territory (S0002)
    return "architect"


def _display(value: Any) -> Any:
    if value is _MISSING:
        return "<absent>"
    return value


class MergeEngine:
    """Three-way semantic merge over one canonicalized YAML document."""

    def __init__(self, target_basename: str):
        self.target_basename = target_basename
        self.conflicts: list[Conflict] = []

    def conflict(
        self,
        kind: str,
        path: str,
        record_id: str | None,
        base: Any,
        ours: Any,
        theirs: Any,
        message: str,
    ) -> None:
        self.conflicts.append(
            Conflict(
                kind=kind,
                record_id=record_id,
                field=path or None,
                base=_display(base),
                ours=_display(ours),
                theirs=_display(theirs),
                owning_role=_owning_role(record_id, path, self.target_basename),
                message=message,
            )
        )

    def merge(self, base: Any, ours: Any, theirs: Any) -> Any:
        return self._merge_value("", None, None, base, ours, theirs)

    def _merge_value(
        self,
        path: str,
        field: str | None,
        record_id: str | None,
        base: Any,
        ours: Any,
        theirs: Any,
    ) -> Any:
        if ours is _MISSING and theirs is _MISSING:
            return _MISSING
        if ours == theirs and ours is not _MISSING:
            return ours

        if base is _MISSING:
            # Added since base on at least one side.
            if ours is _MISSING:
                return theirs
            if theirs is _MISSING:
                return ours
            kind = "DivergentInsert"
            self.conflict(
                kind,
                path,
                record_id,
                base,
                ours,
                theirs,
                "added on both sides with different content",
            )
            return ours

        if ours is _MISSING:
            if theirs == base:
                return _MISSING
            self.conflict(
                "DeleteVsUpdate",
                path,
                record_id,
                base,
                ours,
                theirs,
                "deleted on ours, updated on theirs",
            )
            return _MISSING
        if theirs is _MISSING:
            if ours == base:
                return _MISSING
            self.conflict(
                "DeleteVsUpdate",
                path,
                record_id,
                base,
                ours,
                theirs,
                "updated on ours, deleted on theirs",
            )
            return ours

        if ours == base:
            return theirs
        if theirs == base:
            return ours

        # Both sides changed, differently. Recurse by structure.
        if isinstance(base, dict) and isinstance(ours, dict) and isinstance(theirs, dict):
            return self._merge_mapping(path, record_id, base, ours, theirs)
        if isinstance(base, list) and isinstance(ours, list) and isinstance(theirs, list):
            return self._merge_list(path, field, record_id, base, ours, theirs)

        self.conflict(
            "DivergentUpdate",
            path,
            record_id,
            base,
            ours,
            theirs,
            "both sides changed the same field to different values",
        )
        return ours

    def _merge_mapping(
        self,
        path: str,
        record_id: str | None,
        base: dict[str, Any],
        ours: dict[str, Any],
        theirs: dict[str, Any],
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        keys = list(dict.fromkeys([*base.keys(), *ours.keys(), *theirs.keys()]))
        for key in keys:
            child_path = f"{path}.{key}" if path else key
            value = self._merge_value(
                child_path,
                key,
                record_id,
                base.get(key, _MISSING),
                ours.get(key, _MISSING),
                theirs.get(key, _MISSING),
            )
            if value is not _MISSING:
                merged[key] = value
        return merged

    def _merge_list(
        self,
        path: str,
        field: str | None,
        record_id: str | None,
        base: list[Any],
        ours: list[Any],
        theirs: list[Any],
    ) -> list[Any]:
        record_shaped = all(is_record_list(side) or side == [] for side in (base, ours, theirs))
        if field in ORDERED_LIST_FIELDS:
            if record_shaped:
                return self._merge_ordered_record_list(path, record_id, base, ours, theirs)
            self.conflict(
                "OrderedListConflict",
                path,
                record_id,
                base,
                ours,
                theirs,
                "order-significant list changed on both sides; merge by hand or leave one side unchanged",
            )
            return ours
        if record_shaped:
            merged_by_id = self._merge_records_by_id(path, base, ours, theirs)
            return sorted(merged_by_id.values(), key=lambda item: str(item["id"]))
        if _all_scalar_lists(base, ours, theirs):
            return _set_merge(base, ours, theirs)
        self.conflict(
            "DivergentUpdate",
            path,
            record_id,
            base,
            ours,
            theirs,
            "unregistered list structure changed on both sides; refusing silent union",
        )
        return ours

    def _merge_records_by_id(
        self,
        path: str,
        base: list[Any],
        ours: list[Any],
        theirs: list[Any],
    ) -> dict[str, dict[str, Any]]:
        base_map = {str(record["id"]): record for record in base}
        ours_map = {str(record["id"]): record for record in ours}
        theirs_map = {str(record["id"]): record for record in theirs}

        merged: dict[str, dict[str, Any]] = {}
        all_ids = list(dict.fromkeys([*base_map, *ours_map, *theirs_map]))
        for rid in all_ids:
            record_path = f"{path}[{rid}]"
            value = self._merge_value(
                record_path,
                None,
                rid,
                base_map.get(rid, _MISSING),
                ours_map.get(rid, _MISSING),
                theirs_map.get(rid, _MISSING),
            )
            if value is not _MISSING:
                merged[rid] = value
        return merged

    def _merge_ordered_record_list(
        self,
        path: str,
        record_id: str | None,
        base: list[Any],
        ours: list[Any],
        theirs: list[Any],
    ) -> list[Any]:
        base_ids = [str(record["id"]) for record in base]
        ours_ids = [str(record["id"]) for record in ours]
        theirs_ids = [str(record["id"]) for record in theirs]

        if ours_ids == base_ids:
            order = theirs_ids
        elif theirs_ids == base_ids:
            order = ours_ids
        elif ours_ids == theirs_ids:
            order = ours_ids
        else:
            self.conflict(
                "OrderedListConflict",
                path,
                record_id,
                base_ids,
                ours_ids,
                theirs_ids,
                "order-significant record list changed membership/order on both sides",
            )
            return ours

        merged_by_id = self._merge_records_by_id(path, base, ours, theirs)
        result = [merged_by_id.pop(rid) for rid in order if rid in merged_by_id]
        # Records that survived the merge but are absent from the adopted
        # order (cannot happen unless order adoption raced a deletion) are
        # appended deterministically rather than dropped.
        result.extend(merged_by_id[rid] for rid in sorted(merged_by_id))
        return result


def _all_scalar_lists(*lists: list[Any]) -> bool:
    return all(
        all(item is None or isinstance(item, (str, int, float, bool)) for item in seq)
        for seq in lists
    )


def _set_merge(base: list[Any], ours: list[Any], theirs: list[Any]) -> list[Any]:
    base_set, ours_set, theirs_set = set(base), set(ours), set(theirs)
    removed = (base_set - ours_set) | (base_set - theirs_set)
    added = (ours_set - base_set) | (theirs_set - base_set)
    return sorted((base_set - removed) | added, key=scalar_sort_key)


# ──────────────────────────────────────────────────────────────
# Record extraction and graph-level checks
# ──────────────────────────────────────────────────────────────


def collect_records(doc: Any, path: str = "") -> dict[str, list[tuple[str, dict[str, Any]]]]:
    """Map record id -> [(list-path, record)] for every record list in doc.

    Subtrees under reference fields are skipped: an edge-ref object such as
    `depends_on: [{id: feature:F0008, provenance: inferred}]` is a reference,
    not a record definition.
    """
    found: dict[str, list[tuple[str, dict[str, Any]]]] = {}

    def walk(value: Any, current: str, field: str | None) -> None:
        if field in REF_SCAN_FIELDS:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{current}.{key}" if current else key, key)
        elif is_record_list(value):
            for record in value:
                rid = str(record["id"])
                found.setdefault(rid, []).append((current, record))
                for key, child in record.items():
                    if isinstance(child, (dict, list)):
                        walk(child, f"{current}[{rid}].{key}", key)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (dict, list)):
                    walk(item, current, field)

    walk(doc, path, None)
    return found


def collect_refs(doc: Any, include_record_ids: bool = False) -> set[str]:
    """All node-id references made by a document (not its definitions)."""
    refs: set[str] = set()

    def walk(value: Any, field: str | None) -> None:
        if isinstance(value, dict):
            # Object-form edge refs ({id:, provenance:, ...}) under ref fields.
            if field in REF_SCAN_FIELDS and isinstance(value.get("id"), str):
                refs.add(value["id"])
            for key, child in value.items():
                if key == "id" and include_record_ids and isinstance(child, str):
                    refs.add(child)
                walk(child, key)
        elif isinstance(value, list):
            for item in value:
                walk(item, field)
        elif isinstance(value, str) and field in REF_SCAN_FIELDS:
            refs.add(value)

    walk(doc, None)
    return refs


def check_input_duplicates(doc: Any, label: str) -> None:
    """Duplicate ids inside one record list are input corruption: fail loudly."""
    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{path}.{key}" if path else key)
        elif is_record_list(value):
            seen: set[str] = set()
            for record in value:
                rid = str(record["id"])
                if rid in seen:
                    _die(
                        f"merge3: duplicate id `{rid}` inside `{path}` of {label}; "
                        "fix the input before merging"
                    )
                seen.add(rid)
                walk(record, f"{path}[{rid}]")
        elif isinstance(value, list):
            for item in value:
                walk(item, path)

    walk(doc, "")


def graph_checks(
    result: MergeResult,
    base_doc: Any,
    target: Path,
    target_basename: str,
) -> None:
    """Post-merge, pre-write checks: UniqueViolation, OrphanEdge, duplicates."""
    records = collect_records(result.merged)

    for rid, occurrences in records.items():
        if len(occurrences) > 1:
            paths = ", ".join(path for path, _ in occurrences)
            result.conflicts.append(
                Conflict(
                    kind="UniqueViolation",
                    record_id=rid,
                    field=None,
                    base=None,
                    ours=paths,
                    theirs=paths,
                    owning_role=_owning_role(rid, paths, target_basename),
                    message=f"id `{rid}` appears in more than one record list: {paths}",
                )
            )

    # Ids that existed in base but were deleted by the merge, yet are still
    # referenced by the merged doc or by the sibling curated files in the
    # target's directory.
    base_ids = set(collect_records(base_doc))
    deleted = base_ids - set(records)
    if deleted:
        refs = collect_refs(result.merged)
        for sibling in CURATED_BASENAMES:
            if sibling == target_basename:
                continue
            sibling_path = target.parent / sibling
            if sibling_path.exists():
                sibling_doc = yaml.safe_load(sibling_path.read_text(encoding="utf-8")) or {}
                refs |= collect_refs(sibling_doc, include_record_ids=sibling == "code-index.yaml")
        for rid in sorted(deleted & refs):
            result.conflicts.append(
                Conflict(
                    kind="OrphanEdge",
                    record_id=rid,
                    field=None,
                    base=rid,
                    ours=None,
                    theirs=None,
                    owning_role=_owning_role(rid, "", target_basename),
                    message=(
                        f"`{rid}` was deleted by this merge but is still referenced "
                        "by the merged file or a sibling curated file"
                    ),
                )
            )

    # Alias/name fingerprint overlap across different ids — advisory only.
    fingerprints: dict[str, set[str]] = {}
    for rid, occurrences in records.items():
        for _, record in occurrences:
            for field in ("label", "name", "title"):
                text = record.get(field)
                if isinstance(text, str):
                    normalized = "".join(ch for ch in text.casefold() if ch.isalnum())
                    if normalized:
                        fingerprints.setdefault(normalized, set()).add(rid)
    for normalized, ids in sorted(fingerprints.items()):
        if len(ids) > 1:
            result.warnings.append(
                {
                    "kind": "SemanticDuplicateWarning",
                    "ids": sorted(ids),
                    "message": f"records {sorted(ids)} share the normalized name `{normalized}`",
                }
            )


def merge_documents(
    base_doc: Any,
    ours_doc: Any,
    theirs_doc: Any,
    target_basename: str,
) -> MergeResult:
    """Pure three-way document merge (no I/O). Reused by the tracker merge (S0002)."""
    base = canonicalize_document(base_doc)
    ours = canonicalize_document(ours_doc)
    theirs = canonicalize_document(theirs_doc)

    engine = MergeEngine(target_basename)
    merged = engine.merge(base, ours, theirs)
    if merged is _MISSING:
        merged = {}

    result = MergeResult(merged=canonicalize_document(merged), conflicts=engine.conflicts)
    result.stats = {
        "records_base": len(collect_records(base)),
        "records_ours": len(collect_records(ours)),
        "records_theirs": len(collect_records(theirs)),
        "records_merged": len(collect_records(result.merged)),
        "conflicts": len(result.conflicts),
    }
    return result


# ──────────────────────────────────────────────────────────────
# Semantic diff (ID-level) — canonicalization no-change proof
# ──────────────────────────────────────────────────────────────


def semantic_diff(old_doc: Any, new_doc: Any) -> dict[str, list[str]]:
    old = canonicalize_document(old_doc)
    new = canonicalize_document(new_doc)
    old_records = collect_records(old)
    new_records = collect_records(new)

    added = sorted(set(new_records) - set(old_records))
    removed = sorted(set(old_records) - set(new_records))
    changed = sorted(
        rid
        for rid in set(old_records) & set(new_records)
        if [record for _, record in old_records[rid]]
        != [record for _, record in new_records[rid]]
    )

    def skeleton(doc: Any) -> Any:
        if isinstance(doc, dict):
            return {key: skeleton(value) for key, value in doc.items()}
        if is_record_list(doc):
            return sorted(str(record["id"]) for record in doc)
        if isinstance(doc, list):
            return [skeleton(item) for item in doc]
        return doc

    meta_changed = [] if skeleton(old) == skeleton(new) else ["<document structure/meta fields>"]
    return {"added": added, "removed": removed, "changed": changed, "meta": meta_changed}


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────


def _resolve_text(spec: str, target: Path) -> str:
    """Read raw content from a file path, or from a git ref via `git show REF:target`."""
    candidate = Path(spec)
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    rel = repo_relative(target)
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{spec}:{rel}"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        _die(
            f"merge3: `{spec}` is neither a file nor a resolvable git ref for {rel}: "
            f"{proc.stderr.strip()}"
        )
    return proc.stdout


def _resolve_input(spec: str, target: Path) -> Any:
    """Load YAML from a file path or git ref."""
    return yaml.safe_load(_resolve_text(spec, target)) or {}


def _atomic_write(path: Path, content: str) -> None:
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    )
    try:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.replace(handle.name, path)


def _run_full_validate(
    result: MergeResult,
    target: Path,
    output: Path,
    merged_text: str,
    validate_cmd: list[str],
) -> bool:
    """Write merged output, run the repo validator, roll back on failure."""
    original = output.read_bytes() if output.exists() else None
    _atomic_write(output, merged_text)
    proc = subprocess.run(validate_cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    if proc.returncode == 0:
        return True
    if original is None:
        output.unlink(missing_ok=True)
    else:
        _atomic_write(output, original.decode("utf-8"))
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-12:])
    result.conflicts.append(
        Conflict(
            kind="ConstraintViolation",
            record_id=None,
            field=None,
            base=None,
            ours=None,
            theirs=None,
            owning_role=_owning_role(None, "", target.name),
            message=f"validator failed on the merged graph (rolled back):\n{tail}",
        )
    )
    return False


def _print_report(result: MergeResult, wrote: Path | None) -> None:
    for warning in result.warnings:
        print(f"WARNING {warning['kind']}: {warning['message']}")
    for conflict in result.conflicts:
        location = conflict.field or conflict.record_id or "<document>"
        print(f"CONFLICT {conflict.kind} at {location} -> {conflict.owning_role}")
        print(f"  message: {conflict.message}")
        if conflict.kind in {"DivergentUpdate", "DivergentInsert", "DeleteVsUpdate", "OrderedListConflict"}:
            print(f"  base:   {json.dumps(conflict.base, ensure_ascii=False, default=str)}")
            print(f"  ours:   {json.dumps(conflict.ours, ensure_ascii=False, default=str)}")
            print(f"  theirs: {json.dumps(conflict.theirs, ensure_ascii=False, default=str)}")
    stats = ", ".join(f"{key}={value}" for key, value in result.stats.items())
    print(f"merge3: {stats}")
    if result.conflicts:
        print(f"merge3: {len(result.conflicts)} conflict(s); nothing written")
    elif wrote is not None:
        print(f"merge3: clean merge -> {repo_relative(wrote)}")
    else:
        print("merge3: clean merge (dry run; nothing written)")


def _write_json_report(
    path: Path,
    target: Path,
    args: argparse.Namespace,
    result: MergeResult,
    wrote: Path | None,
) -> None:
    payload = {
        "target": repo_relative(target),
        "inputs": {"base": args.base, "ours": args.ours, "theirs": args.theirs},
        "result": "conflicts" if result.conflicts else "clean",
        "output": repo_relative(wrote) if wrote else None,
        "stats": result.stats,
        "warnings": result.warnings,
        "conflicts": [conflict.as_dict() for conflict in result.conflicts],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def _finish_semantic_diff(diff: dict[str, list[str]], json_path: str | None) -> int:
    differences = sum(len(entries) for entries in diff.values())
    for kind in ("added", "removed", "changed", "meta"):
        for rid in diff[kind]:
            print(f"{kind}: {rid}")
    print(f"merge3 --semantic-diff: {differences} semantic difference(s)")
    if json_path:
        Path(json_path).write_text(
            json.dumps(diff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return EXIT_CLEAN if differences == 0 else EXIT_CONFLICTS


def _run_tracker_mode(parser: argparse.ArgumentParser, args: argparse.Namespace, target: Path) -> int:
    """Markdown tracker targets (REGISTRY.md / ROADMAP.md) — S0002."""
    from tracker_merge import (
        GENERATED_TRACKER_BASENAMES,
        TrackerFormatError,
        merge_tracker_documents,
        tracker_semantic_diff,
    )

    if target.name in GENERATED_TRACKER_BASENAMES:
        parser.exit(
            EXIT_USAGE,
            f"merge3: {target.name} is generated (generate-story-index.py) — "
            "regenerate it after the merge; never merge it\n",
        )

    try:
        if args.semantic_diff:
            diff = tracker_semantic_diff(
                _resolve_text(args.semantic_diff[0], target),
                _resolve_text(args.semantic_diff[1], target),
                target.name,
            )
            return _finish_semantic_diff(diff, args.json)

        if not (args.base and args.ours and args.theirs):
            parser.exit(EXIT_USAGE, "merge3: --base, --ours, and --theirs are all required\n")

        result = merge_tracker_documents(
            _resolve_text(args.base, target),
            _resolve_text(args.ours, target),
            _resolve_text(args.theirs, target),
            target.name,
        )
    except TrackerFormatError as exc:
        _die(f"merge3: {exc}")

    wrote: Path | None = None
    output = Path(args.output) if args.output else target
    if not result.conflicts and not args.dry_run:
        if args.full_validate:
            if _run_full_validate(result, target, output, result.merged_text, args.validate_cmd.split()):
                wrote = output
        else:
            _atomic_write(output, result.merged_text)
            wrote = output

    _print_report(result, wrote)
    if args.json:
        _write_json_report(Path(args.json), target, args, result, wrote)
    return EXIT_CONFLICTS if result.conflicts else EXIT_CLEAN


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Three-way semantic merge of curated knowledge-graph YAML."
    )
    parser.add_argument("target", help="Curated KG file the merge concerns (worktree path)")
    parser.add_argument("--base", help="Merge-base version (file path or git ref)")
    parser.add_argument("--ours", help="Ours version (file path or git ref)")
    parser.add_argument("--theirs", help="Theirs version (file path or git ref)")
    parser.add_argument(
        "--semantic-diff",
        nargs=2,
        metavar=("OLD", "NEW"),
        help="Compare two versions at record level instead of merging",
    )
    parser.add_argument("--output", help="Write merged result here (default: TARGET)")
    parser.add_argument("--json", help="Write a structured JSON report here")
    parser.add_argument("--dry-run", action="store_true", help="Report only; never write")
    parser.add_argument(
        "--full-validate",
        action="store_true",
        help="After a clean merge, run the repo validator against the written "
        "result and roll back on failure (ConstraintViolation)",
    )
    parser.add_argument(
        "--validate-cmd",
        default=f"{sys.executable} scripts/kg/validate.py",
        help="Validator command for --full-validate (default: scripts/kg/validate.py)",
    )
    args = parser.parse_args(argv)

    target = Path(args.target)
    if target.name in GENERATED_KG_BASENAMES:
        parser.exit(
            EXIT_USAGE,
            f"merge3: {target.name} is a generated projection — generated files are "
            "never merge inputs; regenerate it after merging the curated sources\n",
        )

    if target.suffix == ".md":
        return _run_tracker_mode(parser, args, target)

    if args.semantic_diff:
        diff = semantic_diff(
            _resolve_input(args.semantic_diff[0], target),
            _resolve_input(args.semantic_diff[1], target),
        )
        return _finish_semantic_diff(diff, args.json)

    if not (args.base and args.ours and args.theirs):
        parser.exit(EXIT_USAGE, "merge3: --base, --ours, and --theirs are all required\n")

    base_doc = _resolve_input(args.base, target)
    ours_doc = _resolve_input(args.ours, target)
    theirs_doc = _resolve_input(args.theirs, target)
    for doc, label in ((base_doc, "base"), (ours_doc, "ours"), (theirs_doc, "theirs")):
        check_input_duplicates(doc, f"{label} ({target.name})")

    result = merge_documents(base_doc, ours_doc, theirs_doc, target.name)
    graph_checks(result, canonicalize_document(base_doc), target, target.name)
    result.stats["conflicts"] = len(result.conflicts)

    wrote: Path | None = None
    output = Path(args.output) if args.output else target
    if not result.conflicts and not args.dry_run:
        merged_text = canonical_dump(result.merged)
        if args.full_validate:
            if _run_full_validate(result, target, output, merged_text, args.validate_cmd.split()):
                wrote = output
        else:
            _atomic_write(output, merged_text)
            wrote = output

    _print_report(result, wrote)
    if args.json:
        _write_json_report(Path(args.json), target, args, result, wrote)
    return EXIT_CONFLICTS if result.conflicts else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())

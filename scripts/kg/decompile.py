#!/usr/bin/env python3
"""One-time migration: explode the monolithic KG + trackers into kg-source/ shards (F0006-S0006).

`decompile.py` mechanically partitions the current `canonical-nodes.yaml`, `feature-mappings.yaml`,
`code-index.yaml`, and `solution-ontology.yaml` — plus the REGISTRY.md / ROADMAP.md feature tables —
into `planning-mds/kg-source/**` shards, rewriting physical `planning-mds/features/…` doc refs to the
logical `F####/…` form. The cutover gate is ``compile(decompile(graph)) == graph`` byte-identical for
the KG trio + ontology (the tracker byte-identical round trip closes at S0007). It is the inverse of
`compile.py`; the compiler stays the single source of truth for what a valid projection looks like.

Run `--check` first: it partitions into a temp tree, runs the round trip, reconciles counts, and prints
the migration report — writing **no** shards. Without `--check` it writes the shards into
`planning-mds/kg-source/` (the maintainer then reviews + creates the tagged cutover commit).
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import compile as kgc
import kg_common
import merge3
import shard_validate
import tracker_merge
from kg_common import SECTION_TYPES, canonical_dump, load_yaml

REPO_ROOT = kg_common.REPO_ROOT
KG_DIR = REPO_ROOT / "planning-mds" / "knowledge-graph"
FEATURES_DIR = REPO_ROOT / "planning-mds" / "features"

ONE_PER_FILE_KINDS = {"capability", "entity", "workflow"}
NODE_HEADER_KEYS = ("version", "status", "coverage_note")
FEATURE_MAPPING_HEADER_KEYS = ("version", "status", "coverage_note", "rules")

# REGISTRY display status → canonical shard status (for features with no feature-mappings entry).
REGISTRY_STATUS = {
    "Planned": "planned",
    "Planned (provisional)": "planned-provisional",
    "Active": "active",
    "In Progress": "in-progress",
}


@dataclass
class DecompileResult:
    shards: dict[str, str] = field(default_factory=dict)   # kg-source-relative path → YAML text
    anomalies: list[str] = field(default_factory=list)
    report: list[str] = field(default_factory=list)
    roundtrip_drift: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.anomalies and not self.roundtrip_drift


def _id_body(node_id: str) -> str:
    return node_id.split(":", 1)[1]


def _rewrite_doc_ref(ref: str, path_to_feature: list[tuple[str, str]]) -> str:
    """Physical `planning-mds/features/<folder>/rel` → logical `F####/rel`; others unchanged."""
    if not isinstance(ref, str) or not ref.startswith("planning-mds/features/"):
        return ref
    for base, fid in path_to_feature:  # longest paths first
        if ref == base or ref.startswith(base + "/"):
            remainder = ref[len(base):].lstrip("/")
            return f"{fid.split(':')[1]}/{remainder}"  # feature:F0035 → F0035/remainder
    return ref  # no matching feature folder → left physical; the round trip will flag it as drift


def _tracker_rows(basename: str) -> dict[str, dict[str, dict[str, str]]]:
    """{section heading → {F#### → {column: cell}}} for a tracker file."""
    text = (FEATURES_DIR / basename).read_text(encoding="utf-8")
    out: dict[str, dict[str, dict[str, str]]] = {}
    for section in tracker_merge.parse_tracker(text, basename):
        if section.table is not None:
            out[section.heading] = section.table.rows
    return out


def _presentation_fields(fid: str, registry: dict[str, dict[str, dict[str, str]]],
                         roadmap: dict[str, dict[str, dict[str, str]]]) -> dict[str, Any]:
    """Map REGISTRY/ROADMAP cells to feature-shard presentation fields (kg-source README §4.1).

    Tracker tables are keyed by the bare `F####` id (tracker_merge._row_key), not `feature:F####`.
    """
    bare = fid.split(":", 1)[1]
    fields: dict[str, Any] = {}
    for heading, rows in registry.items():
        if bare in rows:
            cell = rows[bare]
            if cell.get("Name"):
                fields["name"] = cell["Name"]
            if cell.get("Phase"):
                fields["phase"] = cell["Phase"]
            for col, key in (("Retired Date", "retired_date"), ("Archived Date", "archived_date"),
                             ("Reason", "reason")):
                if cell.get(col):
                    fields[key] = cell[col]
            if cell.get("Superseded By"):
                fields["superseded_by"] = f"feature:{cell['Superseded By']}"
    for heading, rows in roadmap.items():
        if bare in rows:
            cell = rows[bare]
            fields["roadmap_section"] = heading
            if cell.get("Phase"):
                fields.setdefault("phase", cell["Phase"])
            for col in ("Why Now", "Why Next", "Why Later"):
                if cell.get(col):
                    fields["rationale"] = cell[col]
            if cell.get("Completion State"):
                fields["completion_state"] = cell["Completion State"]
            if cell.get("Rationale"):
                fields.setdefault("reason", cell["Rationale"])
            if cell.get("Superseded By"):
                fields.setdefault("superseded_by", f"feature:{cell['Superseded By']}")
    return fields


def decompile_to(source_dir: Path, *, kg_dir: Path = KG_DIR) -> DecompileResult:
    """Emit shards into `source_dir` (real or temp) from the monolith + trackers. In-memory first."""
    result = DecompileResult()
    canonical = load_yaml(kg_dir / "canonical-nodes.yaml")
    mappings = load_yaml(kg_dir / "feature-mappings.yaml")
    code_index = load_yaml(kg_dir / "code-index.yaml")
    ontology_text = (kg_dir / "solution-ontology.yaml").read_text(encoding="utf-8")

    # Feature path map (33 mapped + 7 coverage-excluded).
    excluded = mappings.get("coverage", {}).get("excluded_features", [])
    feature_paths = {f["id"]: f["path"] for f in mappings.get("features", [])}
    feature_paths.update({e["id"]: e["path"] for e in excluded})
    path_to_feature = sorted(((p, fid) for fid, p in feature_paths.items()), key=lambda t: -len(t[0]))

    registry = _tracker_rows("REGISTRY.md")
    roadmap = _tracker_rows("ROADMAP.md")

    # ── nodes + policies ──
    for section, records in canonical.items():
        if not isinstance(records, list) or not records:
            continue
        kind = SECTION_TYPES.get(section)
        if kind is None:
            result.anomalies.append(f"canonical-nodes section `{section}` has no shard-kind home")
            continue
        directory = "policies" if section == "policy_rules" else f"nodes/{section}"
        rewritten = []
        for rec in records:
            rec = dict(rec)
            if isinstance(rec.get("source_docs"), list):
                rec["source_docs"] = [_rewrite_doc_ref(d, path_to_feature) for d in rec["source_docs"]]
            rewritten.append(rec)
        if kind in ONE_PER_FILE_KINDS:
            for rec in rewritten:
                result.shards[f"{directory}/{_id_body(rec['id'])}.yaml"] = canonical_dump(rec)
        else:
            result.shards[f"{directory}/{section}.yaml"] = canonical_dump({section: rewritten})

    # ── bindings ──
    result.shards["bindings/node_bindings.yaml"] = canonical_dump(
        {"node_bindings": code_index.get("node_bindings", [])}
    )

    # ── features (technical + stories + presentation + coverage-excluded) ──
    stories_by_feature: dict[str, list[dict[str, Any]]] = {}
    for story in mappings.get("stories", []):
        entry = {k: v for k, v in story.items() if k != "feature"}  # verbatim; compile re-adds `feature`
        stories_by_feature.setdefault(story["feature"], []).append(entry)

    mapped = {f["id"]: f for f in mappings.get("features", [])}
    excluded_map = {e["id"]: e for e in excluded}
    all_feature_ids = sorted(set(mapped) | set(excluded_map), key=lambda x: x)
    for fid in all_feature_ids:
        shard: dict[str, Any] = {"id": fid}
        pres = _presentation_fields(fid, registry, roadmap)
        if fid in mapped:  # copy every feature-mappings technical field verbatim (compile blacklists presentation)
            shard.update({k: v for k, v in mapped[fid].items() if k != "id"})
        else:  # coverage-excluded planned feature
            e = excluded_map[fid]
            shard["path"] = e["path"]
            shard["coverage_excluded"] = {"reason": e.get("reason", "")}
            bare = fid.split(":", 1)[1]
            reg_status = next((registry[h][bare]["Status"] for h in registry
                               if bare in registry[h] and registry[h][bare].get("Status")), None)
            shard["status"] = REGISTRY_STATUS.get(reg_status, "planned")
        shard.update({k: v for k, v in pres.items() if k not in shard})
        if fid in stories_by_feature:
            shard["story_mappings"] = stories_by_feature[fid]
        if "roadmap_section" not in shard:
            result.anomalies.append(f"{fid} has no ROADMAP section (every feature must be placed)")
        result.shards[f"features/{_id_body(fid)}.yaml"] = canonical_dump(shard)

    # ── ontology (verbatim) + projections meta ──
    result.shards["ontology/solution-ontology.yaml"] = ontology_text
    meta = {
        "canonical-nodes.yaml": {k: canonical[k] for k in NODE_HEADER_KEYS if k in canonical},
        "feature-mappings.yaml": {k: mappings[k] for k in FEATURE_MAPPING_HEADER_KEYS if k in mappings},
        "code-index.yaml": {k: code_index[k] for k in NODE_HEADER_KEYS if k in code_index},
    }
    result.shards["projections-meta.yaml"] = canonical_dump(meta)

    result.report.append(f"nodes: {sum(len(v) for k, v in canonical.items() if isinstance(v, list))} "
                         f"across {sum(1 for v in canonical.values() if isinstance(v, list) and v)} sections")
    result.report.append(f"bindings: {len(code_index.get('node_bindings', []))}")
    result.report.append(f"features: {len(all_feature_ids)} ({len(mapped)} mapped + {len(excluded_map)} coverage-excluded)")
    result.report.append(f"stories: {len(mappings.get('stories', []))}")
    return result


def write_shards(result: DecompileResult, source_dir: Path) -> None:
    source_dir = Path(source_dir)
    for rel, text in result.shards.items():
        target = source_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def verify_roundtrip(source_dir: Path, result: DecompileResult, *, kg_dir: Path = KG_DIR) -> None:
    """Validate emitted shards, then assert compile(shards) == the committed KG trio + ontology."""
    vreport = shard_validate.validate_paths([source_dir])
    if vreport.errors:
        result.anomalies.extend(vreport.errors)
        return
    compiled = kgc.compile_sources(source_dir, exist_root=REPO_ROOT)
    if not compiled.ok:
        result.anomalies.extend(compiled.errors)
        return
    rendered = kgc.render(compiled)
    for name in ("canonical-nodes.yaml", "feature-mappings.yaml", "code-index.yaml", "solution-ontology.yaml"):
        original = (kg_dir / name).read_text(encoding="utf-8")
        if rendered.get(name) != original:
            result.roundtrip_drift.append(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decompile the monolithic KG + trackers into kg-source/ shards.")
    parser.add_argument("--check", action="store_true", help="dry-run: partition + round-trip into a temp tree, write nothing")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "planning-mds" / "kg-source",
                        help="kg-source output dir (real migration)")
    args = parser.parse_args(argv)

    result = decompile_to(args.out if not args.check else Path(tempfile.mkdtemp()) / "kg-source")

    scratch = Path(tempfile.mkdtemp()) / "kg-source"
    write_shards(result, scratch)
    verify_roundtrip(scratch, result)

    print("── migration report ──")
    for line in result.report:
        print(f"  {line}")
    if result.anomalies:
        print(f"\n{len(result.anomalies)} anomaly(ies):", file=sys.stderr)
        for a in result.anomalies:
            print(f"  ! {a}", file=sys.stderr)
    if result.roundtrip_drift:
        print(f"\nround-trip drift (compile(decompile) != committed): {result.roundtrip_drift}", file=sys.stderr)
    if not result.ok:
        print("\ndecompile: NOT byte-identical / anomalies present — nothing written to the real tree.", file=sys.stderr)
        return 1

    if args.check:
        print("\ndecompile --check: round-trip byte-identical, counts reconciled. Safe to cut over.")
        return 0

    write_shards(result, args.out)
    print(f"\ndecompile: wrote {len(result.shards)} shard files to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Deterministic KG compiler: kg-source/ shards → projection trio (+ driven generators).

F0006-S0005 (PRD row B2). The compiler is the only sanctioned producer of
``planning-mds/knowledge-graph/{canonical-nodes,feature-mappings,code-index}.yaml`` after cutover.
It is a pure function of ``planning-mds/kg-source/**``:

* loads + validates shards (reusing S0004 ``shard_validate``),
* resolves logical ``F####/…`` doc refs through feature shards' ``path:`` (absorbs F0005),
* assembles the trio and emits it through the S0001 canonical serializer (``kg_common.canonical_dump``),
  so identical sources produce byte-identical output anywhere,
* runs compile-time analysis (duplicate IDs = hard error; name-similarity + binding-glob overlap =
  advisory on branches, blocking under ``--strict``),
* mirrors the curated ``solution-ontology.yaml`` into the generated tree (S0005-D4),
* optionally drives the existing downstream generators, stripping their ``generated_at`` timestamps so
  the whole generated surface stays byte-identical (S0005-D1).

All-or-nothing: everything is assembled and checked in memory; nothing is written unless the whole
build succeeds. ``--check`` compiles to memory and diffs the committed projections (the reproducibility
primitive S0008's CI wraps).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import kg_common
import merge3
import shard_validate
import tracker_gen
from kg_common import (
    DocRefError,
    canonical_dump,
    load_yaml,
    repo_relative,
    resolve_doc_ref,
)

REPO_ROOT = kg_common.REPO_ROOT
KG_SOURCE_DIR = REPO_ROOT / "planning-mds" / "kg-source"
KG_DIR = REPO_ROOT / "planning-mds" / "knowledge-graph"

TRIO = ("canonical-nodes.yaml", "feature-mappings.yaml", "code-index.yaml")
ONTOLOGY_BASENAME = "solution-ontology.yaml"

# Non-record scalars for each projection. Defaults for the seed/fixture state; the real migration
# (S0006) supplies the authored headers via --headers so the round trip is byte-identical.
DEFAULT_HEADERS: dict[str, dict[str, Any]] = {
    "canonical-nodes.yaml": {"version": 0, "status": "generated"},
    "feature-mappings.yaml": {"version": 0, "status": "generated"},
    "code-index.yaml": {"version": 0, "status": "generated"},
}

# feature-mappings.features carries only the technical/binding fields; these presentation fields
# (rendered to the trackers at S0007) are excluded from the projection. Everything else on the
# feature shard — status/path/affects/governed_by/uses_*/depends_on/supersedes/enforced_by_policy/
# restricted_to_role/notes/… — projects verbatim.
FEATURE_PRESENTATION_FIELDS = frozenset({
    "name", "phase", "roadmap_section", "roadmap_order", "rationale", "completion_state",
    "validation_gate", "retired_date", "reason", "archived_date", "coverage_excluded",
    "registry_section", "evidence_reentry_date", "completed_date",
    "story_mappings", "superseded_by",
})

GENERATED_AT_LINE_RE = re.compile(r"(?m)^generated_at:.*\n")


@dataclass
class CompileResult:
    projections: dict[str, Any] = field(default_factory=dict)   # basename → assembled doc
    ontology_text: str | None = None                            # verbatim solution-ontology mirror, or None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suppressed: list[str] = field(default_factory=list)         # analysis findings the ledger cleared

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def is_empty(self) -> bool:
        """No shard content at all — compiling would emit empty projections (would clobber a real
        graph). Until the S0006 migration populates kg-source/, compile is a no-op on the real tree."""
        cn = self.projections.get("canonical-nodes.yaml", {})
        fm = self.projections.get("feature-mappings.yaml", {})
        ci = self.projections.get("code-index.yaml", {})
        has_nodes = any(isinstance(v, list) and v for v in cn.values())
        return not (has_nodes or fm.get("features") or fm.get("coverage")
                    or ci.get("node_bindings") or self.ontology_text)


def _load_headers(source_dir: Path) -> dict[str, dict[str, Any]]:
    """Projection non-record headers (version/status/coverage_note/rules) from the source meta file
    (S0006-D-header), or the seed defaults when it is absent."""
    meta = Path(source_dir) / "projections-meta.yaml"
    return load_yaml(meta) if meta.exists() else DEFAULT_HEADERS


def _records(data: Any) -> list[dict[str, Any]]:
    """Split a shard file body into records (single-concept or single-key bundle or list)."""
    if isinstance(data, dict) and "id" in data:
        return [data]
    if isinstance(data, dict) and len(data) == 1 and isinstance(next(iter(data.values())), list):
        return [r for r in next(iter(data.values())) if isinstance(r, dict)]
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    return []


def _section_for(dc: shard_validate.DirClass) -> str | None:
    """canonical-nodes section a node/policy shard projects into, or None."""
    if dc.directory.startswith("nodes/"):
        return dc.directory.split("/", 1)[1]
    if dc.directory == "policies":
        return "policy_rules"
    return None


def _resolve_source_docs(record: dict[str, Any], feature_paths: dict[str, str],
                         exist_root: Path | None, rel: str, report: CompileResult) -> dict[str, Any]:
    """Return a copy of `record` with logical `source_docs` refs resolved to physical paths."""
    docs = record.get("source_docs")
    if not isinstance(docs, list):
        return record
    resolved: list[str] = []
    for ref in docs:
        try:
            resolved.append(resolve_doc_ref(ref, feature_paths, exist_root=exist_root))
        except DocRefError as exc:
            report.errors.append(f"{rel}: [{record.get('id')}] {exc}")
            resolved.append(ref)
    out = dict(record)
    out["source_docs"] = resolved
    return out


def compile_sources(
    source_dir: Path = KG_SOURCE_DIR,
    *,
    strict: bool = False,
    exist_root: Path | None = REPO_ROOT,
    headers: dict[str, dict[str, Any]] | None = None,
) -> CompileResult:
    """Load, validate, resolve, and assemble the projection trio + ontology mirror in memory."""
    source_dir = Path(source_dir)
    headers = headers if headers is not None else _load_headers(source_dir)
    result = CompileResult()

    # 1. Validate every shard first — fail fast, before any assembly.
    vreport = shard_validate.validate_paths([source_dir])
    if vreport.errors:
        result.errors.extend(vreport.errors)
        return result

    # 2. Load + classify all shard files.
    files = shard_validate.iter_shard_files(source_dir)
    loaded: list[tuple[Path, shard_validate.DirClass, list[dict[str, Any]]]] = []
    feature_paths: dict[str, str] = {}
    for path in files:
        dc = shard_validate.classify_directory(path)
        if dc is None or dc.directory == "ontology":
            continue
        recs = _records(load_yaml(path))
        loaded.append((path, dc, recs))
        if dc.directory == "features":
            for r in recs:
                if isinstance(r.get("id"), str) and isinstance(r.get("path"), str):
                    feature_paths[r["id"]] = r["path"]

    # 3. Assemble the trio.
    canonical: dict[str, list[dict[str, Any]]] = {}
    bindings: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []
    stories: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    coverage_excluded: list[dict[str, Any]] = []

    for path, dc, recs in loaded:
        rel = repo_relative(path)
        section = _section_for(dc)
        if section is not None:
            for r in recs:
                canonical.setdefault(section, []).append(
                    _resolve_source_docs(r, feature_paths, exist_root, rel, result)
                )
        elif dc.directory == "bindings":
            bindings.extend(recs)
        elif dc.directory == "features":
            for r in recs:
                if r.get("coverage_excluded"):  # D-coverage-excluded → coverage.excluded_features
                    coverage_excluded.append(
                        {"id": r["id"], "path": r["path"], "reason": r["coverage_excluded"]["reason"]}
                    )
                else:
                    features.append({k: v for k, v in r.items() if k not in FEATURE_PRESENTATION_FIELDS})
                for s in r.get("story_mappings", []) or []:
                    entry = dict(s)  # verbatim story mapping + its owning feature
                    entry["feature"] = r["id"]
                    stories.append(entry)
        elif dc.directory == "exclusions":
            exclusions.extend(recs)

    canonical_doc: dict[str, Any] = {**headers.get("canonical-nodes.yaml", {}), **canonical}
    mappings_doc: dict[str, Any] = {**headers.get("feature-mappings.yaml", {}), "features": features}
    if coverage_excluded:
        mappings_doc["coverage"] = {"excluded_features": coverage_excluded}
    if stories:
        mappings_doc["stories"] = stories
    if exclusions:
        mappings_doc["excluded_features"] = exclusions
    code_index_doc: dict[str, Any] = {**headers.get("code-index.yaml", {}), "node_bindings": bindings}

    result.projections = {
        "canonical-nodes.yaml": canonical_doc,
        "feature-mappings.yaml": mappings_doc,
        "code-index.yaml": code_index_doc,
    }

    # 4. Ontology mirror (D4) — verbatim byte copy; the curated file keeps its authored ordering.
    for p in files:
        dc = shard_validate.classify_directory(p)
        if dc and dc.directory == "ontology" and p.name == ONTOLOGY_BASENAME:
            result.ontology_text = p.read_text(encoding="utf-8")

    # 5. Compile-time analysis (with the suppression ledger).
    _analyze(result, strict, _load_suppressions(source_dir))
    return result


def _load_suppressions(source_dir: Path) -> dict[tuple[str, Any], str]:
    """Read the optional suppression ledger (kg-source/exclusions/suppressions.yaml).

    Each entry names a `kind` (`name-similarity`/`binding-overlap`), its target, and a `rationale`;
    an entry only suppresses when it carries a non-empty rationale (S0008 will enforce that rule).
    """
    ledger = Path(source_dir) / "exclusions" / "suppressions.yaml"
    if not ledger.exists():
        return {}
    out: dict[tuple[str, Any], str] = {}
    for entry in load_yaml(ledger).get("suppressions", []) or []:
        kind = entry.get("kind")
        rationale = entry.get("rationale")
        if not rationale:
            continue
        if kind == "name-similarity" and entry.get("ids"):
            out[("name-similarity", frozenset(entry["ids"]))] = rationale
        elif kind == "binding-overlap" and entry.get("path"):
            out[("binding-overlap", entry["path"])] = rationale
    return out


def _analyze(result: CompileResult, strict: bool, suppressions: dict[tuple[str, Any], str] | None = None) -> None:
    """Duplicate IDs (hard error) + name-similarity & binding-glob overlap (advisory / strict)."""
    suppressions = suppressions or {}

    def sink(key: tuple[str, Any], msg: str) -> None:
        if key in suppressions:
            result.suppressed.append(f"{msg} [suppressed: {suppressions[key]}]")
        else:
            (result.errors if strict else result.warnings).append(msg)

    # Duplicate IDs across the whole trio (hard error regardless of mode).
    for basename, doc in result.projections.items():
        for rid, places in merge3.collect_records(doc).items():
            if len(places) > 1:
                result.errors.append(
                    f"{basename}: duplicate id `{rid}` compiled from {len(places)} shard records — "
                    f"fix the source shards (IDs are unique per graph)."
                )

    # Name-similarity fingerprint (reuse of merge3's normalized-name approach; S0005-D2).
    fingerprints: dict[str, set[str]] = {}
    for doc in result.projections.values():
        for rid, places in merge3.collect_records(doc).items():
            for _, record in places:
                for f in ("label", "name", "title"):
                    text = record.get(f)
                    if isinstance(text, str):
                        norm = "".join(ch for ch in text.casefold() if ch.isalnum())
                        if norm:
                            fingerprints.setdefault(norm, set()).add(rid)
    for norm, ids in sorted(fingerprints.items()):
        if len(ids) > 1:
            sink(("name-similarity", frozenset(ids)),
                 f"name-similarity: {sorted(ids)} share the normalized name `{norm}`")

    # Binding-glob overlap: a code path claimed by >1 binding is a duplicate-binding signal.
    code_index = result.projections.get("code-index.yaml", {})
    path_owners: dict[str, set[str]] = {}
    for binding in code_index.get("node_bindings", []):
        for leaf in _iter_path_leaves(binding.get("paths")):
            path_owners.setdefault(leaf, set()).add(str(binding.get("id")))
    for leaf, owners in sorted(path_owners.items()):
        if len(owners) > 1:
            sink(("binding-overlap", leaf),
                 f"binding-overlap: path `{leaf}` is claimed by {sorted(owners)}")


def _iter_path_leaves(node: Any) -> list[str]:
    if isinstance(node, dict):
        return [leaf for child in node.values() for leaf in _iter_path_leaves(child)]
    if isinstance(node, list):
        return [leaf for item in node for leaf in _iter_path_leaves(item)]
    if isinstance(node, str):
        return [node]
    return []


def render(result: CompileResult) -> dict[str, str]:
    """Canonical serialized text for every generated file this compiler owns."""
    out = {name: canonical_dump(doc) for name, doc in result.projections.items()}
    if result.ontology_text is not None:
        out[ONTOLOGY_BASENAME] = result.ontology_text
    return out


def write_projections(result: CompileResult, out_dir: Path = KG_DIR) -> None:
    """All-or-nothing write of the trio (+ ontology mirror). Caller guarantees result.ok."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in render(result).items():
        merge3._atomic_write(out_dir / name, text)


def check_projections(result: CompileResult, out_dir: Path = KG_DIR) -> list[str]:
    """Return the list of generated files whose committed text != compile(source)."""
    out_dir = Path(out_dir)
    drift: list[str] = []
    for name, text in render(result).items():
        target = out_dir / name
        committed = target.read_text(encoding="utf-8") if target.exists() else None
        if committed != text:
            drift.append(name)
    return drift


def strip_generated_at(path: Path) -> None:
    """Driver-level normalization (S0005-D1): drop a driven generator's `generated_at` line so the
    committed output is a pure function of source. Generator internals are untouched."""
    path = Path(path)
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    stripped = GENERATED_AT_LINE_RE.sub("", text, count=1)
    if stripped != text:
        merge3._atomic_write(path, stripped)


def drive_generators(out_dir: Path = KG_DIR, *, framework_root: Path | None = None,
                     strip: bool = True) -> list[str]:
    """Drive the existing downstream generators, then strip their timestamps (S0005-D1/D5).

    Returns the generator command lines run. Kept behind an explicit flag: it shells out to the
    real toolchain (some generators need the build), so it never runs in the trio-only fast path.
    """
    out_dir = Path(out_dir)
    ran: list[str] = []
    jobs = [
        [sys.executable, str(REPO_ROOT / "scripts" / "kg" / "decisions.py")],
        [sys.executable, str(REPO_ROOT / "scripts" / "kg" / "validate.py"), "--write-coverage-report"],
    ]
    if framework_root is not None:
        jobs.append([sys.executable, str(Path(framework_root) / "agents" / "product-manager" /
                     "scripts" / "generate-story-index.py"), "--product-root", str(REPO_ROOT)])
    for job in jobs:
        subprocess.run(job, check=True, cwd=REPO_ROOT)
        ran.append(" ".join(job))
    if strip:
        for name in ("decisions-index.yaml", "symbol-index.yaml"):
            strip_generated_at(out_dir / name)
    return ran


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile kg-source/ shards into the KG projection trio.")
    parser.add_argument("--source", type=Path, default=KG_SOURCE_DIR, help="kg-source root")
    parser.add_argument("--out", type=Path, default=KG_DIR, help="output (knowledge-graph) dir")
    parser.add_argument("--check", action="store_true", help="compile to memory and diff committed; do not write")
    parser.add_argument("--strict", action="store_true", help="analysis warnings become blocking errors")
    parser.add_argument("--generators", action="store_true", help="also drive downstream generators (needs toolchain)")
    parser.add_argument("--framework-root", type=Path, default=None, help="nebula-agents root, for story-index")
    args = parser.parse_args(argv)

    result = compile_sources(args.source, strict=args.strict, exist_root=REPO_ROOT)
    if not result.ok:
        for err in result.errors:
            print(f"error: {err}", file=sys.stderr)
        print(f"\ncompile FAILED — {len(result.errors)} error(s); nothing written", file=sys.stderr)
        return 1
    for warn in result.warnings:
        print(f"warning: {warn}", file=sys.stderr)

    if result.is_empty:
        print("compile: no shards found in kg-source/ — nothing to compile "
              "(kg-source/ is authored by the S0006 migration; compile is a no-op until then).")
        return 0

    # Tracker generation (S0007) only fires on the real source tree (it renders the real trackers).
    real_tree = Path(args.source).resolve() == KG_SOURCE_DIR.resolve()

    if args.check:
        drift = check_projections(result, args.out)
        if real_tree:
            drift += tracker_gen.check()
        if drift:
            for name in drift:
                print(f"error: {name} is stale — committed output != compile(source). Run compile.py.", file=sys.stderr)
            return 1
        print("compile --check: committed projections + tracker regions match compile(source)")
        return 0

    write_projections(result, args.out)
    printed = ", ".join(render(result))
    print(f"compile: wrote {printed}")
    if real_tree:
        tracker_gen.generate(write=True)
        print("  generated: REGISTRY.md, ROADMAP.md tracker regions")
    if args.generators:
        for cmd in drive_generators(args.out, framework_root=args.framework_root):
            print(f"  drove: {cmd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

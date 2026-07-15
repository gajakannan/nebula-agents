#!/usr/bin/env python3
"""Validate kg-source/ shards against the F0006-S0004 schema + ownership contract.

The shard layer (``planning-mds/kg-source/**``) is the only human/agent-authored graph input; a
deterministic compiler (S0005) projects it into ``planning-mds/knowledge-graph/*.yaml`` and the
tracker tables. This module enforces the *input contract* documented in
``planning-mds/kg-source/README.md``:

* directory ↔ kind agreement and ID grammar (reusing the ontology's ``id_patterns``),
* per-kind required/allowed field profiles (``KIND_PROFILES``),
* references are IDs only (never paths); doc refs are logical ``F####/…`` or stable-root only,
* one concept per file (or an explicitly-allowed per-kind bundle),
* every shard resolves to exactly one owning role.

Standalone CLI *and* importable (S0005's compiler calls ``validate_shard_file``). Every violation
type below is covered by ``scripts/kg/tests/test_shard_validate.py``.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "jsonschema is required for shard validation. Install it with `pip install jsonschema`."
    ) from exc

import kg_common
from kg_common import SECTION_TYPES, load_yaml, repo_relative

REPO_ROOT = kg_common.REPO_ROOT
KG_SOURCE_DIR = REPO_ROOT / "planning-mds" / "kg-source"
SCHEMA_DIR = REPO_ROOT / "planning-mds" / "schemas" / "kg-source"

# Node kinds authored under nodes/<section>/ — every canonical-nodes section except policy_rules,
# which is rehomed to the top-level policies/ directory.
NODE_SECTION_TYPES = {k: v for k, v in SECTION_TYPES.items() if k != "policy_rules"}

# One-concept-per-file directories (D2, confirmed 2026-07-09); every other shard dir allows a bundle.
ONE_PER_FILE_NODE_SECTIONS = {"capabilities", "entities", "workflows"}

# Directories that hold a per-kind bundle-eligible node section, keyed by directory name.
SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"

# Complete ID grammar per kind: reuse kg_common's map, fill the kinds it does not yet cover.
KIND_ID_RE: dict[str, re.Pattern[str]] = dict(kg_common.type_regex_map())
for _kind in ("endpoint", "ui_route", "event", "config_key", "migration", "glossary_term"):
    KIND_ID_RE.setdefault(_kind, re.compile(rf"^{_kind}:{SLUG}$"))

# Every ID prefix a reference may legitimately use (existence is the compiler's job; this catches typos).
KNOWN_ID_PREFIXES = {
    "entity", "workflow", "state", "glossary_term", "capability", "endpoint", "ui_route",
    "event", "config_key", "migration", "role", "policy_rule", "api", "adr", "feature",
    "story", "schema", "evidence", "persona",
}

# Optional fields any node kind may carry (the real graph attaches these broadly).
COMMON_OPTIONAL: set[str] = {"notes", "rationale", "source_docs", "related_nodes", "related_entities"}

# Per-kind field profiles (README §3). id is always allowed. Fields outside required∪allowed fail.
KIND_PROFILES: dict[str, dict[str, set[str]]] = {
    "adr": {"required": {"label", "path"}, "allowed": {"related_nodes"}},
    "api_contract": {"required": {"label", "path"}, "allowed": {"related_nodes"}},
    "capability": {"required": {"label"}, "allowed": {"source_docs", "related_nodes", "notes"}},
    "config_key": {"required": {"label", "key"}, "allowed": {"related_nodes", "source_docs", "notes"}},
    "endpoint": {"required": {"label", "route", "method"}, "allowed": {"related_nodes", "source_docs", "resource"}},
    "entity": {"required": {"label"}, "allowed": {"source_docs", "related_nodes", "related_entities", "notes"}},
    "event": {"required": {"label", "event_type"}, "allowed": {"related_nodes", "source_docs"}},
    "evidence": {"required": {"label", "path"}, "allowed": {"related_nodes"}},
    "glossary_term": {"required": {"label"}, "allowed": {"related_nodes", "source_docs"}},
    "migration": {"required": {"label", "path"}, "allowed": {"related_nodes"}},
    "role": {"required": {"label"}, "allowed": {"notes", "source_docs", "related_nodes"}},
    "schema": {"required": {"path"}, "allowed": {"related_nodes", "label"}},
    "ui_route": {"required": {"label", "route"}, "allowed": {"related_nodes", "source_docs"}},
    "workflow": {"required": {"label"}, "allowed": {"rationale", "states", "source_docs", "related_nodes"}},
    "policy_rule": {"required": {"label", "resource", "action", "allowed_roles"}, "allowed": {"related_nodes", "source_docs"}},
}

# Referential fields whose values must be IDs, not paths. (kg_common.REF_FIELDS + node/role edges.)
REFERENCE_FIELDS = set(kg_common.REF_FIELDS) | {
    "related_nodes", "related_entities", "allowed_roles", "superseded_by", "governed_by",
}

# Fields that carry doc refs (subject to the logical-ref / stable-root rules).
DOC_REF_FIELDS = {"source_docs"}
# node `path` on these kinds is a stable-root doc ref (also subject to the physical-feature-path ban).
PATH_DOCREF_KINDS = {"adr", "api_contract", "migration", "schema", "evidence"}

PHYSICAL_FEATURE_RE = re.compile(r"planning-mds/features/(?:archive/)?F(\d{4})[^/]*(?:/(.*))?$")
LOGICAL_REF_RE = re.compile(r"^F\d{4}/")


@dataclass
class DirClass:
    """Classification of a shard file's directory: kind, schema, ownership, bundle-eligibility."""

    directory: str
    kind: str | None          # node/policy kind, or None for binding/exclusion/ontology
    schema: str | None        # node|feature|binding|exclusion, or None for ontology
    bundle_allowed: bool
    owner: str
    cosign: tuple[str, ...] = ()


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


def _shard_rel_parts(path: Path) -> tuple[str, ...] | None:
    """Path segments after the (last) `kg-source` dir — works for the real tree and test fixtures."""
    parts = path.parts
    if "kg-source" not in parts:
        return None
    idx = len(parts) - 1 - parts[::-1].index("kg-source")
    return parts[idx + 1:]


def classify_directory(path: Path) -> DirClass | None:
    """Map a shard file to its directory class, or None if it lives outside a mapped directory."""
    tail = _shard_rel_parts(path)
    if not tail:
        return None
    top = tail[0]
    if top == "nodes":
        if len(tail) < 3:  # nodes/<section>/<file>
            return None
        section = tail[1]
        kind = NODE_SECTION_TYPES.get(section)
        if kind is None:
            return None
        return DirClass(
            directory=f"nodes/{section}",
            kind=kind,
            schema="node",
            bundle_allowed=section not in ONE_PER_FILE_NODE_SECTIONS,
            owner="architect",
        )
    if top == "policies":
        return DirClass("policies", "policy_rule", "node", True, "architect", cosign=("security",))
    if top == "bindings":
        return DirClass("bindings", None, "binding", True, "architect")
    if top == "features":
        return DirClass("features", "feature", "feature", False, "product-manager")
    if top == "exclusions":
        return DirClass("exclusions", None, "exclusion", True, "product-manager", cosign=("architect",))
    if top == "ontology":
        return DirClass("ontology", None, None, True, "architect", cosign=("product-manager",))
    return None


_SCHEMA_CACHE: dict[str, jsonschema.protocols.Validator] = {}


def _schema_validator(name: str) -> jsonschema.protocols.Validator:
    if name not in _SCHEMA_CACHE:
        schema = load_yaml(SCHEMA_DIR / f"{name}.schema.json")  # JSON is a YAML subset
        _SCHEMA_CACHE[name] = jsonschema.Draft7Validator(schema)
    return _SCHEMA_CACHE[name]


def _records_from_file(data: Any, dc: DirClass, rel: str, report: Report) -> list[dict[str, Any]]:
    """Split a shard file into records, enforcing the one-concept / bundle rule."""
    if isinstance(data, dict) and "id" in data:
        return [data]
    is_bundle = False
    records: list[dict[str, Any]] = []
    if isinstance(data, dict) and len(data) == 1 and isinstance(next(iter(data.values())), list):
        records = [r for r in next(iter(data.values())) if isinstance(r, dict)]
        is_bundle = True
    elif isinstance(data, list):
        records = [r for r in data if isinstance(r, dict)]
        is_bundle = True
    else:
        report.error(
            f"{rel}: file must be a single concept (top-level `id:`) or a single-key bundle "
            f"(`<kind>:` → list of records); found {type(data).__name__} with keys "
            f"{sorted(data)[:5] if isinstance(data, dict) else '—'}"
        )
        return []
    if is_bundle and not dc.bundle_allowed:
        report.error(
            f"{rel}: directory '{dc.directory}' requires one concept per file — bundle form not "
            f"allowed (D2). Split into one file per record."
        )
        return []
    return records


def _check_reference_value(value: Any, field_name: str, rel: str, report: Report) -> None:
    if isinstance(value, dict):  # object-form edge ref {id, provenance, confidence, …}
        value = value.get("id")
    if not isinstance(value, str):
        report.error(f"{rel}: {field_name} entry must be an ID string (or {{id: …}}), got {type(value).__name__}")
        return
    if "/" in value or ":" not in value:
        report.error(
            f"{rel}: {field_name} entry '{value}' must be a canonical ID (e.g. capability:foo), "
            f"never a path — shards reference other concepts by ID only."
        )
        return
    prefix = value.split(":", 1)[0]
    if prefix not in KNOWN_ID_PREFIXES:
        report.error(f"{rel}: {field_name} entry '{value}' has unknown reference kind '{prefix}:'")


def _check_doc_ref(value: str, field_name: str, rel: str, report: Report) -> None:
    if not isinstance(value, str):
        report.error(f"{rel}: {field_name} entry must be a string ref, got {type(value).__name__}")
        return
    m = PHYSICAL_FEATURE_RE.search(value)
    if m:
        rest = m.group(2)
        hint = f"F{m.group(1)}/{rest}" if rest else f"F{m.group(1)}/…"
        report.error(
            f"{rel}: {field_name} '{value}' is a physical feature-doc path; use the logical form "
            f"'{hint}' — the compiler resolves F#### through the feature shard's `path:`, so archive "
            f"moves need no shard edit."
        )
        return
    if LOGICAL_REF_RE.match(value):
        return  # logical ref — resolved at compile time
    # stable-root physical ref (architecture/, api/, schemas/, security/, engine/, …) — passes through.


def _check_binding_paths(node: Any, rel: str, rid: str, report: Report) -> None:
    """Walk a binding's nested `paths` structure; every leaf must be a syntactically valid glob."""
    if isinstance(node, dict):
        for child in node.values():
            _check_binding_paths(child, rel, rid, report)
    elif isinstance(node, list):
        for item in node:
            _check_binding_paths(item, rel, rid, report)
    elif isinstance(node, str):
        if not node.strip():
            report.error(f"{rel}: [{rid}] binding path is empty")
        elif node.count("[") != node.count("]"):
            report.error(f"{rel}: [{rid}] binding path '{node}' is not a syntactically valid glob (unbalanced [ ])")
    else:
        report.error(f"{rel}: [{rid}] binding path must be a string, got {type(node).__name__}")


def _validate_record(record: dict[str, Any], dc: DirClass, rel: str, report: Report) -> None:
    rid = record.get("id")
    if not isinstance(rid, str) or not rid:
        report.error(f"{rel}: record is missing a string `id`")
        return

    # 1. JSON-schema structural envelope.
    if dc.schema:
        for err in _schema_validator(dc.schema).iter_errors(record):
            loc = "/".join(str(p) for p in err.absolute_path) or "(root)"
            report.error(f"{rel}: [{rid}] schema: {loc}: {err.message}")

    # 2. ID grammar + directory/kind agreement (for node & policy_rule kinds).
    if dc.kind and dc.kind in KIND_ID_RE:
        if not KIND_ID_RE[dc.kind].match(rid):
            report.error(
                f"{rel}: [{rid}] id does not match the `{dc.kind}` grammar for directory "
                f"'{dc.directory}' (expected `{dc.kind if dc.kind != 'api_contract' else 'api'}:<slug>`)."
            )

    # 3. Per-kind required/allowed field profile.
    profile = KIND_PROFILES.get(dc.kind or "")
    if profile:
        present = set(record) - {"id"}
        missing = profile["required"] - present
        if missing:
            report.error(f"{rel}: [{rid}] missing required field(s) for `{dc.kind}`: {sorted(missing)}")
        unexpected = present - profile["required"] - profile["allowed"] - COMMON_OPTIONAL
        if unexpected:
            report.error(f"{rel}: [{rid}] unexpected field(s) for `{dc.kind}`: {sorted(unexpected)}")

    # 4. References are IDs only.
    for fname in REFERENCE_FIELDS:
        val = record.get(fname)
        if val is None:
            continue
        for item in (val if isinstance(val, list) else [val]):
            _check_reference_value(item, fname, rel, report)

    # 5. Doc refs are logical or stable-root only (never a physical feature-doc path).
    for fname in DOC_REF_FIELDS:
        for item in record.get(fname, []) or []:
            _check_doc_ref(item, fname, rel, report)
    if dc.kind in PATH_DOCREF_KINDS and isinstance(record.get("path"), str):
        _check_doc_ref(record["path"], "path", rel, report)

    # 6. Binding globs are syntactically valid.
    if dc.schema == "binding" and isinstance(record.get("paths"), dict):
        _check_binding_paths(record["paths"], rel, rid, report)

    # 7. Feature story mappings (D3): story ids well-formed; nested refs are IDs only.
    if dc.schema == "feature" and isinstance(record.get("story_mappings"), list):
        for story in record["story_mappings"]:
            if not isinstance(story, dict):
                continue
            sid = story.get("id")
            if isinstance(sid, str) and not KIND_ID_RE["story"].match(sid):
                report.error(f"{rel}: [{rid}] story id '{sid}' must match `story:F####-S####`")
            for fname in ("affects", "depends_on", "governed_by", "uses_api_contract", "uses_schema"):
                for item in story.get(fname, []) or []:
                    _check_reference_value(item, f"stories[{sid}].{fname}", rel, report)


def validate_shard_file(path: Path, report: Report | None = None) -> Report:
    """Validate one shard file. Returns the Report (accumulating if one is passed in)."""
    report = report or Report()
    path = Path(path)
    rel = repo_relative(path)

    dc = classify_directory(path)
    if dc is None:
        report.error(
            f"{rel}: file is outside a mapped kg-source directory (or an unknown node kind) — "
            f"every shard must live under a directory with exactly one owning role."
        )
        return report

    if dc.directory == "ontology":
        try:
            load_yaml(path)  # curated whole-file source; per-record schema is out of scope for S0004
        except SystemExit as exc:
            report.error(f"{rel}: {exc}")
        return report

    try:
        data = load_yaml(path)
    except SystemExit as exc:
        report.error(f"{rel}: {exc}")
        return report

    for record in _records_from_file(data, dc, rel, report):
        _validate_record(record, dc, rel, report)
    return report


# Files under kg-source/ that are tooling ledgers, not concept shards (not validated/assembled).
NON_SHARD_BASENAMES = {"suppressions.yaml", "projections-meta.yaml"}


def iter_shard_files(root: Path) -> list[Path]:
    root = Path(root)
    if root.is_file():
        return [root]
    return sorted(
        p for p in root.rglob("*.y*ml")
        if p.is_file() and p.name not in NON_SHARD_BASENAMES
    )


def validate_paths(paths: list[Path]) -> Report:
    report = Report()
    files: list[Path] = []
    for p in paths:
        files.extend(iter_shard_files(p))
    for f in files:
        validate_shard_file(f, report)
    return report


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    targets = [Path(a) for a in argv] if argv else [KG_SOURCE_DIR]
    missing = [t for t in targets if not t.exists()]
    if missing:
        for t in missing:
            print(f"error: path does not exist: {t}", file=sys.stderr)
        return 2
    report = validate_paths(targets)
    if report.ok:
        print("shard validation: OK")
        return 0
    for err in report.errors:
        print(f"error: {err}", file=sys.stderr)
    print(f"\nshard validation FAILED — {len(report.errors)} violation(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

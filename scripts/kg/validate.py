#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import yaml

from kg_common import (
    KG_DIR,
    REF_FIELDS,
    REPO_ROOT,
    SECTION_TYPES,
    VALID_PROVENANCE,
    collect_referenced_node_ids,
    edge_ref_id,
    edge_ref_ids,
    edge_ref_provenance,
    excluded_feature_paths,
    expand_declared_pattern,
    iter_feature_dirs,
    load_bundle,
    normalize_repo_path,
    type_regex_map,
)
from hotspots import compute_hotspots


class ValidationReport:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


COVERAGE_REPORT_PATH = KG_DIR / "coverage-report.yaml"
SYMBOL_INDEX_PATH = KG_DIR / "symbol-index.yaml"
DECISIONS_INDEX_PATH = KG_DIR / "decisions-index.yaml"
UNBOUND_REFERENCED_PATH = KG_DIR / "unbound-but-referenced.yaml"
DECISION_KINDS = {"WHY", "DECISION", "TRADEOFF", "SUPERSEDES"}

# Default orphan-check exemptions. Workflow states roll up to their workflow
# and are validated transitively. Glossary terms are vocabulary anchors that
# need no outbound binding — their value is being referenced from prose.
DEFAULT_ORPHAN_EXEMPT_KINDS: frozenset[str] = frozenset({"workflow_state", "glossary_term"})

# Default coverage-gap exclusions. Mirrors scripts/kg/coverage-gaps.py defaults;
# duplicated rather than imported because the gate and the ad-hoc CLI may
# legitimately need to drift independently per product.
DEFAULT_COVERAGE_GAP_EXCLUDES: tuple[str, ...] = (
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

# --check-untested considers only callable bound surfaces. Other kinds
# (interfaces, properties, constructors, enums, types) aren't meaningfully
# "tested" the same way a method or function is.
UNTESTED_TARGET_KINDS: frozenset[str] = frozenset({"method", "function"})
ADR_REF_RE = re.compile(
    r"\b(?:ADR[-\s:]?|adr:)([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)\b",
    re.IGNORECASE,
)


def validate_id(report: ValidationReport, node_id: str, node_type: str, patterns: dict[str, Any]) -> None:
    regex = patterns.get(node_type)
    if regex is None:
        return
    if not regex.fullmatch(node_id):
        report.error(f"ID does not match {node_type} pattern: {node_id}")


def validate_path_exists(report: ValidationReport, path_value: str, context: str) -> None:
    normalized = normalize_repo_path(path_value)
    candidate = Path(normalized)
    if not (REPO_ROOT / candidate).exists():
        report.error(f"Missing path for {context}: {normalized}")


def validate_references(report: ValidationReport, item: dict[str, Any], all_nodes: dict[str, Any]) -> None:
    item_id = item["id"]
    for field in REF_FIELDS:
        for ref in item.get(field, []):
            ref_id = edge_ref_id(ref)
            if ref_id not in all_nodes:
                report.error(f"Unknown reference in {item_id}.{field}: {ref_id}")
            validate_edge_provenance(report, ref, f"{item_id}.{field}")

    feature_ref = item.get("feature")
    if feature_ref and feature_ref not in all_nodes:
        report.error(f"Unknown feature reference in {item_id}.feature: {feature_ref}")


def validate_edge_provenance(report: ValidationReport, ref: Any, context: str) -> None:
    """Validate provenance annotation on an edge reference."""
    if isinstance(ref, str):
        return
    if not isinstance(ref, dict):
        report.error(f"Edge reference in {context} is neither string nor object: {ref!r}")
        return

    ref_id = ref.get("id")
    if not ref_id:
        report.error(f"Edge reference object in {context} is missing 'id'")
        return

    prov = ref.get("provenance")
    if prov is None:
        return

    if prov not in VALID_PROVENANCE:
        report.error(f"Invalid provenance '{prov}' on {ref_id} in {context} (valid: {', '.join(sorted(VALID_PROVENANCE))})")
        return

    if prov == "inferred":
        confidence = ref.get("confidence")
        if confidence is None:
            report.warn(f"Inferred edge {ref_id} in {context} is missing confidence score")
        elif not isinstance(confidence, (int, float)) or confidence < 0.0 or confidence > 1.0:
            report.error(f"Invalid confidence {confidence!r} on {ref_id} in {context} (must be 0.0–1.0)")
        elif confidence < 0.5:
            report.warn(f"Low-confidence inferred edge ({confidence}) on {ref_id} in {context}")

    if prov == "ambiguous":
        report.warn(f"Ambiguous edge {ref_id} in {context} — flagged for architect review")


def validate_rationale_entry(
    report: ValidationReport, entry: Any, node_id: str, all_nodes: dict[str, Any]
) -> None:
    """Validate a single rationale entry on a canonical node."""
    if not isinstance(entry, dict):
        report.error(f"Rationale entry on {node_id} is not an object: {entry!r}")
        return

    adr_ref = entry.get("adr")
    if not adr_ref:
        report.error(f"Rationale entry on {node_id} is missing 'adr' field")
        return
    if adr_ref not in all_nodes:
        report.error(f"Rationale on {node_id} references unknown ADR: {adr_ref}")

    if not entry.get("section"):
        report.error(f"Rationale entry on {node_id} (adr: {adr_ref}) is missing 'section' field")

    if not entry.get("summary"):
        report.error(f"Rationale entry on {node_id} (adr: {adr_ref}) is missing 'summary' field")


def iter_existing_files(paths: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()

    for value in paths:
        normalized = normalize_repo_path(value)
        candidate = REPO_ROOT / normalized
        if not candidate.exists():
            continue

        if candidate.is_dir():
            nested = sorted(path for path in candidate.rglob("*") if path.is_file())
            for path in nested:
                rel = path.relative_to(REPO_ROOT).as_posix()
                if rel not in seen:
                    seen.add(rel)
                    files.append(path)
            continue

        rel = candidate.relative_to(REPO_ROOT).as_posix()
        if rel not in seen:
            seen.add(rel)
            files.append(candidate)

    return files


def digest_files(paths: Iterable[Path]) -> str:
    hasher = hashlib.sha256()
    for path in sorted(paths):
        rel = path.relative_to(REPO_ROOT).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()[:16]


def latest_modified_date(paths: Iterable[Path]) -> str | None:
    timestamps = [path.stat().st_mtime for path in paths]
    if not timestamps:
        return None
    return datetime.fromtimestamp(max(timestamps), UTC).date().isoformat()


def build_freshness_entry(source_paths: Iterable[str]) -> dict[str, Any]:
    files = iter_existing_files(source_paths)
    relative_files = [path.relative_to(REPO_ROOT).as_posix() for path in files]
    return {
        "source_paths": relative_files,
        "source_count": len(relative_files),
        "last_modified": latest_modified_date(files),
        "source_hash": digest_files(files) if files else None,
    }


def build_coverage_report(
    bundle: dict[str, Any],
    mapped_feature_paths: set[str],
    excluded_paths: set[str],
    uncovered: list[str],
    symbol_summary: dict[str, Any] | None = None,
    decisions_summary: dict[str, Any] | None = None,
    hotspot_signals: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    canonical = bundle["canonical"]
    mappings = bundle["mappings"]
    code_index = bundle["code_index"]

    canonical_freshness: dict[str, Any] = {}
    for section in SECTION_TYPES:
        for item in canonical.get(section, []):
            source_paths = list(item.get("source_docs", []))
            if item.get("path"):
                source_paths.append(item["path"])
            entry = build_freshness_entry(source_paths)
            if hotspot_signals and item["id"] in hotspot_signals:
                # Phase 3 fields are additive: merge over the existing
                # source-doc last_modified with the git-derived value when
                # available, so the field reflects the freshest signal.
                signals = hotspot_signals[item["id"]]
                git_last_modified = signals.get("last_modified")
                if git_last_modified:
                    existing = entry.get("last_modified")
                    if not existing or git_last_modified > existing:
                        entry["last_modified"] = git_last_modified
                entry.update(
                    {
                        "hotspot_rank": signals["hotspot_rank"],
                        "hotspot_score": signals["hotspot_score"],
                        "primary_owner": signals["primary_owner"],
                        "primary_owner_pct": signals["primary_owner_pct"],
                        "bus_factor_flag": signals["bus_factor_flag"],
                    }
                )
            canonical_freshness[item["id"]] = entry

    mapping_freshness: dict[str, Any] = {}
    for section_name in ("features", "stories"):
        for item in mappings.get(section_name, []):
            mapping_freshness[item["id"]] = build_freshness_entry([item["path"]])

    binding_freshness: dict[str, Any] = {}
    for binding in code_index.get("node_bindings", []):
        declared_paths = bundle["bindings"].get(binding["id"], {}).get("declared_paths", [])
        resolved: list[str] = []
        for entry in declared_paths:
            resolved.extend(expand_declared_pattern(entry["pattern"]))
        binding_freshness[binding["id"]] = build_freshness_entry(resolved)

    summary: dict[str, Any] = {
        "canonical_nodes": len(bundle["canonical_nodes"]),
        "features_mapped": len(mappings.get("features", [])),
        "stories_mapped": len(mappings.get("stories", [])),
        "features_excluded": len(excluded_paths),
        "features_uncovered": len(uncovered),
        "code_bindings": len(code_index.get("node_bindings", [])),
    }
    if symbol_summary and symbol_summary.get("exists"):
        summary["symbol_count"] = symbol_summary.get("symbol_count", 0)
        summary["bound_symbol_count"] = symbol_summary.get("bound_symbol_count", 0)
    if decisions_summary and decisions_summary.get("exists"):
        summary["decision_count"] = decisions_summary.get("decision_count", 0)
        summary["why_count"] = decisions_summary.get("why_count", 0)

    report_payload: dict[str, Any] = {
        "version": 0,
        "summary": summary,
        "coverage": {
            "mapped_feature_ids": [item["id"] for item in mappings.get("features", [])],
            "excluded_features": mappings.get("coverage", {}).get("excluded_features", []),
            "uncovered_feature_paths": uncovered,
            "mapped_story_ids": [item["id"] for item in mappings.get("stories", [])],
        },
        "freshness": {
            "canonical": canonical_freshness,
            "mappings": mapping_freshness,
            "code_bindings": binding_freshness,
        },
    }
    if symbol_summary and symbol_summary.get("exists"):
        report_payload["symbols"] = {
            "symbol_count": symbol_summary.get("symbol_count", 0),
            "bound_symbol_count": symbol_summary.get("bound_symbol_count", 0),
            "by_language": symbol_summary.get("by_language", {}),
        }
    if decisions_summary and decisions_summary.get("exists"):
        report_payload["decisions"] = {
            "decision_count": decisions_summary.get("decision_count", 0),
            "why_count": decisions_summary.get("why_count", 0),
            "by_kind": decisions_summary.get("by_kind", {}),
        }
    return report_payload


def write_coverage_report(report_payload: dict[str, Any]) -> None:
    COVERAGE_REPORT_PATH.write_text(
        yaml.safe_dump(report_payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Drift checkers
# ---------------------------------------------------------------------------

MEMORY_LINK_RE = re.compile(r"\[([^\]]+)\]\(\./?([\w.-]+\.md)\)")
REPO_PATH_RE = re.compile(
    r"`((?:agents|planning-mds|engine|experience|neuron|scripts|docker"
    r"|\.github)/[\w./*\-]+)`"
)


def validate_external_memory_drift(report: ValidationReport, memory_dir: Path) -> None:
    """Check an external agent memory directory for stale repo-path references.

    Agent-agnostic: any coding agent that stores file-based memory can pass its
    memory directory via --memory-dir. No vendor-specific path conventions are
    assumed.

    Checks performed:
    1. If an index file (MEMORY.md or similar) links to .md files, verify they exist.
    2. All .md files in the directory are scanned for backtick-quoted repo paths
       that no longer resolve — a signal the memory is stale.
    """
    if not memory_dir.is_dir():
        report.error(f"--memory-dir path is not a directory: {memory_dir}")
        return

    # Optional index file — check linked files if present
    memory_md = memory_dir / "MEMORY.md"
    if memory_md.exists():
        content = memory_md.read_text(encoding="utf-8")
        linked_files = {m.group(2): m.group(1) for m in MEMORY_LINK_RE.finditer(content)}

        for filename in linked_files:
            if not (memory_dir / filename).exists():
                report.error(f"Memory index links to missing file: {filename}")

        for path in sorted(memory_dir.glob("*.md")):
            if path.name == "MEMORY.md":
                continue
            if path.name not in linked_files:
                report.warn(f"Memory file not indexed: {path.name}")

    # Scan all .md files for dead repo-path references
    for path in sorted(memory_dir.glob("*.md")):
        file_content = path.read_text(encoding="utf-8")
        for match in REPO_PATH_RE.finditer(file_content):
            ref_path = match.group(1)
            if "*" in ref_path:
                continue
            if not (REPO_ROOT / ref_path).exists():
                report.warn(
                    f"Memory file {path.name} references missing repo path: {ref_path}"
                )


def parse_casbin_policy_pairs(policy_path: Path) -> set[tuple[str, str]]:
    """Extract unique (resource, action) pairs from policy.csv."""
    pairs: set[tuple[str, str]] = set()
    for line in policy_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4 and parts[0] == "p":
            pairs.add((parts[2], parts[3]))
    return pairs


def parse_casbin_role_map(
    policy_path: Path,
) -> dict[tuple[str, str], set[str]]:
    """Map (resource, action) → set of roles from policy.csv."""
    role_map: dict[tuple[str, str], set[str]] = {}
    for line in policy_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4 and parts[0] == "p":
            key = (parts[2], parts[3])
            role_map.setdefault(key, set()).add(parts[1])
    return role_map


ROLE_SLUG_TO_CSV = {
    "distribution-user": "DistributionUser",
    "distribution-manager": "DistributionManager",
    "underwriter": "Underwriter",
    "relationship-manager": "RelationshipManager",
    "program-manager": "ProgramManager",
    "admin": "Admin",
    "broker-user": "BrokerUser",
    "coordinator": "Coordinator",
    "compliance-quality-lead": "ComplianceQualityLead",
    "configuration-steward": "ConfigurationSteward",
    "mga-user": "MgaUser",
    "operations-manager": "OperationsManager",
    "external-user": "ExternalUser",
}


def validate_casbin_drift(
    report: ValidationReport, bundle: dict[str, Any]
) -> None:
    """Cross-check policy_rule nodes against actual policy.csv entries."""
    policy_path = REPO_ROOT / "planning-mds" / "security" / "policies" / "policy.csv"
    if not policy_path.exists():
        report.warn("policy.csv not found; skipping Casbin drift check")
        return

    actual_pairs = parse_casbin_policy_pairs(policy_path)
    actual_roles = parse_casbin_role_map(policy_path)
    canonical = bundle["canonical"]

    declared_pairs: set[tuple[str, str]] = set()
    declared_rules: dict[tuple[str, str], dict[str, Any]] = {}
    for rule in canonical.get("policy_rules", []):
        resource = rule.get("resource")
        action = rule.get("action")
        if resource and action:
            pair = (resource, action)
            declared_pairs.add(pair)
            declared_rules[pair] = rule

    # Pairs in policy.csv but not in canonical-nodes
    for resource, action in sorted(actual_pairs - declared_pairs):
        report.warn(
            f"Casbin policy pair ({resource}, {action}) in policy.csv "
            f"has no policy_rule node in canonical-nodes.yaml"
        )

    # Pairs in canonical-nodes but not in policy.csv
    for resource, action in sorted(declared_pairs - actual_pairs):
        report.error(
            f"policy_rule declares ({resource}, {action}) but no matching "
            f"lines exist in policy.csv"
        )

    # Role-level mismatch for shared pairs
    for pair in sorted(declared_pairs & actual_pairs):
        rule = declared_rules[pair]
        declared_role_slugs = {
            r.replace("role:", "") for r in rule.get("allowed_roles", [])
        }
        declared_csv_roles = {
            ROLE_SLUG_TO_CSV[s]
            for s in declared_role_slugs
            if s in ROLE_SLUG_TO_CSV
        }
        actual_csv_roles = actual_roles.get(pair, set())

        missing_in_ontology = actual_csv_roles - declared_csv_roles
        missing_in_csv = declared_csv_roles - actual_csv_roles

        resource, action = pair
        for role in sorted(missing_in_ontology):
            report.warn(
                f"policy.csv grants {role} ({resource}, {action}) but "
                f"policy_rule:{resource}-{action} omits it from allowed_roles"
            )
        for role in sorted(missing_in_csv):
            report.warn(
                f"policy_rule:{resource}-{action} declares {role} in "
                f"allowed_roles but no matching policy.csv line exists"
            )


def validate_symbol_index(
    report: ValidationReport, bundle: dict[str, Any], *, required: bool = False
) -> dict[str, Any]:
    """Validate symbol-index.yaml: each entry resolves to a canonical node and
    a real file. Returns a small summary used by the coverage report.

    If `required` is True (set when --check-symbols is passed), a missing
    symbol-index.yaml is an error. Otherwise it is silent (the symbol layer
    is optional during framework-bootstrap).
    """
    summary: dict[str, Any] = {
        "exists": False,
        "symbol_count": 0,
        "bound_symbol_count": 0,
        "by_language": {},
    }
    if not SYMBOL_INDEX_PATH.exists():
        if required:
            report.error(
                "symbol-index.yaml not found "
                "(run python3 scripts/kg/symbols.py to generate)"
            )
        return summary

    symbols_doc = yaml.safe_load(SYMBOL_INDEX_PATH.read_text(encoding="utf-8")) or {}
    symbols = symbols_doc.get("symbols", []) or []
    summary["exists"] = True
    summary["symbol_count"] = len(symbols)

    all_nodes = bundle["all_nodes"]
    bindings = bundle["bindings"]
    by_id: dict[str, dict[str, Any]] = {}
    by_language: dict[str, int] = {}
    bound_count = 0

    for entry in symbols:
        sid = entry.get("id")
        if not sid or not isinstance(sid, str):
            report.error(f"symbol-index entry missing id: {entry!r}")
            continue
        if sid in by_id:
            report.error(f"duplicate symbol id in symbol-index.yaml: {sid}")
            continue
        by_id[sid] = entry

        node_id = entry.get("node")
        if not node_id or node_id not in all_nodes:
            report.error(f"symbol {sid} references unknown canonical node: {node_id}")
            continue
        if node_id in bindings:
            bound_count += 1

        file_rel = entry.get("file")
        if not file_rel:
            report.error(f"symbol {sid} missing file")
        else:
            abs_path = REPO_ROOT / normalize_repo_path(file_rel)
            if not abs_path.is_file():
                report.error(f"symbol {sid} file does not exist: {file_rel}")

        line = entry.get("line")
        if not isinstance(line, int) or line < 1:
            report.error(f"symbol {sid} has invalid line: {line!r}")

        lang = entry.get("language") or "unknown"
        by_language[lang] = by_language.get(lang, 0) + 1

    # Dangling caller/callee references are warnings (over-linking is OK).
    for sid, entry in by_id.items():
        for kind, refs in (("callers", entry.get("callers", [])), ("callees", entry.get("callees", []))):
            for ref in refs:
                if ref not in by_id:
                    report.warn(f"symbol {sid}.{kind} references unknown symbol: {ref}")

    summary["bound_symbol_count"] = bound_count
    summary["by_language"] = by_language
    return summary


def normalize_adr_ref(value: str) -> str | None:
    match = ADR_REF_RE.search(value)
    if not match:
        return None
    return f"adr:{match.group(1).lower()}"


def why_polarity_key(text: str) -> tuple[str, str, int] | None:
    """Return a conservative contradiction key for WHY text."""
    normalized = re.sub(r"[^a-z0-9\s-]", " ", text.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    patterns = (
        (r"\bmust not\s+(.+)", "must", -1),
        (r"\bmust\s+(.+)", "must", 1),
        (r"\bshould not\s+(.+)", "should", -1),
        (r"\bshould\s+(.+)", "should", 1),
        (r"\bnever\s+(.+)", "always", -1),
        (r"\balways\s+(.+)", "always", 1),
    )
    for pattern, modal, polarity in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        remainder = " ".join(match.group(1).split()[:10])
        if remainder:
            return modal, remainder, polarity
    return None


def validate_why_contradictions(
    report: ValidationReport, why_entries: list[dict[str, Any]]
) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in why_entries:
        group_key = entry.get("resolved_symbol") or f"file:{entry.get('file')}"
        grouped.setdefault(group_key, []).append(entry)

    for group_key, entries in grouped.items():
        seen: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}
        for entry in entries:
            key = why_polarity_key(entry.get("text", ""))
            if key is None:
                continue
            modal, subject, polarity = key
            prior = seen.get((modal, subject))
            if prior is not None and prior[0] != polarity:
                report.warn(
                    "Potential contradictory WHY markers on "
                    f"{group_key}: {prior[1].get('id')} and {entry.get('id')}"
                )
            else:
                seen[(modal, subject)] = (polarity, entry)


def validate_decision_index(
    report: ValidationReport, bundle: dict[str, Any], *, required: bool = False
) -> dict[str, Any]:
    """Validate decisions-index.yaml and return summary for coverage."""
    summary: dict[str, Any] = {
        "exists": False,
        "decision_count": 0,
        "why_count": 0,
        "by_kind": {},
    }
    if not DECISIONS_INDEX_PATH.exists():
        if required:
            report.error(
                "decisions-index.yaml not found "
                "(run python3 scripts/kg/decisions.py to generate)"
            )
        return summary

    decisions_doc = yaml.safe_load(DECISIONS_INDEX_PATH.read_text(encoding="utf-8")) or {}
    decisions = decisions_doc.get("decisions", []) or []
    summary["exists"] = True
    summary["decision_count"] = len(decisions)

    all_nodes = bundle["all_nodes"]
    symbols_by_id = bundle.get("symbols_by_id", {})
    seen_ids: set[str] = set()
    by_kind: dict[str, int] = {}
    why_entries: list[dict[str, Any]] = []

    for entry in decisions:
        decision_id = entry.get("id")
        if not decision_id or not isinstance(decision_id, str):
            report.error(f"decisions-index entry missing id: {entry!r}")
            continue
        if decision_id in seen_ids:
            report.error(f"duplicate decision id in decisions-index.yaml: {decision_id}")
            continue
        seen_ids.add(decision_id)

        kind = entry.get("kind")
        if kind not in DECISION_KINDS:
            report.error(f"decision {decision_id} has invalid kind: {kind!r}")
        else:
            by_kind[kind] = by_kind.get(kind, 0) + 1
            if kind == "WHY":
                why_entries.append(entry)

        if not entry.get("text"):
            report.error(f"decision {decision_id} is missing text")

        file_rel = entry.get("file")
        line = entry.get("line")
        if not file_rel:
            report.error(f"decision {decision_id} missing file")
        else:
            abs_path = REPO_ROOT / normalize_repo_path(file_rel)
            if not abs_path.is_file():
                report.error(f"decision {decision_id} file does not exist: {file_rel}")
            elif not isinstance(line, int) or line < 1:
                report.error(f"decision {decision_id} has invalid line: {line!r}")
            else:
                line_count = len(abs_path.read_text(encoding="utf-8").splitlines())
                if line > line_count:
                    report.error(
                        f"decision {decision_id} line {line} exceeds file length {line_count}"
                    )

        node_id = entry.get("resolved_node")
        if not node_id or node_id not in all_nodes:
            report.error(
                f"decision {decision_id} references unknown canonical node: {node_id}"
            )

        symbol_id = entry.get("resolved_symbol")
        if symbol_id and symbol_id not in symbols_by_id:
            report.warn(
                f"decision {decision_id} references unknown symbol: {symbol_id}"
            )

        if kind == "SUPERSEDES":
            adr_ref = entry.get("supersedes_adr") or normalize_adr_ref(entry.get("text", ""))
            if not adr_ref:
                report.error(f"SUPERSEDES marker {decision_id} is missing an ADR reference")
            elif adr_ref not in all_nodes:
                report.error(f"SUPERSEDES marker {decision_id} references unknown ADR: {adr_ref}")

    validate_why_contradictions(report, why_entries)
    summary["why_count"] = by_kind.get("WHY", 0)
    summary["by_kind"] = by_kind
    return summary


def validate_orphans(
    report: ValidationReport,
    bundle: dict[str, Any],
    *,
    exempt_kinds: frozenset[str],
    as_errors: bool,
) -> dict[str, Any]:
    """Flag canonical nodes that are not referenced anywhere and have no code-index binding.

    These are ontology orphans — either premature additions that should be
    removed, or genuine concepts that are missing their feature mapping or
    code binding. Either way, a human resolves them at release readiness.

    Default severity is `warn`. Lifecycle gates that want a hard fail set
    `as_errors=True` (CLI flag `--orphans-as-errors`).
    """
    canonical_nodes = bundle["canonical_nodes"]
    bindings = bundle["bindings"]
    referenced = collect_referenced_node_ids(bundle)

    orphans: list[dict[str, Any]] = []
    for node_id, node in canonical_nodes.items():
        kind = node.get("_kind")
        if kind in exempt_kinds:
            continue
        if node_id in referenced:
            continue
        if node_id in bindings:
            continue
        orphans.append({"id": node_id, "kind": kind, "label": node.get("label") or node_id})

    orphans.sort(key=lambda item: (item["kind"] or "", item["id"]))
    emit = report.error if as_errors else report.warn
    for orphan in orphans:
        emit(
            f"Ontology orphan: {orphan['id']} ({orphan['kind']}) has no incoming refs "
            f"and no code-index binding — remove if premature, or add a feature mapping / code binding."
        )

    by_kind: dict[str, int] = {}
    for orphan in orphans:
        kind = orphan["kind"] or "unknown"
        by_kind[kind] = by_kind.get(kind, 0) + 1

    return {
        "orphan_count": len(orphans),
        "by_kind": by_kind,
        "orphans": orphans,
        "exempt_kinds": sorted(exempt_kinds),
    }


def _matches_any_glob(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def validate_coverage_gaps(
    report: ValidationReport,
    *,
    excludes: tuple[str, ...],
    as_errors: bool,
) -> dict[str, Any]:
    """Report invocations whose source file is outside code-index.yaml
    bindings but targets a bound symbol — read from unbound-but-referenced.yaml.

    Degrades gracefully when the sidecar is absent (warn once, return empty
    summary). Severity defaults to `warn`; `as_errors=True` (CLI flag
    `--coverage-gaps-as-errors`) promotes findings to errors.
    """
    if not UNBOUND_REFERENCED_PATH.exists():
        report.warn(
            f"{UNBOUND_REFERENCED_PATH.relative_to(REPO_ROOT)} not found — "
            "run scripts/kg/symbols.py to regenerate before relying on this gate."
        )
        return {
            "kept": 0,
            "excluded": 0,
            "missing_sidecar": True,
            "exclusions": list(excludes),
        }

    data = yaml.safe_load(UNBOUND_REFERENCED_PATH.read_text(encoding="utf-8")) or {}
    invocations: list[dict[str, Any]] = data.get("invocations") or []

    kept: list[dict[str, Any]] = []
    excluded_count = 0
    for inv in invocations:
        src = inv.get("source_file") or ""
        if _matches_any_glob(src, excludes):
            excluded_count += 1
            continue
        kept.append(inv)

    emit = report.error if as_errors else report.warn
    for inv in kept:
        target = inv.get("target_symbol") or (
            f"{inv.get('target_container') or '?'}.{inv.get('target_name') or '?'} (unresolved)"
        )
        emit(
            f"Coverage gap: {inv.get('source_file')}:{inv.get('source_line')} "
            f"-> {target} [{inv.get('target_node')}] — source file is not bound "
            "in code-index.yaml. Add a binding, or list the path in the product "
            "coverage-gap exemption."
        )

    return {
        "kept": len(kept),
        "excluded": excluded_count,
        "missing_sidecar": False,
        "exclusions": list(excludes),
    }


def validate_untested(
    report: ValidationReport,
    bundle: dict[str, Any],
    *,
    exempt_node_ids: frozenset[str],
    as_errors: bool,
) -> dict[str, Any]:
    """Report bound methods/functions with no caller in a classified-as-tests file.

    A symbol is "tested" when at least one entry in its `callers` array points
    at another symbol with `is_test: true`. Test classification is propagated
    from code-index.yaml buckets ending in `.tests` (see symbols.py). Returns
    a summary dict; severity defaults to `warn`.
    """
    symbols_by_id = bundle["symbols_by_id"]
    untested: list[dict[str, Any]] = []

    for sym in symbols_by_id.values():
        if sym.get("is_test"):
            continue
        if sym.get("kind") not in UNTESTED_TARGET_KINDS:
            continue
        if sym.get("visibility") not in (None, "public", "internal", "export"):
            # private/protected: tested transitively through public surface.
            continue
        node_id = sym.get("node")
        if node_id in exempt_node_ids:
            continue
        has_test_caller = False
        for caller_id in sym.get("callers") or []:
            caller = symbols_by_id.get(caller_id)
            if caller and caller.get("is_test"):
                has_test_caller = True
                break
        if not has_test_caller:
            untested.append(
                {
                    "id": sym["id"],
                    "node": node_id,
                    "name": sym.get("name"),
                    "file": sym.get("file"),
                    "line": sym.get("line"),
                }
            )

    untested.sort(key=lambda s: (s["node"] or "", s["id"]))
    emit = report.error if as_errors else report.warn
    for u in untested:
        emit(
            f"Untested surface: {u['id']} at {u['file']}:{u['line']} "
            f"[{u['node']}] has no caller in a *.tests bucket. Add a test, "
            "or list the canonical node in the product untested exemption."
        )

    return {
        "untested_count": len(untested),
        "untested": untested,
        "exempt_nodes": sorted(exempt_node_ids),
    }


def regenerate_symbols() -> int:
    """Delegate to scripts/kg/symbols.py to regenerate symbol-index.yaml."""
    symbols_script = Path(__file__).resolve().parent / "symbols.py"
    if not symbols_script.exists():
        print(f"symbols.py not found at {symbols_script}", file=sys.stderr)
        return 1
    print(f"[validate] regenerating symbol-index via {symbols_script}")
    result = subprocess.run(
        [sys.executable, str(symbols_script)],
        cwd=str(REPO_ROOT),
    )
    return result.returncode


def regenerate_decisions() -> int:
    """Delegate to scripts/kg/decisions.py to regenerate decisions-index.yaml."""
    decisions_script = Path(__file__).resolve().parent / "decisions.py"
    if not decisions_script.exists():
        print(f"decisions.py not found at {decisions_script}", file=sys.stderr)
        return 1
    print(f"[validate] regenerating decisions-index via {decisions_script}")
    result = subprocess.run(
        [sys.executable, str(decisions_script)],
        cwd=str(REPO_ROOT),
    )
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate knowledge-graph integrity.")
    parser.add_argument(
        "--write-coverage-report",
        action="store_true",
        help="Write planning-mds/knowledge-graph/coverage-report.yaml using current KG state.",
    )
    parser.add_argument(
        "--check-drift",
        action="store_true",
        help="Run drift checks: Casbin policy cross-check, and external memory staleness (if --memory-dir given).",
    )
    parser.add_argument(
        "--memory-dir",
        type=Path,
        default=None,
        help="Path to an external agent memory directory to scan for stale repo-path references. Agent-agnostic — works with any tool that stores .md memory files.",
    )
    parser.add_argument(
        "--check-symbols",
        action="store_true",
        help="Validate symbol-index.yaml: each entry must resolve to a canonical node and a real file.",
    )
    parser.add_argument(
        "--regenerate-symbols",
        action="store_true",
        help="Regenerate symbol-index.yaml by running scripts/kg/symbols.py before validating.",
    )
    parser.add_argument(
        "--check-decisions",
        action="store_true",
        help="Validate decisions-index.yaml: inline markers must resolve to real files, nodes, symbols, and ADRs.",
    )
    parser.add_argument(
        "--regenerate-decisions",
        action="store_true",
        help="Regenerate decisions-index.yaml by running scripts/kg/decisions.py before validating.",
    )
    parser.add_argument(
        "--check-orphans",
        action="store_true",
        help="Warn on canonical nodes with no incoming refs and no code-index binding.",
    )
    parser.add_argument(
        "--orphans-as-errors",
        action="store_true",
        help="Promote orphan findings to errors (fails the run). Implies --check-orphans.",
    )
    parser.add_argument(
        "--orphan-exempt-kind",
        action="append",
        default=[],
        metavar="KIND",
        help=(
            "Additional canonical node kind to exempt from the orphan check "
            "(repeatable). Defaults: "
            + ", ".join(sorted(DEFAULT_ORPHAN_EXEMPT_KINDS))
            + "."
        ),
    )
    parser.add_argument(
        "--check-coverage-gaps",
        action="store_true",
        help=(
            "Warn on invocations from files outside code-index.yaml bindings "
            "that target bound symbols (reads unbound-but-referenced.yaml)."
        ),
    )
    parser.add_argument(
        "--coverage-gaps-as-errors",
        action="store_true",
        help=(
            "Promote coverage-gap findings to errors (fails the run). "
            "Implies --check-coverage-gaps."
        ),
    )
    parser.add_argument(
        "--coverage-gap-exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help=(
            "Additional source-file glob to exempt from --check-coverage-gaps "
            "(repeatable). Baked-in defaults already exclude test files, "
            "migrations, scripts/, and tools/."
        ),
    )
    parser.add_argument(
        "--check-reproducible",
        action="store_true",
        help=(
            "Prove committed generated files == compile(source) and enforce the git policy "
            "(F0006-S0008): compile --check + shard validation + archived/ledger/glob rules + "
            ".gitattributes drift. The single CI/integrator reproducibility entry point."
        ),
    )
    parser.add_argument(
        "--check-untested",
        action="store_true",
        help=(
            "Warn on public methods/functions with no caller in a "
            "classified-as-tests file (requires is_test propagation)."
        ),
    )
    parser.add_argument(
        "--untested-as-errors",
        action="store_true",
        help=(
            "Promote untested-surface findings to errors. "
            "Implies --check-untested."
        ),
    )
    parser.add_argument(
        "--untested-exempt-node",
        action="append",
        default=[],
        metavar="NODE_ID",
        help=(
            "Canonical node id to exempt from --check-untested (repeatable). "
            "Use for nodes whose code is intentionally untested (e.g. typed "
            "DTO containers, generated code)."
        ),
    )
    args = parser.parse_args()

    if args.check_reproducible:
        import reproducibility
        return reproducibility.main([])

    if args.regenerate_symbols:
        rc = regenerate_symbols()
        if rc != 0:
            return rc
    if args.regenerate_decisions:
        rc = regenerate_decisions()
        if rc != 0:
            return rc

    bundle = load_bundle()
    report = ValidationReport()
    regex_by_type = type_regex_map()

    ontology = bundle["ontology"]
    canonical = bundle["canonical"]
    mappings = bundle["mappings"]
    code_index = bundle["code_index"]
    all_nodes = bundle["all_nodes"]

    seen_ids: set[str] = set()

    for section, node_type in SECTION_TYPES.items():
        for item in canonical.get(section, []):
            node_id = item["id"]
            if node_id in seen_ids:
                report.error(f"Duplicate ID: {node_id}")
            seen_ids.add(node_id)
            validate_id(report, node_id, node_type, regex_by_type)

            if item.get("path"):
                validate_path_exists(report, item["path"], node_id)
            for source_doc in item.get("source_docs", []):
                validate_path_exists(report, source_doc, f"{node_id}.source_docs")
            for related_id in item.get("related_nodes", []):
                if related_id not in all_nodes:
                    report.error(f"Unknown related node in {node_id}.related_nodes: {related_id}")
            for role_id in item.get("allowed_roles", []):
                if role_id not in all_nodes:
                    report.error(f"Unknown role reference in {node_id}.allowed_roles: {role_id}")
            for rationale_entry in item.get("rationale", []):
                validate_rationale_entry(report, rationale_entry, node_id, all_nodes)

            if section == "workflows":
                workflow_id = item["id"]
                state_ids = {state["id"] for state in item.get("states", [])}
                for state in item.get("states", []):
                    state_id = state["id"]
                    if state_id in seen_ids:
                        report.error(f"Duplicate ID: {state_id}")
                    seen_ids.add(state_id)
                    validate_id(report, state_id, "workflow_state", regex_by_type)
                    for target_id in state.get("transitions_to", []):
                        if target_id not in state_ids:
                            report.error(
                                f"Workflow state transition leaves workflow in {workflow_id}: "
                                f"{state_id} -> {target_id}"
                            )

    for section_name in ("features", "stories"):
        node_type = "feature" if section_name == "features" else "story"
        for item in mappings.get(section_name, []):
            node_id = item["id"]
            if node_id in seen_ids:
                report.error(f"Duplicate ID: {node_id}")
            seen_ids.add(node_id)
            validate_id(report, node_id, node_type, regex_by_type)
            validate_path_exists(report, item["path"], node_id)
            validate_references(report, item, all_nodes)

    mapped_feature_paths = {
        normalize_repo_path(item["path"])
        for item in mappings.get("features", [])
    }
    excluded_paths = excluded_feature_paths(mappings)
    feature_dirs = set(iter_feature_dirs())
    uncovered = sorted(feature_dirs - mapped_feature_paths - excluded_paths)
    for path in uncovered:
        report.error(f"Feature directory is neither mapped nor excluded: {path}")

    excluded_ids: set[str] = set()
    for item in mappings.get("coverage", {}).get("excluded_features", []):
        feature_id = item.get("id")
        path = item.get("path")
        reason = item.get("reason")
        if not feature_id or not path or not reason:
            report.error("Each coverage.excluded_features entry requires id, path, and reason")
            continue
        if feature_id in excluded_ids:
            report.error(f"Duplicate excluded feature entry: {feature_id}")
        excluded_ids.add(feature_id)
        validate_id(report, feature_id, "feature", regex_by_type)
        validate_path_exists(report, path, f"coverage.excluded_features:{feature_id}")

    binding_ids: set[str] = set()
    for binding in code_index.get("node_bindings", []):
        node_id = binding.get("id")
        if not node_id:
            report.error("code-index node binding is missing id")
            continue
        if node_id in binding_ids:
            report.error(f"Duplicate code-index binding: {node_id}")
        binding_ids.add(node_id)
        if node_id not in all_nodes:
            report.error(f"code-index binding references unknown node: {node_id}")

        declared_paths = bundle["bindings"].get(node_id, {}).get("declared_paths", [])
        if not declared_paths:
            report.error(f"code-index binding has no paths: {node_id}")
            continue
        for entry in declared_paths:
            matches = expand_declared_pattern(entry["pattern"])
            if not matches:
                report.error(
                    f"code-index pattern does not resolve for {node_id} ({entry['bucket']}): "
                    f"{entry['pattern']}"
                )

    edge_usage = {
        "transitions_to": 0,
        "validated_by": 0,
        "supersedes": 0,
    }
    for workflow in canonical.get("workflows", []):
        for state in workflow.get("states", []):
            edge_usage["transitions_to"] += len(state.get("transitions_to", []))
    for section_name in ("features", "stories"):
        for item in mappings.get(section_name, []):
            edge_usage["validated_by"] += len(item.get("validated_by", []))
            edge_usage["supersedes"] += len(item.get("supersedes", []))

    for edge in ontology.get("edge_types", []):
        edge_id = edge["id"]
        if edge_id in edge_usage and edge_usage[edge_id] == 0:
            report.warn(f"Declared edge type is unused: {edge_id}")

    if args.check_drift:
        validate_casbin_drift(report, bundle)
        if args.memory_dir:
            validate_external_memory_drift(report, args.memory_dir)

    symbol_summary = validate_symbol_index(report, bundle, required=args.check_symbols)
    decisions_summary = validate_decision_index(
        report, bundle, required=args.check_decisions
    )

    orphan_summary: dict[str, Any] | None = None
    if args.check_orphans or args.orphans_as_errors:
        exempt_kinds = DEFAULT_ORPHAN_EXEMPT_KINDS | frozenset(args.orphan_exempt_kind)
        orphan_summary = validate_orphans(
            report,
            bundle,
            exempt_kinds=exempt_kinds,
            as_errors=args.orphans_as_errors,
        )

    coverage_gap_summary: dict[str, Any] | None = None
    if args.check_coverage_gaps or args.coverage_gaps_as_errors:
        excludes = DEFAULT_COVERAGE_GAP_EXCLUDES + tuple(args.coverage_gap_exclude)
        coverage_gap_summary = validate_coverage_gaps(
            report,
            excludes=excludes,
            as_errors=args.coverage_gaps_as_errors,
        )

    untested_summary: dict[str, Any] | None = None
    if args.check_untested or args.untested_as_errors:
        untested_summary = validate_untested(
            report,
            bundle,
            exempt_node_ids=frozenset(args.untested_exempt_node),
            as_errors=args.untested_as_errors,
        )

    hotspot_signals: dict[str, dict[str, Any]] | None = None
    if args.write_coverage_report:
        try:
            hotspot_signals = compute_hotspots(bundle)
        except SystemExit as exc:
            # Git unavailable, shallow clone, or empty history. Fall through
            # without Phase 3 fields rather than blocking coverage-report write.
            print(f"[validate] hotspots skipped: {exc}", file=sys.stderr)
            hotspot_signals = None

    coverage_report = build_coverage_report(
        bundle,
        mapped_feature_paths,
        excluded_paths,
        uncovered,
        symbol_summary,
        decisions_summary,
        hotspot_signals,
    )
    if args.write_coverage_report:
        write_coverage_report(coverage_report)
    else:
        explicit_check_requested = any(
            [
                args.check_drift,
                args.check_symbols,
                args.regenerate_symbols,
                args.check_decisions,
                args.regenerate_decisions,
                args.check_orphans,
                args.orphans_as_errors,
                args.check_coverage_gaps,
                args.coverage_gaps_as_errors,
                args.check_untested,
                args.untested_as_errors,
            ]
        )
        if explicit_check_requested:
            pass
        elif not COVERAGE_REPORT_PATH.exists():
            report.error(
                "Missing coverage report: planning-mds/knowledge-graph/coverage-report.yaml "
                "(run python3 scripts/kg/validate.py --write-coverage-report)"
            )
        else:
            existing = yaml.safe_load(COVERAGE_REPORT_PATH.read_text(encoding="utf-8")) or {}

            def _extract_hashes(rpt: dict[str, Any]) -> dict[str, str | None]:
                """Extract only source_hash values for staleness comparison.

                last_modified uses st_mtime which differs between local and CI
                (git checkout sets all timestamps to checkout time), so we only
                compare content hashes which are deterministic."""
                hashes: dict[str, str | None] = {}
                for section in ("canonical", "mappings", "code_bindings"):
                    for key, entry in rpt.get("freshness", {}).get(section, {}).items():
                        hashes[f"{section}/{key}"] = entry.get("source_hash")
                return hashes

            if _extract_hashes(existing) != _extract_hashes(coverage_report):
                report.error(
                    "coverage-report.yaml is stale "
                    "(run python3 scripts/kg/validate.py --write-coverage-report)"
                )

    print("Knowledge graph validation")
    print("-" * 60)
    print(f"Features mapped:   {len(mappings.get('features', []))}")
    print(f"Stories mapped:    {len(mappings.get('stories', []))}")
    print(
        "Feature coverage:  "
        f"{len(mapped_feature_paths)} mapped, {len(excluded_paths)} excluded, {len(uncovered)} uncovered"
    )
    print(f"Code bindings:     {len(code_index.get('node_bindings', []))}")
    if symbol_summary["exists"]:
        by_lang = symbol_summary["by_language"]
        lang_summary = ", ".join(f"{lang}: {n}" for lang, n in sorted(by_lang.items()))
        print(
            f"Symbol index:      {symbol_summary['symbol_count']} symbols, "
            f"{symbol_summary['bound_symbol_count']} on bound nodes "
            f"({lang_summary})"
        )
    if decisions_summary["exists"]:
        by_kind = decisions_summary["by_kind"]
        kind_summary = ", ".join(f"{kind}: {n}" for kind, n in sorted(by_kind.items()))
        print(
            f"Decision markers: {decisions_summary['decision_count']} markers, "
            f"{decisions_summary['why_count']} WHY"
            + (f" ({kind_summary})" if kind_summary else "")
        )
    if orphan_summary is not None:
        by_kind = orphan_summary["by_kind"]
        kind_summary = ", ".join(f"{kind}: {n}" for kind, n in sorted(by_kind.items()))
        print(
            f"Orphan nodes:      {orphan_summary['orphan_count']}"
            + (f" ({kind_summary})" if kind_summary else "")
        )

    if report.warnings:
        print("\nWarnings:")
        for warning in report.warnings:
            print(f"- {warning}")

    if report.errors:
        print("\nErrors:")
        for error in report.errors:
            print(f"- {error}")
        return 1

    print("\n[PASS] knowledge-graph integrity checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

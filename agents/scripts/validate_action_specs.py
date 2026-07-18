#!/usr/bin/env python3
"""Validate versioned action policy and resolve manifest contract versions (F0007-S0001).

Two responsibilities, both audit-grade and deterministic:

1. Validate the active contract, active action specs, and immutable history
   bundles under ``agents/actions/spec/``. Structural checks use JSON Schema
   (Draft 2020-12); semantic invariants that JSON Schema cannot express are
   enforced in Python: monotonic/immutable versions, filename==version,
   the active==newest-history tie, placeholder allowlisting, path containment,
   typed-argv/no-shell execution, unique gate/operation/checkpoint IDs,
   declared mutation classes, and checkpoint pre/postconditions.

2. Resolve which policy version interprets a run's evidence, from either an
   explicit ``contract_version`` or a legacy manifest's effective date, with
   named failure rules suitable for audit evidence.

No code execution: YAML is loaded with ``safe_load`` and schema processing is
data-only. Output is deterministic for identical inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover - environment guard
    sys.stderr.write(
        "validate_action_specs.py requires 'jsonschema' "
        "(pip install -r agents/scripts/requirements.txt)\n"
    )
    raise SystemExit(2) from exc

import yaml


FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_DIR = FRAMEWORK_ROOT / "agents" / "actions" / "spec"

VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(-r\d+)?$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")

# Placeholders any action spec may reference without declaring them. A spec also
# implicitly knows its own declared input names, run_id var, and auto_resolved
# keys (see _known_placeholders).
BASE_PLACEHOLDERS = frozenset({
    "PRODUCT_ROOT", "FEATURE_ID", "FEATURE_SLUG", "FEATURE_PATH",
    "FEATURE_INDEX_ROOT", "RUN_ID", "RUN_FOLDER", "RUN_ID_PRIOR",
    "start_tier", "stage",
})

# A path token in an argv must resolve under one of these roots. Run-relative
# artifact names (expected_artifacts, produces, write.artifact) are checked only
# for traversal/absolute escapes, not for a root prefix.
ALLOWED_PATH_ROOTS = ("agents/", "{PRODUCT_ROOT}", "{FEATURE_PATH}",
                      "{RUN_FOLDER}", "{FEATURE_INDEX_ROOT}")

# Mutation classes an operation may declare in ``mutates``.
ALLOWED_MUTATION_CLASSES = frozenset({
    "evidence-manifest", "latest-run.json", "gate-state", "commands.log",
    "lifecycle-gates.log", "run-folder", "trackers", "kg-source",
    "kg-projection", "prior-manifest", "archived-feature-folder",
})


# --------------------------------------------------------------------------- #
# Result accumulation
# --------------------------------------------------------------------------- #
@dataclass
class Finding:
    rule: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "path": self.path, "message": self.message}

    def sort_key(self) -> tuple[str, str, str]:
        return (self.rule, self.path, self.message)


@dataclass
class Result:
    findings: list[Finding] = field(default_factory=list)

    def add(self, rule: str, path: str, message: str) -> None:
        self.findings.append(Finding(rule, path, message))

    @property
    def ok(self) -> bool:
        return not self.findings

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings, key=Finding.sort_key)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
@dataclass
class Bundle:
    version: str
    effective_from: date
    revision: int
    data: dict[str, Any]
    source: str


@dataclass
class Policy:
    spec_dir: Path
    contract: dict[str, Any] | None
    actions: dict[str, dict[str, Any]]  # action name -> spec
    bundles: list[Bundle]

    def version_set(self) -> set[str]:
        return {b.version for b in self.bundles}

    def newest(self) -> Bundle | None:
        if not self.bundles:
            return None
        return max(self.bundles, key=_bundle_sort_key)


def _bundle_sort_key(b: Bundle) -> tuple[date, int]:
    return (b.effective_from, b.revision)


def _parse_version_key(version: str) -> tuple[date, int]:
    """Split a date-form version into (date, revision). Revision is 0 when the
    optional -rNN suffix is absent."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:-r(\d+))?$", version)
    if not m:
        raise ValueError(f"unparseable version: {version!r}")
    y, mo, d, rev = m.groups()
    return date(int(y), int(mo), int(d)), int(rev) if rev else 0


def _normalize_scalars(value: Any) -> Any:
    """Coerce YAML-native date/datetime scalars to ISO strings.

    YAML implicitly types ``2026-07-11`` as a ``datetime.date``; the policy
    schema wants string versions/dates (and version may carry a ``-rNN`` suffix
    that is a string anyway). Normalizing here keeps unquoted date-form values in
    the source files working while the schema pattern still enforces ``YYYY-MM-DD``.
    """
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _normalize_scalars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_scalars(v) for v in value]
    return value


def _load_yaml(path: Path, result: Result) -> dict[str, Any] | None:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        result.add("yaml_parse_error", str(path), f"YAML parse error: {exc}")
        return None
    if not isinstance(loaded, dict):
        result.add("yaml_parse_error", str(path), "top-level YAML value is not a mapping")
        return None
    return _normalize_scalars(loaded)


def load_policy(spec_dir: Path, result: Result) -> Policy:
    contract = None
    contract_path = spec_dir / "_contract.yaml"
    if contract_path.is_file():
        contract = _load_yaml(contract_path, result)
    else:
        result.add("contract_missing", str(contract_path), "_contract.yaml not found")

    actions: dict[str, dict[str, Any]] = {}
    for path in sorted(spec_dir.glob("*.yaml")):
        if path.name == "_contract.yaml":
            continue
        data = _load_yaml(path, result)
        if data is None:
            continue
        name = data.get("action", path.stem)
        actions[str(name)] = data

    bundles: list[Bundle] = []
    history_dir = spec_dir / (contract.get("history_dir", "history") if contract else "history")
    for path in sorted(history_dir.glob("*.yaml")) if history_dir.is_dir() else []:
        data = _load_yaml(path, result)
        if data is None:
            continue
        version = str(data.get("version", path.stem))
        eff_raw = str(data.get("effective_from", ""))
        try:
            eff = _parse_iso(eff_raw)
            _, rev = _parse_version_key(version)
        except ValueError:
            # Structural schema validation reports the precise defect; skip here.
            eff, rev = date.min, 0
        bundles.append(Bundle(version, eff, rev, data, path.name))

    return Policy(spec_dir, contract, actions, bundles)


def _parse_iso(raw: str) -> date:
    if not ISO_DATE_RE.match(raw):
        raise ValueError(f"not an ISO date: {raw!r}")
    y, m, d = raw.split("-")
    return date(int(y), int(m), int(d))


# --------------------------------------------------------------------------- #
# Structural (JSON Schema) validation
# --------------------------------------------------------------------------- #
def _load_schema(spec_dir: Path, name: str) -> dict[str, Any]:
    return json.loads((spec_dir / "schema" / name).read_text(encoding="utf-8"))


def _schema_check(validator: Draft202012Validator, instance: Any, source: str,
                  rule: str, result: Result) -> bool:
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    for err in errors:
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        result.add(rule, f"{source}#{loc}", err.message)
    return not errors


# --------------------------------------------------------------------------- #
# Semantic validation
# --------------------------------------------------------------------------- #
def _known_placeholders(spec: dict[str, Any]) -> set[str]:
    known = set(BASE_PLACEHOLDERS)
    run_id = spec.get("run_id", {})
    if isinstance(run_id, dict) and run_id.get("var"):
        known.add(str(run_id["var"]))
    inputs = spec.get("inputs", {})
    if isinstance(inputs, dict):
        for group in ("required", "optional"):
            for item in inputs.get(group, []) or []:
                if isinstance(item, dict) and item.get("name"):
                    known.add(str(item["name"]))
    auto = spec.get("auto_resolved", {})
    if isinstance(auto, dict):
        known.update(str(k) for k in auto)
    return known


def _scan_placeholders(value: str, known: set[str], src: str, result: Result) -> None:
    for name in PLACEHOLDER_RE.findall(value):
        if name not in known:
            result.add("unknown_placeholder", src,
                       f"unknown placeholder {{{name}}} (allowed: {sorted(known)})")


def _has_traversal(token: str) -> bool:
    return token.startswith("/") or ".." in token.split("/")


def _check_argv_path(token: str, src: str, result: Result) -> None:
    if _has_traversal(token):
        result.add("path_escapes_root", src,
                   f"path token {token!r} escapes root (absolute or contains '..')")
        return
    if "/" in token and not token.startswith(ALLOWED_PATH_ROOTS):
        result.add("path_escapes_root", src,
                   f"path token {token!r} is not under an allowed root {ALLOWED_PATH_ROOTS}")


def _check_relpath(token: str, src: str, result: Result) -> None:
    if _has_traversal(token):
        result.add("path_escapes_root", src,
                   f"artifact path {token!r} escapes run root (absolute or contains '..')")


def _validate_action_semantics(name: str, spec: dict[str, Any], active_version: str | None,
                               result: Result) -> None:
    src = f"{name}.yaml"
    known = _known_placeholders(spec)

    contract = spec.get("contract", {})
    version = contract.get("version") if isinstance(contract, dict) else None
    if active_version is not None and version is not None and version != active_version:
        result.add("action_contract_version_mismatch", src,
                   f"contract.version {version!r} != active_version {active_version!r}")

    gate_ids: list[str] = []
    op_ids: list[str] = []
    for gi, gate in enumerate(spec.get("gates", []) or []):
        if not isinstance(gate, dict):
            continue
        gate_ids.append(str(gate.get("id")))
        gsrc = f"{src}#gates/{gi}({gate.get('id')})"
        for oi, op in enumerate(gate.get("operations", []) or []):
            osrc = f"{gsrc}/operations/{oi}"
            if not isinstance(op, dict) or len(op) != 1:
                result.add("shell_form_command", osrc,
                           "operation must be exactly one typed op (run|checkpoint|write); "
                           "string-form commands are forbidden")
                continue
            kind, body = next(iter(op.items()))
            if kind == "run" and isinstance(body, dict):
                if body.get("id"):
                    op_ids.append(str(body["id"]))
                for ai, tok in enumerate(body.get("argv", []) or []):
                    tsrc = f"{osrc}/run/argv/{ai}"
                    _scan_placeholders(str(tok), known, tsrc, result)
                    _check_argv_path(str(tok), tsrc, result)
                for art in body.get("expected_artifacts", []) or []:
                    _scan_placeholders(str(art), known, f"{osrc}/run/expected_artifacts", result)
                    _check_relpath(str(art), f"{osrc}/run/expected_artifacts", result)
                for cls in body.get("mutates", []) or []:
                    if cls not in ALLOWED_MUTATION_CLASSES:
                        result.add("undeclared_mutation_class", f"{osrc}/run/mutates",
                                   f"mutation class {cls!r} not in allowlist "
                                   f"{sorted(ALLOWED_MUTATION_CLASSES)}")
            elif kind == "checkpoint" and isinstance(body, dict):
                if body.get("id"):
                    op_ids.append(str(body["id"]))
                if not body.get("requires"):
                    result.add("checkpoint_missing_condition", f"{osrc}/checkpoint",
                               "checkpoint has no preconditions (requires)")
                if not body.get("produces"):
                    result.add("checkpoint_missing_condition", f"{osrc}/checkpoint",
                               "checkpoint has no postconditions (produces)")
                for tok in list(body.get("requires", []) or []) + list(body.get("produces", []) or []):
                    _scan_placeholders(str(tok), known, f"{osrc}/checkpoint", result)
                    _check_relpath(str(tok), f"{osrc}/checkpoint", result)
            elif kind == "write" and isinstance(body, dict):
                _scan_placeholders(str(body.get("artifact", "")), known, f"{osrc}/write", result)
                _check_relpath(str(body.get("artifact", "")), f"{osrc}/write", result)
                for cls in body.get("mutates", []) or []:
                    if cls not in ALLOWED_MUTATION_CLASSES:
                        result.add("undeclared_mutation_class", f"{osrc}/write/mutates",
                                   f"mutation class {cls!r} not in allowlist "
                                   f"{sorted(ALLOWED_MUTATION_CLASSES)}")

    _reject_duplicates(gate_ids, "duplicate_gate_id", src, result)
    _reject_duplicates(op_ids, "duplicate_operation_id", src, result)

    for ci, item in enumerate(spec.get("context_load", []) or []):
        _scan_placeholders(str(item), known, f"{src}#context_load/{ci}", result)
    auto = spec.get("auto_resolved", {})
    if isinstance(auto, dict):
        for key, val in auto.items():
            _scan_placeholders(str(val), known, f"{src}#auto_resolved/{key}", result)


def _reject_duplicates(ids: list[str], rule: str, src: str, result: Result) -> None:
    seen: set[str] = set()
    for i in ids:
        if i in seen:
            result.add(rule, src, f"duplicate id {i!r}")
        seen.add(i)


def _validate_bundles(policy: Policy, result: Result) -> None:
    seen_versions: set[str] = set()
    for b in policy.bundles:
        src = f"history/{b.source}"
        stem = b.source[:-len(".yaml")] if b.source.endswith(".yaml") else b.source
        if b.version != stem:
            result.add("bundle_filename_mismatch", src,
                       f"version {b.version!r} != filename {stem!r}")
        eff = str(b.data.get("effective_from", ""))
        ced = str(b.data.get("shared", {}).get("contract_effective_date", "")) \
            if isinstance(b.data.get("shared"), dict) else ""
        if eff != b.version:
            result.add("bundle_effective_from_mismatch", src,
                       f"effective_from {eff!r} != version {b.version!r}")
        if ced and ced != b.version:
            result.add("bundle_effective_from_mismatch", src,
                       f"shared.contract_effective_date {ced!r} != version {b.version!r}")
        if b.version in seen_versions:
            result.add("duplicate_policy_version", src, f"duplicate version {b.version!r}")
        seen_versions.add(b.version)

    ordered = sorted(policy.bundles, key=_bundle_sort_key)
    for prev, cur in zip(ordered, ordered[1:]):
        if _bundle_sort_key(cur) <= _bundle_sort_key(prev):
            result.add("non_monotonic_policy_versions", f"history/{cur.source}",
                       f"version {cur.version!r} is not strictly after {prev.version!r}")


def _validate_active_tie(policy: Policy, result: Result) -> str | None:
    if policy.contract is None:
        return None
    active = policy.contract.get("active_version")
    if active is None:
        return None
    active = str(active)
    versions = policy.version_set()
    if active not in versions:
        result.add("active_version_missing_bundle", "_contract.yaml",
                   f"active_version {active!r} has no history bundle")
        return active
    newest = policy.newest()
    if newest is not None and active != newest.version:
        result.add("active_version_not_newest", "_contract.yaml",
                   f"active_version {active!r} is not the newest bundle {newest.version!r}")
    return active


def validate_policy(spec_dir: Path) -> tuple[Result, Policy]:
    result = Result()
    policy = load_policy(spec_dir, result)

    # Structural (JSON Schema).
    try:
        contract_schema = Draft202012Validator(_load_schema(spec_dir, "contract.schema.json"))
        bundle_schema = Draft202012Validator(_load_schema(spec_dir, "policy-bundle.schema.json"))
        action_schema = Draft202012Validator(_load_schema(spec_dir, "action-spec.schema.json"))
    except (OSError, json.JSONDecodeError) as exc:
        result.add("schema_load_error", str(spec_dir / "schema"), str(exc))
        return result, policy

    if policy.contract is not None:
        _schema_check(contract_schema, policy.contract, "_contract.yaml",
                      "contract_schema", result)
    for b in policy.bundles:
        _schema_check(bundle_schema, b.data, f"history/{b.source}",
                      "policy_bundle_schema", result)
    for name, spec in policy.actions.items():
        _schema_check(action_schema, spec, f"{name}.yaml", "action_spec_schema", result)

    # Semantic invariants.
    _validate_bundles(policy, result)
    active_version = _validate_active_tie(policy, result)
    for name, spec in sorted(policy.actions.items()):
        _validate_action_semantics(name, spec, active_version, result)

    return result, policy


# --------------------------------------------------------------------------- #
# Manifest version resolution
# --------------------------------------------------------------------------- #
def resolve_manifest(policy: Policy, *, version: str | None = None,
                     effective_date: str | None = None) -> dict[str, Any]:
    """Resolve which policy version interprets a manifest.

    Explicit version wins; otherwise a legacy manifest maps to the newest bundle
    whose effective_from is not later than its date. Returns an audit record.
    """
    versions = policy.version_set()
    if version is not None:
        if version in versions:
            return {"ok": True, "selected_version": version,
                    "selection_source": "explicit", "diagnostics": []}
        return {"ok": False, "selected_version": None, "selection_source": "explicit",
                "rule": "manifest_unknown_version",
                "diagnostics": [f"contract_version {version!r} matches no published bundle "
                                f"(known: {sorted(versions)})"]}

    if effective_date is not None:
        try:
            md = _parse_iso(effective_date)
        except ValueError:
            return {"ok": False, "selected_version": None, "selection_source": "legacy-date",
                    "rule": "manifest_bad_effective_date",
                    "diagnostics": [f"effective date {effective_date!r} is not an ISO date"]}
        eligible = [b for b in policy.bundles if b.effective_from <= md]
        if not eligible:
            first = min(policy.bundles, key=_bundle_sort_key).version if policy.bundles else None
            return {"ok": False, "selected_version": None, "selection_source": "legacy-date",
                    "rule": "manifest_date_before_first_policy",
                    "diagnostics": [f"date {effective_date} precedes the first policy {first}"]}
        selected = max(eligible, key=_bundle_sort_key)
        return {"ok": True, "selected_version": selected.version,
                "selection_source": "legacy-date",
                "diagnostics": [f"newest bundle with effective_from <= {effective_date}"]}

    return {"ok": False, "selected_version": None, "selection_source": None,
            "rule": "manifest_no_selector",
            "diagnostics": ["provide --version or --effective-date"]}


# --------------------------------------------------------------------------- #
# Behavioral contract diff (S0002)
# --------------------------------------------------------------------------- #
# The diff compares the *behavioral* meaning of two policy states, not their
# bytes: mappings are key-sorted and order-insensitive lists (artifacts,
# mutates, requirements) are sorted, so a pure YAML reorder yields an empty diff.
# Ordered lists (gates, operations, argv) keep their order because order is
# behavior. Compatibility is derived from the change, never trusted from a label,
# so a breaking change cannot be mislabeled non-breaking; the policy rule
# "every behavioral change to active policy bumps the version" (and history is
# immutable/append-only) is what rejects an under-versioned change.

REQUIREMENT_KEYS = frozenset({
    "security_scans_required", "kg_reconciliation_required",
    "kg_generated_regen_required", "compile_projection_contract",
    "required_security_scan_classes",
})
EMPTY_MODEL: dict[str, Any] = {"active_version": None, "shared": {}, "actions": {}, "history": {}}


def _op_fingerprint(op: Any) -> dict[str, Any]:
    if not isinstance(op, dict) or len(op) != 1:
        return {"kind": "invalid", "raw": repr(op)}
    kind, body = next(iter(op.items()))
    body = body if isinstance(body, dict) else {}
    if kind == "run":
        return {"kind": "run", "argv": list(body.get("argv", []) or []), "cwd": body.get("cwd"),
                "timeout_seconds": body.get("timeout_seconds"),
                "expected_artifacts": sorted(body.get("expected_artifacts", []) or []),
                "mutates": sorted(body.get("mutates", []) or [])}
    if kind == "checkpoint":
        return {"kind": "checkpoint", "id": body.get("id"),
                "requires": sorted(body.get("requires", []) or []),
                "produces": sorted(body.get("produces", []) or [])}
    if kind == "write":
        return {"kind": "write", "artifact": body.get("artifact"), "after": body.get("after"),
                "mutates": sorted(body.get("mutates", []) or [])}
    return {"kind": kind}


def _shared_model(shared: dict[str, Any] | None) -> dict[str, Any]:
    shared = shared or {}
    reqs = dict(shared.get("requirements", {}) or {})
    if isinstance(reqs.get("required_security_scan_classes"), list):
        reqs["required_security_scan_classes"] = sorted(reqs["required_security_scan_classes"])
    return {
        "coverage_min_pct": shared.get("coverage_min_pct"),
        "run_id_format": shared.get("run_id_format"),
        "run_id_forbidden": sorted(shared.get("run_id_forbidden", []) or []),
        "base_run_files": sorted(shared.get("base_run_files", []) or []),
        "commands_log_fields": list((shared.get("commands_log_schema") or {}).get("fields", []) or []),
        "requirements": reqs,
    }


def _action_model(spec: dict[str, Any]) -> dict[str, Any]:
    # Gates are keyed by id so per-gate/artifact/operation changes diff granularly;
    # gate_order is an ordered list so a reorder (which is behavior) still surfaces.
    contract = spec.get("contract", {}) if isinstance(spec.get("contract"), dict) else {}
    gate_order = []
    gates: dict[str, Any] = {}
    for g in spec.get("gates", []) or []:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id"))
        gate_order.append(gid)
        gates[gid] = {
            "role": g.get("role"),
            "artifacts": sorted(g.get("artifacts", []) or []),
            "constraints": sorted(json.dumps(c, sort_keys=True) for c in g.get("constraints", []) or []),
            "operations": [_op_fingerprint(o) for o in g.get("operations", []) or []],
        }
    return {
        "scope": contract.get("scope"),
        "severity_gate": spec.get("severity_gate"),
        "stop_conditions": sorted(spec.get("stop_conditions", []) or []),
        "forbidden": sorted(spec.get("forbidden", []) or []),
        "gate_order": gate_order,
        "gates": gates,
    }


def bundle_model(bundle: Bundle) -> dict[str, Any]:
    data = bundle.data
    shared = data.get("shared", {}) if isinstance(data.get("shared"), dict) else {}
    actions = {}
    for name, matrix in sorted((data.get("actions", {}) or {}).items()):
        if not isinstance(matrix, dict):
            continue
        gates = [{"id": g.get("id"), "role": g.get("role"),
                  "required_artifacts": sorted(g.get("required_artifacts", []) or [])}
                 for g in matrix.get("gates", []) or [] if isinstance(g, dict)]
        actions[name] = {"scope": matrix.get("scope"), "gates": gates}
    return {"version": bundle.version, "effective_from": bundle.effective_from.isoformat(),
            "shared": _shared_model(shared), "actions": actions}


def _hash_model(model: Any) -> str:
    return hashlib.sha256(json.dumps(model, sort_keys=True).encode("utf-8")).hexdigest()


def build_behavioral_model(policy: Policy) -> dict[str, Any]:
    contract = policy.contract or {}
    return {
        "active_version": contract.get("active_version"),
        "shared": _shared_model(contract.get("shared", {})),
        "actions": {name: _action_model(spec) for name, spec in sorted(policy.actions.items())},
        "history": {b.version: _hash_model(bundle_model(b))
                    for b in sorted(policy.bundles, key=_bundle_sort_key)},
    }


def _deep_diff(bval: Any, hval: Any, path: list[str], out: list[dict[str, Any]]) -> None:
    if isinstance(bval, dict) and isinstance(hval, dict):
        for key in sorted(set(bval) | set(hval), key=str):
            if key not in bval:
                out.append({"path": path + [str(key)], "kind": "added", "base": None, "head": hval[key]})
            elif key not in hval:
                out.append({"path": path + [str(key)], "kind": "removed", "base": bval[key], "head": None})
            else:
                _deep_diff(bval[key], hval[key], path + [str(key)], out)
    elif bval != hval:
        out.append({"path": path, "kind": "changed", "base": bval, "head": hval})


def _classify(entry: dict[str, Any]) -> str:
    path, kind = entry["path"], entry["kind"]
    top = path[0] if path else ""
    leaf = path[-1] if path else ""
    if top == "history":
        return {"added": "additive", "removed": "breaking", "changed": "breaking"}[kind]
    if top == "active_version":
        return "informational"
    # active policy (shared / actions)
    if kind == "removed":
        return "breaking"
    requirement_touch = leaf in REQUIREMENT_KEYS or "requirements" in path
    artifact_touch = any(p in {"artifacts", "required_artifacts", "expected_artifacts", "operations"} for p in path)
    threshold_touch = leaf == "coverage_min_pct"
    if kind == "added":
        if requirement_touch or artifact_touch or leaf == "gates" or "gates" in path:
            return "breaking"
        return "additive"
    # changed
    if requirement_touch or artifact_touch or threshold_touch or "gates" in path:
        return "breaking"
    return "breaking"  # any other active-policy change is still compat-impacting


def diff_models(base: dict[str, Any], head: dict[str, Any],
                base_ref: str = "base", head_ref: str = "head") -> dict[str, Any]:
    raw: list[dict[str, Any]] = []
    _deep_diff(base, head, [], raw)

    changes = []
    for entry in raw:
        changes.append({
            "path": "/".join(entry["path"]),
            "kind": entry["kind"],
            "compatibility": _classify(entry),
            "base": entry["base"],
            "head": entry["head"],
        })
    changes.sort(key=lambda c: (c["path"], c["kind"]))

    active_changed = any(c["path"].split("/")[0] in {"shared", "actions"} for c in changes)
    version_bumped = base.get("active_version") != head.get("active_version")
    history_mutated = [c for c in changes
                       if c["path"].startswith("history/") and c["kind"] in {"changed", "removed"}]

    violations = []
    if active_changed and not version_bumped:
        violations.append({
            "rule": "behavioral_change_without_version_bump",
            "detail": "active policy changed but active_version was not bumped; every "
                      "compatibility-impacting change must publish a new policy version",
        })
    for c in history_mutated:
        rule = "historical_bundle_mutated" if c["kind"] == "changed" else "historical_bundle_removed"
        violations.append({"rule": rule, "detail": f"published bundle {c['path']} was {c['kind']}; "
                                                    "history is immutable and append-only"})

    if violations or any(c["compatibility"] == "breaking" for c in changes):
        compat = "breaking"
    elif changes:
        compat = "additive"
    else:
        compat = "identical"

    return {
        "ok": not violations,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "compatibility_class": compat,
        "requires_version_bump": active_changed,
        "version_bumped": version_bumped,
        "added": [c for c in changes if c["kind"] == "added"],
        "removed": [c for c in changes if c["kind"] == "removed"],
        "changed": [c for c in changes if c["kind"] == "changed"],
        "violations": violations,
    }


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def _materialize_spec_at_ref(ref: str, repo: Path,
                             spec_relpath: str = "agents/actions/spec") -> Path | None:
    """Check out the policy files as they existed at ``ref`` into a temp dir.
    Returns None when the spec path did not exist at that ref (e.g. before S0001)."""
    listed = _git(["ls-tree", "-r", "--name-only", ref, "--", spec_relpath], repo)
    if listed.returncode != 0 or not listed.stdout.strip():
        return None
    tmp = Path(tempfile.mkdtemp(prefix="f0007-diff-"))
    for rel in listed.stdout.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        show = _git(["show", f"{ref}:{rel}"], repo)
        if show.returncode != 0:
            continue
        dst = tmp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(show.stdout, encoding="utf-8")
    return tmp / spec_relpath


def _model_at_ref(ref: str, repo: Path) -> dict[str, Any]:
    spec_dir = _materialize_spec_at_ref(ref, repo)
    if spec_dir is None:
        return dict(EMPTY_MODEL)
    try:
        model = build_behavioral_model(load_policy(spec_dir, Result()))
    finally:
        shutil.rmtree(spec_dir.parents[2], ignore_errors=True)
    return model


def contract_diff(base_ref: str, head_ref: str, repo: Path = FRAMEWORK_ROOT) -> dict[str, Any]:
    return diff_models(_model_at_ref(base_ref, repo), _model_at_ref(head_ref, repo),
                       base_ref, head_ref)


def diff_spec_dirs(base_dir: Path, head_dir: Path) -> dict[str, Any]:
    """Diff two on-disk spec directories (used by tests without git plumbing)."""
    base = build_behavioral_model(load_policy(base_dir, Result())) if base_dir else dict(EMPTY_MODEL)
    head = build_behavioral_model(load_policy(head_dir, Result())) if head_dir else dict(EMPTY_MODEL)
    return diff_models(base, head, str(base_dir), str(head_dir))


def render_diff_md(diff: dict[str, Any]) -> str:
    lines = [f"# Behavioral contract diff: `{diff['base_ref']}` -> `{diff['head_ref']}`", ""]
    lines.append(f"- Compatibility: **{diff['compatibility_class']}**")
    lines.append(f"- Requires version bump: **{diff['requires_version_bump']}** "
                 f"(version bumped: {diff['version_bumped']})")
    lines.append(f"- Result: **{'OK' if diff['ok'] else 'REJECTED'}**")
    for label in ("added", "removed", "changed"):
        rows = diff[label]
        if not rows:
            continue
        lines += ["", f"## {label.capitalize()} ({len(rows)})", "", "| path | compatibility |", "|------|---------------|"]
        lines += [f"| `{r['path']}` | {r['compatibility']} |" for r in rows]
    if diff["violations"]:
        lines += ["", "## Violations", ""]
        lines += [f"- **{v['rule']}** — {v['detail']}" for v in diff["violations"]]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def build_report(result: Result, policy: Policy) -> dict[str, Any]:
    newest = policy.newest()
    active = policy.contract.get("active_version") if policy.contract else None
    versions = [
        {"version": b.version, "effective_from": b.effective_from.isoformat(),
         "active": b.version == active}
        for b in sorted(policy.bundles, key=_bundle_sort_key)
    ]
    actions = []
    for name, spec in sorted(policy.actions.items()):
        contract = spec.get("contract", {}) if isinstance(spec.get("contract"), dict) else {}
        gates = [{"id": g.get("id"), "role": g.get("role")}
                 for g in spec.get("gates", []) or [] if isinstance(g, dict)]
        actions.append({"action": name, "scope": contract.get("scope"),
                        "version": contract.get("version"), "gates": gates})
    shared = policy.contract.get("shared", {}) if policy.contract else {}
    return {
        "ok": result.ok,
        "spec_dir": str(policy.spec_dir),
        "active_version": active,
        "versions": versions,
        "actions": actions,
        "shared": {
            "coverage_min_pct": shared.get("coverage_min_pct"),
            "base_run_files": shared.get("base_run_files", []),
            "requirements": shared.get("requirements", {}),
        },
        "audit": {
            "version_decision": "active-policy-validation",
            "selected_version": active,
            "selection_source": "active",
            "newest_history_version": newest.version if newest else None,
        },
        "errors": [f.as_dict() for f in result.sorted_findings()],
    }


def render_text(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"action-policy validation: {'OK' if report['ok'] else 'FAILED'}")
    lines.append(f"spec_dir: {report['spec_dir']}")
    lines.append(f"active_version: {report['active_version']} "
                 f"(newest history: {report['audit']['newest_history_version']})")
    lines.append("")
    lines.append("versions:")
    for v in report["versions"]:
        mark = " *active" if v["active"] else ""
        lines.append(f"  - {v['version']} (effective_from {v['effective_from']}){mark}")
    lines.append("")
    lines.append("actions:")
    for a in report["actions"]:
        gate_ids = ", ".join(f"{g['id']}:{g['role']}" for g in a["gates"])
        lines.append(f"  - {a['action']} [{a['scope']}] v{a['version']}")
        lines.append(f"      gates: {gate_ids}")
    lines.append("")
    shared = report["shared"]
    lines.append("shared:")
    lines.append(f"  coverage_min_pct: {shared['coverage_min_pct']}")
    lines.append(f"  base_run_files: {len(shared['base_run_files'])} files")
    reqs = shared.get("requirements", {})
    lines.append(f"  requirements: {json.dumps(reqs, sort_keys=True)}")
    if report["errors"]:
        lines.append("")
        lines.append(f"errors ({len(report['errors'])}):")
        for e in report["errors"]:
            lines.append(f"  [{e['rule']}] {e['path']}: {e['message']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec-dir", type=Path, default=DEFAULT_SPEC_DIR,
                        help="Policy directory (default: agents/actions/spec).")
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    parser.add_argument("--resolve-manifest", action="store_true",
                        help="Resolve a manifest's policy version instead of validating.")
    parser.add_argument("--version", help="Explicit contract_version to resolve.")
    parser.add_argument("--effective-date", help="Legacy manifest effective date (YYYY-MM-DD).")
    parser.add_argument("--contract-diff", metavar="BASE..HEAD",
                        help="Behavioral policy diff between two git refs (e.g. origin/main..HEAD).")
    parser.add_argument("--format", choices=["json", "md"], default="json",
                        help="Output format for --contract-diff (default: json).")
    args = parser.parse_args(argv)

    if args.contract_diff:
        if ".." not in args.contract_diff:
            sys.stderr.write("--contract-diff expects BASE..HEAD\n")
            return 2
        base_ref, head_ref = args.contract_diff.split("..", 1)
        diff = contract_diff(base_ref or "HEAD", head_ref or "HEAD")
        print(render_diff_md(diff) if args.format == "md"
              else json.dumps(diff, indent=2, sort_keys=True))
        return 0 if diff["ok"] else 1

    if args.resolve_manifest:
        result = Result()
        policy = load_policy(args.spec_dir, result)
        record = resolve_manifest(policy, version=args.version,
                                  effective_date=args.effective_date)
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0 if record["ok"] else 1

    result, policy = validate_policy(args.spec_dir)
    report = build_report(result, policy)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_text(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

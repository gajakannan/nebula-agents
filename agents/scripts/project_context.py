#!/usr/bin/env python3
"""Discover product-owned instructions and checks without a CWD fallback."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from _product_root import ProductRootError, resolve_product_root

SCRIPT_DIR = Path(__file__).resolve().parent
SPEC_DIR = SCRIPT_DIR.parent / "actions" / "spec"
SCHEMA = SCRIPT_DIR / "schemas" / "project.schema.json"
MANIFEST = ".nebula-project.yaml"


class ProjectError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def explicit_root(value: str | None) -> Path:
    try:
        root = resolve_product_root(value)
    except ProductRootError as exc:
        raise ProjectError("product_root_required", str(exc)) from exc
    if not root.is_dir():
        raise ProjectError("product_root_missing", f"Product directory is missing: {root}")
    return root


def contained(root: Path, value: str, *, exists: bool = True) -> Path:
    path = Path(value)
    if ".." in path.parts:
        raise ProjectError("path_escape", f"Parent traversal is not allowed: {value}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise ProjectError("path_escape", f"Path must stay inside the product: {value}")
    if exists and not resolved.exists():
        raise ProjectError("path_missing", f"Required product path is missing: {value}")
    return resolved


def read_document(root: Path, value: str) -> dict[str, str]:
    path = contained(root, value)
    if not path.is_file():
        raise ProjectError("not_a_file", f"Expected a file: {value}")
    raw = path.read_bytes()
    if not raw.strip():
        raise ProjectError("empty_instruction", f"Required document is empty: {value}")
    return {"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "text": raw.decode("utf-8")}


def load_context(root: Path, action: str, spec_dir: Path = SPEC_DIR) -> dict[str, Any]:
    root = root.resolve()
    if not re.fullmatch(r"[a-z][a-z-]*", action) or not (spec_dir / f"{action}.yaml").is_file():
        raise ProjectError("unknown_action", f"Unknown action: {action}")
    path = contained(root, MANIFEST, exists=False)
    if not path.exists():
        return {"product_root": str(root), "action": action, "manifest_hash": None, "instructions": [], "checks": []}
    raw = path.read_bytes()
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ProjectError("invalid_manifest", f"Invalid project YAML: {exc}") from exc
    schema = json.loads(SCHEMA.read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: str(list(e.path)))
    if errors:
        raise ProjectError("invalid_manifest", "; ".join(f"{list(e.path)}: {e.message}" for e in errors))
    known_actions = {p.stem for p in spec_dir.glob("*.yaml") if not p.stem.startswith("_")}
    instructions = []
    blueprint = root / "planning-mds" / "BLUEPRINT.md"
    if blueprint.exists() or action != "init":
        instructions.append(read_document(root, "planning-mds/BLUEPRINT.md"))
    for item in data["instructions"]:
        if set(item.get("actions", [])) - known_actions:
            raise ProjectError("unknown_action", f"Unknown instruction action: {item['path']}")
        document = read_document(root, item["path"])
        if action in item.get("actions", [action]) and document["path"] not in {d["path"] for d in instructions}:
            instructions.append(document)
    seen = set()
    for check in data["checks"]:
        if check["id"] in seen:
            raise ProjectError("duplicate_check", f"Duplicate project check: {check['id']}")
        seen.add(check["id"])
        if check["action"] not in known_actions:
            raise ProjectError("unknown_action", f"Unknown check action: {check['action']}")
        spec = yaml.safe_load((spec_dir / f"{check['action']}.yaml").read_text())
        gates = {g["id"]: g for g in spec["gates"]}
        if check["event"] not in gates.get(check["stage"], {}).get("project_checks", []):
            raise ProjectError("unsupported_extension", f"Unsupported project check point: {check['action']}:{check['stage']}:{check['event']}")
    return {"product_root": str(root), "action": action,
            "manifest_hash": hashlib.sha256(raw).hexdigest(), "instructions": instructions,
            "checks": [c for c in data["checks"] if c["action"] == action]}


def resolve_scope(root: Path, scope: str, target: str) -> dict[str, Any]:
    """Resolve feature identity from the registry, never an arbitrary supplied path."""
    registry_path = contained(root, "planning-mds/features/REGISTRY.md")
    entries: dict[str, Path] = {}
    active: set[str] = set()
    for line in registry_path.read_text().splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if cells and re.fullmatch(r"F\d{4}", cells[0]):
            folders = [c for c in cells[1:] if re.fullmatch(r"(?:archive/)?F\d{4}-[a-z0-9-]+/?", c)]
            if len(folders) != 1 or cells[0] in entries:
                raise ProjectError("invalid_registry", f"Ambiguous registry entry: {cells[0]}")
            entries[cells[0]] = contained(root, "planning-mds/features/" + folders[0], exists=False)
            if "Active" in cells:
                active.add(cells[0])
    if scope == "project":
        if target != "project":
            raise ProjectError("invalid_scope", "Project scope requires --target project.")
        ids = sorted(k for k, p in entries.items()
                     if "archive" not in p.relative_to(root).parts and (k in active or (p / "PRD.md").exists()))
    else:
        ids = [x.strip() for x in target.split(",")]
        if scope not in {"feature", "feature-set"} or (scope == "feature" and len(ids) != 1):
            raise ProjectError("invalid_scope", f"Invalid scope/target: {scope}/{target}")
        if not ids or len(ids) != len(set(ids)) or any(not re.fullmatch(r"F\d{4}", x) for x in ids):
            raise ProjectError("invalid_scope", "Targets must be distinct feature IDs.")
    for feature in ids:
        if feature not in entries or not entries[feature].is_dir():
            raise ProjectError("unknown_feature", f"No registered feature folder for {feature}")
    return {"plan_scope": scope, "target": target, "features": [{"id": k, "path": str(entries[k])} for k in ids]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-root")
    parser.add_argument("--action", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        context = load_context(explicit_root(args.product_root), args.action)
    except (ProjectError, OSError, ValueError, yaml.YAMLError) as exc:
        print(json.dumps({"ok": False, "code": getattr(exc, "code", "context_error"), "error": str(exc)}))
        return 2
    if args.json:
        print(json.dumps(context, indent=2))
    else:
        print(f"Product instructions for {context['product_root']} ({args.action})")
        if context["manifest_hash"] is None:
            print("No project manifest; follow the existing action context procedure.")
        for document in context["instructions"]:
            print(f"\n--- {document['path']} (sha256:{document['sha256']}) ---\n{document['text']}")
        print("\nRequired project checks: " + ", ".join(c["id"] for c in context["checks"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

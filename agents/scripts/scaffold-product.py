#!/usr/bin/env python3
"""Idempotent product scaffolding — the mechanical portion of init.md (F0007-S0003).

Creates the planning-mds directory tree and copies each framework template to its
{PRODUCT_ROOT} destination IFF the destination is missing. Product-owned files are
never overwritten. Writes only inside {PRODUCT_ROOT} (asserted, not trusted). On
any failure, files this run created are rolled back so no partial scaffold remains.
The user-interview / blueprint-tailoring portion of init.md stays judgment work.

    python3 agents/scripts/scaffold-product.py --product-root PATH [--check] [--json]

--check reports missing required destinations without mutating anything.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
FRAMEWORK_ROOT = SCRIPT_DIR.parents[1]
TEMPLATES_DIR = FRAMEWORK_ROOT / "agents" / "templates"
DEFAULT_MAP = SCRIPT_DIR / "scaffold-map.yaml"

sys.path.insert(0, str(SCRIPT_DIR))
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402


def load_map(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _contained(product_root: Path, relative: str) -> Path:
    """Resolve *relative* under *product_root*, refusing any path escape."""
    dest = (product_root / relative).resolve()
    if product_root not in dest.parents and dest != product_root:
        raise ValueError(f"destination {relative!r} escapes product root")
    return dest


def check(product_root: Path, scaffold: dict[str, Any]) -> dict[str, Any]:
    missing_required, missing_optional, present = [], [], []
    for entry in scaffold.get("files", []):
        dest_rel = entry["destination"]
        dest = _contained(product_root, dest_rel)
        if dest.exists():
            present.append(dest_rel)
        elif entry.get("required"):
            missing_required.append(dest_rel)
        else:
            missing_optional.append(dest_rel)
    missing_dirs = [d for d in scaffold.get("directories", [])
                    if not _contained(product_root, d).is_dir()]
    return {
        "mode": "check",
        "product_root": str(product_root),
        "ok": not missing_required,
        "present": sorted(present),
        "missing_required": sorted(missing_required),
        "missing_optional": sorted(missing_optional),
        "missing_directories": sorted(missing_dirs),
    }


def scaffold_write(product_root: Path, scaffold: dict[str, Any]) -> dict[str, Any]:
    created_files: list[str] = []
    created_dirs: list[Path] = []
    preserved: list[str] = []
    missing_templates: list[str] = []
    try:
        for d in scaffold.get("directories", []):
            path = _contained(product_root, d)
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                created_dirs.append(path)

        for entry in scaffold.get("files", []):
            dest_rel = entry["destination"]
            dest = _contained(product_root, dest_rel)
            template = TEMPLATES_DIR / entry["template"]
            if dest.exists():
                preserved.append(dest_rel)  # product-owned; never overwrite
                continue
            if not template.is_file():
                missing_templates.append(entry["template"])
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(template, dest)
            created_files.append(dest_rel)
    except Exception as exc:  # roll back only what this run created
        for rel in created_files:
            (product_root / rel).unlink(missing_ok=True)
        for path in reversed(created_dirs):
            try:
                path.rmdir()
            except OSError:
                pass
        return {"mode": "write", "product_root": str(product_root), "ok": False,
                "error": str(exc), "created": [], "preserved": sorted(preserved),
                "rolled_back": sorted(created_files)}

    return {
        "mode": "write",
        "product_root": str(product_root),
        "ok": not missing_templates,
        "created": sorted(created_files),
        "preserved": sorted(preserved),
        "created_directories": sorted(str(p.relative_to(product_root)) for p in created_dirs),
        "missing_templates": sorted(missing_templates),
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [f"scaffold-product ({report['mode']}): {'OK' if report['ok'] else 'FAILED'}",
             f"product_root: {report['product_root']}"]
    for key in ("created", "preserved", "missing_required", "missing_optional",
                "missing_directories", "missing_templates", "rolled_back"):
        if report.get(key):
            lines.append(f"  {key}: {report[key]}")
    if report.get("error"):
        lines.append(f"  error: {report['error']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_product_root_arg(parser)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--check", action="store_true",
                        help="Report missing required files without mutating anything.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    product_root = resolve_product_root(args.product_root)
    if not product_root.is_dir():
        sys.stderr.write(f"product root does not exist: {product_root}\n")
        return 2
    scaffold = load_map(args.map)

    report = check(product_root, scaffold) if args.check else scaffold_write(product_root, scaffold)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_text(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

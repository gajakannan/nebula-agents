#!/usr/bin/env python3
"""Patch prior approved feature evidence manifests to `status: superseded`.

Invoked by `agents/actions/feature.md` and `agents/actions/build.md` per §17
step 4 before writing a new `latest-run.json`. Scans canonical run folders
under `planning-mds/operations/evidence/runs/`, reads each manifest for the
requested feature, and rewrites `status: approved` to `superseded` for every
run other than `--new-run-id`. Idempotent: re-running over a state where all
prior approved manifests are already superseded is a no-op.

Exit codes:
- 0: zero or more prior approved manifests successfully patched (no-op OK).
- 1: --new-run-id manifest is missing/unparseable, or IO failure while
     patching a prior manifest. Aborts on first failure; per §24 the script
     uses atomic write-temp-then-rename within the same directory so no
     manifest is left partially written.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(FRAMEWORK_ROOT / "agents" / "scripts"))
from _product_root import ProductRootError, resolve_product_root  # noqa: E402

RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]{8}$")
FEATURE_ID_RE = re.compile(r"^F\d{4}$")


def evidence_runs_root(product_root: Path) -> Path:
    return product_root / "planning-mds" / "operations" / "evidence" / "runs"


def atomic_write_json(target: Path, data: dict) -> None:
    """Write JSON atomically via temp file + rename in the same directory."""
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Patch prior approved feature evidence manifests.")
    parser.add_argument("--product-root", default=None)
    parser.add_argument("--feature", required=True, help="Feature ID, e.g. F0036")
    parser.add_argument("--new-run-id", required=True, help="The new approved run's run ID")
    args = parser.parse_args(argv)

    if not FEATURE_ID_RE.fullmatch(args.feature):
        print(f"error: --feature must match F#### (got {args.feature!r})", file=sys.stderr)
        return 1
    if not RUN_ID_RE.fullmatch(args.new_run_id):
        print(f"error: --new-run-id must match the run-ID regex (got {args.new_run_id!r})", file=sys.stderr)
        return 1

    try:
        product_root = resolve_product_root(args.product_root)
    except ProductRootError as exc:
        parser.error(str(exc))
    if not product_root.exists() or not product_root.is_dir():
        print(f"error: --product-root {product_root} is not a directory", file=sys.stderr)
        return 1

    runs_root = evidence_runs_root(product_root)
    if not runs_root.exists():
        print(f"error: evidence runs root not found under {product_root}", file=sys.stderr)
        return 1

    new_manifest_path = runs_root / args.new_run_id / "evidence-manifest.json"
    if not new_manifest_path.exists():
        print(f"error: new run manifest missing: {new_manifest_path}", file=sys.stderr)
        return 1
    try:
        new_manifest = json.loads(new_manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"error: cannot parse new run manifest {new_manifest_path}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(new_manifest, dict) or new_manifest.get("feature_id") != args.feature:
        print(f"error: new run manifest {new_manifest_path} does not belong to {args.feature}", file=sys.stderr)
        return 1

    patched: list[str] = []
    for run_folder in sorted(runs_root.iterdir()):
        if not run_folder.is_dir():
            continue
        if not RUN_ID_RE.fullmatch(run_folder.name):
            continue
        if run_folder.name == args.new_run_id:
            continue
        manifest_path = run_folder / "evidence-manifest.json"
        if not manifest_path.exists():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"error: cannot parse prior manifest {manifest_path}: {exc}", file=sys.stderr)
            return 1
        if not isinstance(data, dict) or data.get("feature_id") != args.feature or data.get("status") != "approved":
            continue
        data["status"] = "superseded"
        try:
            atomic_write_json(manifest_path, data)
        except OSError as exc:
            print(f"error: failed to write {manifest_path}: {exc}", file=sys.stderr)
            return 1
        patched.append(str(manifest_path))

    if patched:
        print(f"patched {len(patched)} prior approved manifest(s) to superseded:")
        for path in patched:
            print(f"  {path}")
    else:
        print("no prior approved manifests to patch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

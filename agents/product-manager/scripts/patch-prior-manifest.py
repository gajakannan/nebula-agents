#!/usr/bin/env python3
"""Patch prior approved feature evidence manifests to `status: superseded`.

Invoked by `agents/actions/feature.md` and `agents/actions/build.md` per §17
step 4 before writing a new `latest-run.json`. Scans canonical run folders
under `planning-mds/operations/evidence/runs/`, reads each manifest for the
requested feature, and rewrites `status: approved` to `superseded` for every
feature-completion run other than `--new-run-id`. Planning approvals are
independent and untouched. Idempotent: re-running over a state where all
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
import re
import sys
from pathlib import Path


FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(FRAMEWORK_ROOT / "agents" / "scripts"))
from _product_root import ProductRootError, resolve_product_root  # noqa: E402
from approval_history import (FEATURE_SCOPE, approval_lock, manifests_for,
                              manifest_scope, supersede_prior)  # noqa: E402

RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]{8}$")
FEATURE_ID_RE = re.compile(r"^F\d{4}$")


def evidence_runs_root(product_root: Path) -> Path:
    return product_root / "planning-mds" / "operations" / "evidence" / "runs"


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
        with approval_lock(product_root, args.feature, FEATURE_SCOPE):
            manifests = manifests_for(product_root, args.feature)
            new_manifest = manifests.get(new_manifest_path)
            if not new_manifest or manifest_scope(new_manifest) != FEATURE_SCOPE:
                raise ValueError(f"new run must belong to {args.feature} in feature-completion scope")
            patched = supersede_prior(manifests, new_manifest_path)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if patched:
        print(f"patched {len(patched)} prior approved manifest(s) to superseded:")
        for path in patched:
            print(f"  {path}")
    else:
        print("no prior approved manifests to patch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read-only check that each reviewed feature has one current planning approval."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from _product_root import resolve_product_root
from approval_history import PLAN_SCOPE, manifests_for, manifest_scope
from project_context import resolve_scope


def check(product: Path, feature: str) -> dict:
    manifests = manifests_for(product, feature)
    plans = {p.parent.name: d for p, d in manifests.items() if manifest_scope(d) == PLAN_SCOPE}
    approved = [rid for rid, d in plans.items() if d.get("status") == "approved"]
    errors = []
    if len(approved) != 1:
        errors.append(f"expected one current planning approval; found {len(approved)}: {approved}")
    active = [rid for rid, d in plans.items() if d.get("status") in {"draft", "in-progress"}]
    if active:
        errors.append(f"planning rework is still active: {active}")
    for rid, data in plans.items():
        predecessors = data.get("supersedes", [])
        if not isinstance(predecessors, list) or any(not isinstance(p, str) for p in predecessors):
            errors.append(f"invalid supersedes list on {rid}")
            continue
        for predecessor in predecessors:
            prior = plans.get(predecessor, {})
            if prior.get("status") != "superseded" or prior.get("superseded_by") != rid:
                errors.append(f"inconsistent supersession link: {rid} supersedes {predecessor}")
    # Older approvals may not have links. Validate every explicit successor,
    # including cycles and chains that terminate at a draft or another scope.
    for rid, data in plans.items():
        if data.get("status") != "superseded" or not data.get("superseded_by"):
            continue
        seen = {rid}
        successor = data["superseded_by"]
        while True:
            if successor in seen or successor not in plans:
                errors.append(f"invalid supersession chain from {rid}: {successor}")
                break
            seen.add(successor)
            target = plans[successor]
            if target.get("status") == "approved":
                break
            if target.get("status") != "superseded" or not target.get("superseded_by"):
                errors.append(f"unfinished supersession from {rid} to {successor}; resume plan closeout")
                break
            successor = target["superseded_by"]
    return {"feature_id": feature, "approved_plan_run_id": approved[0] if len(approved) == 1 else None,
            "errors": errors}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-root")
    parser.add_argument("--plan-scope", choices=["feature", "feature-set", "project"], required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args(argv)
    try:
        product = resolve_product_root(args.product_root)
        scope = resolve_scope(product, args.plan_scope, args.target)
        results = [check(product, f["id"]) for f in scope["features"]]
        print(json.dumps({"status": "fail" if any(r["errors"] for r in results) else "pass", "features": results}, indent=2))
        return int(any(r["errors"] for r in results))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Publish a planning approval after its attested gate and exit checks.

Run by plan G3/G5. Only PHASE=A publishes at G3; A+B waits until G5. No
feature-completion manifest or latest-run.json is created or modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import yaml

from _product_root import resolve_product_root
from approval_history import (PLAN_SCOPE, RUN_ID_RE, approval_lock, atomic_write_json,
                              manifests_for, manifest_scope, read_json, supersede_prior)

SPEC = Path(__file__).resolve().parents[1] / "actions/spec/plan.yaml"


def verify_checkpoint(state: dict, checkpoint: str, run: Path, *, current_evidence: bool = True) -> dict:
    att = next((a for a in reversed(state.get("attestations", []))
                if a.get("checkpoint_id") == checkpoint), None)
    if not att or not all(att.get(k) for k in ("actor", "role", "timestamp", "evidence")):
        raise ValueError(f"missing complete approval attestation: {checkpoint}")
    for evidence in att["evidence"]:
        path = (run / evidence["path"]).resolve()
        if not path.is_relative_to(run.resolve()) or not path.is_file():
            raise ValueError(f"missing/escaping approval evidence: {path}")
        if current_evidence and hashlib.sha256(path.read_bytes()).hexdigest() != evidence["sha256"]:
            raise ValueError(f"approval evidence changed: {path}")
    return att


def approve(product: Path, feature: str, run_id: str, stage: str) -> dict:
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("invalid run ID")
    with approval_lock(product, feature, PLAN_SCOPE):
        manifests = manifests_for(product, feature)
        run = product / "planning-mds/operations/evidence/runs" / run_id
        path = run / "evidence-manifest.json"
        manifest = manifests.get(path)
        if not manifest or manifest_scope(manifest) != PLAN_SCOPE or manifest.get("action", "plan") != "plan":
            raise ValueError("selected run is not this feature's planning run")
        if manifest.get("status") not in {"draft", "in-progress", "approved"}:
            raise ValueError("cannot approve a superseded/invalid planning run")
        phase = manifest.get("plan_phase", "A+B")
        if phase not in {"A", "B", "A+B"} or (stage == "G3" and phase == "B") or (stage == "G5" and phase == "A"):
            raise ValueError("approval stage conflicts with recorded plan phase")
        journal = read_json(run / "gate-state.json")
        if journal.get("action") != "plan" or journal.get("run_id") != run_id:
            raise ValueError("approval journal identity mismatch")
        context_root = journal.get("project_context", {}).get("product_root")
        if context_root and Path(context_root).resolve() != product.resolve():
            raise ValueError("approval journal product root mismatch")
        states = journal.get("stages", {})
        required_stages = ["G1", "G2"] if stage == "G3" else (["G1", "G2", "G3", "G4"] if phase == "A+B" else ["G4"])
        if any(states.get(s, {}).get("status") != "completed" for s in required_stages):
            raise ValueError(f"approval requires completed prior stages: {required_stages}")
        spec = yaml.safe_load(SPEC.read_text())
        gate = next(g for g in spec["gates"] if g["id"] == stage)
        required_ops = []
        for op in gate["operations"]:
            kind, body = next(iter(op.items()))
            if body.get("id") == ("approve-plan-phase-a" if stage == "G3" else "approve-plan"):
                break
            required_ops.append(f"checkpoint:{body['id']}" if kind == "checkpoint" else body["id"])
        if not set(required_ops) <= set(states.get(stage, {}).get("completed_operations", [])):
            raise ValueError("approval requires all preceding gate operations to pass")
        checkpoint = "approve-phase-a" if stage == "G3" else "approve-phase-b"
        attestation = verify_checkpoint(states.get(stage, {}), checkpoint, run)
        if stage == "G5" and phase == "A+B":
            # The shared gate-decisions.md legitimately gains G4/G5 entries
            # after Phase A. Its original attestation remains historical; the
            # Phase B attestation must hash the current approval evidence.
            verify_checkpoint(states["G3"], "approve-phase-a", run, current_evidence=False)
        if stage == "G3" and phase == "A+B":
            return {"status": "pending-phase-b", "run_id": run_id}
        patched = supersede_prior(manifests, path)
        manifest.update(status="approved", approval={k: attestation[k] for k in (
            "checkpoint_id", "actor", "role", "timestamp", "evidence")})
        manifest["approved_phases"] = ["A", "B"] if phase == "A+B" else [phase]
        atomic_write_json(path, manifest)
        return {"status": "approved", "run_id": run_id, "superseded": [p.parent.name for p in patched]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-root")
    parser.add_argument("--feature", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", required=True, choices=["G3", "G5"])
    args = parser.parse_args(argv)
    try:
        print(json.dumps(approve(resolve_product_root(args.product_root), args.feature, args.run_id, args.stage)))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

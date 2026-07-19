#!/usr/bin/env python3
"""Durable action-gate driver (F0007-S0005).

Resolves an action stage from the spec and runs its typed operations in declared
order through the shared runtime (S0004), stopping at the first failure. A durable
gate-state journal records completed operations, the pending manual checkpoint,
and evidence attestations (with sha256 hashes). Manual checkpoints pause the
journal and resume only after an authorized, hashed evidence attestation — a
resume cannot skip an unattested checkpoint, and changed checkpoint output is
rejected. Journal writes are atomic and serialized by a per-run lock.

Responsibility boundary: the driver owns *procedure integrity* (ordering,
checkpoint gating, audit). Pass/fail of each invoked validator is the validator's
own exit code; the driver never re-judges evidence.

    run-gate.py --action feature --stage G4 --product-root P --feature F#### --run-id R
    run-gate.py --action feature --stage G8 --attest-checkpoint archive-move \
        --evidence pm-closeout.md --evidence signoff-ledger.md --actor NAME --role product-manager
    run-gate.py --action feature --list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import validate_action_specs as vas  # noqa: E402
import gate_runtime as gr  # noqa: E402
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402

JOURNAL_SCHEMA_VERSION = 1
JOURNAL_NAME = "gate-state.json"
LOCK_NAME = ".gate.lock"
DEFAULT_LOCK_TIMEOUT = 5.0


class GateDriverError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# --------------------------------------------------------------------------- #
# Lock + atomic journal
# --------------------------------------------------------------------------- #
def acquire_lock(lock_path: Path, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.write(fd, f"{os.getpid()} {datetime.now().isoformat()}\n".encode())
            os.close(fd)
            return
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise GateDriverError("concurrent_operation",
                                      "another gate operation holds the run lock")
            time.sleep(0.05)
        except OSError as exc:
            raise GateDriverError("lock_failed", f"cannot acquire run lock (failing closed): {exc}")


def release_lock(lock_path: Path) -> None:
    lock_path.unlink(missing_ok=True)


def _atomic_write_json(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_journal(run_folder: Path, *, run_id: str, action: str, contract_version: str) -> dict[str, Any]:
    path = run_folder / JOURNAL_NAME
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != JOURNAL_SCHEMA_VERSION:
            raise GateDriverError("stale_journal_version",
                                  f"gate-state schema {data.get('schema_version')} != {JOURNAL_SCHEMA_VERSION}")
        if data.get("run_id") != run_id:
            raise GateDriverError("wrong_run", f"journal run_id {data.get('run_id')} != {run_id}")
        return data
    return {"schema_version": JOURNAL_SCHEMA_VERSION, "run_id": run_id, "action": action,
            "contract_version": contract_version, "stages": {}}


def _stage_state(journal: dict[str, Any], stage: str) -> dict[str, Any]:
    return journal["stages"].setdefault(
        stage, {"status": "pending", "completed_operations": [],
                "pending_checkpoint": None, "attestations": []})


# --------------------------------------------------------------------------- #
# Operation identity + hashing
# --------------------------------------------------------------------------- #
def op_kind(op: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    kind, body = next(iter(op.items()))
    return kind, body if isinstance(body, dict) else {}


def op_id(op: dict[str, Any], index: int) -> str:
    kind, body = op_kind(op)
    if kind == "run":
        return body.get("id") or f"run:{index}"
    if kind == "checkpoint":
        return f"checkpoint:{body.get('id')}"
    if kind == "write":
        return f"write:{body.get('artifact')}"
    return f"{kind}:{index}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _resolve_evidence(run_folder: Path, rel: str) -> Path:
    if ".." in Path(rel).parts or Path(rel).is_absolute():
        raise GateDriverError("evidence_escapes_run", f"evidence path escapes run folder: {rel!r}")
    return run_folder / rel


def _find_attestation(stage_state: dict[str, Any], checkpoint_id: str) -> dict[str, Any] | None:
    for att in stage_state.get("attestations", []):
        if att.get("checkpoint_id") == checkpoint_id:
            return att
    return None


def _verify_attested(stage_state: dict[str, Any], checkpoint_id: str, run_folder: Path) -> bool:
    """True if the checkpoint is attested AND its hashed evidence is unchanged."""
    att = _find_attestation(stage_state, checkpoint_id)
    if att is None:
        return False
    for ev in att.get("evidence", []):
        path = _resolve_evidence(run_folder, ev["path"])
        if not path.exists():
            raise GateDriverError("checkpoint_output_missing",
                                  f"attested evidence missing: {ev['path']}")
        if sha256_file(path) != ev["sha256"]:
            raise GateDriverError("checkpoint_output_changed",
                                  f"attested evidence changed since attestation: {ev['path']}")
    return True


# --------------------------------------------------------------------------- #
# Variables + constraints + lifecycle log
# --------------------------------------------------------------------------- #
def build_variables(*, product_root: Path, feature_id: str, slug: str, run_id: str,
                    run_folder: Path, stage: str) -> dict[str, str]:
    index_root = product_root / "planning-mds" / "operations" / "evidence" / "features" / f"{feature_id}-{slug}"
    return {
        "PRODUCT_ROOT": str(product_root),
        "FEATURE_ID": feature_id,
        "FEATURE_SLUG": slug,
        "RUN_ID": run_id,
        "RUN_FOLDER": str(run_folder),
        "FEATURE_INDEX_ROOT": str(index_root),
        "FEATURE_PATH": str(product_root / "planning-mds" / "features" / f"{feature_id}-{slug}"),
        "start_tier": "1",
        "stage": stage,
    }


def check_constraints(gate: dict[str, Any], argv: list[str], stage: str) -> None:
    for constraint in gate.get("constraints", []) or []:
        forbid = constraint.get("forbid")
        if forbid and any(forbid in token for token in argv):
            raise GateDriverError("forbidden_flag",
                                  f"{forbid!r} is forbidden at {stage}: {constraint.get('reason')}")


def _append_lifecycle_log(run_folder: Path, stage: str, argv: list[str], result: dict[str, Any]) -> None:
    verdict = "PASS" if result["ok"] else ("TIMEOUT" if result["timed_out"] else "FAIL")
    refs = ", ".join(result.get("artifacts", [])) or "-"
    block = (f"\n### {stage}\n"
             f"Command: {shlex.join(argv)}\n"
             f"Stage: {stage}\n"
             f"Exit Code: {result['exit_code']}\n"
             f"Result: {verdict}\n"
             f"Output References: {refs}\n"
             f"Skipped Gates: -\n")
    with (run_folder / "lifecycle-gates.log").open("a", encoding="utf-8") as handle:
        handle.write(block)


# --------------------------------------------------------------------------- #
# Spec resolution
# --------------------------------------------------------------------------- #
def _load_spec(spec_dir: Path, action: str):
    policy = vas.load_policy(spec_dir, vas.Result())
    if policy.contract is None:
        raise GateDriverError("policy_load_failed", "could not load active contract")
    spec = policy.actions.get(action)
    if spec is None:
        raise GateDriverError("unknown_action", f"no action spec named {action!r}")
    return policy, spec


def _find_gate(spec: dict[str, Any], stage: str) -> dict[str, Any]:
    for gate in spec.get("gates", []) or []:
        if isinstance(gate, dict) and gate.get("id") == stage:
            return gate
    raise GateDriverError("unknown_stage", f"action has no gate {stage!r}")


# --------------------------------------------------------------------------- #
# Attest
# --------------------------------------------------------------------------- #
def attest_checkpoint(*, spec_dir: Path, action: str, stage: str, product_root: Path,
                      run_id: str, run_folder: Path, checkpoint_id: str,
                      evidence: list[str], actor: str, role: str, note: str = "",
                      lock_timeout: float = DEFAULT_LOCK_TIMEOUT) -> dict[str, Any]:
    policy, _ = _load_spec(spec_dir, action)
    contract_version = str(policy.contract.get("active_version"))
    lock = run_folder / LOCK_NAME
    acquire_lock(lock, lock_timeout)
    try:
        journal = load_journal(run_folder, run_id=run_id, action=action, contract_version=contract_version)
        stage_state = _stage_state(journal, stage)
        pending = stage_state.get("pending_checkpoint")
        if not pending or pending.get("id") != checkpoint_id:
            raise GateDriverError("no_pending_checkpoint",
                                  f"no pending checkpoint {checkpoint_id!r} at {stage}")
        to_hash = list(dict.fromkeys(list(pending.get("requires", []) or []) + list(evidence or [])))
        if not to_hash:
            raise GateDriverError("missing_checkpoint_evidence",
                                  "checkpoint attestation requires at least one evidence file")
        recorded = []
        for rel in to_hash:
            path = _resolve_evidence(run_folder, rel)
            if not path.exists():
                raise GateDriverError("checkpoint_output_missing", f"checkpoint output missing: {rel}")
            recorded.append({"path": rel, "sha256": sha256_file(path)})
        attestation = {
            "checkpoint_id": checkpoint_id, "actor": actor, "role": role,
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "evidence": recorded, "note": note,
        }
        stage_state["attestations"].append(attestation)
        oid = f"checkpoint:{checkpoint_id}"
        if oid not in stage_state["completed_operations"]:
            stage_state["completed_operations"].append(oid)
        stage_state["pending_checkpoint"] = None
        _atomic_write_json(run_folder / JOURNAL_NAME, journal)
        return {"ok": True, "stage": stage, "attested": checkpoint_id, "evidence": recorded}
    finally:
        release_lock(lock)


# --------------------------------------------------------------------------- #
# Run a stage
# --------------------------------------------------------------------------- #
def run_stage(*, spec_dir: Path, action: str, stage: str, product_root: Path, feature_id: str,
              slug: str, run_id: str, run_folder: Path, dry_run: bool = False,
              from_op: str | None = None, force: bool = False,
              lock_timeout: float = DEFAULT_LOCK_TIMEOUT) -> dict[str, Any]:
    policy, spec = _load_spec(spec_dir, action)
    contract_version = str(policy.contract.get("active_version"))
    gate = _find_gate(spec, stage)
    variables = build_variables(product_root=product_root, feature_id=feature_id, slug=slug,
                                run_id=run_id, run_folder=run_folder, stage=stage)
    ops = gate.get("operations", []) or []
    lock = run_folder / LOCK_NAME
    acquire_lock(lock, lock_timeout)
    try:
        journal = load_journal(run_folder, run_id=run_id, action=action, contract_version=contract_version)
        stage_state = _stage_state(journal, stage)

        if force:
            stage_state.update(status="pending", completed_operations=[], pending_checkpoint=None)
        elif stage_state["status"] == "completed":
            return {"stage": stage, "status": "completed",
                    "note": "idempotent: stage already completed", "log_refs": []}

        start_index = 0
        if from_op:
            indices = [i for i, op in enumerate(ops) if op_id(op, i) == from_op]
            if not indices:
                raise GateDriverError("unknown_op", f"no operation {from_op!r} in {stage}")
            start_index = indices[0]
            for j in range(start_index):
                kind, body = op_kind(ops[j])
                if kind == "checkpoint" and not _verify_attested(stage_state, body.get("id"), run_folder):
                    raise GateDriverError("cannot_skip_unattested_checkpoint",
                                          f"--from would skip unattested checkpoint {body.get('id')!r}")

        completed = set(stage_state["completed_operations"])
        stage_state["status"] = "in-progress"
        log_refs: list[str] = []

        for i, op in enumerate(ops):
            oid = op_id(op, i)
            kind, body = op_kind(op)
            if i < start_index:
                continue
            if oid in completed:
                # Re-verify an already-attested checkpoint on resume so tampered or
                # deleted evidence is caught even though the op is marked complete.
                if kind == "checkpoint":
                    _verify_attested(stage_state, body.get("id"), run_folder)
                continue

            if kind == "run":
                check_constraints(gate, [str(t) for t in body.get("argv", [])], stage)
                if dry_run:
                    log_refs.append(f"would-run:{oid}")
                    continue
                result = gr.run_operation(op, product_root=product_root, variables=variables,
                                          run_folder=run_folder, log_path=run_folder / "commands.log")
                argv = [gr._expand(str(t), variables) for t in body.get("argv", [])]
                _append_lifecycle_log(run_folder, stage, argv, result)
                if not result["ok"]:
                    stage_state["status"] = "failed"
                    _atomic_write_json(run_folder / JOURNAL_NAME, journal)
                    return {"stage": stage, "status": "fail", "failed_step": oid,
                            "exit_code": result["exit_code"], "timed_out": result["timed_out"],
                            "log_refs": log_refs + ["commands.log", "lifecycle-gates.log"]}
                stage_state["completed_operations"].append(oid)
                _atomic_write_json(run_folder / JOURNAL_NAME, journal)

            elif kind == "checkpoint":
                cid = body.get("id")
                if _find_attestation(stage_state, cid) and _verify_attested(stage_state, cid, run_folder):
                    if oid not in stage_state["completed_operations"]:
                        stage_state["completed_operations"].append(oid)
                        _atomic_write_json(run_folder / JOURNAL_NAME, journal)
                    continue
                stage_state["pending_checkpoint"] = {
                    "id": cid, "description": body.get("description"),
                    "requires": list(body.get("requires", []) or []),
                    "produces": list(body.get("produces", []) or []),
                }
                stage_state["status"] = "pending-checkpoint"
                if not dry_run:
                    _atomic_write_json(run_folder / JOURNAL_NAME, journal)
                return {"stage": stage, "status": "paused", "pending_checkpoint": cid,
                        "requires": list(body.get("requires", []) or []),
                        "message": f"MANUAL: {body.get('description')} — attest with "
                                   f"--attest-checkpoint {cid}", "log_refs": log_refs}

            elif kind == "write":
                artifact = body.get("artifact")
                if (run_folder / artifact).exists():
                    stage_state["completed_operations"].append(oid)
                    _atomic_write_json(run_folder / JOURNAL_NAME, journal)
                    continue
                stage_state["pending_checkpoint"] = {
                    "id": oid, "description": f"write {artifact} after {body.get('after')}",
                    "requires": [], "produces": [artifact]}
                stage_state["status"] = "pending-checkpoint"
                if not dry_run:
                    _atomic_write_json(run_folder / JOURNAL_NAME, journal)
                return {"stage": stage, "status": "paused", "pending_write": artifact,
                        "message": f"MANUAL: write {artifact}", "log_refs": log_refs}

        stage_state["status"] = "completed"
        stage_state["pending_checkpoint"] = None
        if not dry_run:
            _atomic_write_json(run_folder / JOURNAL_NAME, journal)
        return {"stage": stage, "status": "pass" if not dry_run else "dry-run",
                "completed_operations": stage_state["completed_operations"], "log_refs": log_refs}
    finally:
        release_lock(lock)


def list_runbook(spec_dir: Path, action: str) -> dict[str, Any]:
    _, spec = _load_spec(spec_dir, action)
    stages = []
    for gate in spec.get("gates", []) or []:
        ops = []
        for i, op in enumerate(gate.get("operations", []) or []):
            kind, body = op_kind(op)
            if kind == "run":
                ops.append({"op": op_id(op, i), "kind": "run", "argv": body.get("argv")})
            elif kind == "checkpoint":
                ops.append({"op": op_id(op, i), "kind": "checkpoint (MANUAL)",
                            "description": body.get("description")})
            else:
                ops.append({"op": op_id(op, i), "kind": kind})
        stages.append({"stage": gate.get("id"), "role": gate.get("role"),
                       "title": gate.get("title"), "operations": ops})
    return {"action": action, "stages": stages}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _resolve_run_folder(args, product_root: Path) -> Path:
    if args.run_folder:
        return Path(args.run_folder).resolve()
    return (product_root / "planning-mds" / "operations" / "evidence"
            / "runs" / args.run_id).resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_product_root_arg(parser)
    parser.add_argument("--action", default="feature")
    parser.add_argument("--stage")
    parser.add_argument("--feature")
    parser.add_argument("--feature-slug")
    parser.add_argument("--run-id")
    parser.add_argument("--run-folder", help="Override the resolved run folder (tests/advanced).")
    parser.add_argument("--spec-dir", type=Path, default=vas.DEFAULT_SPEC_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--from", dest="from_op", help="Resume from an operation id (cannot skip an unattested checkpoint).")
    parser.add_argument("--force", action="store_true", help="Re-run a completed stage (non-idempotent replay).")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--attest-checkpoint", dest="attest")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--actor", default="")
    parser.add_argument("--role", default="")
    parser.add_argument("--note", default="")
    args = parser.parse_args(argv)

    if args.list:
        print(json.dumps(list_runbook(args.spec_dir, args.action), indent=2, sort_keys=True))
        return 0

    product_root = resolve_product_root(args.product_root)
    run_folder = _resolve_run_folder(args, product_root)

    try:
        if args.attest:
            record = attest_checkpoint(
                spec_dir=args.spec_dir, action=args.action, stage=args.stage,
                product_root=product_root, run_id=args.run_id, run_folder=run_folder,
                checkpoint_id=args.attest, evidence=args.evidence, actor=args.actor,
                role=args.role, note=args.note)
            print(json.dumps(record, indent=2, sort_keys=True))
            return 0

        verdict = run_stage(
            spec_dir=args.spec_dir, action=args.action, stage=args.stage,
            product_root=product_root, feature_id=args.feature, slug=args.feature_slug,
            run_id=args.run_id, run_folder=run_folder, dry_run=args.dry_run,
            from_op=args.from_op, force=args.force)
    except GateDriverError as exc:
        print(json.dumps({"ok": False, "error": exc.message, "code": exc.code}))
        return 3

    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if verdict["status"] in {"pass", "completed", "dry-run", "paused"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

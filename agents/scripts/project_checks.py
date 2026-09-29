#!/usr/bin/env python3
"""Execute required product checks for gates or CI using the same contract."""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

import gate_runtime as gr
from project_context import ProjectError, SPEC_DIR, contained, digest, explicit_root, load_context, resolve_scope


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def framework_revision() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, timeout=5)
    return result.stdout.strip() if result.returncode == 0 else "unversioned"


def prepare(root: Path, action: str, *, plan_scope: str = "feature", target: str = "",
            spec_dir: Path = SPEC_DIR) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    context = load_context(root, action, spec_dir)
    context["scope"] = {"plan_scope": plan_scope, "target": target}
    if not context["checks"]:
        return context, []
    context["scope"] = resolve_scope(root, plan_scope, target)
    variables = {"NEBULA_PRODUCT_ROOT": str(root), "PLAN_SCOPE": plan_scope, "TARGET": target}
    if plan_scope == "feature":
        variables["FEATURE_PATH"] = context["scope"]["features"][0]["path"]
        variables["FEATURE_ID"] = target
    prepared = []
    for check in context["checks"]:
        argv = [gr._expand(x, variables) for x in check["argv"]]
        # v1 invokes a repository Python script, not shell text or inline code.
        if Path(argv[0]).name not in {"python", "python3"} or argv[1].startswith("-"):
            raise ProjectError("unsupported_command", "Project checks v1 require python3 followed by a product-local script.")
        script = contained(root, argv[1])
        if script.suffix != ".py" or not script.is_file():
            raise ProjectError("invalid_script", f"Expected a product Python script: {argv[1]}")
        argv[0], argv[1] = sys.executable, str(script)
        paths = {script}
        for pattern in check["inputs"]:
            expanded = gr._expand(pattern, variables)
            # Check containment before glob expansion and for every returned file.
            candidate = contained(root, expanded, exists=False)
            matches = [contained(root, p) for p in glob.glob(str(candidate), recursive=True)]
            files = {p for p in matches if p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts}
            if not files:
                raise ProjectError("input_missing", f"Check {check['id']} has no files matching {pattern}")
            paths.update(files)
        paths.add(contained(root, "planning-mds/features/REGISTRY.md"))
        inputs = {p.relative_to(root).as_posix(): file_hash(p) for p in sorted(paths)}
        framework_files = [Path(__file__), Path(__file__).with_name("project_context.py"),
                           Path(__file__).with_name("gate_runtime.py"), Path(__file__).with_name("run-gate.py"),
                           Path(__file__).with_name("validate_action_specs.py"),
                           Path(__file__).parent / "schemas/project.schema.json", spec_dir / f"{action}.yaml",
                           spec_dir / "_contract.yaml", spec_dir / "schema/action-spec.schema.json"]
        identity = {"manifest": context["manifest_hash"], "check": check,
                    "instructions": [{"path": d["path"], "sha256": d["sha256"]} for d in context["instructions"]],
                    "scope": context["scope"], "inputs": inputs,
                    "framework": {p.name: file_hash(p) for p in framework_files},
                    "framework_revision": framework_revision(), "argv": argv}
        prepared.append({**check, "argv": argv, "fingerprint": digest(identity), "identity": identity,
                         "spec_dir": str(spec_dir.resolve())})
    return context, prepared


def bind_context(journal: dict, context: dict) -> None:
    identity = {"product_root": context["product_root"], "action": context["action"],
                "manifest_hash": context["manifest_hash"], "scope": context["scope"]}
    previous = journal.get("project_context")
    if previous is not None and previous != identity:
        raise ProjectError("project_context_changed", "Product, action, scope, or manifest changed during this run; start a new run context.")
    journal["project_context"] = identity


def passed(record: dict | None, check: dict, run_folder: Path) -> bool:
    if not record or not record.get("ok") or record.get("fingerprint") != check["fingerprint"]:
        return False
    for artifact in record.get("evidence", []):
        path = contained(run_folder, artifact["path"], exists=False)
        if not path.is_file() or file_hash(path) != artifact["sha256"]:
            return False
    return bool(record.get("evidence"))


def require_prior_checks(journal: dict, spec: dict, stage: str, checks: list[dict], run_folder: Path) -> None:
    order = [g["id"] for g in spec["gates"]]
    for check in checks:
        if order.index(check["stage"]) >= order.index(stage):
            continue
        previous = journal.get("stages", {}).get(check["stage"], {})
        record = previous.get("project_checks", {}).get(check["id"])
        if previous.get("status") != "completed" or not passed(record, check, run_folder):
            raise ProjectError("project_check_required", f"Run {check['stage']} again: {check['id']} lacks a current passing result.")


def parse_result(stdout: str, check_id: str, exit_code: int, root: Path) -> dict:
    try:
        result = json.loads(stdout)
    except (ValueError, TypeError) as exc:
        raise ProjectError("invalid_check_output", "Validator must emit one JSON result.") from exc
    if not isinstance(result, dict) or set(result) != {"schema_version", "check_id", "status", "findings"}:
        raise ProjectError("invalid_check_output", "Validator result fields do not match v1.")
    if type(result["schema_version"]) is not int or result["schema_version"] != 1 or result["check_id"] != check_id:
        raise ProjectError("invalid_check_output", "Validator result version or check ID does not match.")
    if not isinstance(result["status"], str) or result["status"] not in {"pass", "fail"} or not isinstance(result["findings"], list):
        raise ProjectError("invalid_check_output", "Invalid validator status or findings.")
    for finding in result["findings"]:
        if not isinstance(finding, dict) or set(finding) != {"rule_id", "message", "path"}:
            raise ProjectError("invalid_check_output", "Findings need rule_id, message, and product-relative path.")
        if any(not isinstance(v, str) or not v.strip() for v in finding.values()):
            raise ProjectError("invalid_check_output", "Finding fields must be nonempty strings.")
        if Path(finding["path"]).is_absolute():
            raise ProjectError("invalid_check_output", "Finding paths must be product-relative.")
        contained(root, finding["path"], exists=False)
    if exit_code not in {0, 1} or (exit_code == 0) != (result["status"] == "pass"):
        raise ProjectError("check_result_disagrees", "Exit code and structured result must agree (0 pass, 1 fail).")
    if result["status"] == "pass" and result["findings"]:
        raise ProjectError("check_result_disagrees", "Passing results cannot contain failed findings.")
    return result


def execute(check: dict, *, root: Path, action: str, run_folder: Path, run_id: str) -> dict:
    artifact_dir = contained(run_folder, "artifacts/project-checks", exists=False)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{check['stage']}-{check['id']}-{uuid4().hex}"
    stdout_path = artifact_dir / f"{stem}.stdout.json"
    stderr_path = artifact_dir / f"{stem}.stderr.txt"
    metadata_path = artifact_dir / f"{stem}.result.json"
    try:
        execution = gr.execute_argv(check["argv"], cwd=root, timeout=check["timeout_seconds"], capture=True,
                                    env={"NEBULA_PRODUCT_ROOT": str(root)})
        stdout, stderr = execution.stdout or "", execution.stderr or ""
        error = None
        parsed = None
        try:
            parsed = parse_result(stdout, check["id"], execution.exit_code, root)
        except ProjectError as exc:
            error = {"code": exc.code, "message": str(exc)}
        if execution.timed_out:
            error = {"code": "check_timeout", "message": "Project check exceeded its timeout."}
        # Bind the result to both sides of execution. An editor (or validator)
        # changing declared inputs while a check runs cannot produce fresh evidence.
        try:
            scope = check["identity"]["scope"]
            _, current = prepare(root, action, plan_scope=scope["plan_scope"], target=scope["target"],
                                 spec_dir=Path(check["spec_dir"]))
            latest = next((c for c in current if c["id"] == check["id"]), None)
            if latest is None or latest["fingerprint"] != check["fingerprint"]:
                raise ProjectError("check_inputs_changed", "Project check inputs changed during execution; rerun the stage.")
        except (ProjectError, gr.GateRuntimeError, OSError, ValueError) as exc:
            error = {"code": getattr(exc, "code", "check_inputs_changed"), "message": str(exc)}
        record = {"ok": error is None and parsed["status"] == "pass", "exit_code": execution.exit_code,
                  "timed_out": execution.timed_out, "started_at": execution.started_at,
                  "ended_at": execution.ended_at, "result": parsed, "error": error}
        record["duration_seconds"] = (datetime.fromisoformat(execution.ended_at) - datetime.fromisoformat(execution.started_at)).total_seconds()
    except gr.GateRuntimeError as exc:
        stdout, stderr = "", str(exc)
        record = {"ok": False, "exit_code": 2, "timed_out": False, "error": {"code": exc.code, "message": str(exc)}}
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    record.update({"run_id": run_id, "action": action, "stage": check["stage"], "check_id": check["id"],
                   "fingerprint": check["fingerprint"], "identity": check["identity"], "cwd": str(root),
                   "argv": check["argv"]})
    metadata_path.write_text(json.dumps(record, indent=2) + "\n")
    artifacts = [stdout_path, stderr_path, metadata_path]
    record["evidence"] = [{"path": p.relative_to(run_folder).as_posix(), "sha256": file_hash(p)} for p in artifacts]
    record["artifacts"] = [str(p) for p in artifacts]
    log = gr._append_command_log()
    entry = log.build_entry(cwd="{NEBULA_PRODUCT_ROOT}", command=shlex.join(check["argv"]),
                           exit_code=record["exit_code"], artifacts=[log.normalize_artifact(str(p), root) for p in artifacts], redactions=[])
    log.append_entry(run_folder / "commands.log", entry)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-root")
    parser.add_argument("--action", default="plan-review")
    parser.add_argument("--plan-scope", choices=["feature", "feature-set", "project"], required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--run-folder", type=Path)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    try:
        root = explicit_root(args.product_root)
        context, checks = prepare(root, args.action, plan_scope=args.plan_scope, target=args.target)
        if args.list:
            print(json.dumps({"context": context, "checks": checks}, indent=2))
            return 0
        if not args.run_id or not re.fullmatch(r"\d{4}-\d{2}-\d{2}-[a-f0-9]{8}", args.run_id):
            raise ProjectError("run_id_required", "Provide --run-id YYYY-MM-DD-xxxxxxxx.")
        folder = args.run_folder or root / "planning-mds/operations/evidence/runs" / args.run_id
        folder = contained(root, str(folder)) if folder.exists() else contained(root, str(folder), exists=False)
        folder.mkdir(parents=True, exist_ok=True)
        # CI uses the same driver and journal, but executes only declared product
        # checks. It never marks a framework review stage complete.
        import importlib.util
        spec = importlib.util.spec_from_file_location("project_gate_driver", Path(__file__).with_name("run-gate.py"))
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        lock = folder / driver.LOCK_NAME
        driver.acquire_lock(lock, 5)
        try:
            state_path = folder / "project-check-state.json"
            state = json.loads(state_path.read_text()) if state_path.exists() else {"run_id": args.run_id, "results": {}}
            if state.get("run_id") != args.run_id:
                raise ProjectError("wrong_run", "Project check journal belongs to another run ID.")
            context, checks = prepare(root, args.action, plan_scope=args.plan_scope, target=args.target)
            bind_context(state, context)
            driver._atomic_write_json(state_path, state)
            for check in checks:
                record = execute(check, root=root, action=args.action, run_folder=folder, run_id=args.run_id)
                state["results"][check["id"]] = record
                driver._append_lifecycle_log(folder, check["stage"], check["argv"], record)
                driver._atomic_write_json(state_path, state)
            ok = all(r["ok"] for r in state["results"].values())
            print(json.dumps({"ok": ok, "checks": len(checks), "run_folder": str(folder), "review_approval": False}))
            return 0 if ok else 1
        finally:
            driver.release_lock(lock)
    except (ProjectError, gr.GateRuntimeError, OSError, ValueError, yaml.YAMLError) as exc:
        print(json.dumps({"ok": False, "code": getattr(exc, "code", "check_error"), "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Version-stamped, concurrency-safe evidence run initialization (F0007-S0003).

SESSION_SETUP as code. Resolves product/feature paths, mints a contract-scheme
RUN_ID, and creates the evidence skeleton — run folder, manifest stamped with the
active contract version/date, base files, empty logs, artifact subdirs, and a
seeded action-context — then emits every resolved variable as JSON for the caller.
A competing active run for the same feature is rejected.

Concurrency: a per-feature lock (identity = feature id + resolved product root)
serializes the scan-and-create critical section via an atomic O_EXCL lock file
that fails closed; the durable "one active draft/in-progress run per feature"
guard is a manifest scan performed while holding the lock. On any failure after
the run folder is created, the partial folder is rolled back — no partial skeleton.

    python3 agents/scripts/init-run.py --action feature --feature F0007 \
        --product-root PATH [--feature-slug SLUG] [--mode clean] \
        [--rerun-of RUN_ID] [--run-id RUN_ID --resume] [--force-unlock] [--json]

Exit codes: 0 ok · 2 usage · 3 active-run/lock conflict · 4 run folder exists
(no --resume) · 5 invalid input / path escape.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
FRAMEWORK_ROOT = SCRIPT_DIR.parents[1]
TEMPLATES_DIR = FRAMEWORK_ROOT / "agents" / "templates"
MANIFEST_TEMPLATE = TEMPLATES_DIR / "evidence-manifest-template.json"

sys.path.insert(0, str(SCRIPT_DIR))
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402
import validate_action_specs as vas  # noqa: E402

FEATURE_ID_RE = re.compile(r"^F\d{4}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]{8}$")
ACTIVE_STATUSES = {"draft", "in-progress"}
LOCK_TIMEOUT_SECONDS = 5.0
LOCK_POLL_SECONDS = 0.05

# base_run_files -> template (action-context is seeded; *.log start empty).
BASE_FILE_TEMPLATES = {
    "README.md": "feature-evidence-readme-template.md",
    "artifact-trace.md": "artifact-trace-template.md",
    "gate-decisions.md": "gate-decisions-template.md",
}
LOG_FILES = {"commands.log", "lifecycle-gates.log"}


class InitError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# --------------------------------------------------------------------------- #
# Resolution helpers
# --------------------------------------------------------------------------- #
def resolve_feature_slug(product_root: Path, feature_id: str, override: str | None) -> str:
    if override:
        slug = override
    else:
        registry = product_root / "planning-mds" / "features" / "REGISTRY.md"
        slug = None
        if registry.is_file():
            m = re.search(rf"{re.escape(feature_id)}-([a-z0-9][a-z0-9-]*)", registry.read_text(encoding="utf-8"))
            slug = m.group(1) if m else None
        if slug is None:
            raise InitError(5, f"feature slug for {feature_id} not found in REGISTRY.md; pass --feature-slug")
    if not SLUG_RE.match(slug):
        raise InitError(5, f"invalid feature slug {slug!r}")
    return slug


def _contained(product_root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if product_root not in resolved.parents and resolved != product_root:
        raise InitError(5, f"path {path} escapes product root {product_root}")
    return resolved


def _strip_comments(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_comments(v) for k, v in value.items() if not k.startswith("_comment")}
    if isinstance(value, list):
        return [_strip_comments(v) for v in value]
    return value


def mint_run_id() -> str:
    return f"{date.today().isoformat()}-{secrets.token_hex(4)}"


# --------------------------------------------------------------------------- #
# Locking (atomic O_EXCL; fails closed)
# --------------------------------------------------------------------------- #
def acquire_lock(lock_path: Path, *, timeout: float = LOCK_TIMEOUT_SECONDS, force: bool = False) -> None:
    if force:
        lock_path.unlink(missing_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.write(fd, f"{os.getpid()} {datetime.now().isoformat()}\n".encode())
            os.close(fd)
            return
        except FileExistsError:
            if time.monotonic() >= deadline:
                holder = lock_path.read_text(encoding="utf-8").strip() if lock_path.exists() else "unknown"
                raise InitError(3, f"feature lock held ({holder}); another initializer is active "
                                   f"(use --force-unlock to break a stale lock)")
            time.sleep(LOCK_POLL_SECONDS)
        except OSError as exc:  # fail closed — never proceed unlocked
            raise InitError(3, f"cannot acquire feature lock (failing closed): {exc}")


def release_lock(lock_path: Path) -> None:
    lock_path.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Active-run scan
# --------------------------------------------------------------------------- #
def scan_active_runs(runs_root: Path, feature_id: str, exclude_run_id: str,
                     scope: str = "feature-completion") -> list[str]:
    """Runs live under a shared evidence/runs/ tree; a run belongs to this feature when its
    manifest feature_id matches. The exclusivity rule is per scope: a feature-completion init
    conflicts only with active feature-completion runs, so a base-run (plan) for the same
    feature does not block it (and vice versa). Legacy manifests without run_scope default to
    feature-completion. Returns this feature's active (draft/in-progress) runs of *scope*."""
    active = []
    if not runs_root.is_dir():
        return active
    for child in sorted(runs_root.iterdir()):
        if not child.is_dir() or child.name == exclude_run_id:
            continue
        manifest = child / "evidence-manifest.json"
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (data.get("feature_id") == feature_id
                and data.get("status") in ACTIVE_STATUSES
                and data.get("run_scope", "feature-completion") == scope):
            active.append(child.name)
    return active


# --------------------------------------------------------------------------- #
# Skeleton creation
# --------------------------------------------------------------------------- #
def _write_manifest(run_folder: Path, *, feature_id: str, slug: str, run_id: str,
                    contract_version: str, effective_date: str, rerun_of: str | None,
                    scope: str | None = None) -> None:
    manifest = _strip_comments(json.loads(MANIFEST_TEMPLATE.read_text(encoding="utf-8")))
    feature_path = f"planning-mds/features/{feature_id}-{slug}"
    manifest.update({
        "feature_id": feature_id,
        "feature_slug": slug,
        "run_id": run_id,
        "status": "draft",
        "recorded_on": date.today().isoformat(),
        "contract_version": contract_version,
        "contract_effective_date": effective_date,
        # run_scope lets the concurrent-run scan distinguish a feature-completion run from a
        # base-run (e.g. plan), so a plan run never blocks a feature run for the same feature.
        "run_scope": scope or "feature-completion",
        "feature_path_at_run_start": feature_path,
        "feature_path_at_closeout": None,
        "rerun_of": rerun_of,
        "changed_paths": [feature_path],
    })
    _atomic_write(run_folder / "evidence-manifest.json", json.dumps(manifest, indent=2) + "\n")


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _action_context_seed(variables: dict[str, Any]) -> str:
    return (
        "# Action Context\n\n"
        "> Seeded by init-run.py. Fill the judgment sections before G0.\n\n"
        "## Run Identity\n\n"
        + "".join(f"- **{k}:** {v}\n" for k, v in sorted(variables.items()))
        + "\n## Inputs\n\n- TODO\n\n## Assumptions\n\n- TODO\n\n"
        "## Scope Boundaries\n\n- TODO\n\n## Lifecycle Stage\n\n- feature run initialized\n"
    )


def create_skeleton(run_folder: Path, *, base_run_files: list[str], artifacts_subdirs: list[str],
                    variables: dict[str, Any], resume: bool) -> tuple[list[str], list[str]]:
    created: list[str] = []
    preserved: list[str] = []

    def ensure(rel: str, content: str) -> None:
        dest = run_folder / rel
        if dest.exists():
            preserved.append(rel)
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(dest, content)
        created.append(rel)

    run_folder.mkdir(parents=True, exist_ok=True)
    for sub in artifacts_subdirs:
        (run_folder / "artifacts" / sub).mkdir(parents=True, exist_ok=True)

    for name in base_run_files:
        if name in LOG_FILES:
            ensure(name, "")
        elif name == "action-context.md":
            ensure(name, _action_context_seed(variables))
        elif name in BASE_FILE_TEMPLATES:
            template = TEMPLATES_DIR / BASE_FILE_TEMPLATES[name]
            ensure(name, template.read_text(encoding="utf-8") if template.is_file()
                   else f"# {name}\n")
        else:
            ensure(name, f"# {name}\n")
    return created, preserved


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def init_run(*, product_root: Path, feature_id: str, action: str, mode: str,
             feature_slug: str | None, run_id: str | None, rerun_of: str | None,
             resume: bool, force_unlock: bool, spec_dir: Path) -> dict[str, Any]:
    if not FEATURE_ID_RE.match(feature_id):
        raise InitError(5, f"malformed feature id {feature_id!r} (expected F####)")

    result = vas.Result()
    policy = vas.load_policy(spec_dir, result)
    if policy.contract is None:
        raise InitError(2, "could not load active contract policy")
    shared = policy.contract.get("shared", {})
    contract_version = str(policy.contract.get("active_version"))
    effective_date = str(shared.get("contract_effective_date", contract_version))
    base_run_files = list(shared.get("base_run_files", []))
    artifacts_subdirs = list(shared.get("artifacts_subdirs", []))
    action_spec = policy.actions.get(action, {})
    action_contract = action_spec.get("contract", {}) if isinstance(action_spec, dict) else {}
    action_scope = action_contract.get("scope") if isinstance(action_contract, dict) else None
    base_run_only = action_scope == "base-run-only"

    slug = resolve_feature_slug(product_root, feature_id, feature_slug)
    # Real evidence layout: the run folder lives in the shared runs/ tree; the per-feature index
    # (features/{FID}-{slug}) holds latest-run.json and the per-feature init lock.
    evidence_root = product_root / "planning-mds" / "operations" / "evidence"
    runs_root = _contained(product_root, evidence_root / "runs")
    index_root = _contained(product_root, evidence_root / "features" / f"{feature_id}-{slug}")

    run_id = run_id or mint_run_id()
    if not RUN_ID_RE.match(run_id):
        raise InitError(5, f"malformed run id {run_id!r}")
    run_folder = _contained(product_root, runs_root / run_id)

    runs_root.mkdir(parents=True, exist_ok=True)
    prior = index_root / "latest-run.json"
    run_id_prior = None
    if not base_run_only:
        index_root.mkdir(parents=True, exist_ok=True)
    if not base_run_only and prior.is_file():
        try:
            run_id_prior = json.loads(prior.read_text(encoding="utf-8")).get("run_id")
        except (OSError, json.JSONDecodeError):
            run_id_prior = None

    # Base-run-only actions must not create a feature evidence package. Keep their
    # transient per-feature lock in the shared runs tree instead of index_root.
    lock_path = ((runs_root / f".{feature_id}.init.lock") if base_run_only
                 else (index_root / ".init.lock"))
    acquire_lock(lock_path, force=force_unlock)
    created_run_folder = not run_folder.exists()
    try:
        conflicts = scan_active_runs(runs_root, feature_id, exclude_run_id=run_id,
                                     scope=action_scope or "feature-completion")
        if conflicts:
            raise InitError(3, f"active {action_scope or 'feature-completion'} run(s) already "
                               f"exist for {feature_id}: {conflicts}")

        if run_folder.exists() and any(run_folder.iterdir()) and not resume:
            raise InitError(4, f"run folder {run_folder.name} already exists (use --resume)")

        variables = {
            "action": action, "feature_id": feature_id, "feature_slug": slug,
            "mode": mode, "run_id": run_id, "run_id_prior": run_id_prior,
            "contract_version": contract_version, "contract_effective_date": effective_date,
            "product_root": str(product_root),
            "feature_index_root": str(index_root),
            "run_folder": str(run_folder),
        }
        created, preserved = create_skeleton(
            run_folder, base_run_files=base_run_files, artifacts_subdirs=artifacts_subdirs,
            variables=variables, resume=resume)
        manifest_path = run_folder / "evidence-manifest.json"
        if manifest_path.exists():
            preserved.append("evidence-manifest.json")  # version fixed at creation; never restamp
        else:
            _write_manifest(run_folder, feature_id=feature_id, slug=slug, run_id=run_id,
                            contract_version=contract_version, effective_date=effective_date,
                            rerun_of=rerun_of, scope=action_scope)
            created.append("evidence-manifest.json")
    except Exception:
        if created_run_folder and run_folder.exists():
            shutil.rmtree(run_folder, ignore_errors=True)  # no partial skeleton
        raise
    finally:
        release_lock(lock_path)

    return {
        "ok": True,
        "action": action,
        "feature_id": feature_id,
        "feature_slug": slug,
        "mode": mode,
        "run_id": run_id,
        "run_id_prior": run_id_prior,
        "rerun_of": rerun_of,
        "contract_version": contract_version,
        "contract_effective_date": effective_date,
        "product_root": str(product_root),
        "feature_index_root": str(index_root),
        "run_folder": str(run_folder),
        "created": sorted(created),
        "preserved": sorted(preserved),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_product_root_arg(parser)
    parser.add_argument("--action", default="feature")
    parser.add_argument("--feature", required=True, help="Feature id (F####).")
    parser.add_argument("--feature-slug", default=None)
    parser.add_argument("--mode", default="clean", choices=["clean", "drift-reconcile"])
    parser.add_argument("--run-id", default=None, help="Reuse a specific run id (with --resume).")
    parser.add_argument("--rerun-of", default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force-unlock", action="store_true")
    parser.add_argument("--spec-dir", type=Path, default=vas.DEFAULT_SPEC_DIR)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    product_root = resolve_product_root(args.product_root)
    if not product_root.is_dir():
        sys.stderr.write(f"product root does not exist: {product_root}\n")
        return 2

    try:
        report = init_run(
            product_root=product_root, feature_id=args.feature, action=args.action,
            mode=args.mode, feature_slug=args.feature_slug, run_id=args.run_id,
            rerun_of=args.rerun_of, resume=args.resume, force_unlock=args.force_unlock,
            spec_dir=args.spec_dir)
    except InitError as exc:
        print(json.dumps({"ok": False, "error": exc.message, "code": exc.code}))
        return exc.code

    print(json.dumps(report, indent=2, sort_keys=True) if args.json
          else f"initialized run {report['run_id']} for {report['feature_id']} "
               f"(contract {report['contract_version']})\n  run_folder: {report['run_folder']}\n"
               f"  created: {report['created']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

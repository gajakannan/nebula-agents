"""Scope-aware evidence approval history shared by plan and feature closeout."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]{8}$")
FEATURE_ID_RE = re.compile(r"^F\d{4}$")
PLAN_SCOPE = "base-run-only"
FEATURE_SCOPE = "feature-completion"


def manifest_scope(manifest: dict) -> str:
    # Historical feature manifests predate run_scope. Do not infer their action
    # from a folder name, feature state, or current working directory.
    return manifest.get("run_scope", FEATURE_SCOPE)


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot parse manifest/journal {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def manifests_for(product_root: Path, feature: str) -> dict[Path, dict]:
    runs = product_root / "planning-mds/operations/evidence/runs"
    if not runs.resolve().is_relative_to(product_root.resolve()):
        raise ValueError("evidence runs root escapes product root")
    found = {}
    for path in sorted(runs.glob("*/evidence-manifest.json")):
        if not RUN_ID_RE.fullmatch(path.parent.name):
            continue
        if not path.resolve().is_relative_to(runs.resolve()):
            raise ValueError(f"manifest escapes evidence runs root: {path}")
        data = read_json(path)
        if data.get("feature_id") == feature:
            if data.get("run_id") != path.parent.name:
                raise ValueError(f"manifest run_id disagrees with its folder: {path}")
            found[path] = data
    return found


def atomic_write_json(path: Path, data: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


@contextmanager
def approval_lock(product_root: Path, feature: str, scope: str):
    if not FEATURE_ID_RE.fullmatch(feature) or scope not in {PLAN_SCOPE, FEATURE_SCOPE}:
        raise ValueError("invalid feature or approval scope")
    path = product_root / "planning-mds/operations/evidence/runs" / f".{feature}.{scope}.approval.lock"
    if not path.parent.resolve().is_relative_to(product_root.resolve()):
        raise ValueError("approval lock escapes product root")
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError as exc:
        raise ValueError(f"cannot acquire approval lock {path}: {exc}") from exc
    try:
        with os.fdopen(fd, "w") as holder:
            holder.write(f"{os.getpid()}\n")
        yield
    finally:
        path.unlink(missing_ok=True)


def supersede_prior(manifests: dict[Path, dict], current: Path) -> list[Path]:
    """Persist the successor's links first, then retire approvals in its scope.

    A retry after a partial write recovers links from both sides. Publication of
    the new approved status/pointer belongs to the caller and occurs last.
    """
    new = manifests[current]
    if new.get("status") not in {"draft", "in-progress", "approved"}:
        raise ValueError("cannot publish or resurrect a superseded/invalid run")
    scope = manifest_scope(new)
    prior = {p: d for p, d in manifests.items() if p != current and manifest_scope(d) == scope
             and d.get("status") == "approved"}
    links = new.get("supersedes", [])
    if not isinstance(links, list) or any(not isinstance(r, str) or not RUN_ID_RE.fullmatch(r) for r in links):
        raise ValueError("supersedes must be a list of run IDs")
    links = sorted(set(links) | {p.parent.name for p in prior} | {
        p.parent.name for p, d in manifests.items() if manifest_scope(d) == scope
        and d.get("status") == "superseded" and d.get("superseded_by") == new["run_id"]})
    if links != new.get("supersedes", []):
        new["supersedes"] = links
        atomic_write_json(current, new)
    timestamp = datetime.now(timezone.utc).isoformat()
    for path, data in prior.items():
        data.update(status="superseded", superseded_by=new["run_id"], superseded_at=timestamp)
        atomic_write_json(path, data)
    return list(prior)

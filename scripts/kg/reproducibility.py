#!/usr/bin/env python3
"""Reproducibility + enforcement checks for the compiled-projection policy (F0006-S0008).

`--check-reproducible` (also exposed as `validate.py --check-reproducible`) is the single entry point
CI and the integrator use: it proves the committed generated files are a pure function of source and
enforces the git policy. It fails non-zero, naming the file + remediation, on any of:

* a committed projection / tracker region != compile(source)  (hand-edited or stale generated file),
* an invalid shard,
* `.gitattributes` drift from the `generated_paths.yaml` manifest,
* an archived feature reachable by a non-archive path in a projection,
* a suppression-ledger entry without a rationale,
* a code-index binding path that matches no file.

`.gitattributes` is *generated* from the manifest (never hand-listed): whole-file paths get
`linguist-generated` + `merge=ours`; fenced-region trackers get neither.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import compile as kgc
import kg_common
import shard_validate
import tracker_gen
from kg_common import expand_declared_pattern, load_yaml

REPO_ROOT = kg_common.REPO_ROOT
KG_SOURCE = REPO_ROOT / "planning-mds" / "kg-source"
KG_DIR = REPO_ROOT / "planning-mds" / "knowledge-graph"
MANIFEST = REPO_ROOT / "scripts" / "kg" / "generated_paths.yaml"
GITATTRIBUTES = REPO_ROOT / ".gitattributes"
OVERRIDE_TRAILER = "KG-Reproducibility-Override:"

_NONARCHIVE_FEATURE_RE = re.compile(r"planning-mds/features/(?!archive/)F(\d{4})[^\s/'\"]*")


def load_manifest() -> list[dict[str, Any]]:
    return load_yaml(MANIFEST).get("generated_paths", [])


# ── .gitattributes generated from the manifest ──────────────────────────────
def render_gitattributes() -> str:
    lines = [
        "# Generated from scripts/kg/generated_paths.yaml (F0006-S0008). Do not hand-edit.",
        "# Regenerate: python3 scripts/kg/reproducibility.py --write-gitattributes",
        "# `merge=ours` needs a one-time local: git config merge.ours.driver true",
        "",
    ]
    for entry in load_manifest():
        if entry.get("granularity") == "whole-file":
            lines.append(f"{entry['path']} linguist-generated=true merge=ours")
    return "\n".join(lines) + "\n"


def check_gitattributes() -> list[str]:
    want = render_gitattributes()
    have = GITATTRIBUTES.read_text(encoding="utf-8") if GITATTRIBUTES.exists() else ""
    if have != want:
        return [".gitattributes drifted from scripts/kg/generated_paths.yaml — run "
                "`python3 scripts/kg/reproducibility.py --write-gitattributes`"]
    return []


# ── enforcement rules ───────────────────────────────────────────────────────
def rule_archived_no_stale_path() -> list[str]:
    """An archived feature must not be reachable by a non-archive path in any projection (F0038 rule)."""
    mappings = load_yaml(KG_DIR / "feature-mappings.yaml")
    archived = set()
    for feat in mappings.get("features", []):
        # a feature whose path is under archive/ is archived
        if isinstance(feat.get("path"), str) and "planning-mds/features/archive/" in feat["path"]:
            archived.add(feat["id"].split(":")[1])
    errors = []
    for name in ("canonical-nodes.yaml", "feature-mappings.yaml", "code-index.yaml"):
        text = (KG_DIR / name).read_text(encoding="utf-8")
        for m in _NONARCHIVE_FEATURE_RE.finditer(text):
            if f"F{m.group(1)}" in archived:
                errors.append(f"{name}: archived feature F{m.group(1)} reached by a non-archive path "
                              f"`{m.group(0)}` — recompile (paths resolve through the feature shard).")
    return errors


def rule_suppression_rationale() -> list[str]:
    ledger = KG_SOURCE / "exclusions" / "suppressions.yaml"
    if not ledger.exists():
        return []
    errors = []
    for entry in load_yaml(ledger).get("suppressions", []) or []:
        if not entry.get("rationale"):
            errors.append(f"suppressions.yaml: entry {entry.get('kind')} {entry.get('ids') or entry.get('path')} "
                          f"has no rationale (suppressions must be justified)")
    return errors


def rule_binding_glob_matches() -> list[str]:
    code_index = load_yaml(KG_DIR / "code-index.yaml")
    errors = []
    for binding in code_index.get("node_bindings", []):
        for leaf in _iter_leaves(binding.get("paths")):
            if not expand_declared_pattern(leaf):
                errors.append(f"code-index: binding {binding.get('id')} path `{leaf}` matches no file")
    return errors


def _iter_leaves(node: Any) -> list[str]:
    if isinstance(node, dict):
        return [x for v in node.values() for x in _iter_leaves(v)]
    if isinstance(node, list):
        return [x for v in node for x in _iter_leaves(v)]
    return [node] if isinstance(node, str) else []


RULES = (rule_archived_no_stale_path, rule_suppression_rationale, rule_binding_glob_matches)


# ── orchestration ───────────────────────────────────────────────────────────
def check_reproducible() -> list[str]:
    """Return all reproducibility/enforcement violations (empty = clean)."""
    errors: list[str] = []

    vreport = shard_validate.validate_paths([KG_SOURCE])
    errors += vreport.errors

    result = kgc.compile_sources(KG_SOURCE, exist_root=REPO_ROOT)
    if not result.ok:
        errors += result.errors
    else:
        errors += [f"{n}: committed output != compile(source) — edit the shard / run compile.py; "
                   f"generated files are never hand-edited." for n in kgc.check_projections(result)]
        errors += [f"{n}: tracker regions stale — run tracker_gen.py / compile.py." for n in tracker_gen.check()]

    for rule in RULES:
        errors += rule()
    errors += check_gitattributes()
    return errors


def _override_reason() -> str | None:
    """Read a maintainer override trailer from the HEAD commit message, if present."""
    import subprocess
    try:
        msg = subprocess.check_output(["git", "log", "-1", "--pretty=%B"], cwd=REPO_ROOT, text=True)
    except Exception:  # noqa: BLE001 - git absent / not a repo
        return None
    for line in msg.splitlines():
        if line.startswith(OVERRIDE_TRAILER):
            return line[len(OVERRIDE_TRAILER):].strip()
    return None


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--write-gitattributes" in argv:
        GITATTRIBUTES.write_text(render_gitattributes(), encoding="utf-8")
        print(f"wrote {GITATTRIBUTES.relative_to(REPO_ROOT)} from generated_paths.yaml")
        return 0

    if "--strip-generated-at" in argv:
        # Drop `generated_at` from every whole-file generated output so a regenerate-and-diff is
        # deterministic (S0008-D1). Used by CI after regenerating symbols/decisions/coverage.
        for entry in load_manifest():
            if entry.get("granularity") == "whole-file":
                kgc.strip_generated_at(REPO_ROOT / entry["path"])
        print("stripped generated_at from whole-file generated outputs")
        return 0

    errors = check_reproducible()
    if not errors:
        print("reproducibility: OK — committed generated files == compile(source); git policy consistent")
        return 0

    override = _override_reason()
    stream = sys.stdout if override else sys.stderr
    for e in errors:
        print(f"{'warning' if override else 'error'}: {e}", file=stream)
    if override:
        print(f"\nreproducibility: {len(errors)} violation(s) DOWNGRADED by override "
              f"({OVERRIDE_TRAILER} {override}) — logged for the integrator.", file=stream)
        return 0
    print(f"\nreproducibility FAILED — {len(errors)} violation(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

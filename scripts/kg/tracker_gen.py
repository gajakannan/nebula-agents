#!/usr/bin/env python3
"""Generate the REGISTRY.md / ROADMAP.md feature tables from kg-source/features/** (F0006-S0007).

The generator owns only the fenced regions (`<!-- generated:begin <file>:<table> -->` …
`<!-- generated:end … -->`); surrounding PM-authored prose is byte-untouched. Feature facts live in
the feature shards (S0004/S0006); this renders them into the tracker tables and closes the
byte-identical tracker round trip (`compile(decompile(trackers)) == trackers`, modulo the one-time
canonicalization). Deterministic: re-running on unchanged shards is zero-diff. `compile.py` drives it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable

import kg_common
from kg_common import load_yaml

REPO_ROOT = kg_common.REPO_ROOT
KG_SOURCE = REPO_ROOT / "planning-mds" / "kg-source"
FEATURES_DIR = REPO_ROOT / "planning-mds" / "features"

STATUS_DISPLAY = {
    "planned": "Planned",
    "planned-provisional": "Planned (provisional)",
    "active": "Active",
    "in-progress": "In Progress",
    "architecture-complete": "Active",
    "done": "Done",
    "archived": "Archived",
    "archived-done": "Archived",
    "superseded": "Superseded",
}


class TrackerGenError(RuntimeError):
    pass


def load_features() -> list[dict[str, Any]]:
    return [load_yaml(p) for p in sorted((KG_SOURCE / "features").glob("*.yaml"))]


def _bare(fid: str) -> str:
    return fid.split(":", 1)[1]


def _folder(feature: dict[str, Any]) -> str:
    rel = feature["path"].replace("planning-mds/features/", "")
    return f"`{rel}/`"


def _link(feature: dict[str, Any]) -> str:
    rel = feature["path"].replace("planning-mds/features/", "")
    return f"[{_bare(feature['id'])} — {feature['name']}](./{rel}/README.md)"


def _registry_table(f: dict[str, Any]) -> str:
    explicit = str(f.get("registry_section", "")).casefold()
    if explicit in {"active", "retired", "planned", "archived"}:
        return explicit
    if f.get("retired_date") or f.get("superseded_by"):
        return "retired"
    if f.get("archived_date"):
        return "archived"
    if f.get("status") in ("planned", "planned-provisional"):
        return "planned"
    return "active"


def _id_num(f: dict[str, Any]) -> int:
    return int(_bare(f["id"])[1:])


def _date_desc_key(date_field: str) -> Callable[[dict[str, Any]], tuple]:
    # newest first; feature-ID descending tiebreak (the published REGISTRY rule)
    return lambda f: (f.get(date_field, ""), _id_num(f))


def _roadmap_key(f: dict[str, Any]) -> Any:
    return f.get("roadmap_order", 0)


# ── table specs: (header, separator, membership, sort key, reverse, row renderer) ──
def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


REGISTRY_TABLES: dict[str, dict[str, Any]] = {
    "registry:active": {
        "header": "| Feature ID | Name | Status | Phase | Folder |",
        "sep": "|------------|------|--------|-------|--------|",
        "select": lambda f: _registry_table(f) == "active",
        "key": _id_num, "reverse": False,
        "row": lambda f: _row([_bare(f["id"]), f["name"], STATUS_DISPLAY.get(f.get("status"), f.get("status", "")), f.get("phase", ""), _folder(f)]),
    },
    "registry:retired": {
        "header": "| Feature ID | Name | Terminal Status | Superseded By | Retired Date | Folder | Reason |",
        "sep": "|------------|------|-----------------|---------------|--------------|--------|--------|",
        "select": lambda f: _registry_table(f) == "retired",
        "key": _date_desc_key("retired_date"), "reverse": True,
        "row": lambda f: _row([_bare(f["id"]), f["name"], "Superseded", _bare(f.get("superseded_by", "")), f.get("retired_date", ""), _folder(f), f.get("reason", "")]),
    },
    "registry:planned": {
        "header": "| Feature ID | Name | Status | Phase | Folder |",
        "sep": "|------------|------|--------|-------|--------|",
        "select": lambda f: _registry_table(f) == "planned",
        "key": _id_num, "reverse": False,
        "row": lambda f: _row([_bare(f["id"]), f["name"], STATUS_DISPLAY.get(f.get("status"), f.get("status", "")), f.get("phase", ""), _folder(f)]),
    },
    "registry:archived": {
        "header": "| Feature ID | Name | Archived Date | Evidence Reentry Date | Folder |",
        "sep": "|------------|------|---------------|-----------------------|--------|",
        "select": lambda f: _registry_table(f) == "archived",
        "key": _date_desc_key("archived_date"), "reverse": True,
        "row": lambda f: _row([_bare(f["id"]), f["name"], f.get("archived_date", ""), f.get("evidence_reentry_date", ""), _folder(f)]),
    },
}

ROADMAP_TABLES: dict[str, dict[str, Any]] = {
    "roadmap:now": {
        "header": "| Feature | Status | Why Now | Validation Gate |", "sep": "|---------|--------|---------|-----------------|",
        "select": lambda f: f.get("roadmap_section") == "Now", "key": _roadmap_key, "reverse": False,
        "row": lambda f: _row([_link(f), STATUS_DISPLAY.get(f.get("status"), f.get("status", "")), f.get("rationale", ""), f.get("validation_gate", "")]),
    },
    "roadmap:next": {
        "header": "| Feature | Status | Why Next | Entry Criteria |", "sep": "|---------|--------|----------|----------------|",
        "select": lambda f: f.get("roadmap_section") == "Next", "key": _roadmap_key, "reverse": False,
        "row": lambda f: _row([_link(f), STATUS_DISPLAY.get(f.get("status"), f.get("status", "")), f.get("rationale", ""), f.get("validation_gate", "")]),
    },
    "roadmap:later": {
        "header": "| Feature | Status | Notes |", "sep": "|---------|--------|-------|",
        "select": lambda f: f.get("roadmap_section") == "Later", "key": _roadmap_key, "reverse": False,
        "row": lambda f: _row([_link(f), STATUS_DISPLAY.get(f.get("status"), f.get("status", "")), f.get("rationale", "")]),
    },
    "roadmap:abandoned": {
        "header": "| Feature | Superseded By | Rationale |", "sep": "|---------|---------------|-----------|",
        "select": lambda f: f.get("roadmap_section") == "Abandoned", "key": _roadmap_key, "reverse": False,
        "row": lambda f: _row([_link(f), _bare(f.get("superseded_by", "")), f.get("rationale", "")]),
    },
    "roadmap:completed": {
        "header": "| Feature | Completed Date | Evidence |", "sep": "|---------|----------------|----------|",
        "select": lambda f: f.get("roadmap_section") == "Completed", "key": _roadmap_key, "reverse": False,
        "row": lambda f: _row([_link(f), f.get("completed_date", f.get("archived_date", "")), f.get("completion_state", "")]),
    },
}


def render_table(spec: dict[str, Any], features: list[dict[str, Any]]) -> str:
    rows = sorted((f for f in features if spec["select"](f)), key=spec["key"], reverse=spec["reverse"])
    lines = [spec["header"], spec["sep"], *(spec["row"](f) for f in rows)]
    return "\n".join(lines)


def _replace_region(text: str, name: str, body: str, basename: str) -> str:
    begin, end = f"<!-- generated:begin {name} -->", f"<!-- generated:end {name} -->"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise TrackerGenError(f"{basename}: region `{name}` must have exactly one begin/end marker pair")
    pattern = re.compile(re.escape(begin) + r"\n.*?\n" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise TrackerGenError(f"{basename}: malformed markers for region `{name}`")
    return pattern.sub(f"{begin}\n{body}\n{end}", text, count=1)


def render_file(basename: str, specs: dict[str, dict[str, Any]], features: list[dict[str, Any]]) -> str:
    text = (FEATURES_DIR / basename).read_text(encoding="utf-8")
    for name, spec in specs.items():
        text = _replace_region(text, name, render_table(spec, features), basename)
    # Next Available Feature Number = max(existing F####) + 1
    if basename == "REGISTRY.md":
        nxt = f"F{max(_id_num(f) for f in features) + 1:04d}"
        text = re.sub(r"(\*\*Next Available Feature Number:\*\*\s*)F\d{4}", rf"\g<1>{nxt}", text, count=1)
    return text


TRACKER_SPECS = {"REGISTRY.md": REGISTRY_TABLES, "ROADMAP.md": ROADMAP_TABLES}


def generate(write: bool = True) -> dict[str, str]:
    """Render every tracker; write in place when `write`. Returns {basename: rendered text}."""
    features = load_features()
    _check_placement(features)
    out: dict[str, str] = {}
    for basename, specs in TRACKER_SPECS.items():
        rendered = render_file(basename, specs, features)
        out[basename] = rendered
        if write:
            (FEATURES_DIR / basename).write_text(rendered, encoding="utf-8")
    return out


def _check_placement(features: list[dict[str, Any]]) -> None:
    for f in features:
        if not f.get("roadmap_section"):
            raise TrackerGenError(f"{f['id']}: no roadmap_section (every feature must be placed)")


def check() -> list[str]:
    """Return trackers whose committed text != generate(). Zero-diff = round trip closed."""
    drift = []
    for basename, rendered in generate(write=False).items():
        if (FEATURES_DIR / basename).read_text(encoding="utf-8") != rendered:
            drift.append(basename)
    return drift


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        drift = check()
        if drift:
            for b in drift:
                print(f"error: {b} tracker regions are stale — run tracker_gen.py.", file=sys.stderr)
            return 1
        print("tracker_gen --check: tracker regions match the shards")
        return 0
    generate(write=True)
    print(f"tracker_gen: regenerated {', '.join(TRACKER_SPECS)} fenced regions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

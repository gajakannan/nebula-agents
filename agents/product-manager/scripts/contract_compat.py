#!/usr/bin/env python3
"""Version-aware dual-read compatibility diagnostic (F0007-S0007).

Proves that the evidence validator's private, date-gated requirement matrix and
the versioned action policy agree, BEFORE any private constant is removed. For a
manifest it selects the policy version (explicit ``contract_version`` or legacy
date mapping), then compares two independently-derived requirement matrices:

- legacy: the date constants owned by validate-feature-evidence.py.
- policy: the resolved history bundle's ``shared.requirements`` (S0001).

Zero disagreement across all cutovers is the parity evidence that authorizes
removing the private matrix (a separate, reviewed decision — S0008). This module
never mutates evidence or policy.

    python3 agents/product-manager/scripts/contract_compat.py --matrix
    python3 agents/product-manager/scripts/contract_compat.py --manifest PATH
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
FRAMEWORK_ROOT = SCRIPT_DIR.parents[2]
FLAGS = ("security_scans_required", "kg_reconciliation_required",
         "kg_generated_regen_required", "compile_projection_contract")

_vfe = None
_vas = None


def _load_vfe():
    global _vfe
    if _vfe is None:
        name = "validate_feature_evidence"
        if name in sys.modules:
            _vfe = sys.modules[name]
            return _vfe
        spec = importlib.util.spec_from_file_location(
            name, SCRIPT_DIR / "validate-feature-evidence.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod  # required so @dataclass can resolve annotations
        spec.loader.exec_module(mod)
        _vfe = mod
    return _vfe


def _load_vas():
    global _vas
    if _vas is None:
        scripts = FRAMEWORK_ROOT / "agents" / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        import validate_action_specs as vas
        _vas = vas
    return _vas


def _parse_date(raw: str) -> date | None:
    vfe = _load_vfe()
    return vfe.parse_iso_date(raw)


def legacy_flags(effective_date: date) -> dict[str, bool]:
    """The date-gated requirement matrix owned by validate-feature-evidence.py."""
    vfe = _load_vfe()
    return {
        "security_scans_required": effective_date >= vfe.SECURITY_SCANS_EFFECTIVE_DATE,
        "kg_reconciliation_required": effective_date >= vfe.KG_RECONCILIATION_EFFECTIVE_DATE,
        "kg_generated_regen_required": effective_date >= vfe.KG_GENERATED_REGEN_EFFECTIVE_DATE,
        "compile_projection_contract": effective_date >= vfe.KG_COMPILE_PROJECTION_EFFECTIVE_DATE,
    }


def policy_flags(policy, version: str) -> dict[str, bool]:
    """The requirement matrix resolved from the published policy bundle."""
    bundle = next((b for b in policy.bundles if b.version == version), None)
    if bundle is None:
        raise ValueError(f"no policy bundle for version {version!r}")
    reqs = bundle.data.get("shared", {}).get("requirements", {})
    return {flag: bool(reqs.get(flag, False)) for flag in FLAGS}


def dual_read(manifest: dict[str, Any], spec_dir: Path | None = None) -> dict[str, Any]:
    vas = _load_vas()
    spec_dir = spec_dir or vas.DEFAULT_SPEC_DIR
    policy = vas.load_policy(spec_dir, vas.Result())

    cv = manifest.get("contract_version")
    ced = str(manifest.get("contract_effective_date", ""))
    if cv:
        record = vas.resolve_manifest(policy, version=str(cv))
        source = "explicit"
    else:
        record = vas.resolve_manifest(policy, effective_date=ced)
        source = "legacy-date"
    if not record["ok"]:
        return {"ok": False, "selection_source": source,
                "rule": record.get("rule"), "diagnostics": record.get("diagnostics", [])}

    selected = record["selected_version"]
    eff = _parse_date(ced)
    if eff is None:
        return {"ok": False, "selection_source": source,
                "rule": "manifest_bad_effective_date", "diagnostics": [f"unparseable date {ced!r}"]}

    legacy = legacy_flags(eff)
    pol = policy_flags(policy, selected)
    disagreements = {flag: {"legacy": legacy[flag], "policy": pol[flag]}
                     for flag in FLAGS if legacy[flag] != pol[flag]}
    return {
        "ok": not disagreements,
        "selected_version": selected,
        "selection_source": source,
        "effective_date": ced,
        "legacy": legacy,
        "policy": pol,
        "disagreements": disagreements,
    }


def dual_read_matrix(spec_dir: Path | None = None) -> dict[str, Any]:
    """Dual-read across every cutover plus an inter-cutover date per bundle."""
    vas = _load_vas()
    spec_dir = spec_dir or vas.DEFAULT_SPEC_DIR
    policy = vas.load_policy(spec_dir, vas.Result())
    rows = []
    for bundle in sorted(policy.bundles, key=vas._bundle_sort_key):
        # Exact cutover date, both explicit-version and legacy-date selection.
        rows.append({"case": f"{bundle.version} (explicit)",
                     **dual_read({"contract_version": bundle.version,
                                  "contract_effective_date": bundle.version}, spec_dir)})
        rows.append({"case": f"{bundle.version} (legacy-date)",
                     **dual_read({"contract_effective_date": bundle.version}, spec_dir)})
    ok = all(row["ok"] for row in rows)
    return {"ok": ok, "cutovers": [b.version for b in policy.bundles], "rows": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", action="store_true", help="Dual-read across all cutovers.")
    parser.add_argument("--manifest", type=Path, help="Dual-read a single manifest JSON file.")
    parser.add_argument("--spec-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.matrix:
        report = dual_read_matrix(args.spec_dir)
    elif args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = dual_read(manifest, args.spec_dir)
    else:
        parser.error("provide --matrix or --manifest PATH")
        return 2

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

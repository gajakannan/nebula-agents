#!/usr/bin/env python3
"""Resolve shared policy values for consumers (F0007-S0008).

The single enforceable answer for shared policy literals (coverage floor, run-id
format, banned words, ...) lives in `agents/actions/spec/_contract.yaml`. This
tool resolves a value by name so consumers reference the shared contract instead
of hardcoding a private literal. An unknown key is rejected — there is no hidden
fallback (a consumer that cannot resolve a value must fail, not guess).

`--audit` runs the inverse-literal check: it verifies that owned consumers do not
carry a private policy-owned numeric literal that has drifted from the contract
(today: `agent-map.yaml:unit_coverage_pct` must equal `coverage_min_pct`).

    python3 agents/scripts/contract-value.py coverage_min_pct
    python3 agents/scripts/contract-value.py --json
    python3 agents/scripts/contract-value.py --audit
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
FRAMEWORK_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_CONTRACT = FRAMEWORK_ROOT / "agents" / "actions" / "spec" / "_contract.yaml"


class ContractValueError(KeyError):
    """Raised when a shared value cannot be resolved (no fallback is permitted)."""


def _load_shared(contract_path: Path | None = None) -> dict[str, Any]:
    path = contract_path or DEFAULT_CONTRACT
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("shared", {}) if isinstance(data, dict) else {}


def resolve(key: str, contract_path: Path | None = None) -> Any:
    shared = _load_shared(contract_path)
    if key not in shared:
        raise ContractValueError(
            f"shared contract value {key!r} is not defined (known: {sorted(shared)}); "
            "no fallback is permitted")
    return shared[key]


def audit(framework_root: Path | None = None, contract_path: Path | None = None) -> dict[str, Any]:
    """Inverse-literal audit: owned consumers must not carry a drifted policy literal."""
    root = framework_root or FRAMEWORK_ROOT
    coverage = resolve("coverage_min_pct", contract_path)
    findings: list[dict[str, Any]] = []

    agent_map = root / "agents" / "agent-map.yaml"
    if agent_map.is_file():
        match = re.search(r"unit_coverage_pct:\s*(\d+)", agent_map.read_text(encoding="utf-8"))
        if match is None:
            findings.append({"consumer": "agents/agent-map.yaml", "field": "unit_coverage_pct",
                             "issue": "missing", "expected": coverage})
        elif int(match.group(1)) != coverage:
            findings.append({"consumer": "agents/agent-map.yaml", "field": "unit_coverage_pct",
                             "value": int(match.group(1)), "expected": coverage,
                             "issue": "drifted from coverage_min_pct"})
    return {"ok": not findings, "coverage_min_pct": coverage, "findings": findings}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("key", nargs="?", help="Shared value name to resolve.")
    parser.add_argument("--contract", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print all shared values as JSON.")
    parser.add_argument("--audit", action="store_true", help="Run the inverse-literal drift audit.")
    args = parser.parse_args(argv)

    if args.audit:
        report = audit(contract_path=args.contract)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["ok"] else 1
    if args.json:
        print(json.dumps(_load_shared(args.contract), indent=2, sort_keys=True, default=str))
        return 0
    if not args.key:
        parser.error("provide a key, --json, or --audit")
        return 2
    try:
        value = resolve(args.key, args.contract)
    except ContractValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    print(value if not isinstance(value, (dict, list)) else json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

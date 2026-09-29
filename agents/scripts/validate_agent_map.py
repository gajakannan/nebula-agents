#!/usr/bin/env python3
"""Validate the Phase 3a model_tier + execution annotations in agent-map.yaml.

Vendor-neutral: model tiers are abstract (lightweight | balanced | advanced); a
per-harness adapter (Phase 3b, deferred) maps them to concrete model ids. This validator
catches drift — a missing/invalid tier, unknown execution values, a concurrent action
without its mandatory sequential fallback, or a vendor model id leaking into the neutral
map.

Usage:
    python3 agents/scripts/validate_agent_map.py [--map agents/agent-map.yaml]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

# {NEBULA_PRODUCT_ROOT}/... placeholders read as YAML flow-mappings, so strip the braces from
# single-token {PLACEHOLDER}s before parsing. Real flow mappings (execution: {a: b, ...})
# contain ':'/spaces and are left untouched.
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z0-9_]+)\}")


def parse_map(text: str):
    """Parse agent-map.yaml, neutralizing {PLACEHOLDER} braces that aren't valid YAML."""
    return yaml.safe_load(_PLACEHOLDER_RE.sub(r"\1", text))

MODEL_TIERS = {"lightweight", "balanced", "advanced"}
ISOLATION = {"fresh", "shared"}
RETURNS = {"summary", "full"}
ORCHESTRATION = {"sequential", "parallel", "nested"}
# tokens that signal a concrete vendor model id leaked into the neutral map
VENDOR_HINTS = ("gpt-", "claude-", "gemini", "llama", "mistral", "o1-", "o3-",
                "haiku", "sonnet", "opus")

DEFAULT_MAP = Path(__file__).resolve().parents[1] / "agent-map.yaml"


def _check_execution(execution, where: str, errors: list[str]) -> None:
    if not isinstance(execution, dict):
        errors.append(f"{where}: execution must be a mapping")
        return
    iso = execution.get("isolation")
    if iso is not None and iso not in ISOLATION:
        errors.append(f"{where}: execution.isolation '{iso}' not in {sorted(ISOLATION)}")
    ret = execution.get("returns")
    if ret is not None and ret not in RETURNS:
        errors.append(f"{where}: execution.returns '{ret}' not in {sorted(RETURNS)}")
    pg = execution.get("parallel_group")
    if pg is not None and not isinstance(pg, str):
        errors.append(f"{where}: execution.parallel_group must be a string or null")


def validate_agent_map(data) -> list[str]:
    """Return a list of validation errors (empty == valid). Operates on parsed YAML."""
    errors: list[str] = []
    data = data or {}

    for role, spec in (data.get("agents") or {}).items():
        if not isinstance(spec, dict):
            continue
        tier = spec.get("model_tier")
        if tier is None:
            errors.append(f"agent '{role}': missing model_tier")
        elif tier not in MODEL_TIERS:
            errors.append(
                f"agent '{role}': model_tier '{tier}' not in {sorted(MODEL_TIERS)} "
                "(use an abstract tier, not a vendor model id)")

    for action, spec in (data.get("actions") or {}).items():
        if not isinstance(spec, dict):
            continue
        steps = spec.get("steps") or []
        has_parallel = any(isinstance(s, dict) and "parallel" in s for s in steps)
        min_orch = spec.get("min_orchestration")
        if has_parallel and not (isinstance(min_orch, list) and "sequential" in min_orch):
            errors.append(
                f"action '{action}': has parallel steps but min_orchestration must "
                "include 'sequential' (the mandatory sequential fallback)")
        if min_orch is not None:
            if not isinstance(min_orch, list):
                errors.append(f"action '{action}': min_orchestration must be a list")
            else:
                for value in min_orch:
                    if value not in ORCHESTRATION:
                        errors.append(
                            f"action '{action}': min_orchestration '{value}' not in {sorted(ORCHESTRATION)}")
        for i, step in enumerate(steps):
            if isinstance(step, dict) and "execution" in step:
                _check_execution(step["execution"], f"action '{action}' step {i}", errors)

    return errors


def scan_vendor_ids(text: str) -> list[str]:
    """Flag a vendor model id appearing in a model_tier / model field (neutrality guard)."""
    hits: list[str] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if "model_tier" in low or low.strip().startswith(("model:", "model_id:")):
            for hint in VENDOR_HINTS:
                if hint in low:
                    hits.append(f"line {line_no}: vendor model id '{hint}' in a model field: {line.strip()}")
                    break
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate agent-map.yaml Phase 3a annotations.")
    ap.add_argument("--map", default=str(DEFAULT_MAP), help="Path to agent-map.yaml")
    args = ap.parse_args()

    path = Path(args.map)
    if not path.is_file():
        print(f"agent-map not found: {path}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")
    data = parse_map(text)

    errors = validate_agent_map(data) + scan_vendor_ids(text)
    if errors:
        print(f"agent-map validation FAILED ({len(errors)} issue(s)):")
        for error in errors:
            print(f"  - {error}")
        return 1
    agents = (data or {}).get("agents") or {}
    actions = (data or {}).get("actions") or {}
    print(f"agent-map OK: {len(agents)} roles tiered, {len(actions)} actions checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

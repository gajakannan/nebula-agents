#!/usr/bin/env python3
"""Central severity state machine (F0007-S0005).

One implementation of the gate-severity arithmetic that was duplicated across
build / feature / review / validate / test / plan-review / feature-review.
Agents classify findings; this module only computes the allowed outcome from the
per-domain critical/high counts. It never classifies.

Profiles:
- standard: BLOCKED (any critical) / WARNING (any high) / ACCEPTABLE.
- review-family: NOT READY / CONDITIONALLY READY / READY (plan variant);
  NOT DONE / CONDITIONALLY DONE / TRULY DONE (feature variant).
- none: always PASS (no severity gate).

    python3 -m gate_policy --profile standard --code-critical 0 --code-high 1 \
        --security-critical 0 --security-high 0
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

PROFILES = ("standard", "review-family", "none")
REVIEW_VARIANTS = {
    "plan": ("NOT READY", "CONDITIONALLY READY", "READY"),
    "feature": ("NOT DONE", "CONDITIONALLY DONE", "TRULY DONE"),
}


class SeverityError(ValueError):
    """Raised on an impossible severity input (negative or non-integer count)."""


def _validate_counts(domains: dict[str, dict[str, int]]) -> tuple[int, int]:
    total_critical = 0
    total_high = 0
    for name, counts in domains.items():
        for key in ("critical", "high"):
            value = counts.get(key, 0)
            if isinstance(value, bool) or not isinstance(value, int):
                raise SeverityError(f"{name}.{key} must be a non-negative integer, got {value!r}")
            if value < 0:
                raise SeverityError(f"{name}.{key} must not be negative, got {value}")
        total_critical += counts.get("critical", 0)
        total_high += counts.get("high", 0)
    return total_critical, total_high


def evaluate(profile: str, domains: dict[str, dict[str, int]], *, variant: str = "plan") -> dict[str, Any]:
    if profile not in PROFILES:
        raise SeverityError(f"unknown profile {profile!r} (expected one of {PROFILES})")
    total_critical, total_high = _validate_counts(domains)

    def result(status: str, options: list[str], approve: bool, justify: bool) -> dict[str, Any]:
        return {
            "profile": profile,
            "variant": variant if profile == "review-family" else None,
            "status": status,
            "options": options,
            "approve_enabled": approve,
            "requires_justification": justify,
            "totals": {"critical": total_critical, "high": total_high},
            "domains": {k: {"critical": v.get("critical", 0), "high": v.get("high", 0)}
                        for k, v in sorted(domains.items())},
        }

    if profile == "none":
        return result("PASS", ["approve"], True, False)

    if profile == "standard":
        blocked, warning, ok = "BLOCKED", "WARNING", "ACCEPTABLE"
    else:  # review-family
        if variant not in REVIEW_VARIANTS:
            raise SeverityError(f"unknown review variant {variant!r}")
        blocked, warning, ok = REVIEW_VARIANTS[variant]

    if total_critical > 0:
        return result(blocked, ["fix issues", "reject"], False, False)
    if total_high > 0:
        return result(warning, ["fix issues", "approve with justification", "reject"], True, True)
    return result(ok, ["approve", "fix issues"], True, False)


def _domains_from_args(args: argparse.Namespace) -> dict[str, dict[str, int]]:
    domains: dict[str, dict[str, int]] = {
        "code": {"critical": args.code_critical, "high": args.code_high},
        "security": {"critical": args.security_critical, "high": args.security_high},
    }
    for spec in args.domain or []:
        try:
            name, critical, high = spec.split(":")
            domains[name] = {"critical": int(critical), "high": int(high)}
        except ValueError:
            raise SeverityError(f"--domain must be name:critical:high, got {spec!r}")
    return domains


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="standard")
    parser.add_argument("--variant", choices=list(REVIEW_VARIANTS), default="plan")
    parser.add_argument("--code-critical", type=int, default=0)
    parser.add_argument("--code-high", type=int, default=0)
    parser.add_argument("--security-critical", type=int, default=0)
    parser.add_argument("--security-high", type=int, default=0)
    parser.add_argument("--domain", action="append", default=[],
                        help="Extra domain as name:critical:high. Repeatable.")
    args = parser.parse_args(argv)
    try:
        decision = evaluate(args.profile, _domains_from_args(args), variant=args.variant)
    except SeverityError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

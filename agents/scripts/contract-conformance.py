#!/usr/bin/env python3
"""Independent conformance + historical baseline matrix for action policy (F0007-S0002).

Schema validity (S0001) and generated drift prove only *internal* consistency —
prompts, runners, and validators derived from one spec can all agree on a
weakened or accidental contract change. This adds a separate, independently
authored line of defense:

1. Hard-coded structural invariants (written here, NOT derived from the spec):
   canonical action scope, forbidden run-ID schemes, required gate/artifact
   relations, historical immutability + monotonic dates, and typed (no-shell)
   execution. Removing a required gate artifact fails here even if the edited
   spec is internally consistent and its generated output matches.

2. A golden baseline matrix (conformance-baseline.yaml, independently authored):
   each published version's expected verdict, requirement flags, required
   artifacts, and an immutable model-hash fingerprint. A weakening edit to a
   published bundle fails the matrix.

Read-only: never mutates policy, evidence, or the baseline. Updating an expected
outcome requires editing conformance-baseline.yaml WITH an audit-log entry — the
same authorization as publishing a new policy version.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import validate_action_specs as vas  # noqa: E402

DEFAULT_BASELINE = SCRIPT_DIR / "conformance-baseline.yaml"

# ---- Independent expectations (authored here, never read from the spec) ---- #
CANONICAL_SCOPES = frozenset({"feature-completion", "base-run-only", "read-only-audit", "merge"})
CANONICAL_RUN_ID_SCHEMES = frozenset({"contract", "integrate"})
CANONICAL_RUN_ID_FORMAT = "YYYY-MM-DD-[a-z0-9]{8}"
REQUIRED_RUN_ID_FORBIDDEN = frozenset({"uuid4"})

# Gate -> artifact relations that MUST hold in the active feature action.
FEATURE_UNCONDITIONAL_ARTIFACTS = {
    "G0": "g0-assembly-plan-validation.md",
    "G8": "pm-closeout.md",
}
# (requirement flag -> (gate, artifact)) — required only when the flag resolves true.
# G3 is the code+security review gate; G7 is the architect KG reconciliation (real contract).
FEATURE_CONDITIONAL_ARTIFACTS = {
    "kg_reconciliation_required": ("G7", "kg-reconciliation.md"),
    "security_scans_required": ("G3", "security-review-report.md"),
}


def load_baseline(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _feature_gate_artifacts(spec: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for g in spec.get("gates", []) or []:
        if isinstance(g, dict) and g.get("id"):
            out[str(g["id"])] = list(g.get("artifacts", []) or [])
    return out


def check_invariants(policy: vas.Policy, result: vas.Result) -> None:
    contract = policy.contract or {}
    shared = contract.get("shared", {}) if isinstance(contract.get("shared"), dict) else {}

    # Canonical scope + run-ID scheme per action.
    for name, spec in sorted(policy.actions.items()):
        c = spec.get("contract", {}) if isinstance(spec.get("contract"), dict) else {}
        if c.get("scope") not in CANONICAL_SCOPES:
            result.add("noncanonical_scope", f"{name}.yaml",
                       f"scope {c.get('scope')!r} not in {sorted(CANONICAL_SCOPES)}")
        scheme = (spec.get("run_id", {}) or {}).get("scheme")
        if scheme not in CANONICAL_RUN_ID_SCHEMES:
            result.add("noncanonical_run_id_scheme", f"{name}.yaml",
                       f"run_id.scheme {scheme!r} not in {sorted(CANONICAL_RUN_ID_SCHEMES)}")

    # Forbidden run-ID schemes / canonical format on the active shared contract.
    if shared.get("run_id_format") != CANONICAL_RUN_ID_FORMAT:
        result.add("noncanonical_run_id_format", "_contract.yaml",
                   f"run_id_format {shared.get('run_id_format')!r} != {CANONICAL_RUN_ID_FORMAT!r}")
    forbidden = set(shared.get("run_id_forbidden", []) or [])
    for term in sorted(REQUIRED_RUN_ID_FORBIDDEN - forbidden):
        result.add("run_id_forbidden_missing", "_contract.yaml",
                   f"run_id_forbidden must include {term!r}")

    # Required gate/artifact relations on the active feature action (independent
    # of what the spec's generated output shows).
    feature = policy.actions.get("feature")
    if feature is None:
        result.add("missing_feature_action", "spec", "no active feature action to conform")
    else:
        gate_arts = _feature_gate_artifacts(feature)
        for gate, artifact in FEATURE_UNCONDITIONAL_ARTIFACTS.items():
            if artifact not in gate_arts.get(gate, []):
                result.add("missing_required_gate_artifact", f"feature.yaml#{gate}",
                           f"{gate} must declare artifact {artifact!r}")
        reqs = shared.get("requirements", {}) if isinstance(shared.get("requirements"), dict) else {}
        for flag, (gate, artifact) in FEATURE_CONDITIONAL_ARTIFACTS.items():
            if reqs.get(flag) and artifact not in gate_arts.get(gate, []):
                result.add("missing_required_gate_artifact", f"feature.yaml#{gate}",
                           f"{gate} must declare artifact {artifact!r} while {flag} is true")

    # Historical immutability + monotonic dates, re-derived independently.
    ordered = sorted(policy.bundles, key=vas._bundle_sort_key)
    for prev, cur in zip(ordered, ordered[1:]):
        if vas._bundle_sort_key(cur) <= vas._bundle_sort_key(prev):
            result.add("nonmonotonic_history", f"history/{cur.source}",
                       f"{cur.version} not strictly after {prev.version}")
    for b in policy.bundles:
        if str(b.data.get("effective_from")) != b.version:
            result.add("history_effective_from_mismatch", f"history/{b.source}",
                       f"effective_from != version {b.version}")

    # Typed (no-shell) execution — independent scan of every operation.
    for name, spec in sorted(policy.actions.items()):
        for gi, gate in enumerate(spec.get("gates", []) or []):
            for oi, op in enumerate(gate.get("operations", []) or []) if isinstance(gate, dict) else []:
                if not isinstance(op, dict) or len(op) != 1:
                    result.add("shell_form_execution", f"{name}.yaml#gates/{gi}/operations/{oi}",
                               "operation is not a single typed op; shell-form execution is forbidden")


def check_baseline(policy: vas.Policy, baseline: dict[str, Any], result: vas.Result) -> list[dict[str, Any]]:
    fixtures = {str(f["version"]): f for f in baseline.get("fixtures", [])}
    bundles = {b.version: b for b in policy.bundles}
    matrix: list[dict[str, Any]] = []

    for v in sorted(bundles):
        if v not in fixtures:
            result.add("undocumented_policy_version", f"history/{v}",
                       f"published version {v} has no golden baseline fixture")
    for v in sorted(fixtures):
        if v not in bundles:
            result.add("baseline_missing_bundle", f"conformance-baseline.yaml#{v}",
                       f"baseline fixture {v} has no published bundle")

    for v in sorted(set(fixtures) & set(bundles)):
        fx, b = fixtures[v], bundles[v]
        model = vas.bundle_model(b)
        expected_reqs = vas._shared_model({"requirements": fx.get("requirements", {})})["requirements"]
        actual_reqs = model["shared"]["requirements"]
        verdict = "pass"
        if actual_reqs != expected_reqs:
            result.add("baseline_requirements_mismatch", v,
                       f"expected {expected_reqs} got {actual_reqs}")
            verdict = "fail"
        actual_arts = {g["id"]: sorted(g["required_artifacts"]) for g in model["actions"]["feature"]["gates"]}
        for gid, expected in (fx.get("feature_required_artifacts", {}) or {}).items():
            if actual_arts.get(gid, []) != sorted(expected):
                result.add("baseline_artifacts_mismatch", f"{v}#{gid}",
                           f"expected {sorted(expected)} got {actual_arts.get(gid, [])}")
                verdict = "fail"
        actual_hash = vas._hash_model(model)
        if actual_hash != fx.get("model_hash"):
            result.add("historical_expectation_changed", v,
                       f"model hash changed (expected {str(fx.get('model_hash'))[:12]}..., "
                       f"got {actual_hash[:12]}...); if intentional, publish a new version and add "
                       f"an audit-log entry to conformance-baseline.yaml")
            verdict = "fail"
        matrix.append({"version": v, "expected_verdict": fx.get("expected_verdict"),
                       "verdict": verdict})
    return matrix


def run_conformance(spec_dir: Path, baseline_path: Path) -> tuple[vas.Result, dict[str, Any]]:
    result = vas.Result()
    policy = vas.load_policy(spec_dir, result)
    try:
        baseline = load_baseline(baseline_path)
    except (OSError, yaml.YAMLError) as exc:
        result.add("baseline_load_error", str(baseline_path), str(exc))
        baseline = {}
    check_invariants(policy, result)
    matrix = check_baseline(policy, baseline, result)
    report = {
        "ok": result.ok,
        "spec_dir": str(spec_dir),
        "baseline": str(baseline_path),
        "baseline_matrix": matrix,
        "audit_log": baseline.get("audit_log", []),
        "findings": [f.as_dict() for f in result.sorted_findings()],
    }
    return result, report


def render_text(report: dict[str, Any]) -> str:
    lines = [f"contract conformance: {'OK' if report['ok'] else 'FAILED'}",
             f"spec_dir: {report['spec_dir']}",
             f"baseline: {report['baseline']}", "", "historical baseline matrix:"]
    for row in report["baseline_matrix"]:
        mark = "ok" if row["verdict"] == row["expected_verdict"] else "MISMATCH"
        lines.append(f"  - {row['version']}: expected={row['expected_verdict']} "
                     f"actual={row['verdict']} [{mark}]")
    if report["findings"]:
        lines.append("")
        lines.append(f"findings ({len(report['findings'])}):")
        for f in report["findings"]:
            lines.append(f"  [{f['rule']}] {f['path']}: {f['message']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec-dir", type=Path, default=vas.DEFAULT_SPEC_DIR)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    _, report = run_conformance(args.spec_dir, args.baseline)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_text(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

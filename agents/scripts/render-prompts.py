#!/usr/bin/env python3
"""Compile evidence-contract prompts from action policy, with a drift gate (F0007-S0006).

Both prompt variants — operator-friendly (prose) and automation-safe (uppercase
outline) — are rendered from the SAME action spec + shared contract, so the fixed
procedure stays aligned without paraphrase maintenance. A stdlib renderer (plain
Python string assembly) is used: it never evaluates template data as code or shell
content. Output is byte-stable for identical input.

Generated files carry a do-not-edit header and are committed under
``agents/templates/prompts/evidence-contract/generated/``. ``--check`` regenerates
to memory and fails on any drift, so a hand edit to a generated file is caught.

    python3 agents/scripts/render-prompts.py            # regenerate all
    python3 agents/scripts/render-prompts.py --action feature
    python3 agents/scripts/render-prompts.py --check    # CI drift gate (no writes)
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
FRAMEWORK_ROOT = SCRIPT_DIR.parents[1]
GENERATED_DIR = FRAMEWORK_ROOT / "agents" / "templates" / "prompts" / "evidence-contract"
RENDERER_VERSION = 1
KNOWN_SCOPES = frozenset({"feature-completion", "base-run-only", "read-only-audit", "merge"})
PACKAGE_ROOT_REF = "planning-mds/operations/evidence"
ALL_VARIANTS = ("operator-friendly", "automation-safe")
# Only identifier-form placeholders; ignores {8} in a format or {a,b} lists.
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

sys.path.insert(0, str(SCRIPT_DIR))
import validate_action_specs as vas  # noqa: E402


class RenderError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _header(action: str, policy_version: str) -> str:
    return (f"<!-- GENERATED from agents/actions/spec/{action}.yaml + _contract.yaml — "
            f"do not edit; run: python3 agents/scripts/render-prompts.py --action {action} -->\n"
            f"<!-- policy_version: {policy_version} | renderer_version: {RENDERER_VERSION} -->\n")


def _run_id_method(shared: dict[str, Any]) -> str:
    argv = (shared.get("run_id_suffix", {}) or {}).get("argv", [])
    return " ".join(str(a) for a in argv)


def _op_lines(gate: dict[str, Any]) -> list[str]:
    lines = []
    for op in gate.get("operations", []) or []:
        kind, body = next(iter(op.items()))
        body = body if isinstance(body, dict) else {}
        if kind == "run":
            lines.append(f"    - run `{' '.join(str(a) for a in body.get('argv', []))}` "
                         f"(cwd: {body.get('cwd')}, timeout: {body.get('timeout_seconds', 'none')}s)")
        elif kind == "checkpoint":
            lines.append(f"    - MANUAL checkpoint `{body.get('id')}`: {body.get('description')} "
                         f"(requires: {', '.join(body.get('requires', []))}; "
                         f"produces: {', '.join(body.get('produces', []))})")
        elif kind == "write":
            lines.append(f"    - write `{body.get('artifact')}` after `{body.get('after')}`")
    return lines


def _common_facts(spec: dict[str, Any], shared: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id_format": shared.get("run_id_format", ""),
        "run_id_method": _run_id_method(shared),
        "run_id_forbidden": shared.get("run_id_forbidden", []),
        "base_run_files": ", ".join(shared.get("base_run_files", [])),
        "artifacts_subdirs": ", ".join(shared.get("artifacts_subdirs", [])),
        "context_preamble": shared.get("context_preamble", []),
        "coverage_min_pct": shared.get("coverage_min_pct"),
    }


def _auto_resolved(spec: dict[str, Any]) -> list[tuple[str, str]]:
    auto = spec.get("auto_resolved", {})
    return sorted((str(k), str(v)) for k, v in auto.items()) if isinstance(auto, dict) else []


def _tiers(spec: dict[str, Any]) -> list[tuple[str, Any]]:
    tiers = (spec.get("retrieval", {}) or {}).get("tier_defaults", {})
    return sorted(tiers.items()) if isinstance(tiers, dict) else []


def _ownership(spec: dict[str, Any]) -> list[tuple[str, list[str]]]:
    own = spec.get("ownership", {})
    return sorted((str(k), list(v)) for k, v in own.items()) if isinstance(own, dict) else []


def render_operator(spec: dict[str, Any], shared: dict[str, Any], policy_version: str) -> str:
    action = spec["action"]
    contract = spec.get("contract", {})
    facts = _common_facts(spec, shared)
    out = [_header(action, policy_version), ""]
    out.append(f"This prompt encodes the **{contract.get('name')}** "
               f"(scope `{contract.get('scope')}`, policy `{policy_version}`).")
    out.append("")
    out.append("Required inputs:")
    for item in spec.get("inputs", {}).get("required", []):
        out.append(f"- `{item['name']}`" + (f" (format `{item['format']}`)" if item.get("format") else ""))
    optional = spec.get("inputs", {}).get("optional", [])
    if optional:
        out.append("")
        out.append("Optional inputs (defaults apply when omitted):")
        for item in optional:
            default = f" — default `{item['default']}`" if item.get("default") else ""
            out.append(f"- `{item['name']}`{default}")
    auto = _auto_resolved(spec)
    if auto:
        out.append("")
        out.append("Auto-resolved (do not set; SESSION_SETUP / the orchestrator compute these):")
        out.extend(f"- `{name}` — {value}" for name, value in auto)
    out.append("")
    out.append(f"Generate `{spec['run_id']['var']}` once at session start in the contract format "
               f"`{facts['run_id_format']}` using `{facts['run_id_method']}`. "
               f"Do not use: {', '.join(facts['run_id_forbidden']) or 'n/a'}.")
    out.append("")
    out.append(f"Session setup: create the run under `{PACKAGE_ROOT_REF}/`, initialize "
               f"`evidence-manifest.json` (status `draft`) with the active contract version stamped, "
               f"create the base run files ({facts['base_run_files']}) and artifact subdirs "
               f"({facts['artifacts_subdirs']}). Run `agents/scripts/init-run.py` to perform this.")
    tiers = _tiers(spec)
    if tiers:
        out.append("")
        out.append("Retrieval tier defaults: " + "; ".join(f"{mode}: {vals}" for mode, vals in tiers))
    out.append("")
    out.append("Load context in this order, then navigate rather than eager-load:")
    ctx = list(facts["context_preamble"]) + [c for c in spec.get("context_load", []) if c not in facts["context_preamble"]]
    for i, path in enumerate(ctx, 1):
        out.append(f"{i}. `{path}`")
    out.append("")
    out.append("Gates (run each stage through `agents/scripts/run-gate.py`, in order):")
    for gate in spec.get("gates", []):
        out.append(f"- **{gate['id']} — {gate.get('title')}** (role: {gate.get('role')}; "
                   f"artifacts: {', '.join(gate.get('artifacts', [])) or 'none'})")
        out.extend(_op_lines(gate))
        for c in gate.get("constraints", []) or []:
            out.append(f"    - constraint: `{c['forbid']}` forbidden — {c['reason']}")
        if gate.get("judgment"):
            out.append(f"    - judgment: {gate['judgment'].strip()}")
    out.append("")
    out.append(f"Severity gate profile: `{spec.get('severity_gate', 'none')}` "
               f"(compute allowed outcomes with `agents/scripts/gate_policy.py`; "
               f"coverage floor is {facts['coverage_min_pct']}%).")
    ownership = _ownership(spec)
    if ownership:
        out.append("")
        out.append("Ownership (strict):")
        out.extend(f"- **{role}** owns: {', '.join(items)}" for role, items in ownership)
    if spec.get("forbidden"):
        out.append("")
        out.append("Forbidden:")
        out.extend(f"- {f}" for f in spec["forbidden"])
    out.append("")
    out.append("Stop conditions:")
    out.extend(f"- {s}" for s in spec.get("stop_conditions", []))
    if spec.get("conflict_resolution"):
        out.append("")
        out.append("Conflict resolution:")
        out.extend(f"- {c}" for c in spec["conflict_resolution"])
    for name, text in sorted((spec.get("notes", {}) or {}).items()):
        out.append("")
        out.append(f"Note ({name}): {text.strip()}")
    return "\n".join(out).rstrip() + "\n"


def render_automation(spec: dict[str, Any], shared: dict[str, Any], policy_version: str) -> str:
    action = spec["action"]
    contract = spec.get("contract", {})
    facts = _common_facts(spec, shared)
    out = [_header(action, policy_version), ""]
    out.append(f"CONTRACT: {contract.get('name')} | SCOPE: {contract.get('scope')} | POLICY: {policy_version}")
    out.append("")
    out.append("REQUIRED_INPUTS:")
    for item in spec.get("inputs", {}).get("required", []):
        out.append(f"- {item['name']}" + (f" [{item['format']}]" if item.get("format") else ""))
    out.append("OPTIONAL_INPUTS:")
    for item in spec.get("inputs", {}).get("optional", []):
        out.append(f"- {item['name']}" + (f" =default:{item['default']}" if item.get("default") else ""))
    auto = _auto_resolved(spec)
    if auto:
        out.append("AUTO_RESOLVED:")
        out.extend(f"- {name} = {value}" for name, value in auto)
    out.append("")
    out.append(f"RUN_ID: var={spec['run_id']['var']} format={facts['run_id_format']} "
               f"method={facts['run_id_method']} forbidden={','.join(facts['run_id_forbidden']) or 'none'}")
    out.append(f"SESSION_SETUP: init-run.py -> {PACKAGE_ROOT_REF}/... "
               f"manifest=draft base_files=[{facts['base_run_files']}] "
               f"artifacts=[{facts['artifacts_subdirs']}]")
    tiers = _tiers(spec)
    if tiers:
        out.append("RETRIEVAL_TIERS: " + "; ".join(f"{mode}={vals}" for mode, vals in tiers))
    ctx = list(facts["context_preamble"]) + [c for c in spec.get("context_load", []) if c not in facts["context_preamble"]]
    out.append(f"CONTEXT: {' -> '.join(ctx)}")
    out.append("")
    out.append("GATES:")
    for gate in spec.get("gates", []):
        out.append(f"- {gate['id']} role={gate.get('role')} "
                   f"artifacts=[{', '.join(gate.get('artifacts', []))}]")
        out.extend(_op_lines(gate))
        for c in gate.get("constraints", []) or []:
            out.append(f"    - FORBID {c['forbid']} :: {c['reason']}")
    out.append("")
    out.append(f"SEVERITY_GATE: profile={spec.get('severity_gate', 'none')} "
               f"tool=gate_policy.py coverage_min_pct={facts['coverage_min_pct']}")
    ownership = _ownership(spec)
    if ownership:
        out.append("OWNERSHIP:")
        out.extend(f"- {role}: {', '.join(items)}" for role, items in ownership)
    out.append("FORBIDDEN:")
    out.extend(f"- {f}" for f in spec.get("forbidden", []))
    out.append("STOP_CONDITIONS:")
    out.extend(f"- {s}" for s in spec.get("stop_conditions", []))
    if spec.get("conflict_resolution"):
        out.append("CONFLICT_RESOLUTION:")
        out.extend(f"- {c}" for c in spec["conflict_resolution"])
    for name, text in sorted((spec.get("notes", {}) or {}).items()):
        out.append(f"NOTE[{name}]: {text.strip()}")
    return "\n".join(out).rstrip() + "\n"


RENDERERS = {"operator-friendly": render_operator, "automation-safe": render_automation}


def variants_for(spec: dict[str, Any]) -> list[str]:
    declared = spec.get("variants")
    return list(declared) if declared else list(ALL_VARIANTS)


def _semantic_check(text: str, spec: dict[str, Any], shared: dict[str, Any]) -> None:
    if PACKAGE_ROOT_REF not in text:
        raise RenderError("missing_package_reference",
                          f"generated prompt for {spec['action']} omits the evidence package reference")
    method = _run_id_method(shared)
    for token in shared.get("run_id_forbidden", []):
        if token in method:
            raise RenderError("forbidden_run_id_scheme",
                              f"run-id method uses forbidden scheme {token!r}")
    known = vas._known_placeholders(spec) | {"start_tier", "stage"}
    for name in PLACEHOLDER_RE.findall(text):
        if name not in known:
            raise RenderError("unresolved_placeholder", f"unresolved placeholder {{{name}}}")


def render_action(spec: dict[str, Any], shared: dict[str, Any], policy_version: str) -> dict[str, str]:
    scope = spec.get("contract", {}).get("scope")
    if scope not in KNOWN_SCOPES:
        raise RenderError("unknown_scope", f"action {spec.get('action')} has unknown scope {scope!r}")
    outputs = {}
    for variant in variants_for(spec):
        renderer = RENDERERS.get(variant)
        if renderer is None:
            raise RenderError("missing_template_branch", f"no renderer for variant {variant!r}")
        text = renderer(spec, shared, policy_version)
        _semantic_check(text, spec, shared)
        outputs[variant] = text
    return outputs


def _target(action: str, variant: str) -> Path:
    return GENERATED_DIR / f"{action}-{variant}.md"


def _rel(path: Path) -> str:
    try:
        return path.relative_to(FRAMEWORK_ROOT).as_posix()
    except ValueError:
        return str(path)


# --------------------------------------------------------------------------- #
# Generate / check
# --------------------------------------------------------------------------- #
def _load(spec_dir: Path, action: str | None):
    policy = vas.load_policy(spec_dir, vas.Result())
    if policy.contract is None:
        raise RenderError("policy_load_failed", "could not load active contract")
    shared = policy.contract.get("shared", {})
    version = str(policy.contract.get("active_version"))
    actions = {action: policy.actions[action]} if action else dict(policy.actions)
    if action and action not in policy.actions:
        raise RenderError("unknown_action", f"no action spec named {action!r}")
    return actions, shared, version


def generate(spec_dir: Path, action: str | None = None, write: bool = True) -> dict[str, Any]:
    actions, shared, version = _load(spec_dir, action)
    written = []
    for name, spec in sorted(actions.items()):
        outputs = render_action(spec, shared, version)
        for variant, text in outputs.items():
            path = _target(name, variant)
            if write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            written.append(_rel(path))
    return {"ok": True, "policy_version": version, "generated": sorted(written)}


def check(spec_dir: Path, action: str | None = None) -> dict[str, Any]:
    actions, shared, version = _load(spec_dir, action)
    drifts, missing = [], []
    expected_files = set()
    for name, spec in sorted(actions.items()):
        outputs = render_action(spec, shared, version)
        for variant, text in outputs.items():
            path = _target(name, variant)
            expected_files.add(path)
            if not path.exists():
                missing.append(_rel(path))
                continue
            committed = path.read_text(encoding="utf-8")
            if committed != text:
                diff = "".join(difflib.unified_diff(
                    committed.splitlines(keepends=True), text.splitlines(keepends=True),
                    fromfile=f"committed/{path.name}", tofile=f"regenerated/{path.name}"))
                drifts.append({"file": _rel(path), "diff": diff[:2000]})
    # Undeclared extra files under generated/ for these actions (e.g. operator-only leaking a variant).
    # An undeclared variant file for an action that declares a subset (e.g. an operator-only
    # action leaking an automation-safe file). Only the exact variant filenames are considered,
    # so a different action whose name shares a prefix (feature vs feature-review) is not matched.
    extra = []
    for name in actions:
        for variant in ALL_VARIANTS:
            candidate = _target(name, variant)
            if candidate.exists() and candidate not in expected_files:
                extra.append(_rel(candidate))
    ok = not (drifts or missing or extra)
    return {"ok": ok, "policy_version": version, "drift": drifts,
            "missing": sorted(missing), "undeclared_extra": sorted(extra)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec-dir", type=Path, default=vas.DEFAULT_SPEC_DIR)
    parser.add_argument("--action", default=None)
    parser.add_argument("--check", action="store_true", help="Fail on drift; do not write.")
    args = parser.parse_args(argv)

    try:
        if args.check:
            report = check(args.spec_dir, args.action)
            import json
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0 if report["ok"] else 1
        report = generate(args.spec_dir, args.action)
        import json
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except RenderError as exc:
        import json
        print(json.dumps({"ok": False, "error": exc.message, "code": exc.code}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Contract audit for the compiled-projection framework (F0006-S0009).

Two parts:

1. Ownership invariant (HARD): no authoring role in agent-map.yaml writes a generated
   knowledge-graph projection (canonical-nodes / feature-mappings / code-index / solution-ontology).
   Those are compile.py outputs — only the integrator (mainline, regenerated) may list them, plus the
   coverage-report.yaml regeneration.

2. Stale-behavior sweep (advisory): lists occurrences, in the authoring-flow surfaces, of language that
   describes the pre-compiled-projection world — so the contract never tells a strict agent to
   hand-edit a generated file, do an off-book repoint, or author a physical feature-doc ref in a shard.

Exit non-zero if the ownership invariant is violated. Re-runnable; the sweep output is reviewed at
signoff and stored with the story evidence.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_MAP = ROOT / "agents" / "agent-map.yaml"

GENERATED_PROJECTIONS = (
    "canonical-nodes.yaml", "feature-mappings.yaml", "code-index.yaml", "solution-ontology.yaml",
)

# Authoring-flow surfaces whose prose a strict agent obeys literally.
SWEEP_FILES = [
    "agents/actions/feature.md", "agents/actions/build.md", "agents/actions/plan.md",
    "agents/docs/KNOWLEDGE-GRAPH.md", "agents/docs/ORCHESTRATION-CONTRACT.md",
    "agents/templates/prompts/evidence-contract/feature-operator-friendly.md",
    "agents/templates/prompts/evidence-contract/feature-automation-safe.md",
    "agents/templates/prompts/evidence-contract/build-operator-friendly.md",
    "agents/templates/prompts/evidence-contract/build-automation-safe.md",
    "agents/templates/prompts/evidence-contract/plan-operator-friendly.md",
    "agents/templates/prompts/evidence-contract/plan-automation-safe.md",
    "agents/templates/kg-reconciliation-template.md",
    "agents/templates/feature-assembly-plan-template.md",
]

# Phrases that describe old behavior. Tight enough to avoid legitimate read-only mentions and the
# still-valid symbol/decision regeneration (`validate.py --regenerate-*` is unchanged — compile.py does
# not do symbol extraction). What IS stale is authoring/hand-editing the compiled trio + ontology.
STALE_PATTERNS = [
    (re.compile(r"(?i)hand[- ]?edit\w*\s+(?:the\s+)?(?:canonical-nodes|feature-mappings|code-index)"), "hand-edit of a generated projection"),
    (re.compile(r"(?i)(?:author|write|update|maintain|edit|add/update)\s+(?:the\s+)?canonical-nodes\.yaml"), "authoring the generated canonical-nodes.yaml (author kg-source/nodes/** instead)"),
    (re.compile(r"(?i)(?:author|write|update|maintain|add/update)\s+(?:the\s+)?code-index\.yaml"), "authoring the generated code-index.yaml (author kg-source/bindings/** instead)"),
    (re.compile(r"(?i)(?:author|write|update|maintain)\s+(?:the\s+)?feature-mappings\.yaml"), "authoring the generated feature-mappings.yaml (author kg-source/features/** instead)"),
    (re.compile(r"(?i)repoint\w*\s+.*(?:archive|feature folder|doc ref)"), "off-book archive repoint narrative (archive = one feature-shard path: edit + recompile)"),
]


def _parse_map():
    spec = importlib.util.spec_from_file_location("vam", ROOT / "agents" / "scripts" / "validate_agent_map.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.parse_map(AGENT_MAP.read_text(encoding="utf-8"))


def check_ownership() -> list[str]:
    errors = []
    agents = _parse_map().get("agents", {})
    for role, cfg in agents.items():
        if role == "integrator":
            continue
        for w in cfg.get("writes", []):
            w = str(w)
            if "knowledge-graph/" in w and any(g in w for g in GENERATED_PROJECTIONS):
                gen = next(g for g in GENERATED_PROJECTIONS if g in w)
                errors.append(f"agent-map.yaml: `{role}` writes generated projection {gen} — it is a "
                              f"compile.py output; author kg-source/** instead (F0006-S0009).")
    return errors


def sweep() -> list[tuple[str, int, str, str]]:
    hits = []
    for rel in SWEEP_FILES:
        p = ROOT / rel
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for pat, label in STALE_PATTERNS:
                if pat.search(line):
                    hits.append((rel, i, label, line.strip()[:120]))
    return hits


def main() -> int:
    errors = check_ownership()
    hits = sweep()

    print("── contract audit (F0006-S0009) ──")
    print(f"ownership invariant: {'OK' if not errors else f'{len(errors)} VIOLATION(S)'}")
    for e in errors:
        print(f"  error: {e}", file=sys.stderr)

    print(f"stale-behavior sweep over {len(SWEEP_FILES)} authoring surfaces: {len(hits)} match(es)")
    for rel, i, label, text in hits:
        print(f"  {rel}:{i}: [{label}] {text}")

    if errors:
        print(f"\naudit FAILED — ownership invariant violated ({len(errors)}).", file=sys.stderr)
        return 1
    if hits:
        print(f"\naudit: ownership clean; {len(hits)} stale-phrase match(es) to reconcile (see above).")
        return 1
    print("\naudit: contract clean — no authoring role writes a generated projection; no stale phrases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

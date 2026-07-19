#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ONTOLOGY_OWNERS = ["product-manager", "architect", "implementation_agents"]

HEADING_RE = re.compile(r"^##\s+(?P<name>.+)$", re.MULTILINE)
GATE_INLINE_RE = re.compile(r"`(G\d(?:\.\d+)?(?:\s+[^`]+)?)`")
GATE_BLOCK_RE = re.compile(r"^(G\d(?:\.\d+)?)\s+(.+?)(?:\s+—|$)", re.MULTILINE)
LIST_ITEM_RE = re.compile(r"^\s*(?:-|\d+\.)\s+(.*)$", re.MULTILINE)
PATH_RE = re.compile(r"(?:agents|planning-mds|scripts)/[A-Za-z0-9_./<>{}*:-]+")
COMMAND_RE = re.compile(r"(?:IF KG changed:\s+)?python3 [^\n`]+|Applicable backend/frontend/test commands for changed surfaces \(inside runtime containers; evidence paths recorded\)")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_section(text: str, name: str) -> str:
    match = next((m for m in HEADING_RE.finditer(text) if m.group("name") == name), None)
    if match is None:
        return ""
    start = match.end()
    next_match = next((m for m in HEADING_RE.finditer(text, start) if m.start() > start), None)
    end = next_match.start() if next_match else len(text)
    return text[start:end].strip()


def normalize_item(value: str) -> str:
    return value.strip().strip("`").strip()


def parse_list_items(section: str) -> list[str]:
    return [normalize_item(item) for item in LIST_ITEM_RE.findall(section)]


def parse_gates(text: str) -> dict[str, str]:
    gates: dict[str, str] = {}
    for match in GATE_INLINE_RE.finditer(text):
        gate = normalize_item(match.group(1))
        if gate.startswith("G"):
            gate_id, _, name = gate.partition(" ")
            gates[gate_id] = name.strip()
    for match in GATE_BLOCK_RE.finditer(text):
        gates[match.group(1)] = match.group(2).strip()
    return gates


def parse_paths(text: str) -> set[str]:
    paths = {match.group(0).rstrip(".,)") for match in PATH_RE.finditer(text)}
    # `agents/**` is used as a broad negative boundary marker ("not agents/**"),
    # not as a concrete required template path.
    return {path for path in paths if path != "agents/**"}


def parse_commands(text: str) -> list[str]:
    commands = []
    for match in COMMAND_RE.finditer(text):
        command = normalize_item(match.group(0))
        command = command.replace("IF KG changed: ", "")
        command = re.sub(r"\s+\(if stories changed\)$", "", command)
        commands.append(command)
    return sorted(dict.fromkeys(commands))


def normalize_words(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def gate_name_matches(expected: str, actual: str) -> bool:
    expected_norm = normalize_words(expected)
    actual_norm = normalize_words(actual)
    return expected_norm in actual_norm or actual_norm in expected_norm


def _strip_product_root(value: str) -> str:
    return value[len("{PRODUCT_ROOT}/") :] if value.startswith("{PRODUCT_ROOT}/") else value


def path_covered(path: str, template_text: str, template_paths: set[str]) -> bool:
    if path in template_paths:
        return True

    bare = _strip_product_root(path)
    prefixed = "{PRODUCT_ROOT}/" + bare

    if prefixed.startswith("{PRODUCT_ROOT}/planning-mds/knowledge-graph/"):
        stem = Path(bare).stem.replace(".schema", "")
        return (
            "{PRODUCT_ROOT}/planning-mds/knowledge-graph/" in template_text and stem in template_text
        ) or "{PRODUCT_ROOT}/scripts/kg/lookup.py" in template_text

    if prefixed == "{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/**":
        return "{FEATURE_PATH}/**" in template_text or "{PRODUCT_ROOT}/planning-mds/features/{F####-slug}" in template_text

    if prefixed == "{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/feature-assembly-plan.md":
        return "{FEATURE_PATH}/feature-assembly-plan.md" in template_text

    if prefixed == "{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md":
        return "BLUEPRINT" in template_text

    if bare.endswith("/REGISTRY.md"):
        return "REGISTRY" in template_text

    if bare.endswith("/ROADMAP.md"):
        return "ROADMAP" in template_text

    return bare in template_text or path in template_text


def parse_action_contract(path: Path) -> dict[str, Any]:
    text = read_text(path)
    sections = {
        name: extract_section(text, name)
        for name in (
            "Context Files",
            "On-Demand Paths",
            "Deliverables Contract",
            "Primary Spec",
            "Ownership Contract",
            "Forbidden",
            "Gate Contract",
            "Exit Validation",
        )
    }
    return {
        "gates": parse_gates(sections["Gate Contract"]),
        "commands": parse_commands(sections["Exit Validation"]),
        "paths": parse_paths(
            "\n".join(
                value for key, value in sections.items() if key not in {"Forbidden", "Gate Contract", "Ownership Contract"}
            )
        ),
        "ownership": parse_list_items(sections["Ownership Contract"]),
        "forbidden": parse_list_items(sections["Forbidden"]),
    }


def parse_template(path: Path) -> dict[str, Any]:
    text = read_text(path)
    return {
        "path": path,
        "text": text,
        "gates": parse_gates(text),
        "commands": parse_commands(text),
        "paths": parse_paths(text),
    }


def ontology_expectations(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return list(DEFAULT_ONTOLOGY_OWNERS)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ownership = data.get("ownership", {})
    expected = []
    for owner in ("product-manager", "architect"):
        if ownership.get(owner):
            expected.append(owner)
    if ownership.get("implementation_agents"):
        expected.append("implementation_agents")
    return expected


def validate_template(
    action_name: str,
    action_contract: dict[str, Any],
    template: dict[str, Any],
    ontology_owners: list[str],
) -> list[str]:
    errors: list[str] = []
    text = template["text"]

    missing_gates = []
    for gate_id, gate_name in action_contract["gates"].items():
        template_name = template["gates"].get(gate_id)
        if template_name is None or not gate_name_matches(gate_name, template_name):
            missing_gates.append(f"{gate_id} {gate_name}")
    if missing_gates:
        errors.append(f"{action_name}: missing gates in {template['path'].name}: {', '.join(missing_gates)}")

    missing_commands = [command for command in action_contract["commands"] if command not in template["commands"]]
    if missing_commands:
        errors.append(
            f"{action_name}: missing exit-validation commands in {template['path'].name}: {', '.join(missing_commands)}"
        )

    missing_paths = sorted(
        path
        for path in action_contract["paths"]
        if not path_covered(path, text, template["paths"])
    )
    if missing_paths:
        errors.append(f"{action_name}: missing paths in {template['path'].name}: {', '.join(missing_paths)}")

    missing_ownership = []
    if "product-manager owns" not in text:
        missing_ownership.append("product-manager owns")
    if "architect owns" not in text:
        missing_ownership.append("architect owns")
    if "other roles" not in text and "implementation" not in text:
        missing_ownership.append("implementation ownership boundary")
    if missing_ownership:
        errors.append(
            f"{action_name}: ownership drift in {template['path'].name}: {', '.join(missing_ownership)}"
        )

    missing_forbidden = []
    required_tokens = [
        "lookup/KG mappings as authoritative",
        "max_auto_tier",
        "workstate.py escalate",
    ]
    for token in required_tokens:
        if token not in text:
            missing_forbidden.append(token)
    if missing_forbidden:
        errors.append(
            f"{action_name}: forbidden drift in {template['path'].name}: {', '.join(missing_forbidden)}"
        )

    if "Editing code without prior `hint.py <path>`" in text and "`hint.py <path>`" not in text:
        errors.append(f"{action_name}: hint.py forbidden/required mismatch in {template['path'].name}")
    if "Editing shared semantics without prior `blast.py <node>`" in text and "`blast.py <node-id>`" not in text and "`blast.py <node>`" not in text:
        errors.append(f"{action_name}: blast.py forbidden/required mismatch in {template['path'].name}")
    if "Climbing past max_auto_tier without a workstate.py escalate event" in text and "workstate.py escalate" not in text:
        errors.append(f"{action_name}: escalate forbidden/required mismatch in {template['path'].name}")

    for owner in ontology_owners:
        if owner == "implementation_agents":
            if "other roles" not in text and "implementation" not in text:
                errors.append(f"{action_name}: template {template['path'].name} does not describe implementation agent ownership boundaries")
            continue
        if owner not in text:
            errors.append(f"{action_name}: template {template['path'].name} missing ontology owner reference '{owner}'")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate prompt templates against action contracts.")
    parser.add_argument("--plan-action", type=Path, default=FRAMEWORK_ROOT / "agents/actions/plan.md")
    parser.add_argument("--feature-action", type=Path, default=FRAMEWORK_ROOT / "agents/actions/feature.md")
    parser.add_argument("--templates-dir", type=Path, default=FRAMEWORK_ROOT / "agents/templates/prompts")
    parser.add_argument(
        "--ontology",
        type=Path,
        default=None,
        help=(
            "Optional path to solution-ontology.yaml. Defaults to the built-in "
            "framework owner list so this validator runs with no product repo."
        ),
    )
    args = parser.parse_args()

    templates_dir = args.templates_dir
    if not (templates_dir / "plan-automation-safe.md").exists():
        for candidate_name in ("retired", "evidence-contract"):
            candidate_dir = templates_dir / candidate_name
            if (candidate_dir / "plan-automation-safe.md").exists():
                templates_dir = candidate_dir
                break

    # F0007: the feature and plan prompt pairs are GENERATED from agents/actions/spec/*.yaml and
    # validated by the prompt_drift gate (render-prompts.py --check) + action_spec_schema, so the
    # legacy <action>.md<->prompt cross-check is fully retired (design §7 — the drift check subsumes
    # it). The dead cross-check helpers remain callable for any action re-added here before it is
    # cut over to generation. The report-template checks below (headings, canonical paths) stay.
    templates: dict[str, list[dict[str, Any]]] = {}
    action_contracts: dict[str, dict[str, Any]] = {}
    ontology_owners = ontology_expectations(args.ontology)

    errors: list[str] = []
    for action_name, action_contract in action_contracts.items():
        for template in templates[action_name]:
            errors.extend(validate_template(action_name, action_contract, template, ontology_owners))

    errors.extend(validate_evidence_template_alignment())

    print("Template validation")
    print("-" * 60)

    if errors:
        print("Errors:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("[PASS] prompt templates align with action contracts.")
    return 0


# --------------------------------------------------------------------------- #
# §24 evidence-template alignment rules (tpl_*)
# --------------------------------------------------------------------------- #


# Canonical evidence templates per §25.
EVIDENCE_TEMPLATES = [
    "feature-evidence-readme-template.md",
    "evidence-manifest-template.json",
    "feature-action-execution-template.md",
    "artifact-trace-template.md",
    "gate-decisions-template.md",
    "commands-log-template.md",
    "lifecycle-gates-log-template.md",
    "runtime-preflight-template.md",
    "self-review-template.md",
    "test-plan-template.md",
    "test-execution-report-template.md",
    "coverage-report-template.md",
    "deployability-check-template.md",
    "code-review-report-template.md",
    "security-review-template.md",
    "signoff-ledger-template.md",
    "pm-closeout-template.md",
    "pm-validation-report-template.md",
    "architect-validation-report-template.md",
    "implementation-validation-report-template.md",
]

# §8 / §10 / §14 canonical heading sets, keyed by template filename.
CANONICAL_HEADINGS: dict[str, list[str]] = {
    "feature-evidence-readme-template.md": ["Run Summary", "Status", "Evidence Index", "Validation Summary", "Open Follow-ups"],
    "artifact-trace-template.md": [
        "Artifacts Read",
        "Artifacts Created Or Updated",
        "Generated Evidence",
        "External Or Global Evidence References",
        "Omissions And Waivers",
    ],
    "self-review-template.md": ["Scope Review", "Acceptance Criteria Review", "Implementation Risks", "Validation Evidence"],
    "signoff-ledger-template.md": ["Required Role Matrix", "Current Signoff State", "Recommendation Acceptances", "Waivers And Omissions"],
    "pm-closeout-template.md": ["Final Story Status", "Archive Decision", "Deferred Follow-ups", "Recommendation Acceptances", "Tracker Updates", "Validator Results"],
    "pm-validation-report-template.md": ["Run Identity", "Validation Scope", "PM Findings", "Recommendations", "Result"],
    "architect-validation-report-template.md": ["Run Identity", "Validation Scope", "Architect Findings", "Recommendations", "Result"],
    "implementation-validation-report-template.md": ["Run Identity", "Validator Invocations", "Findings By Rule ID", "Recommendations", "Result"],
}

# §24 (c): action files that must reference the canonical evidence package.
# F0007: GENERATED evidence-contract prompts are covered by the prompt_drift gate
# (render-prompts.py --check) plus the generator's own missing_package_reference /
# forbidden_run_id_scheme semantic checks, so they are no longer asserted here.
ACTIONS_THAT_MUST_REFERENCE_PACKAGE = [
    ("agents/actions/feature.md", "planning-mds/operations/evidence/"),
    ("agents/actions/build.md", "planning-mds/operations/evidence/"),
]

# §24 (d): prompt templates that must not generate `uuid4`-based run IDs.
# F0007: the feature prompts are generated; the generator's forbidden_run_id_scheme
# check (over the run-id method in the policy) enforces this at the source, so the
# text grep is retired for them. Any non-generated prompt can be re-added here.
PROMPTS_FORBIDDEN_UUID4: list[str] = []

# §24 (e): per-gate template references inside action docs.
# F0007: feature.md is thinned — its gate->artifact mapping now lives in
# agents/actions/spec/feature.yaml (verified by action_spec_schema) and renders into
# the generated prompt (verified by prompt_drift), so it is no longer asserted here.
GATE_TEMPLATE_REFS: dict[str, list[str]] = {}


def validate_evidence_template_alignment() -> list[str]:
    errors: list[str] = []
    templates_dir = FRAMEWORK_ROOT / "agents" / "templates"

    # tpl_missing_template_file_fails
    for filename in EVIDENCE_TEMPLATES:
        if not (templates_dir / filename).exists():
            errors.append(f"tpl_missing_template_file_fails: {filename} is missing from agents/templates/")

    # tpl_missing_canonical_heading_fails — per §14 heading-match rule,
    # we tolerate a trailing parenthesised clause (e.g. "(when WITH RECOMMENDATIONS)").
    for filename, required_headings in CANONICAL_HEADINGS.items():
        path = templates_dir / filename
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        for heading in required_headings:
            heading_re = re.compile(
                rf"^##\s+{re.escape(heading)}(?:\s*\([^)]*\))?\s*$",
                re.MULTILINE | re.IGNORECASE,
            )
            if not heading_re.search(content):
                errors.append(f"tpl_missing_canonical_heading_fails: {filename} missing required heading '{heading}'")

    # tpl_action_missing_canonical_path_fails
    for rel_path, needle in ACTIONS_THAT_MUST_REFERENCE_PACKAGE:
        path = FRAMEWORK_ROOT / rel_path
        if not path.exists():
            errors.append(f"tpl_action_missing_canonical_path_fails: {rel_path} does not exist")
            continue
        content = path.read_text(encoding="utf-8")
        if needle not in content:
            errors.append(f"tpl_action_missing_canonical_path_fails: {rel_path} does not reference canonical path {needle!r}")

    # tpl_prompt_uses_uuid4_fails
    uuid_re = re.compile(r"uuid4", re.IGNORECASE)
    for rel_path in PROMPTS_FORBIDDEN_UUID4:
        path = FRAMEWORK_ROOT / rel_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if not uuid_re.search(line):
                continue
            normalized_line = line.casefold()
            if (
                "do not" in normalized_line
                or "don't" in normalized_line
                or "not use" in normalized_line
                or "non-contract format" in normalized_line
            ):
                continue
            errors.append(f"tpl_prompt_uses_uuid4_fails: {rel_path} contains uuid4 reference for run ID")
            break

    # tpl_gate_missing_template_ref_fails
    for rel_path, expected_refs in GATE_TEMPLATE_REFS.items():
        path = FRAMEWORK_ROOT / rel_path
        if not path.exists():
            errors.append(f"tpl_gate_missing_template_ref_fails: {rel_path} does not exist")
            continue
        content = path.read_text(encoding="utf-8")
        for ref in expected_refs:
            if ref not in content:
                errors.append(f"tpl_gate_missing_template_ref_fails: {rel_path} does not reference {ref}")

    return errors


if __name__ == "__main__":
    raise SystemExit(main())

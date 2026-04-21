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

    templates = {
        "plan": [
            parse_template(args.templates_dir / "plan-automation-safe.md"),
            parse_template(args.templates_dir / "plan-operator-friendly.md"),
        ],
        "feature": [
            parse_template(args.templates_dir / "feature-automation-safe.md"),
            parse_template(args.templates_dir / "feature-operator-friendly.md"),
        ],
    }
    action_contracts = {
        "plan": parse_action_contract(args.plan_action),
        "feature": parse_action_contract(args.feature_action),
    }
    ontology_owners = ontology_expectations(args.ontology)

    errors: list[str] = []
    for action_name, action_contract in action_contracts.items():
        for template in templates[action_name]:
            errors.extend(validate_template(action_name, action_contract, template, ontology_owners))

    print("Template validation")
    print("-" * 60)

    if errors:
        print("Errors:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("[PASS] prompt templates align with action contracts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

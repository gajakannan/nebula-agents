#!/usr/bin/env python3
"""
Run validation gates declared in lifecycle-stage.yaml.

Usage:
    python3 agents/scripts/run-lifecycle-gates.py
    python3 agents/scripts/run-lifecycle-gates.py --list
    python3 agents/scripts/run-lifecycle-gates.py --stage planning
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


DEFAULT_CONFIG_PATH = Path("lifecycle-stage.yaml")


def load_config(path: Path) -> Dict:
    if not path.exists():
        raise ValueError(
            "Config file not found: "
            f"{path}. Seed from agents/templates/lifecycle-stage-template.yaml"
        )

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError("Lifecycle config must be a YAML mapping")

    if "stages" not in data or not isinstance(data["stages"], dict):
        raise ValueError("Lifecycle config must define a 'stages' mapping")

    if "gates" not in data or not isinstance(data["gates"], dict):
        raise ValueError("Lifecycle config must define a 'gates' mapping")

    if "current_stage" not in data or not isinstance(data["current_stage"], str):
        raise ValueError("Lifecycle config must define string field 'current_stage'")

    return data


def validate_gate_definitions(config: Dict) -> None:
    gates = config["gates"]
    for gate_name, gate in gates.items():
        if not isinstance(gate, dict):
            raise ValueError(f"Gate '{gate_name}' must be a mapping")

        command = gate.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
            raise ValueError(
                f"Gate '{gate_name}' must define non-empty string list field 'command'"
            )


def resolve_stage(config: Dict, override_stage: str) -> Tuple[str, Dict]:
    stages = config["stages"]
    stage_name = override_stage or config["current_stage"]

    stage_config = stages.get(stage_name)
    if not isinstance(stage_config, dict):
        raise ValueError(f"Unknown lifecycle stage: {stage_name}")

    required_gates = stage_config.get("required_gates", [])
    if not isinstance(required_gates, list) or not all(isinstance(g, str) for g in required_gates):
        raise ValueError(
            f"Stage '{stage_name}' must define 'required_gates' as a list of gate names"
        )

    return stage_name, stage_config


def print_stage_matrix(config: Dict) -> None:
    print("Lifecycle stages and required gates:")
    print("-" * 60)
    for stage_name, stage in config["stages"].items():
        description = stage.get("description", "").strip()
        required = stage.get("required_gates", [])
        print(f"{stage_name}: {description}")
        for gate in required:
            print(f"  - {gate}")
        if not required:
            print("  - (none)")
    print("-" * 60)
    print(f"Current stage: {config['current_stage']}")


def run_gate(repo_root: Path, gate_name: str, gate_config: Dict) -> int:
    description = gate_config.get("description", "")
    command = gate_config["command"]

    print(f"[GATE] {gate_name}")
    if description:
        print(f"  {description}")
    print(f"  command: {' '.join(command)}")

    completed = subprocess.run(command, cwd=repo_root, check=False)
    if completed.returncode == 0:
        print(f"[PASS] {gate_name}\n")
    else:
        print(f"[FAIL] {gate_name} (exit code {completed.returncode})\n")
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lifecycle-stage gate commands")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to lifecycle-stage YAML config",
    )
    parser.add_argument(
        "--stage",
        default="",
        help="Optional stage override (otherwise uses current_stage from config)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print stage/gate matrix and exit",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    repo_root = Path(__file__).resolve().parents[2]

    try:
        config = load_config(config_path)
        validate_gate_definitions(config)
        stage_name, stage_config = resolve_stage(config, args.stage)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 2

    if args.list:
        print_stage_matrix(config)
        return 0

    required_gate_names: List[str] = stage_config.get("required_gates", [])
    gates = config["gates"]

    unknown_gates = [gate for gate in required_gate_names if gate not in gates]
    if unknown_gates:
        print(f"[ERROR] Stage '{stage_name}' references unknown gates: {', '.join(unknown_gates)}")
        return 2

    print(f"Running lifecycle gates for stage: {stage_name}")
    print("-" * 60)

    failures: List[str] = []
    for gate_name in required_gate_names:
        if run_gate(repo_root, gate_name, gates[gate_name]) != 0:
            failures.append(gate_name)

    print("=" * 60)
    if failures:
        print(f"[SUMMARY] FAILED ({len(failures)} gate(s)): {', '.join(failures)}")
        return 1

    print(f"[SUMMARY] PASSED ({len(required_gate_names)} gate(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())

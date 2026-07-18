#!/usr/bin/env python3
"""
Test Coverage Validation Script

Validates test coverage against a minimum threshold.
Supports lcov (.info) and Cobertura XML formats.

Usage:
    python validate-test-coverage.py <coverage-file> [--min 80]
    python validate-test-coverage.py --auto [--min 80]
    python validate-test-coverage.py --auto --product-root ../my-product

Auto-detect mode searches {PRODUCT_ROOT} for common coverage artifacts.
"""

import argparse
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402


def resolve_contract_value(key: str):
    """Resolve a shared policy value via contract-value.py (single source of truth)."""
    import importlib.util
    cv_path = Path(__file__).resolve().parents[2] / "scripts" / "contract-value.py"
    spec = importlib.util.spec_from_file_location("contract_value", cv_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.resolve(key)

LCOV_CANDIDATES = [
    "coverage/lcov.info",
    "coverage/lcov-report/lcov.info",
    "lcov.info",
]

COBERTURA_CANDIDATES = [
    "coverage.xml",
    "coverage/coverage.xml",
    "cobertura.xml",
]


def parse_lcov(path: Path) -> float:
    """Return line coverage percent from lcov file."""
    total = 0
    hit = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("LF:"):
            total += int(line.split(":", 1)[1].strip() or 0)
        elif line.startswith("LH:"):
            hit += int(line.split(":", 1)[1].strip() or 0)
    if total == 0:
        return 0.0
    return (hit / total) * 100.0


def parse_cobertura(path: Path) -> float:
    """Return line coverage percent from Cobertura XML file."""
    tree = ET.parse(path)
    root = tree.getroot()
    line_rate = root.attrib.get("line-rate")
    if line_rate is None:
        return 0.0
    return float(line_rate) * 100.0


def find_auto_file(search_root: Path) -> Optional[Path]:
    for candidate in LCOV_CANDIDATES + COBERTURA_CANDIDATES:
        path = search_root / candidate
        if path.exists():
            return path
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate test coverage.")
    add_product_root_arg(parser)
    parser.add_argument("coverage_file", nargs="?", help="Path to coverage file")
    parser.add_argument("--min", type=float, default=0.0, help="Minimum coverage percentage")
    parser.add_argument("--min-from-contract", action="store_true",
                        help="Resolve the minimum from the shared contract (coverage_min_pct) "
                             "instead of hardcoding it. Fails closed if it cannot be resolved.")
    parser.add_argument("--auto", action="store_true", help="Auto-detect coverage file under {PRODUCT_ROOT}")
    args = parser.parse_args()

    if args.min_from_contract:
        # F0007-S0008: consume the shared policy value rather than a private literal.
        try:
            args.min = float(resolve_contract_value("coverage_min_pct"))
        except Exception as exc:
            print(f"❌ Could not resolve coverage_min_pct from the shared contract: {exc}")
            return 2

    if args.auto:
        search_root = resolve_product_root(args.product_root)
        path = find_auto_file(search_root)
        if path is None:
            print(f"❌ No coverage file found (auto-detect under {search_root}).")
            return 1
    else:
        if not args.coverage_file:
            print("Usage: python validate-test-coverage.py <coverage-file> [--min 80]")
            print("   or: python validate-test-coverage.py --auto [--min 80]")
            return 1
        path = Path(args.coverage_file)
        if not path.exists():
            print(f"❌ Coverage file not found: {path}")
            return 1

    try:
        if path.suffix == ".info":
            coverage = parse_lcov(path)
        elif path.suffix in {".xml"}:
            coverage = parse_cobertura(path)
        else:
            print(f"❌ Unsupported coverage file format: {path.name}")
            return 1
    except Exception as exc:
        print(f"❌ Failed to parse coverage file: {exc}")
        return 1

    print(f"Coverage: {coverage:.2f}% (min {args.min:.2f}%)")
    if coverage < args.min:
        print("❌ Coverage below minimum threshold.")
        return 1

    print("✅ Coverage check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

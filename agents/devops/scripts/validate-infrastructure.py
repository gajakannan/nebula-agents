#!/usr/bin/env python3
"""
Infrastructure Validation Script

Lightweight checks for common infra artifacts (compose files, Dockerfiles, env examples).

Usage:
    python3 validate-infrastructure.py [root-path] [--strict]
    python3 validate-infrastructure.py --product-root ../my-product

If no root path is supplied, the script checks {PRODUCT_ROOT}.
"""

import argparse
from pathlib import Path
import sys
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402

COMPOSE_FILES = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]
DOCKERFILES = ["Dockerfile", "Dockerfile.dev", "Dockerfile.prod"]
CI_DIRS = [".github/workflows", ".gitlab", ".circleci"]
ENV_FILES = [".env.example", ".env.sample"]


def exists_any(root: Path, names: Iterable[str]) -> bool:
    return any((root / name).exists() for name in names)


def exists_any_dir(root: Path, names: Iterable[str]) -> bool:
    return any((root / name).is_dir() for name in names)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate infrastructure artifacts.")
    add_product_root_arg(parser)
    parser.add_argument("root", nargs="?", default=None, help="Root path to check (default: {PRODUCT_ROOT})")
    parser.add_argument("--strict", action="store_true", help="Fail if any item is missing")
    args = parser.parse_args()

    root = Path(args.root) if args.root else resolve_product_root(args.product_root)
    if not root.exists():
        print(f"❌ Root path not found: {root}")
        return 1

    missing = []

    if not exists_any(root, COMPOSE_FILES):
        missing.append("docker-compose.yml / compose.yml")
    if not exists_any(root, DOCKERFILES):
        missing.append("Dockerfile")
    if not exists_any_dir(root, CI_DIRS):
        missing.append("CI configuration directory")
    if not exists_any(root, ENV_FILES):
        missing.append(".env.example or .env.sample")

    if missing:
        print("⚠️  Missing infrastructure items:")
        for item in missing:
            print(f"  - {item}")
        return 1 if args.strict else 0

    print("✅ Infrastructure artifacts look present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

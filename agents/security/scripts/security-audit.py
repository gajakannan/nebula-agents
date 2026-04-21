#!/usr/bin/env python3
"""
Security artifact audit checks.

Light mode validates required planning files exist and are not effectively empty.
Strict mode additionally enforces non-draft status, minimum section/content depth,
and at least one dated security review output.

Usage:
    python3 security-audit.py [path-to-planning-security-dir]
    python3 security-audit.py {PRODUCT_ROOT}/planning-mds/security --strict
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402

REQUIRED_FILES = [
    "threat-model.md",
    "authorization-review.md",
    "data-protection.md",
    "secrets-management.md",
    "owasp-top-10-results.md",
]

MIN_STRICT_NON_EMPTY_LINES = 10
MIN_STRICT_SECTION_COUNT = 3
DRAFT_STATUSES = {"draft", "placeholder", "tbd", "todo"}
REVIEW_FILE_PATTERN = re.compile(r"^security-review-\d{4}-\d{2}-\d{2}\.md$")


def is_effectively_empty(path: Path) -> bool:
    content = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not content:
        return True
    # Consider a single heading as empty
    lines = [line for line in content.splitlines() if line.strip()]
    return len(lines) <= 1


def extract_status(content: str) -> Optional[str]:
    match = re.search(r"^\s*Status:\s*(.+?)\s*$", content, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def non_empty_line_count(content: str) -> int:
    return len([line for line in content.splitlines() if line.strip()])


def section_count(content: str) -> int:
    return len([line for line in content.splitlines() if line.strip().startswith("## ")])


def validate_dated_review_outputs(reviews_dir: Path) -> List[str]:
    errors: List[str] = []
    if not reviews_dir.is_dir():
        return [f"Security reviews directory not found: {reviews_dir}"]

    candidate_files = [
        path for path in reviews_dir.iterdir() if path.is_file() and REVIEW_FILE_PATTERN.match(path.name)
    ]
    if not candidate_files:
        return [
            "No dated security review output found in "
            f"{reviews_dir} (expected files like security-review-YYYY-MM-DD.md)"
        ]

    has_usable_review = False
    for review_file in sorted(candidate_files):
        content = review_file.read_text(encoding="utf-8", errors="ignore")
        if non_empty_line_count(content) < 5:
            continue
        if re.search(r"^\s*Date:\s*\d{4}-\d{2}-\d{2}\s*$", content, flags=re.MULTILINE):
            has_usable_review = True
            break

    if not has_usable_review:
        errors.append(
            "Dated security review files exist but none contain minimum content "
            "and a Date: YYYY-MM-DD header"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit security planning artifacts")
    add_product_root_arg(parser)
    parser.add_argument(
        "base",
        nargs="?",
        default=None,
        help="Path to security planning directory (default: {PRODUCT_ROOT}/planning-mds/security)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on draft statuses and enforce deeper content/review evidence checks",
    )
    args = parser.parse_args()

    if args.base:
        base = Path(args.base)
    else:
        product_root = resolve_product_root(args.product_root)
        base = product_root / "planning-mds" / "security"
    if not base.exists():
        print(f"❌ Security directory not found: {base}")
        return 1

    errors = []
    warnings = []

    for name in REQUIRED_FILES:
        path = base / name
        if not path.exists():
            errors.append(f"Missing security artifact: {path}")
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if is_effectively_empty(path):
            message = f"Security artifact looks empty: {path}"
            if args.strict:
                errors.append(message)
            else:
                warnings.append(message)
            continue

        if args.strict:
            status = extract_status(content)
            if not status:
                errors.append(f"Missing 'Status:' line in strict mode: {path}")
            elif status.lower() in DRAFT_STATUSES:
                errors.append(f"Security artifact is not finalized (Status: {status}): {path}")

            if section_count(content) < MIN_STRICT_SECTION_COUNT:
                errors.append(
                    f"Security artifact missing minimum section depth (need >= {MIN_STRICT_SECTION_COUNT} '##' sections): {path}"
                )

            if non_empty_line_count(content) < MIN_STRICT_NON_EMPTY_LINES:
                errors.append(
                    f"Security artifact missing minimum content depth (need >= {MIN_STRICT_NON_EMPTY_LINES} non-empty lines): {path}"
                )

    if args.strict:
        errors.extend(validate_dated_review_outputs(base / "reviews"))

    if errors:
        print("❌ SECURITY ARTIFACT ERRORS:")
        for item in errors:
            print(f"  - {item}")

    if warnings:
        print("⚠️  SECURITY ARTIFACT WARNINGS:")
        for item in warnings:
            print(f"  - {item}")

    if not errors and not warnings:
        print("✅ Security artifacts present and non-empty.")
        return 0

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

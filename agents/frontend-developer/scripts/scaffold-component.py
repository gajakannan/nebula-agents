#!/usr/bin/env python3
"""
Scaffold a React component with TypeScript templates.

Usage:
    python scaffold-component.py CustomerCard --type shared --with-tests
    python scaffold-component.py StatusBadge --type ui --with-styles --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402


COMPONENT_TYPES = ("ui", "forms", "layouts", "shared")
PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")


@dataclass
class WriteResult:
    created: List[Path]
    updated: List[Path]


def to_pascal_case(raw: str) -> str:
    """Convert arbitrary input to PascalCase."""
    chunks = re.findall(r"[A-Za-z0-9]+", raw)
    if not chunks:
        return ""
    return "".join(chunk[:1].upper() + chunk[1:] for chunk in chunks)


def to_kebab_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1-\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s1)
    return s2.lower()


def ensure_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def write_file(
    path: Path,
    content: str,
    force: bool,
    dry_run: bool,
    result: WriteResult,
) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"File already exists: {path}")

    if dry_run:
        if path.exists():
            result.updated.append(path)
        else:
            result.created.append(path)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.write_text(content, encoding="utf-8")
        result.updated.append(path)
    else:
        path.write_text(content, encoding="utf-8")
        result.created.append(path)


def update_barrel(
    barrel_path: Path,
    export_line: str,
    dry_run: bool,
    result: WriteResult,
) -> None:
    if barrel_path.exists():
        lines = barrel_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    if export_line in lines:
        return

    lines.append(export_line)
    lines = sorted(line for line in lines if line.strip())
    content = "\n".join(lines) + "\n"

    if dry_run:
        if barrel_path.exists():
            result.updated.append(barrel_path)
        else:
            result.created.append(barrel_path)
        return

    barrel_path.parent.mkdir(parents=True, exist_ok=True)
    barrel_path.write_text(content, encoding="utf-8")
    if barrel_path.exists():
        # write_text creates when missing and updates when existing; the lists are informational.
        if barrel_path in result.created or barrel_path in result.updated:
            return
    if content:
        if barrel_path.exists():
            result.updated.append(barrel_path)


def build_types_content(component_name: str) -> str:
    return (
        'import type { ReactNode } from "react";\n'
        "\n"
        f"export interface {component_name}Props {{\n"
        "  className?: string;\n"
        "  children?: ReactNode;\n"
        "}\n"
    )


def build_component_content(
    component_name: str,
    test_id: str,
    with_styles: bool,
) -> str:
    lines = [
        f'import type {{ {component_name}Props }} from "./{component_name}.types";',
    ]
    if with_styles:
        lines.append(f'import styles from "./{component_name}.module.css";')
    lines.extend(
        [
            "",
            f"export function {component_name}({{ className, children }}: {component_name}Props) {{",
        ]
    )
    if with_styles:
        lines.extend(
            [
                "  const classes = className ? `${styles.root} ${className}` : styles.root;",
                "",
                "  return (",
                f'    <section className={{classes}} data-testid="{test_id}">',
                f"      {{children ?? \"{component_name}\"}}",
                "    </section>",
                "  );",
                "}",
            ]
        )
    else:
        lines.extend(
            [
                "  return (",
                f'    <section className={{className}} data-testid="{test_id}">',
                f"      {{children ?? \"{component_name}\"}}",
                "    </section>",
                "  );",
                "}",
            ]
        )
    return "\n".join(lines) + "\n"


def build_styles_content() -> str:
    return (
        ".root {\n"
        "  display: block;\n"
        "}\n"
    )


def build_test_content(component_name: str, test_id: str) -> str:
    return (
        'import { render, screen } from "@testing-library/react";\n'
        'import { describe, expect, it } from "vitest";\n'
        f'import {{ {component_name} }} from "./{component_name}";\n'
        "\n"
        f'describe("{component_name}", () => {{\n'
        "  it(\"renders a component root\", () => {\n"
        f"    render(<{component_name} />);\n"
        f'    expect(screen.getByTestId("{test_id}")).toBeTruthy();\n'
        "  });\n"
        "});\n"
    )


def build_index_content(component_name: str) -> str:
    return (
        f'export {{ {component_name} }} from "./{component_name}";\n'
        f'export type {{ {component_name}Props }} from "./{component_name}.types";\n'
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scaffold a React component with TypeScript templates."
    )
    add_product_root_arg(parser)
    parser.add_argument("name", help="Component name (e.g., CustomerCard)")
    parser.add_argument(
        "--type",
        choices=COMPONENT_TYPES,
        default="shared",
        help="Component category under src/components (default: shared)",
    )
    parser.add_argument(
        "--components-dir",
        default=None,
        help="Base components directory (default: {PRODUCT_ROOT}/experience/src/components)",
    )
    parser.add_argument(
        "--subdir",
        default="",
        help="Optional subdirectory under the selected type (e.g., customer/cards)",
    )
    parser.add_argument(
        "--with-tests",
        action="store_true",
        help="Generate a Vitest/RTL test file",
    )
    parser.add_argument(
        "--with-styles",
        action="store_true",
        help="Generate a CSS module and wire it to the component",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite files if they already exist",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned file changes without writing files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    normalized = to_pascal_case(args.name.strip())
    if not normalized or not PASCAL_RE.match(normalized):
        print(
            "ERROR: component name must resolve to PascalCase and start with a letter.",
            file=sys.stderr,
        )
        return 1

    component_name = normalized
    test_id = to_kebab_case(component_name)

    if args.components_dir:
        components_dir = Path(args.components_dir)
    else:
        product_root = resolve_product_root(args.product_root)
        components_dir = product_root / "experience" / "src" / "components"
    type_dir = components_dir / args.type
    if args.subdir:
        type_dir = type_dir / args.subdir.strip().strip("/")
    component_dir = type_dir / component_name

    result = WriteResult(created=[], updated=[])

    try:
        ensure_dir(component_dir, args.dry_run)
        write_file(
            component_dir / f"{component_name}.types.ts",
            build_types_content(component_name),
            force=args.force,
            dry_run=args.dry_run,
            result=result,
        )
        write_file(
            component_dir / f"{component_name}.tsx",
            build_component_content(component_name, test_id, args.with_styles),
            force=args.force,
            dry_run=args.dry_run,
            result=result,
        )
        if args.with_styles:
            write_file(
                component_dir / f"{component_name}.module.css",
                build_styles_content(),
                force=args.force,
                dry_run=args.dry_run,
                result=result,
            )
        if args.with_tests:
            write_file(
                component_dir / f"{component_name}.test.tsx",
                build_test_content(component_name, test_id),
                force=args.force,
                dry_run=args.dry_run,
                result=result,
            )
        write_file(
            component_dir / "index.ts",
            build_index_content(component_name),
            force=args.force,
            dry_run=args.dry_run,
            result=result,
        )

        # Update type-level barrel export: src/components/<type>[/subdir]/index.ts
        relative_path = Path(component_name)
        export_line = f"export * from './{relative_path.as_posix()}';"
        update_barrel(type_dir / "index.ts", export_line, args.dry_run, result)
    except FileExistsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Tip: re-run with --force to overwrite existing files.", file=sys.stderr)
        return 1

    if args.dry_run:
        print("Dry run: no files written.")

    print(f"Scaffolded component: {component_name}")
    for path in result.created:
        print(f"  created: {path}")
    for path in result.updated:
        print(f"  updated: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

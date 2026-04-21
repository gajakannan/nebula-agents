#!/usr/bin/env python3
"""
Scaffold a React page module with optional route metadata.

Usage:
    python scaffold-page.py CustomerDetails --route /customers/:id --with-tests
    python scaffold-page.py Orders --route /orders --routes-file {PRODUCT_ROOT}/experience/src/routes/index.tsx
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


PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
ROUTE_IMPORTS_START = "// <scaffold-route-imports>"
ROUTE_IMPORTS_END = "// </scaffold-route-imports>"
ROUTES_START = "// <scaffold-routes>"
ROUTES_END = "// </scaffold-routes>"


@dataclass
class WriteResult:
    created: List[Path]
    updated: List[Path]


def to_pascal_case(raw: str) -> str:
    chunks = re.findall(r"[A-Za-z0-9]+", raw)
    if not chunks:
        return ""
    return "".join(chunk[:1].upper() + chunk[1:] for chunk in chunks)


def to_kebab_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1-\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s1)
    return s2.lower()


def to_camel_case(name: str) -> str:
    if not name:
        return name
    return name[:1].lower() + name[1:]


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
    result.updated.append(barrel_path)


def build_page_types_content(page_component_name: str) -> str:
    return (
        f"export interface {page_component_name}Props {{\n"
        "  className?: string;\n"
        "}\n"
    )


def build_page_component_content(
    page_component_name: str,
    page_title: str,
    test_id: str,
) -> str:
    return (
        f'import type {{ {page_component_name}Props }} from "./{page_component_name}.types";\n'
        "\n"
        f"export function {page_component_name}({{ className }}: {page_component_name}Props) {{\n"
        "  return (\n"
        f'    <main className={{className}} data-testid="{test_id}">\n'
        f"      <h1>{page_title}</h1>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def build_page_test_content(page_component_name: str, test_id: str) -> str:
    return (
        'import { render, screen } from "@testing-library/react";\n'
        'import { describe, expect, it } from "vitest";\n'
        f'import {{ {page_component_name} }} from "./{page_component_name}";\n'
        "\n"
        f'describe("{page_component_name}", () => {{\n'
        "  it(\"renders a page root\", () => {\n"
        f"    render(<{page_component_name} />);\n"
        f'    expect(screen.getByTestId("{test_id}")).toBeTruthy();\n'
        "  });\n"
        "});\n"
    )


def build_route_content(page_component_name: str, route_path: str, route_const: str) -> str:
    return (
        'import type { RouteObject } from "react-router-dom";\n'
        f'import {{ {page_component_name} }} from "./{page_component_name}";\n'
        "\n"
        f"export const {route_const}: RouteObject = {{\n"
        f'  path: "{route_path}",\n'
        f"  element: <{page_component_name} />,\n"
        "};\n"
    )


def build_index_content(page_component_name: str, include_route: bool, route_const: str) -> str:
    lines = [
        f'export {{ {page_component_name} }} from "./{page_component_name}";',
        f'export type {{ {page_component_name}Props }} from "./{page_component_name}.types";',
    ]
    if include_route:
        lines.append(f'export {{ {route_const} }} from "./{page_component_name}.route";')
    return "\n".join(lines) + "\n"


def update_routes_file(
    routes_file: Path,
    page_name: str,
    page_component_name: str,
    route_const: str,
    route_path: str,
    dry_run: bool,
    result: WriteResult,
) -> None:
    if not routes_file.exists():
        raise FileNotFoundError(f"Routes file not found: {routes_file}")

    content = routes_file.read_text(encoding="utf-8")
    for marker in (ROUTE_IMPORTS_START, ROUTE_IMPORTS_END, ROUTES_START, ROUTES_END):
        if marker not in content:
            raise ValueError(
                f"Routes file is missing marker '{marker}'. "
                "Add scaffold markers before using --routes-file."
            )

    import_line = (
        f'import {{ {route_const} }} from "@/pages/{page_name}/{page_component_name}.route";'
    )
    route_line = f"  {route_const},"

    updated = content
    if import_line not in updated:
        updated = updated.replace(
            ROUTE_IMPORTS_END,
            f"{import_line}\n{ROUTE_IMPORTS_END}",
        )
    if route_line not in updated:
        updated = updated.replace(
            ROUTES_END,
            f"{route_line}\n{ROUTES_END}",
        )

    if updated == content:
        return

    if dry_run:
        result.updated.append(routes_file)
        return

    routes_file.write_text(updated, encoding="utf-8")
    result.updated.append(routes_file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scaffold a React page module with optional route metadata."
    )
    add_product_root_arg(parser)
    parser.add_argument("name", help="Page name (e.g., CustomerDetails)")
    parser.add_argument(
        "--pages-dir",
        default=None,
        help="Pages directory (default: {PRODUCT_ROOT}/experience/src/pages)",
    )
    parser.add_argument(
        "--route",
        help='Route path (e.g., "/customers/:id"). Generates a .route.tsx file.',
    )
    parser.add_argument(
        "--routes-file",
        help=(
            "Optional route registry file to patch. Requires scaffold markers:\n"
            "  // <scaffold-route-imports>\n"
            "  // </scaffold-route-imports>\n"
            "  // <scaffold-routes>\n"
            "  // </scaffold-routes>"
        ),
    )
    parser.add_argument(
        "--with-tests",
        action="store_true",
        help="Generate a page test file",
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
            "ERROR: page name must resolve to PascalCase and start with a letter.",
            file=sys.stderr,
        )
        return 1

    page_name = normalized[:-4] if normalized.endswith("Page") else normalized
    page_component_name = f"{page_name}Page"
    route_const = f"{to_camel_case(page_name)}Route"
    test_id = f"{to_kebab_case(page_name)}-page"
    page_title = " ".join(re.findall(r"[A-Z][a-z0-9]*", page_name)) or page_name

    if args.pages_dir:
        pages_dir = Path(args.pages_dir)
    else:
        product_root = resolve_product_root(args.product_root)
        pages_dir = product_root / "experience" / "src" / "pages"
    page_dir = pages_dir / page_name

    result = WriteResult(created=[], updated=[])

    try:
        ensure_dir(page_dir, args.dry_run)
        write_file(
            page_dir / f"{page_component_name}.types.ts",
            build_page_types_content(page_component_name),
            force=args.force,
            dry_run=args.dry_run,
            result=result,
        )
        write_file(
            page_dir / f"{page_component_name}.tsx",
            build_page_component_content(page_component_name, page_title, test_id),
            force=args.force,
            dry_run=args.dry_run,
            result=result,
        )

        if args.route:
            write_file(
                page_dir / f"{page_component_name}.route.tsx",
                build_route_content(page_component_name, args.route, route_const),
                force=args.force,
                dry_run=args.dry_run,
                result=result,
            )

        if args.with_tests:
            write_file(
                page_dir / f"{page_component_name}.test.tsx",
                build_page_test_content(page_component_name, test_id),
                force=args.force,
                dry_run=args.dry_run,
                result=result,
            )

        write_file(
            page_dir / "index.ts",
            build_index_content(page_component_name, bool(args.route), route_const),
            force=args.force,
            dry_run=args.dry_run,
            result=result,
        )

        update_barrel(
            pages_dir / "index.ts",
            f"export * from './{page_name}';",
            args.dry_run,
            result,
        )

        if args.route and args.routes_file:
            update_routes_file(
                routes_file=Path(args.routes_file),
                page_name=page_name,
                page_component_name=page_component_name,
                route_const=route_const,
                route_path=args.route,
                dry_run=args.dry_run,
                result=result,
            )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if isinstance(exc, FileExistsError):
            print("Tip: re-run with --force to overwrite existing files.", file=sys.stderr)
        return 1

    if args.dry_run:
        print("Dry run: no files written.")

    print(f"Scaffolded page: {page_component_name}")
    if args.route:
        print(f"Route metadata: {route_const} -> {args.route}")
    for path in result.created:
        print(f"  created: {path}")
    for path in result.updated:
        print(f"  updated: {path}")

    if args.route and not args.routes_file:
        print("")
        print("Route registration tip:")
        print(f"  Import:  {route_const} from '@/pages/{page_name}/{page_component_name}.route'")
        print(f"  Add to route array: {route_const}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

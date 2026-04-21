#!/usr/bin/env python3
"""
Code Quality Check Script

Lightweight, language-agnostic checks:
- TODO/FIXME counts
- Max line length
- Large files

Usage:
    python check-code-quality.py [path] [--max-line 120] [--max-file-kb 500] [--todo-limit 0]
    python check-code-quality.py --product-root ../my-product

If no path is supplied the script scans {PRODUCT_ROOT}.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402

EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "out",
    "bin",
    "obj",
    ".venv",
    "venv",
}

INCLUDE_EXTS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".cs",
    ".java",
    ".go",
    ".rb",
    ".php",
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".sh",
}


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        if path.suffix in INCLUDE_EXTS:
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight code quality checks.")
    add_product_root_arg(parser)
    parser.add_argument("path", nargs="?", default=None, help="Root path to scan (default: {PRODUCT_ROOT})")
    parser.add_argument("--max-line", type=int, default=120, help="Maximum line length")
    parser.add_argument("--max-file-kb", type=int, default=500, help="Max file size in KB")
    parser.add_argument("--todo-limit", type=int, default=0, help="Allowed TODO/FIXME count")
    args = parser.parse_args()

    root = Path(args.path) if args.path else resolve_product_root(args.product_root)
    if not root.exists():
        print(f"❌ Path not found: {root}")
        return 1

    todo_count = 0
    long_lines = []
    large_files = []

    for file_path in iter_files(root):
        try:
            size_kb = file_path.stat().st_size / 1024
            if size_kb > args.max_file_kb:
                large_files.append((file_path, size_kb))

            content = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            for i, line in enumerate(content, 1):
                if len(line) > args.max_line:
                    long_lines.append((file_path, i, len(line)))
                if "TODO" in line or "FIXME" in line:
                    todo_count += 1
        except Exception:
            continue

    failed = False

    if todo_count > args.todo_limit:
        print(f"❌ TODO/FIXME count exceeded: {todo_count} (limit {args.todo_limit})")
        failed = True
    else:
        print(f"✅ TODO/FIXME count: {todo_count} (limit {args.todo_limit})")

    if long_lines:
        print(f"⚠️  Long lines (> {args.max_line}): {len(long_lines)}")
        for item in long_lines[:20]:
            print(f"  {item[0]}:{item[1]} ({item[2]} chars)")
    else:
        print(f"✅ No lines exceed {args.max_line} chars")

    if large_files:
        print(f"⚠️  Large files (> {args.max_file_kb} KB): {len(large_files)}")
        for item in large_files[:10]:
            print(f"  {item[0]} ({item[1]:.1f} KB)")
    else:
        print(f"✅ No files exceed {args.max_file_kb} KB")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

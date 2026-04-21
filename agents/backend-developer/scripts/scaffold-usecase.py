#!/usr/bin/env python3
"""
Scaffold an application use case (command/query).

Usage:
    python scaffold-usecase.py CreateCustomer --application-dir src/App.Application --namespace App.Application
    python scaffold-usecase.py GetCustomer --type query --application-dir src/App.Application --namespace App.Application
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"File already exists: {path}")
    path.write_text(content, encoding="utf-8")


def build_request_content(name: str, namespace: str) -> str:
    return "\n".join(
        [
            f"namespace {namespace};",
            "",
            f"public record {name}Request();",
            "",
        ]
    )


def build_result_content(name: str, namespace: str) -> str:
    return "\n".join(
        [
            f"namespace {namespace};",
            "",
            f"public record {name}Result();",
            "",
        ]
    )


def build_handler_content(name: str, namespace: str) -> str:
    return "\n".join(
        [
            "using System;",
            "using System.Threading;",
            "using System.Threading.Tasks;",
            "",
            f"namespace {namespace};",
            "",
            f"public class {name}Handler",
            "{",
            f"    public Task<{name}Result> Handle({name}Request request, CancellationToken cancellationToken)",
            "    {",
            "        throw new NotImplementedException();",
            "    }",
            "}",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold an application use case.")
    parser.add_argument("name", help="Use case name (e.g., CreateCustomer)")
    parser.add_argument(
        "--type",
        choices=["command", "query"],
        default="command",
        help="Use case type (default: command)",
    )
    parser.add_argument("--application-dir", required=True, help="Path to the application project root")
    parser.add_argument("--namespace", required=True, help="C# namespace for the use case")
    args = parser.parse_args()

    name = args.name.strip()
    if not name or not name[0].isalpha() or not name[0].isupper():
        print("❌ Use case name must start with an uppercase letter.")
        return 1

    application_dir = Path(args.application_dir)
    use_case_dir = application_dir / "UseCases" / name
    ensure_dir(use_case_dir)

    try:
        write_file(use_case_dir / f"{name}Request.cs", build_request_content(name, args.namespace))
        write_file(use_case_dir / f"{name}Result.cs", build_result_content(name, args.namespace))
        write_file(use_case_dir / f"{name}Handler.cs", build_handler_content(name, args.namespace))
    except FileExistsError as exc:
        print(f"❌ {exc}")
        return 1

    print(f"✅ Created use case ({args.type}): {use_case_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Scaffold a backend domain entity for .NET or Python services.

Examples:
    python scaffold-entity.py Customer --stack dotnet --domain-dir src/App.Domain --namespace App.Domain
    python scaffold-entity.py Customer --stack python --domain-dir src/domain
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"File already exists: {path}")
    path.write_text(content, encoding="utf-8")


def write_file_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def snake_case(value: str) -> str:
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return value.lower()


def build_dotnet_entity(
    name: str,
    namespace: str,
    id_type: str,
    with_audit: bool,
    with_soft_delete: bool,
) -> str:
    lines = [
        "using System;",
        "",
        f"namespace {namespace};",
        "",
        f"public class {name}",
        "{",
        f"    public {id_type} Id {{ get; private set; }}",
    ]
    if with_audit:
        lines += [
            "    public DateTime CreatedAt { get; private set; }",
            "    public DateTime UpdatedAt { get; private set; }",
        ]
    if with_soft_delete:
        lines.append("    public bool IsDeleted { get; private set; }")

    lines += [
        "",
        f"    protected {name}() {{ }}",
        "",
        f"    public {name}({id_type} id)",
        "    {",
        "        Id = id;",
    ]
    if with_audit:
        lines += [
            "        CreatedAt = DateTime.UtcNow;",
            "        UpdatedAt = DateTime.UtcNow;",
        ]
    lines.append("    }")

    if with_soft_delete:
        lines += [
            "",
            "    public void MarkDeleted()",
            "    {",
            "        IsDeleted = true;",
            "    }",
        ]
    if with_audit:
        lines += [
            "",
            "    public void Touch()",
            "    {",
            "        UpdatedAt = DateTime.UtcNow;",
            "    }",
        ]

    lines.append("}")
    return "\n".join(lines) + "\n"


def build_dotnet_config(
    name: str,
    namespace: str,
    with_audit: bool,
    with_soft_delete: bool,
) -> str:
    lines = [
        "using Microsoft.EntityFrameworkCore;",
        "using Microsoft.EntityFrameworkCore.Metadata.Builders;",
        "",
        f"namespace {namespace};",
        "",
        f"public class {name}Configuration : IEntityTypeConfiguration<{name}>",
        "{",
        f"    public void Configure(EntityTypeBuilder<{name}> builder)",
        "    {",
        f"        builder.ToTable(\"{name}\");",
        "        builder.HasKey(x => x.Id);",
    ]
    if with_audit:
        lines += [
            "        builder.Property(x => x.CreatedAt).IsRequired();",
            "        builder.Property(x => x.UpdatedAt).IsRequired();",
        ]
    if with_soft_delete:
        lines.append("        builder.Property(x => x.IsDeleted).IsRequired();")
    lines += [
        "    }",
        "}",
    ]
    return "\n".join(lines) + "\n"


def build_python_entity(name: str, with_audit: bool, with_soft_delete: bool) -> str:
    class_name = name
    lines = [
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass, field",
        "from datetime import datetime, timezone",
        "from uuid import UUID, uuid4",
        "",
        "",
        "@dataclass",
        f"class {class_name}:",
        "    id: UUID = field(default_factory=uuid4)",
    ]
    if with_audit:
        lines += [
            "    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))",
            "    updated_at: datetime | None = None",
        ]
    if with_soft_delete:
        lines += [
            "    is_deleted: bool = False",
            "    deleted_at: datetime | None = None",
        ]
    lines += [
        "",
        "    def touch(self) -> None:",
        "        self.updated_at = datetime.now(timezone.utc)",
    ]
    if with_soft_delete:
        lines += [
            "",
            "    def mark_deleted(self) -> None:",
            "        self.is_deleted = True",
            "        self.deleted_at = datetime.now(timezone.utc)",
            "        self.touch()",
        ]
    return "\n".join(lines) + "\n"


def build_python_repository(name: str) -> str:
    variable = snake_case(name)
    return f"""from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .{variable} import {name}


class {name}Repository(Protocol):
    async def get(self, {variable}_id: UUID) -> {name} | None:
        ...

    async def save(self, {variable}: {name}) -> None:
        ...
"""


def build_python_test(name: str, import_path: str) -> str:
    variable = snake_case(name)
    return f"""from {import_path} import {name}


def test_{variable}_can_be_created() -> None:
    {variable} = {name}()

    assert {variable}.id is not None
"""


def scaffold_dotnet(args: argparse.Namespace) -> list[Path]:
    domain_dir = Path(args.domain_dir)
    entity_dir = domain_dir / "Entities"
    ensure_dir(entity_dir)

    name = args.name
    with_audit = not args.no_audit
    with_soft_delete = not args.no_soft_delete
    created = []

    entity_path = entity_dir / f"{name}.cs"
    write_file(
        entity_path,
        build_dotnet_entity(
            name=name,
            namespace=args.namespace,
            id_type=args.id_type,
            with_audit=with_audit,
            with_soft_delete=with_soft_delete,
        ),
    )
    created.append(entity_path)

    if args.infrastructure_dir:
        config_dir = Path(args.infrastructure_dir) / "Persistence" / "Configurations"
        ensure_dir(config_dir)
        config_path = config_dir / f"{name}Configuration.cs"
        write_file(
            config_path,
            build_dotnet_config(
                name=name,
                namespace=args.infra_namespace or args.namespace,
                with_audit=with_audit,
                with_soft_delete=with_soft_delete,
            ),
        )
        created.append(config_path)

    return created


def scaffold_python(args: argparse.Namespace) -> list[Path]:
    domain_dir = Path(args.domain_dir)
    ensure_dir(domain_dir)
    tests_dir = Path(args.tests_dir) if args.tests_dir else domain_dir.parent.parent / "tests" / "unit"
    ensure_dir(tests_dir)

    name = args.name
    variable = snake_case(name)
    created = []

    init_path = domain_dir / "__init__.py"
    if write_file_if_missing(init_path, ""):
        created.append(init_path)

    entity_path = domain_dir / f"{variable}.py"
    write_file(entity_path, build_python_entity(name, not args.no_audit, not args.no_soft_delete))
    created.append(entity_path)

    repository_path = domain_dir / f"{variable}_repository.py"
    write_file(repository_path, build_python_repository(name))
    created.append(repository_path)

    test_path = tests_dir / f"test_{variable}.py"
    import_path = f"{domain_dir.name}.{variable}"
    write_file(test_path, build_python_test(name, import_path))
    created.append(test_path)

    return created


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaffold a domain entity.")
    parser.add_argument("name", help="Entity class name, for example Customer")
    parser.add_argument("--stack", choices=("dotnet", "python"), default="dotnet")
    parser.add_argument("--domain-dir", required=True, help="Domain project or package path")
    parser.add_argument("--namespace", help="C# namespace for .NET entity scaffolds")
    parser.add_argument("--id-type", default="Guid", help="C# Id property type")
    parser.add_argument("--no-audit", action="store_true", help="Disable audit fields")
    parser.add_argument("--no-soft-delete", action="store_true", help="Disable soft delete fields")
    parser.add_argument("--infrastructure-dir", help="Infrastructure project root for .NET")
    parser.add_argument("--infra-namespace", help="C# namespace for EF Core configuration")
    parser.add_argument("--tests-dir", help="Python unit test directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    name = args.name.strip()
    if not name or not name[0].isalpha() or not name[0].isupper():
        print("ERROR: Entity name must start with an uppercase letter.")
        return 1

    if args.stack == "dotnet" and not args.namespace:
        print("ERROR: --namespace is required for --stack dotnet.")
        return 1

    try:
        created = scaffold_dotnet(args) if args.stack == "dotnet" else scaffold_python(args)
    except FileExistsError as exc:
        print(f"ERROR: {exc}")
        return 1

    for path in created:
        print(f"Created: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

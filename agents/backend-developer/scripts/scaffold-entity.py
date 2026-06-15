#!/usr/bin/env python3
"""
Scaffold a domain entity (and optional EF Core configuration).

Usage:
    python scaffold-entity.py Customer --domain-dir src/App.Domain --namespace App.Domain
    python scaffold-entity.py Customer --domain-dir src/App.Domain --namespace App.Domain \
        --infrastructure-dir src/App.Infrastructure --infra-namespace App.Infrastructure
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


def build_entity_content(
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
    lines += [
        "    }",
    ]

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


def build_config_content(
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a domain entity.")
    parser.add_argument("name", help="Entity class name (e.g., Customer)")
    parser.add_argument("--domain-dir", required=True, help="Path to the domain project root")
    parser.add_argument("--namespace", required=True, help="C# namespace for the entity")
    parser.add_argument("--id-type", default="Guid", help="Type of the Id property")
    parser.add_argument(
        "--no-audit",
        action="store_true",
        help="Disable CreatedAt/UpdatedAt fields",
    )
    parser.add_argument(
        "--no-soft-delete",
        action="store_true",
        help="Disable IsDeleted field and MarkDeleted()",
    )
    parser.add_argument(
        "--infrastructure-dir",
        help="Path to the infrastructure project root (optional)",
    )
    parser.add_argument(
        "--infra-namespace",
        help="C# namespace for the EF Core configuration (optional)",
    )
    args = parser.parse_args()

    name = args.name.strip()
    if not name or not name[0].isalpha() or not name[0].isupper():
        print("❌ Entity name must start with an uppercase letter.")
        return 1

    domain_dir = Path(args.domain_dir)
    entity_dir = domain_dir / "Entities"
    ensure_dir(entity_dir)

    entity_path = entity_dir / f"{name}.cs"
    with_audit = not args.no_audit
    with_soft_delete = not args.no_soft_delete

    try:
        write_file(
            entity_path,
            build_entity_content(
                name=name,
                namespace=args.namespace,
                id_type=args.id_type,
                with_audit=with_audit,
                with_soft_delete=with_soft_delete,
            ),
        )
    except FileExistsError as exc:
        print(f"❌ {exc}")
        return 1

    if args.infrastructure_dir:
        infra_dir = Path(args.infrastructure_dir)
        config_dir = infra_dir / "Persistence" / "Configurations"
        ensure_dir(config_dir)
        config_path = config_dir / f"{name}Configuration.cs"
        infra_namespace = args.infra_namespace or args.namespace
        try:
            write_file(
                config_path,
                build_config_content(
                    name=name,
                    namespace=infra_namespace,
                    with_audit=with_audit,
                    with_soft_delete=with_soft_delete,
                ),
            )
        except FileExistsError as exc:
            print(f"❌ {exc}")
            return 1

    print(f"✅ Created entity: {entity_path}")
    if args.infrastructure_dir:
        print(f"✅ Created configuration: {config_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

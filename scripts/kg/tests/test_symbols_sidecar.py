from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "kg"))

import symbols  # noqa: E402


def test_unbound_sidecar_preserves_non_refreshed_languages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sidecar_path = tmp_path / "unbound-but-referenced.yaml"
    sidecar_path.write_text(
        yaml.safe_dump(
            {
                "version": 0,
                "invocations": [
                    {
                        "source_file": "old-csharp.cs",
                        "source_line": 10,
                        "language": "csharp",
                        "target_symbol": "symbol:old-csharp",
                        "target_node": "entity:old",
                    },
                    {
                        "source_file": "existing-ts.ts",
                        "source_line": 20,
                        "language": "typescript",
                        "target_symbol": "symbol:existing-ts",
                        "target_node": "entity:existing",
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(symbols, "UNBOUND_REFS_PATH", sidecar_path)

    records = [
        symbols.SymbolRecord(
            id="symbol:new-csharp",
            node="entity:new",
            kind="method",
            name="DoWork",
            file="bound.cs",
            line=1,
            signature="void DoWork()",
            visibility="public",
            language="csharp",
            container="Worker",
        )
    ]

    count = symbols.write_unbound_but_referenced(
        {
            "csharp": [
                {
                    "source_file": "new-csharp.cs",
                    "source_line": 30,
                    "target": {"name": "DoWork", "container": "Worker"},
                }
            ]
        },
        records,
        {"csharp"},
    )

    doc = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))
    invocations = doc["invocations"]

    assert count == 2
    assert doc["summary"]["refreshed_languages"] == ["csharp"]
    assert doc["summary"]["preserved_languages"] == ["typescript"]
    assert {entry["language"] for entry in invocations} == {"csharp", "typescript"}
    assert {entry["source_file"] for entry in invocations} == {
        "new-csharp.cs",
        "existing-ts.ts",
    }

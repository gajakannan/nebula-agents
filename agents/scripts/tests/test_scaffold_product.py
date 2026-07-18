"""Tests for scaffold-product.py (F0007-S0003)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "agents" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sp = _load("scaffold_product", SCRIPTS_DIR / "scaffold-product.py")
SCAFFOLD_MAP = yaml.safe_load((SCRIPTS_DIR / "scaffold-map.yaml").read_text())


def test_check_reports_missing_on_empty(tmp_path):
    report = sp.check(tmp_path, SCAFFOLD_MAP)
    assert not report["ok"]
    assert "CONTRIBUTING.md" in report["missing_required"]


def test_write_then_check_ok(tmp_path):
    written = sp.scaffold_write(tmp_path, SCAFFOLD_MAP)
    assert written["ok"]
    assert "CONTRIBUTING.md" in written["created"]
    assert (tmp_path / "planning-mds" / "operations" / "evidence").is_dir()
    assert sp.check(tmp_path, SCAFFOLD_MAP)["ok"]


def test_write_is_idempotent(tmp_path):
    sp.scaffold_write(tmp_path, SCAFFOLD_MAP)
    again = sp.scaffold_write(tmp_path, SCAFFOLD_MAP)
    assert again["ok"]
    assert again["created"] == []
    assert "CONTRIBUTING.md" in again["preserved"]


def test_existing_file_preserved_byte_for_byte(tmp_path):
    (tmp_path / "CONTRIBUTING.md").write_text("PRODUCT OWNED\n", encoding="utf-8")
    sp.scaffold_write(tmp_path, SCAFFOLD_MAP)
    assert (tmp_path / "CONTRIBUTING.md").read_text(encoding="utf-8") == "PRODUCT OWNED\n"


def test_check_is_read_only(tmp_path):
    sp.check(tmp_path, SCAFFOLD_MAP)
    assert not (tmp_path / "CONTRIBUTING.md").exists()
    assert not (tmp_path / "planning-mds").exists()


def test_path_escape_rolls_back(tmp_path):
    bad_map = {
        "directories": [],
        "files": [
            {"template": "contributing-template.md", "destination": "CONTRIBUTING.md", "required": True},
            {"template": "contributing-template.md", "destination": "../escape.md", "required": True},
        ],
    }
    report = sp.scaffold_write(tmp_path, bad_map)
    assert not report["ok"]
    # The first file was created then rolled back; the escape never landed.
    assert not (tmp_path / "CONTRIBUTING.md").exists()
    assert not (tmp_path.parent / "escape.md").exists()
    assert report["rolled_back"] == ["CONTRIBUTING.md"]

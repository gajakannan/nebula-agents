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


def test_pre_commit_hook_is_scaffolded_executable(tmp_path):
    written = sp.scaffold_write(tmp_path, SCAFFOLD_MAP)
    hook = tmp_path / ".githooks" / "pre-commit"
    assert ".githooks/pre-commit" in written["created"]
    assert hook.stat().st_mode & 0o111
    assert (tmp_path / ".githooks" / "README.md").is_file()


def _hook_repo(tmp_path: Path, validate_body: str) -> Path:
    import shutil
    import subprocess

    shutil.copy(REPO_ROOT / "agents" / "templates" / "githooks-pre-commit-template.sh",
                tmp_path / "pre-commit")
    (tmp_path / "scripts" / "kg").mkdir(parents=True)
    (tmp_path / "scripts" / "kg" / "validate.py").write_text(validate_body, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "planning-mds").mkdir()
    (tmp_path / "planning-mds" / "doc.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "planning-mds/doc.md"], check=True)
    return tmp_path


STUB = """import sys
if '--check-reproducible' in sys.argv:
    sys.exit(0)
print('Errors:')
print('- coverage-report.yaml is stale')
sys.exit({code})
"""


def test_pre_commit_hook_blocks_stale_coverage(tmp_path):
    import subprocess

    repo = _hook_repo(tmp_path, STUB.format(code=1))
    result = subprocess.run(["bash", str(repo / "pre-commit")], cwd=repo,
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "coverage-report.yaml is stale" in result.stderr
    assert "--write-coverage-report" in result.stderr


def test_pre_commit_hook_passes_fresh_tree(tmp_path):
    import subprocess

    repo = _hook_repo(tmp_path, STUB.format(code=0))
    result = subprocess.run(["bash", str(repo / "pre-commit")], cwd=repo,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

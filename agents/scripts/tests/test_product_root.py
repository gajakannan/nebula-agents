"""Selection must survive directory changes and never choose a product implicitly."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from _product_root import ProductRootError, expand_product_root, resolve_product_root
from project_context import explicit_root


def load_resolver(name):
    path = SCRIPTS.parent / "product-manager" / "scripts" / name
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.resolve_product_root


@pytest.mark.parametrize("resolver", [resolve_product_root, explicit_root,
    load_resolver("patch-prior-manifest.py"), load_resolver("validate-feature-evidence.py")])
def test_same_selection_across_entry_points_and_directory_changes(tmp_path, monkeypatch, resolver):
    framework = tmp_path / "framework"
    product = tmp_path / "chosen product"
    nested = framework / "engine"
    nested.mkdir(parents=True)
    product.mkdir()
    monkeypatch.chdir(framework)
    monkeypatch.setenv("NEBULA_PRODUCT_ROOT", "../chosen product")
    selected = resolver(None)
    assert selected == product
    monkeypatch.chdir(nested)
    monkeypatch.setenv("NEBULA_PRODUCT_ROOT", "../wrong-product")
    assert resolver(str(selected)) == product


@pytest.mark.parametrize("value", [None, "", "   "])
def test_no_implicit_product_even_with_legacy_variable(tmp_path, monkeypatch, value):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NEBULA_PRODUCT_ROOT", raising=False)
    monkeypatch.setenv("NEBULA_AGENTS_PRODUCT_ROOT", str(tmp_path))
    monkeypatch.setenv("PRODUCT_ROOT", str(tmp_path))
    with pytest.raises(ProductRootError, match="no product is selected"):
        resolve_product_root(value)


def test_canonical_placeholder_expands_to_the_selected_product(tmp_path):
    assert expand_product_root("{NEBULA_PRODUCT_ROOT}/engine", tmp_path) == tmp_path / "engine"


@pytest.mark.parametrize("name", ["PRODUCT_ROOT", "NEBULA_AGENTS_PRODUCT_ROOT"])
def test_legacy_placeholders_fail_instead_of_becoming_literal_paths(tmp_path, name):
    with pytest.raises(ProductRootError, match="use \\{NEBULA_PRODUCT_ROOT\\}"):
        expand_product_root("{" + name + "}/engine", tmp_path)


def test_explicit_prompt_value_needs_no_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("NEBULA_PRODUCT_ROOT", raising=False)
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "_product_root.py"), "--product-root", "../product"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == str(tmp_path.parent / "product")
    assert "source: --product-root" in result.stderr


def test_missing_root_cli_errors_before_work(tmp_path, monkeypatch):
    monkeypatch.delenv("NEBULA_PRODUCT_ROOT", raising=False)
    result = subprocess.run([sys.executable, str(SCRIPTS / "_product_root.py")],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 2
    assert not result.stdout
    assert "no product is selected" in result.stderr

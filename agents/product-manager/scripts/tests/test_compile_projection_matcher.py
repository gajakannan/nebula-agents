"""F0006-S0009: validate-feature-evidence.py learns the compile.py regeneration flow (date-gated)."""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "vfe", Path(__file__).resolve().parents[1] / "validate-feature-evidence.py"
)
vfe = importlib.util.module_from_spec(_SPEC)
sys.modules["vfe"] = vfe  # dataclasses need the module in sys.modules before exec (py3.14)
_SPEC.loader.exec_module(vfe)


def test_compile_py_recognized_as_projection_regeneration():
    assert vfe._command_compiles_projection("python3 scripts/kg/compile.py")
    assert vfe._command_compiles_projection("python3 scripts/kg/validate.py --check-reproducible")
    assert not vfe._command_compiles_projection("python3 scripts/kg/validate.py --regenerate-symbols")


def test_symbol_decision_matchers_unchanged():
    # symbols/decisions stay validate.py-driven — compile.py must NOT count as those
    assert vfe._command_regenerates_symbols("validate.py --regenerate-symbols")
    assert not vfe._command_regenerates_symbols("scripts/kg/compile.py")
    assert not vfe._command_regenerates_decisions("scripts/kg/compile.py")


def test_compile_projection_contract_is_date_gated():
    # on/after the cutover date → under the compiled-projection contract
    assert vfe.compile_projection_contract({"contract_effective_date": "2026-07-11"})
    assert vfe.compile_projection_contract({"contract_effective_date": "2026-08-01"})
    # earlier runs keep the old contract (evidence stays valid)
    assert not vfe.compile_projection_contract({"contract_effective_date": "2026-07-05"})
    assert not vfe.compile_projection_contract({"contract_effective_date": "2026-06-01"})
    assert not vfe.compile_projection_contract({})


def test_effective_date_constant():
    assert vfe.KG_COMPILE_PROJECTION_EFFECTIVE_DATE == date(2026, 7, 11)

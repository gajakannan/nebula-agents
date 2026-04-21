"""Product-root resolution helper for framework scripts.

Resolves {PRODUCT_ROOT} in a single uniform order across every framework-owned
script that reads or writes product-side artifacts:

  1. --product-root CLI flag, if supplied
  2. NEBULA_PRODUCT_ROOT environment variable, if set
  3. Default: ../nebula-insurance-crm relative to the nebula-agents repo root

The resolved absolute path is echoed to stderr on first call so CI logs and
interactive sessions show which root the script is operating against.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


_FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]  # nebula-agents repo root
_DEFAULT_PRODUCT_ROOT = (_FRAMEWORK_ROOT / ".." / "nebula-insurance-crm").resolve()


def add_product_root_arg(parser: argparse.ArgumentParser) -> None:
    """Attach a `--product-root` flag to *parser*.

    Call this after creating the argparse parser in any framework script that
    needs to read product-side artifacts.
    """
    parser.add_argument(
        "--product-root",
        default=None,
        help=(
            "Path to {PRODUCT_ROOT} (the sibling product repo). "
            "Overrides NEBULA_PRODUCT_ROOT and the default fallback."
        ),
    )


def resolve_product_root(cli_value: str | None = None, *, echo: bool = True) -> Path:
    """Resolve {PRODUCT_ROOT} via CLI flag → env var → default.

    Parameters
    ----------
    cli_value:
        Value from ``args.product_root`` (None if not supplied).
    echo:
        If True (default), print the resolved root to stderr on first call.
    """
    if cli_value:
        root = Path(cli_value).expanduser().resolve()
        source = "--product-root"
    elif os.environ.get("NEBULA_PRODUCT_ROOT"):
        root = Path(os.environ["NEBULA_PRODUCT_ROOT"]).expanduser().resolve()
        source = "NEBULA_PRODUCT_ROOT"
    else:
        root = _DEFAULT_PRODUCT_ROOT
        source = "default (../nebula-insurance-crm)"

    if echo:
        print(f"[product-root] {root} (source: {source})", file=sys.stderr)
    return root


def expand_product_root(raw: str, product_root: Path) -> Path:
    """Expand a literal `{PRODUCT_ROOT}`-prefixed string into an absolute path.

    Use this when migrating scripts whose argparse defaults previously held the
    literal placeholder `"{PRODUCT_ROOT}/..."`. If *raw* is already an absolute
    path or does not contain the placeholder, it is returned untouched (still
    resolved for normalization).
    """
    if "{PRODUCT_ROOT}" in raw:
        resolved = raw.replace("{PRODUCT_ROOT}", str(product_root))
        return Path(resolved).expanduser().resolve()
    return Path(raw).expanduser().resolve()

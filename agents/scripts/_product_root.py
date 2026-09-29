"""Product-root resolution helper for framework scripts.

Resolves {NEBULA_PRODUCT_ROOT} in a single uniform order across every framework-owned
script that reads or writes product-side artifacts:

  1. --product-root CLI flag, if supplied
  2. NEBULA_PRODUCT_ROOT environment variable, if set
Missing selection is an error. Relative paths use the invocation directory;
resolve once and pass the absolute result across commands and directory changes.

The resolved absolute path is echoed to stderr on each call so CI logs and
interactive sessions show which root the script is operating against.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


_FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]  # nebula-agents repo root
# Scripts run directly from a framework checkout without an installed engine.
sys.path.insert(0, str(_FRAMEWORK_ROOT / "engine" / "src"))
from nebula_agents.product_root import ProductRootError, resolve_product_root as _resolve  # noqa: E402


def add_product_root_arg(parser: argparse.ArgumentParser) -> None:
    """Attach a `--product-root` flag to *parser*.

    Call this after creating the argparse parser in any framework script that
    needs to read product-side artifacts.
    """
    parser.add_argument(
        "--product-root",
        default=None,
        help=(
            "Path to {NEBULA_PRODUCT_ROOT} (the sibling product repo). "
            "Overrides NEBULA_PRODUCT_ROOT. Required if that variable is unset."
        ),
    )


def resolve_product_root(cli_value: str | None = None, *, echo: bool = True) -> Path:
    """Resolve {NEBULA_PRODUCT_ROOT} via CLI flag → NEBULA_PRODUCT_ROOT → error.

    Parameters
    ----------
    cli_value:
        Value from ``args.product_root`` (None if not supplied).
    echo:
        If True (default), print the resolved root to stderr on each call.
    """
    root = _resolve(cli_value)
    source = "--product-root" if cli_value is not None else "NEBULA_PRODUCT_ROOT"

    if echo:
        print(f"[product-root] {root} (source: {source})", file=sys.stderr)
    return root


def expand_product_root(raw: str, product_root: Path) -> Path:
    """Expand a literal `{NEBULA_PRODUCT_ROOT}`-prefixed string into an absolute path.

    Use this when migrating scripts whose argparse defaults previously held the
    literal placeholder `"{NEBULA_PRODUCT_ROOT}/..."`. If *raw* is already an absolute
    path or does not contain the placeholder, it is returned untouched (still
    resolved for normalization).
    """
    if any(token in raw for token in ("{PRODUCT_ROOT}", "{NEBULA_AGENTS_PRODUCT_ROOT}")):
        raise ProductRootError("Unsupported root placeholder; use {NEBULA_PRODUCT_ROOT}.")
    if "{NEBULA_PRODUCT_ROOT}" in raw:
        resolved = raw.replace("{NEBULA_PRODUCT_ROOT}", str(product_root))
        return Path(resolved).expanduser().resolve()
    return Path(raw).expanduser().resolve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    add_product_root_arg(parser)
    args = parser.parse_args()
    try:
        print(resolve_product_root(args.product_root))
    except ProductRootError as exc:
        parser.error(str(exc))

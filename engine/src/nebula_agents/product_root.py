"""Product selection shared by the native runtime and framework scripts."""

from __future__ import annotations

import os
from pathlib import Path


class ProductRootError(ValueError):
    """No product was selected; never guess a sibling or use CWD as a product."""


def resolve_product_root(value: str | Path | None = None, *, base: Path | None = None) -> Path:
    """Explicit selection wins over NEBULA_PRODUCT_ROOT; normalize once at entry.

    Relative inputs use the invocation directory (or an explicitly captured session
    directory). Callers must pass the returned absolute path across CWD changes.
    """
    raw = value if value is not None else os.environ.get("NEBULA_PRODUCT_ROOT")
    if raw is None or not str(raw).strip():
        raise ProductRootError(
            "Pass --product-root or set NEBULA_PRODUCT_ROOT; no product is selected by default."
        )
    path = Path(raw).expanduser()
    return (path if path.is_absolute() else (base or Path.cwd()) / path).resolve()

"""Filesystem path invariants shared by launch and validation workflows."""

from __future__ import annotations

import os
from pathlib import Path


def governed_feature_root(workspace: Path, feature_id: str) -> Path | None:
    """Resolve one direct feature directory without following any symlink."""
    root = workspace.expanduser().resolve()
    current = root
    try:
        for component in ("planning-mds", "features"):
            current = current / component
            if current.is_symlink() or not current.is_dir():
                return None
        features_root = current.resolve(strict=True)
        if features_root.parent != (root / "planning-mds").resolve(strict=True):
            return None
        matches = tuple(current.glob(f"{feature_id}-*"))
        if len(matches) != 1:
            return None
        requested = matches[0]
        if requested.is_symlink() or not requested.is_dir():
            return None
        resolved = requested.resolve(strict=True)
        if resolved.parent != features_root or _contains_symlink(resolved):
            return None
        return resolved
    except OSError:
        return None


def governed_story_file(feature_root: Path, story_id: str) -> Path | None:
    """Resolve one direct governed story file beneath a trusted feature root."""
    root = feature_root.resolve(strict=True)
    stories = root / "stories"
    if stories.is_symlink():
        return None
    direct = tuple(root.glob(f"{story_id}-*.md"))
    nested = tuple(stories.glob(f"{story_id}-*.md")) if stories.is_dir() else ()
    matches = direct + nested
    if len(matches) != 1:
        return None
    requested = matches[0]
    try:
        if requested.is_symlink() or not requested.is_file():
            return None
        resolved = requested.resolve(strict=True)
        allowed_parents = {root}
        if stories.is_dir():
            allowed_parents.add(stories.resolve(strict=True))
        return resolved if resolved.parent in allowed_parents else None
    except OSError:
        return None


def _contains_symlink(root: Path) -> bool:
    """Reject symlinked files or directories anywhere in governed feature data."""
    try:
        for current, directories, filenames in os.walk(root, followlinks=False):
            parent = Path(current)
            if parent.is_symlink() or not parent.resolve(strict=True).is_relative_to(root):
                return True
            if any((parent / name).is_symlink() for name in (*directories, *filenames)):
                return True
        return False
    except OSError:
        return True

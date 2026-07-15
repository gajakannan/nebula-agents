#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path


def rotated_name(path: Path, stamp: str) -> Path:
    candidate = path.with_name(f"{path.name}.{stamp}.jsonl")
    if not candidate.exists():
        return candidate

    suffix = 1
    while True:
        numbered = path.with_name(f"{path.name}.{stamp}.{suffix}.jsonl")
        if not numbered.exists():
            return numbered
        suffix += 1


def prune_old_rotations(path: Path, keep_days: int) -> list[Path]:
    deleted: list[Path] = []
    cutoff = datetime.now(UTC) - timedelta(days=keep_days)
    prefix = f"{path.name}."
    for candidate in path.parent.glob(f"{path.name}.*.jsonl"):
        if not candidate.name.startswith(prefix):
            continue
        modified = datetime.fromtimestamp(candidate.stat().st_mtime, UTC)
        if modified < cutoff:
            candidate.unlink()
            deleted.append(candidate)
    return deleted


def rotate_if_needed(path: Path, max_size_mb: int) -> Path | None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return None

    if path.stat().st_size <= max_size_mb * 1024 * 1024:
        return None

    destination = rotated_name(path, datetime.now(UTC).date().isoformat())
    path.rename(destination)
    path.write_text("", encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotate KG telemetry JSONL files.")
    parser.add_argument("telemetry_file", type=Path, help="Path to the active telemetry JSONL file.")
    parser.add_argument("--max-size-mb", type=int, default=50, help="Rotate when the file exceeds this size in MB.")
    parser.add_argument("--keep-days", type=int, default=14, help="Delete rotated files older than this many days.")
    args = parser.parse_args()

    rotated = rotate_if_needed(args.telemetry_file, args.max_size_mb)
    deleted = prune_old_rotations(args.telemetry_file, args.keep_days)

    if rotated:
        print(f"Rotated: {rotated}")
    else:
        print("No rotation needed.")

    if deleted:
        for path in deleted:
            print(f"Deleted: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath


SCHEMA_VERSION = 1
PRODUCT_LABEL = "{PRODUCT_ROOT}"
FRAMEWORK_LABEL = "nebula-agents"
# Spec cwd labels (gate_runtime._resolve_cwd, exec-and-log --cwd) map to the same telemetry
# labels here, so every entry point records one spelling for one directory. A relative
# path under the product root that begins with a directory literally named "product" or
# "framework" must be passed as an absolute path.
SPEC_CWD_LABELS = {"product": PRODUCT_LABEL, "framework": FRAMEWORK_LABEL}
SCRATCH_ROOTS = (Path("/tmp"), Path("/var/tmp"), Path("/private/tmp"), Path("/dev/shm"))
DEFAULT_FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]


class CommandLogError(ValueError):
    """Raised when a command-log entry cannot be normalized safely."""


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _require_existing_root(raw: str, label: str) -> Path:
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise CommandLogError(f"{label} must be an existing directory: {raw}")
    return root


def _normalize_label_suffix(suffix: str) -> str:
    if suffix in ("", "."):
        return ""
    path = PurePosixPath(suffix)
    if path.is_absolute() or ".." in path.parts:
        raise CommandLogError(f"stable label path must not be absolute or traverse upward: {suffix}")
    parts = [part for part in path.parts if part not in ("", ".")]
    return "/".join(parts)


def _label_path(label: str, suffix: str) -> str:
    normalized = _normalize_label_suffix(suffix)
    return label if not normalized else f"{label}/{normalized}"


def _relative_artifact_from_candidate(candidate: Path, product_root: Path, raw: str) -> str:
    resolved = candidate.expanduser().resolve(strict=False)
    if not _is_relative_to(resolved, product_root):
        raise CommandLogError(f"artifact escapes product root: {raw}")
    if not resolved.exists():
        raise CommandLogError(f"artifact does not exist: {raw}")
    relative = resolved.relative_to(product_root).as_posix()
    if not relative or relative == ".":
        raise CommandLogError(f"artifact must point inside the product root, not at the root: {raw}")
    return relative


def normalize_cwd(raw: str, product_root: Path, framework_root: Path) -> str:
    value = raw.strip()
    if not value:
        raise CommandLogError("--cwd must be non-empty")

    if value == PRODUCT_LABEL:
        return PRODUCT_LABEL
    if value.startswith(f"{PRODUCT_LABEL}/"):
        return _label_path(PRODUCT_LABEL, value[len(PRODUCT_LABEL) + 1 :])

    if value == FRAMEWORK_LABEL:
        return FRAMEWORK_LABEL
    if value.startswith(f"{FRAMEWORK_LABEL}/"):
        return _label_path(FRAMEWORK_LABEL, value[len(FRAMEWORK_LABEL) + 1 :])

    spec_base, _, spec_sub = value.partition("/")
    if spec_base in SPEC_CWD_LABELS:
        return _label_path(SPEC_CWD_LABELS[spec_base], spec_sub)

    path = Path(value).expanduser()
    if path.is_absolute():
        resolved = path.resolve(strict=False)
        if _is_relative_to(resolved, product_root):
            relative = resolved.relative_to(product_root).as_posix()
            return PRODUCT_LABEL if relative == "." else f"{PRODUCT_LABEL}/{relative}"
        if _is_relative_to(resolved, framework_root):
            relative = resolved.relative_to(framework_root).as_posix()
            return FRAMEWORK_LABEL if relative == "." else f"{FRAMEWORK_LABEL}/{relative}"
        raise CommandLogError(f"cwd is outside product/framework roots and is not a stable label: {raw}")

    if ".." in PurePosixPath(value).parts:
        raise CommandLogError(f"relative cwd must not traverse upward: {raw}")
    normalized = _normalize_label_suffix(value)
    return PRODUCT_LABEL if not normalized else f"{PRODUCT_LABEL}/{normalized}"


def _is_scratch_path(path: Path) -> bool:
    resolved = path.expanduser().resolve(strict=False)
    return any(resolved == root or _is_relative_to(resolved, root) for root in SCRATCH_ROOTS)


def normalize_artifact(raw: str, product_root: Path) -> str:
    value = raw.strip()
    if not value:
        raise CommandLogError("--artifact values must be non-empty")
    if is_url(value):
        return value

    if value == PRODUCT_LABEL:
        raise CommandLogError("artifact must point inside the product root, not at {PRODUCT_ROOT}")
    if value.startswith(f"{PRODUCT_LABEL}/"):
        suffix = value[len(PRODUCT_LABEL) + 1 :]
        return _relative_artifact_from_candidate(product_root / suffix, product_root, raw)

    path = Path(value).expanduser()
    if path.is_absolute():
        resolved = path.resolve(strict=False)
        if _is_relative_to(resolved, product_root):
            return _relative_artifact_from_candidate(resolved, product_root, raw)
        if _is_scratch_path(resolved):
            raise CommandLogError(f"scratch artifact paths are not durable evidence: {raw}")
        raise CommandLogError(f"artifact is outside product root: {raw}")

    if ".." in PurePosixPath(value).parts:
        candidate = (product_root / value).resolve(strict=False)
        if not _is_relative_to(candidate, product_root):
            raise CommandLogError(f"artifact escapes product root: {raw}")
    return _relative_artifact_from_candidate(product_root / value, product_root, raw)


def resolve_log_path(raw: str, product_root: Path) -> Path:
    value = raw.strip()
    if not value:
        raise CommandLogError("--log must be non-empty")
    if value == PRODUCT_LABEL:
        raise CommandLogError("--log must point to a commands.log file, not {PRODUCT_ROOT}")
    if value.startswith(f"{PRODUCT_LABEL}/"):
        candidate = product_root / value[len(PRODUCT_LABEL) + 1 :]
    else:
        path = Path(value).expanduser()
        candidate = path if path.is_absolute() else product_root / path

    resolved = candidate.resolve(strict=False)
    if not _is_relative_to(resolved, product_root):
        raise CommandLogError(f"--log must stay inside product root: {raw}")
    return resolved


def build_entry(
    *,
    cwd: str,
    command: str,
    exit_code: int,
    artifacts: list[str],
    redactions: list[str],
) -> dict[str, object]:
    sanitized_command = command.strip()
    if not sanitized_command:
        raise CommandLogError("--command must be non-empty")
    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cwd": cwd,
        "command": sanitized_command,
        "exit_code": exit_code,
        "artifacts": artifacts,
        "redactions": redactions,
    }


def append_entry(log_path: Path, entry: dict[str, object]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, separators=(",", ":")) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append one normalized JSONL command entry to a framework evidence commands.log."
    )
    parser.add_argument("--log", required=True, help="Path to the commands.log file under {PRODUCT_ROOT}.")
    parser.add_argument("--product-root", required=True, help="Resolved product repository root.")
    parser.add_argument(
        "--framework-root",
        default=str(DEFAULT_FRAMEWORK_ROOT),
        help="Resolved framework repository root. Defaults to this script's nebula-agents root.",
    )
    parser.add_argument("--cwd", required=True,
                        help="Command working directory: an absolute path, a stable label "
                             "({PRODUCT_ROOT}, nebula-agents), or a spec label (product, framework), "
                             "each optionally with a contained subpath.")
    parser.add_argument("--command", required=True, help="Sanitized command string to record.")
    parser.add_argument("--exit-code", required=True, type=int, help="Command exit code.")
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="Durable artifact path or URL. Repeat for multiple artifacts.",
    )
    parser.add_argument(
        "--redaction",
        action="append",
        default=[],
        help="Document a class or field redacted from the command or artifacts. Repeat as needed.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        product_root = _require_existing_root(args.product_root, "--product-root")
        framework_root = _require_existing_root(args.framework_root, "--framework-root")
        log_path = resolve_log_path(args.log, product_root)
        cwd = normalize_cwd(args.cwd, product_root, framework_root)
        artifacts = [normalize_artifact(artifact, product_root) for artifact in args.artifact]
        redactions = [redaction.strip() for redaction in args.redaction if redaction.strip()]
        entry = build_entry(
            cwd=cwd,
            command=args.command,
            exit_code=args.exit_code,
            artifacts=artifacts,
            redactions=redactions,
        )
        append_entry(log_path, entry)
    except CommandLogError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

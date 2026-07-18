#!/usr/bin/env python3
"""Run one arbitrary command shell-free and append normalized telemetry (F0007-S0004).

The supported entry point for non-gate commands during an active evidence run:
implementation, investigation, and manual-checkpoint commands. The command after
``--`` is executed as argv (never through a shell) via the shared gate runtime,
and one JSONL entry is appended to the run's commands.log through
append-command-log.py.

    python3 agents/scripts/exec-and-log.py --log RUN_FOLDER/commands.log \
        --product-root PATH --cwd product [--timeout N] [--artifact P] -- cmd arg ...

Exit code mirrors the command (124 on timeout, 128+signal when signalled).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import gate_runtime as gr  # noqa: E402
from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402

_acl = gr._load_hyphenated("append_command_log", "append-command-log.py")


def parse_args(argv: list[str] | None):
    parser = argparse.ArgumentParser(description=__doc__)
    add_product_root_arg(parser)
    parser.add_argument("--log", required=True, help="Path to the run's commands.log (under product root).")
    parser.add_argument("--cwd", default="product",
                        help="cwd label: 'product' or 'framework' (optionally with a contained subpath).")
    parser.add_argument("--timeout", type=float, default=None, help="Timeout in seconds.")
    parser.add_argument("--artifact", action="append", default=[], help="Durable artifact path or URL.")
    parser.add_argument("--redaction", action="append", default=[], help="Documented redaction class.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="The command argv, after `--`.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        sys.stderr.write("no command supplied after `--`\n")
        return 2

    product_root = resolve_product_root(args.product_root)
    if not product_root.is_dir():
        sys.stderr.write(f"product root does not exist: {product_root}\n")
        return 2

    try:
        log_path = _acl.resolve_log_path(args.log, product_root)
    except _acl.CommandLogError as exc:
        sys.stderr.write(f"invalid --log: {exc}\n")
        return 2

    op = {"run": {"argv": command, "cwd": args.cwd, "timeout_seconds": args.timeout,
                  "expected_artifacts": [], "mutates": []}}
    try:
        result = gr.run_operation(op, product_root=product_root, variables=None,
                                  log_path=log_path, extra_artifacts=args.artifact,
                                  redactions=args.redaction)
    except gr.GateRuntimeError as exc:
        print(json.dumps({"ok": False, "error": exc.message, "code": exc.code}))
        return 2

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))

    if result["timed_out"]:
        return 124
    ec = result["exit_code"]
    return 128 + (-ec) if ec is not None and ec < 0 else ec


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Deterministic native-provider stand-in for argv and real-tmux tests."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path


def _record_start(counter: Path | None, argv_log: Path | None) -> None:
    if counter is not None:
        count = int(counter.read_text(encoding="utf-8")) if counter.exists() else 0
        counter.write_text(str(count + 1), encoding="utf-8")
    if argv_log is not None:
        argv_log.write_text(json.dumps(sys.argv, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nebula deterministic fake provider")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--mode", choices=("wait", "exit", "emit"), default="wait")
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--counter", type=Path)
    parser.add_argument("--argv-log", type=Path)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--output", default="")
    parser.add_argument("prompt", nargs="?")
    args, extras = parser.parse_known_args(argv)

    if args.version:
        print("nebula-fake-provider 1.0")
        return 0

    _record_start(args.counter, args.argv_log)
    if args.ready_file is not None:
        args.ready_file.write_text(str(os.getpid()), encoding="utf-8")

    if args.mode == "emit":
        sys.stdout.write(args.output)
        sys.stdout.flush()
        return args.exit_code
    if args.mode == "exit":
        return args.exit_code

    stopped = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print("FAKE_PROVIDER_READY", flush=True)
    while not stopped:
        time.sleep(0.05)
    return args.exit_code


if __name__ == "__main__":
    raise SystemExit(main())


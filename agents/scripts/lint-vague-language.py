#!/usr/bin/env python3
"""Vague-language linter (F0007-S0008).

The banned-word list previously restated in plan.md / plan-review.md / validate.md
is now owned by `agents/actions/spec/_contract.yaml:banned_words`. This linter
scans given files and reports each hit (path, line, term, suggestion). It NEVER
rewrites content. A line carrying a `vague-ok` marker is a documented exception
and is skipped, so intentional prose (e.g. quoting the banned word itself) is
allowed without silencing the whole file.

    python3 agents/scripts/lint-vague-language.py FILE [FILE ...]
    python3 agents/scripts/lint-vague-language.py --json story.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
FRAMEWORK_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_CONTRACT = FRAMEWORK_ROOT / "agents" / "actions" / "spec" / "_contract.yaml"
EXCEPTION_MARKER = "vague-ok"

# Corrections for the common offenders; a generic suggestion covers the rest.
SUGGESTIONS = {
    "should": "state the requirement with 'must' or describe the exact condition",
    "might": "state the exact condition under which it happens",
    "probably": "state the actual likelihood or remove the hedge",
    "usually": "state the exact cases; avoid an unquantified frequency",
    "easy": "remove; describe the concrete steps instead",
    "simple": "remove; describe the concrete design instead",
    "fast": "state a measurable latency/throughput target",
    "secure": "name the specific control (authz, encryption, validation)",
    "robust": "state the specific failure it tolerates",
    "seamless": "remove; describe the concrete behavior",
    "just": "remove the minimizing qualifier",
}


def banned_words(contract_path: Path | None = None) -> list[str]:
    path = contract_path or DEFAULT_CONTRACT
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list((data.get("shared", {}) or {}).get("banned_words", []))


def _suggest(term: str) -> str:
    return SUGGESTIONS.get(term.lower(), "remove or replace with a specific, measurable statement")


def lint_text(text: str, words: list[str], path: str = "<text>") -> list[dict[str, Any]]:
    patterns = {w: re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE) for w in words}
    findings: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if EXCEPTION_MARKER in line:  # documented exception
            continue
        for word, pattern in patterns.items():
            for match in pattern.finditer(line):
                findings.append({
                    "path": path, "line": lineno, "col": match.start() + 1,
                    "term": match.group(0), "suggestion": _suggest(word),
                })
    findings.sort(key=lambda f: (f["path"], f["line"], f["col"], f["term"].lower()))
    return findings


def lint_files(paths: list[Path], contract_path: Path | None = None) -> dict[str, Any]:
    words = banned_words(contract_path)
    findings: list[dict[str, Any]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append({"path": str(path), "line": 0, "col": 0, "term": "",
                             "suggestion": f"could not read: {exc}"})
            continue
        findings.extend(lint_text(text, words, str(path)))
    return {"ok": not findings, "banned_words": words, "findings": findings}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--contract", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = lint_files(args.files, args.contract)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for f in report["findings"]:
            print(f"{f['path']}:{f['line']}:{f['col']}: vague term {f['term']!r} — {f['suggestion']}")
        if report["ok"]:
            print("no vague-language findings")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

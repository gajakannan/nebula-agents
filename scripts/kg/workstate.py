#!/usr/bin/env python3
"""Maintain a structured working-state file for long agent sessions.

During long architect or implementation sessions, context compaction can lose
key decisions and progress. This tool maintains a structured YAML file that
captures decisions, files touched, open questions, and explicit retrieval
escalations so post-compaction recovery reads structured state instead of
re-deriving it from conversation.

The working-state file is session-scoped (not committed) and its location is
set via --state-file. Agent-agnostic — any coding agent that supports long
sessions can pass its preferred scratch location.

Usage:
    python3 scripts/kg/workstate.py --state-file /tmp/ws.yaml init --role architect --scope F0007
    python3 scripts/kg/workstate.py --state-file /tmp/ws.yaml decision "Added rationale field" --topic rationale
    python3 scripts/kg/workstate.py --state-file /tmp/ws.yaml escalate "empty lookup" --nodes entity:submission
    python3 scripts/kg/workstate.py --state-file /tmp/ws.yaml dump --compact
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from kg_common import (
    emit_telemetry,
    estimate_tokens,
    load_bundle,
    normalize_target_id,
    now_iso,
    repo_relative,
)


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def save_state(state: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(state, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
    )


def ensure_state_shape(state: dict[str, Any]) -> dict[str, Any]:
    session = state.setdefault("session", {})
    session.setdefault("run_id", None)
    session.setdefault("mode", None)
    state.setdefault("decisions", [])
    state.setdefault("files_touched", [])
    state.setdefault("open_questions", [])
    state.setdefault("escalations", [])
    return state


def resolve_run_id(state: dict[str, Any]) -> str | None:
    return state.get("session", {}).get("run_id")


def next_decision_id(state: dict[str, Any]) -> int:
    decision_ids = [
        decision["decision_id"]
        for decision in state.get("decisions", [])
        if isinstance(decision, dict) and isinstance(decision.get("decision_id"), int)
    ]
    if not decision_ids:
        return 0
    return max(decision_ids) + 1


def decision_by_id(state: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        decision["decision_id"]: decision
        for decision in state.get("decisions", [])
        if isinstance(decision, dict) and isinstance(decision.get("decision_id"), int)
    }


def transitive_superseded_ids(state: dict[str, Any]) -> set[int]:
    by_id = decision_by_id(state)
    superseded: set[int] = set()

    def collect(decision_id: int) -> None:
        decision = by_id.get(decision_id)
        if not decision:
            return
        for prior_id in decision.get("supersedes", []):
            if prior_id in superseded:
                continue
            superseded.add(prior_id)
            collect(prior_id)

    for decision in state.get("decisions", []):
        for prior_id in decision.get("supersedes", []):
            if prior_id in superseded:
                continue
            superseded.add(prior_id)
            collect(prior_id)

    return superseded


def active_decisions_for_topic(state: dict[str, Any], topic: str) -> list[dict[str, Any]]:
    superseded = transitive_superseded_ids(state)
    return [
        decision
        for decision in state.get("decisions", [])
        if decision.get("topic") == topic and decision.get("decision_id") not in superseded
    ]


def compact_state(state: dict[str, Any], *, current_view: bool = False) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "session": state.get("session", {}),
    }

    decisions = state.get("decisions", [])
    if current_view:
        superseded = transitive_superseded_ids(state)
        current_by_topic: dict[str, dict[str, Any]] = {}
        passthrough: list[dict[str, Any]] = []
        for decision in decisions:
            topic = decision.get("topic")
            decision_id = decision.get("decision_id")
            if topic is None:
                passthrough.append(decision)
                continue
            if decision_id in superseded:
                continue
            existing = current_by_topic.get(topic)
            if existing is None or decision_id > existing.get("decision_id", -1):
                current_by_topic[topic] = decision
        decisions = passthrough + sorted(
            current_by_topic.values(),
            key=lambda item: item.get("decision_id", -1),
        )

    if decisions:
        compact["decisions"] = [d["summary"] for d in decisions]

    files = state.get("files_touched", [])
    if files:
        compact["files_touched"] = [
            f"{f['path']} ({f.get('action', 'touched')})" for f in files
        ]

    open_qs = [q for q in state.get("open_questions", []) if not q.get("resolved")]
    if open_qs:
        compact["open_questions"] = [q["question"] for q in open_qs]

    resolved_qs = [q for q in state.get("open_questions", []) if q.get("resolved")]
    if resolved_qs:
        compact["resolved_questions"] = [
            f"{q['question']} -> {q.get('answer', '(resolved)')}"
            for q in resolved_qs
        ]

    escalations = state.get("escalations", [])
    if escalations:
        compact["escalations"] = [
            " | ".join(
                part
                for part in (
                    esc["reason"],
                    f"nodes={','.join(esc.get('nodes', []))}" if esc.get("nodes") else None,
                    f"opened_raw={','.join(esc.get('opened_raw', []))}" if esc.get("opened_raw") else None,
                )
                if part
            )
            for esc in escalations
        ]

    return compact


def build_digest(state: dict[str, Any]) -> dict[str, Any]:
    """A terse work-narrative for cheap session resume: what was done, decided, and next.

    Cheaper to rehydrate than `dump --compact`: files collapse to action counts + only
    the *changed* paths (not every read), decisions are the current-view actives, open
    questions are framed as "next", and escalations collapse to a count. Complements
    `dump` (full structured state) — this is the narrative, not the replay.
    """
    state = ensure_state_shape(state)
    session = state.get("session", {})
    header = {
        key: session[key]
        for key in ("role", "scope", "scope_label", "mode", "run_id", "started")
        if session.get(key) is not None
    }

    action_counts: dict[str, int] = {}
    changed: list[str] = []
    for entry in state.get("files_touched", []):
        action = entry.get("action", "touched")
        action_counts[action] = action_counts.get(action, 0) + 1
        if action in ("modified", "created"):
            changed.append(entry["path"])

    active = compact_state(state, current_view=True).get("decisions", [])
    next_up = [q["question"] for q in state.get("open_questions", []) if not q.get("resolved")]
    escalations = state.get("escalations", [])

    digest: dict[str, Any] = {"session": header}
    done: dict[str, Any] = {}
    if action_counts:
        done["files"] = action_counts
    if changed:
        done["changed"] = changed
    if done:
        digest["done"] = done
    if active:
        digest["decided"] = active
    if next_up:
        digest["next"] = next_up
    if escalations:
        digest["escalations"] = len(escalations)
    return digest


def emit_workstate_event(
    telemetry_file: Path | None,
    state: dict[str, Any],
    tool: str,
    payload: dict[str, Any],
) -> None:
    event = {
        **payload,
        "tokens_estimated": estimate_tokens(payload),
    }
    emit_telemetry(telemetry_file, resolve_run_id(state), tool, event)


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new working-state file for a session."""
    sf = Path(args.state_file)
    if sf.exists() and not args.force:
        print(
            f"Working state already exists at {sf}. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    state: dict[str, Any] = ensure_state_shape(
        {
            "session": {
                "started": now_iso(),
                "role": args.role,
                "scope": args.scope,
                "run_id": args.run_id,
                "mode": args.mode,
            },
        }
    )

    if args.scope:
        try:
            bundle = load_bundle()
            target_id = normalize_target_id(args.scope)
            node = bundle["all_nodes"].get(target_id)
            if node:
                state["session"]["scope_label"] = node.get("label", args.scope)
                state["session"]["scope_id"] = target_id
        except SystemExit:
            pass

    save_state(state, sf)
    print(f"Initialized working state: {sf}")
    return 0


def cmd_decision(args: argparse.Namespace) -> int:
    """Record a decision made during the session."""
    sf = Path(args.state_file)
    state = ensure_state_shape(load_state(sf))
    if not state.get("session"):
        print("No working state. Run 'init' first.", file=sys.stderr)
        return 1

    if args.topic is None:
        print(
            "Deprecation warning: workstate.py decision should include --topic for supersession-aware history.",
            file=sys.stderr,
        )

    if args.topic:
        active = active_decisions_for_topic(state, args.topic)
        active_ids = {decision["decision_id"] for decision in active}
        superseding = set(args.supersedes or [])
        unresolved = sorted(active_ids - superseding)
        if unresolved:
            print(
                f"Warning: decision #{unresolved[0]} on topic '{args.topic}' is already active; pass --supersedes to replace.",
                file=sys.stderr,
            )

    entry: dict[str, Any] = {
        "decision_id": next_decision_id(state),
        "timestamp": now_iso(),
        "summary": args.summary,
        "topic": args.topic,
        "supersedes": list(args.supersedes or []),
    }
    if args.files:
        entry["files_affected"] = [repo_relative(f) for f in args.files]
    if args.rationale:
        entry["rationale"] = args.rationale

    state.setdefault("decisions", []).append(entry)
    save_state(state, sf)
    emit_workstate_event(
        args.telemetry_file,
        state,
        "workstate-decision",
        {
            "decision_id": entry["decision_id"],
            "summary": args.summary,
            "topic": args.topic,
            "supersedes": entry["supersedes"],
            "files_affected": entry.get("files_affected", []),
            "empty_scope": False,
            "ambiguous_count": 0,
            "hint_emitted": False,
            "confidence_band": "high",
        },
    )
    print(f"Decision #{entry['decision_id']} recorded.")
    return 0


def cmd_touch(args: argparse.Namespace) -> int:
    """Record a file that was read or modified."""
    sf = Path(args.state_file)
    state = ensure_state_shape(load_state(sf))
    if not state.get("session"):
        print("No working state. Run 'init' first.", file=sys.stderr)
        return 1

    rel_path = repo_relative(args.path)
    action = args.action or "modified"

    touched = state.setdefault("files_touched", [])
    for entry in touched:
        if entry["path"] == rel_path:
            if entry.get("action") != action:
                entry["action"] = action
                entry["last_touched"] = now_iso()
                save_state(state, sf)
                print(f"Updated {rel_path} -> {action}")
            else:
                entry["last_touched"] = now_iso()
                save_state(state, sf)
                print(f"Refreshed {rel_path}")
            return 0

    touched.append(
        {
            "path": rel_path,
            "action": action,
            "first_touched": now_iso(),
        }
    )
    save_state(state, sf)
    print(f"Tracked {rel_path} ({action})")
    return 0


def cmd_question(args: argparse.Namespace) -> int:
    """Record an open question or blocker."""
    sf = Path(args.state_file)
    state = ensure_state_shape(load_state(sf))
    if not state.get("session"):
        print("No working state. Run 'init' first.", file=sys.stderr)
        return 1

    entry: dict[str, Any] = {
        "question": args.text,
        "added": now_iso(),
        "resolved": False,
    }
    if args.context:
        entry["context"] = args.context

    questions = state.setdefault("open_questions", [])
    questions.append(entry)
    save_state(state, sf)
    idx = len(questions) - 1
    print(f"Question #{idx} recorded.")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    """Mark an open question as resolved."""
    sf = Path(args.state_file)
    state = ensure_state_shape(load_state(sf))
    if not state.get("session"):
        print("No working state. Run 'init' first.", file=sys.stderr)
        return 1

    questions = state.get("open_questions", [])
    if args.index >= len(questions):
        print(f"Question #{args.index} does not exist (have {len(questions)}).", file=sys.stderr)
        return 1

    questions[args.index]["resolved"] = True
    questions[args.index]["resolved_at"] = now_iso()
    if args.answer:
        questions[args.index]["answer"] = args.answer
    save_state(state, sf)
    print(f"Question #{args.index} resolved.")
    return 0


def cmd_escalate(args: argparse.Namespace) -> int:
    """Record an explicit insufficient-context escalation."""
    sf = Path(args.state_file)
    state = ensure_state_shape(load_state(sf))
    if not state.get("session"):
        print("No working state. Run 'init' first.", file=sys.stderr)
        return 1

    entry = {
        "timestamp": now_iso(),
        "reason": args.reason,
        "nodes": list(args.nodes or []),
        "opened_raw": [repo_relative(path) for path in (args.opened_raw or [])],
    }
    state.setdefault("escalations", []).append(entry)
    save_state(state, sf)
    emit_workstate_event(
        args.telemetry_file,
        state,
        "workstate-escalate",
        {
            "reason": args.reason,
            "nodes_returned": entry["nodes"],
            "nodes_count": len(entry["nodes"]),
            "opened_raw": entry["opened_raw"],
            "empty_scope": False,
            "ambiguous_count": len(entry["nodes"]),
            "hint_emitted": False,
            "confidence_band": "ambiguous",
        },
    )
    print(f"Escalation recorded: {args.reason}")
    return 0


def cmd_dump(args: argparse.Namespace) -> int:
    """Dump working state for context recovery."""
    sf = Path(args.state_file)
    state = ensure_state_shape(load_state(sf))
    if not state.get("session"):
        print("No working state found.", file=sys.stderr)
        return 1

    if args.current_view:
        state = compact_state(state, current_view=True)
    elif args.compact:
        state = compact_state(state, current_view=False)

    if args.json:
        json.dump(state, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        yaml.safe_dump(state, sys.stdout, sort_keys=False, allow_unicode=True, width=120)

    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    """Print a terse work-narrative digest (done/decided/next) for cheap session resume."""
    sf = Path(args.state_file)
    state = ensure_state_shape(load_state(sf))
    if not state.get("session"):
        print("No working state found.", file=sys.stderr)
        return 1
    digest = build_digest(state)
    if args.json:
        json.dump(digest, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        yaml.safe_dump(digest, sys.stdout, sort_keys=False, allow_unicode=True, width=120)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Maintain structured working state for long agent sessions."
    )
    parser.add_argument(
        "--state-file",
        required=True,
        help="Path to the working-state YAML file. Agent-agnostic — each tool passes its own scratch location.",
    )
    parser.add_argument(
        "--telemetry-file",
        type=Path,
        default=None,
        help="Append one JSONL telemetry event for decision and escalate invocations.",
    )
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize a new working-state file.")
    p_init.add_argument("--role", required=True, help="Agent role (architect, product-manager, etc.).")
    p_init.add_argument("--scope", default=None, help="Feature or story ID (e.g. F0007, F0007-S0003).")
    p_init.add_argument("--run-id", default=None, help="Correlation ID for the session.")
    p_init.add_argument("--mode", default=None, help="Execution mode such as clean, greenfield, or drift-reconcile.")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing state.")

    p_dec = sub.add_parser("decision", help="Record a decision.")
    p_dec.add_argument("summary", help="One-line decision summary.")
    p_dec.add_argument("--files", nargs="*", help="Files affected by this decision.")
    p_dec.add_argument("--rationale", help="Brief rationale for the decision.")
    p_dec.add_argument("--topic", default=None, help="Decision topic slug used for supersession-aware views.")
    p_dec.add_argument(
        "--supersedes",
        nargs="*",
        type=int,
        default=None,
        help="Prior decision_id values explicitly replaced by this decision.",
    )

    p_touch = sub.add_parser("touch", help="Record a file read or modified.")
    p_touch.add_argument("path", help="File path.")
    p_touch.add_argument("--action", choices=["read", "modified", "created", "deleted"], default="modified")

    p_q = sub.add_parser("question", help="Record an open question.")
    p_q.add_argument("text", help="The question.")
    p_q.add_argument("--context", help="Additional context.")

    p_res = sub.add_parser("resolve", help="Mark a question as resolved.")
    p_res.add_argument("index", type=int, help="Question index (from dump output).")
    p_res.add_argument("--answer", help="Resolution answer.")

    p_esc = sub.add_parser("escalate", help="Record an explicit insufficient-context escalation.")
    p_esc.add_argument("reason", help="Reason for escalation.")
    p_esc.add_argument("--nodes", nargs="*", help="Node IDs that triggered the escalation.")
    p_esc.add_argument("--opened-raw", nargs="*", help="Raw artifact paths opened during the escalation.")

    p_dump = sub.add_parser("dump", help="Dump working state.")
    p_dump.add_argument("--compact", action="store_true", help="Compact format for post-compaction recovery.")
    p_dump.add_argument(
        "--current-view",
        action="store_true",
        help="Compact current-view projection with superseded topic decisions filtered out.",
    )
    p_dump.add_argument("--json", action="store_true", help="Output as JSON instead of YAML.")

    p_digest = sub.add_parser("digest", help="Terse work-narrative for cheap resume (done/decided/next).")
    p_digest.add_argument("--json", action="store_true", help="Output as JSON instead of YAML.")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    handlers = {
        "init": cmd_init,
        "decision": cmd_decision,
        "touch": cmd_touch,
        "question": cmd_question,
        "resolve": cmd_resolve,
        "escalate": cmd_escalate,
        "dump": cmd_dump,
        "digest": cmd_digest,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())

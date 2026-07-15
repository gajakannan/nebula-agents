#!/usr/bin/env python3
"""Tool-agnostic harness usage ingestion + cache-cost metrics for KG telemetry.

The durable interface is the **normalized turn event** (below) and the
`ingest`/`report` CLI — not any one harness. Reading a given harness's raw usage
is the only harness-specific step, so it is isolated behind a small *source
adapter* registry (`SOURCE_ADAPTERS`); nothing else in this module is
harness-aware. Any tool that can emit the normalized event uses the `jsonl`
adapter and needs no native parser at all. (This realizes the KG-MCP-PLAN Phase 3
adapter principle for the usage feed: neutral contract + per-harness adapter, with
a manual/CI fallback that works for every harness.)

Ingestion is an explicit command (run it manually or from CI) — there is no
harness-specific auto-trigger. A harness that offers its own post-run hook may
call `ingest --source <name> ...`, but that wiring lives in the harness, never here.

Normalized turn event (the contract every adapter targets):
  {"tool": "turn", "source": "harness", "harness": "<tool>", "session_id", "msg_id",
   "ts", "model", "is_sidechain",
   "payload": {"input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"}}

Standalone (no git walk, unlike eval.py):
  ingest  — normalize a harness usage feed -> planning-mds/operations/telemetry/usage.jsonl
  report  — cache-hit ratio, cost-per-turn, cache-write spikes from those events

eval.py imports cache_metrics() to fold the same numbers into its unified report.
This is the measurement half of KG-MCP-PLAN Phase 2.1, pulled ahead of Phase 1 so
MCP retrieval can be validated against a real prompt-cache-cost baseline (the KG
CLIs only measure retrieval *payload* size, never the model's prompt cache).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable

from kg_common import REPO_ROOT, now_iso

# Committed operations telemetry — the durable, diffable usage/cost stream.
USAGE_PATH = REPO_ROOT / "planning-mds" / "operations" / "telemetry" / "usage.jsonl"

# Cost weights in input-token-equivalent units (model-agnostic; not dollars).
# Anthropic 5-min prompt cache: write 1.25x, read 0.1x base input. Output ~5x.
WEIGHT_INPUT, WEIGHT_CACHE_WRITE, WEIGHT_CACHE_READ, WEIGHT_OUTPUT = 1.0, 1.25, 0.1, 5.0
SPIKE_FACTOR = 5.0  # flag turns whose cost >= factor x median turn cost


@dataclass
class Turn:
    session_id: str
    msg_id: str
    ts: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    is_sidechain: bool
    harness: str = "unknown"  # which tool produced this turn (claude-code, codex, ...)

    @property
    def cost(self) -> float:
        return (self.input_tokens * WEIGHT_INPUT
                + self.cache_write_tokens * WEIGHT_CACHE_WRITE
                + self.cache_read_tokens * WEIGHT_CACHE_READ
                + self.output_tokens * WEIGHT_OUTPUT)

    @property
    def prefix_input(self) -> int:  # input-side only; cache-hit denominator basis
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    @property
    def write_share(self) -> float:
        return (self.cache_write_tokens / self.prefix_input) if self.prefix_input else 0.0


# ---------- normalized event <-> Turn (the tool-agnostic contract) ----------

def turn_to_event(turn: Turn) -> dict[str, Any]:
    """Serialize a Turn to the normalized event written to usage.jsonl."""
    return {
        "ts": turn.ts or now_iso(), "source": "harness", "harness": turn.harness,
        "session_id": turn.session_id, "msg_id": turn.msg_id, "model": turn.model,
        "is_sidechain": turn.is_sidechain, "tool": "turn",
        "payload": {
            "input_tokens": turn.input_tokens, "output_tokens": turn.output_tokens,
            "cache_read_tokens": turn.cache_read_tokens,
            "cache_write_tokens": turn.cache_write_tokens,
        },
    }


def _turn_from_event(event: dict[str, Any]) -> Turn | None:
    if event.get("tool") != "turn":
        return None
    p = event.get("payload") or {}
    return Turn(
        session_id=event.get("session_id", ""), msg_id=event.get("msg_id", ""),
        ts=event.get("ts"), model=event.get("model"),
        input_tokens=int(p.get("input_tokens", 0) or 0),
        output_tokens=int(p.get("output_tokens", 0) or 0),
        cache_read_tokens=int(p.get("cache_read_tokens", 0) or 0),
        cache_write_tokens=int(p.get("cache_write_tokens", 0) or 0),
        is_sidechain=bool(event.get("is_sidechain", False)),
        harness=event.get("harness", "unknown"),
    )


# ---------- source adapters: a harness's raw usage feed -> normalized Turns ----------
# Add support for a new harness by registering ONE function here. Everything else —
# dedup, metrics, eval.py wiring, the CLI — is harness-neutral. Feed locations are
# never auto-resolved; the operator/CI passes --input/--input-dir explicitly. A harness
# that can already emit the normalized event uses the "jsonl" adapter (no native parser).

def parse_claude_transcript_text(text: str) -> list[Turn]:
    """Adapter: Claude Code session transcript (.jsonl) -> Turns."""
    turns: list[Turn] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("type") != "assistant":
            continue
        message = rec.get("message") or {}
        usage = message.get("usage")
        if not usage:
            continue
        msg_id = message.get("id") or rec.get("uuid") or ""
        if msg_id in seen:        # streaming repeats a message id; dedupe (first wins)
            continue
        seen.add(msg_id)
        turns.append(Turn(
            session_id=rec.get("sessionId") or "",
            msg_id=msg_id,
            ts=rec.get("timestamp"),
            model=message.get("model"),
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            cache_read_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
            cache_write_tokens=int(usage.get("cache_creation_input_tokens", 0) or 0),
            is_sidechain=bool(rec.get("isSidechain", False)),
            harness="claude-code",
        ))
    return turns


def parse_normalized_jsonl_text(text: str) -> list[Turn]:
    """Adapter: pre-normalized turn events — the tool-agnostic feed any harness can emit."""
    turns: list[Turn] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        turn = _turn_from_event(rec)
        if turn is None or turn.msg_id in seen:
            continue
        seen.add(turn.msg_id)
        turns.append(turn)
    return turns


def parse_codex_rollout_text(text: str) -> list[Turn]:
    """Adapter: Codex session rollout (.jsonl) -> Turns.

    Per-turn usage is in `event_msg`/`token_count` records: `info.last_token_usage`
    is the per-turn delta (`info.total_token_usage` is the running sum — we use last).
    Codex `input_tokens` is the *total* input incl. the cached portion, so we split it:
    `cache_read = cached_input_tokens`, `input = input_tokens - cached`. OpenAI caching
    has no write premium, so `cache_write = 0`. `output_tokens` already includes
    reasoning tokens. Turn id = `<session id>:<token_count ordinal>` (stable on re-ingest).
    """
    session_id = ""
    model = None
    turns: list[Turn] = []
    tc_index = -1
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        rtype = rec.get("type")
        if rtype == "session_meta":
            meta = rec.get("payload") or rec
            session_id = meta.get("id") or session_id
            model = meta.get("model") or model
            continue
        if rtype != "event_msg":
            continue
        payload = rec.get("payload") or {}
        if payload.get("type") != "token_count":
            continue
        tc_index += 1
        last = (payload.get("info") or {}).get("last_token_usage") or {}
        total_in = int(last.get("input_tokens", 0) or 0)
        out = int(last.get("output_tokens", 0) or 0)
        cached = int(last.get("cached_input_tokens", 0) or 0)
        if total_in == 0 and out == 0:        # no usage recorded for this tick
            continue
        turns.append(Turn(
            session_id=session_id,
            msg_id=f"{session_id or 'codex'}:{tc_index}",
            ts=rec.get("timestamp"),
            model=model,
            input_tokens=max(0, total_in - cached),   # uncached input only
            output_tokens=out,                         # includes reasoning tokens
            cache_read_tokens=cached,
            cache_write_tokens=0,                      # OpenAI caching has no write cost
            is_sidechain=False,
            harness="codex",
        ))
    return turns


# name -> adapter. `jsonl` is the lowest-common-denominator path for any harness.
SOURCE_ADAPTERS: dict[str, Callable[[str], list[Turn]]] = {
    "claude-code": parse_claude_transcript_text,
    "codex": parse_codex_rollout_text,
    "jsonl": parse_normalized_jsonl_text,
}


def parse_claude_transcript(path: Path) -> list[Turn]:
    """Helper: parse a Claude transcript FILE (fills session_id from the filename)."""
    turns = parse_claude_transcript_text(_read_text(Path(path)))
    stem = Path(path).stem
    for turn in turns:
        if not turn.session_id:
            turn.session_id = stem
    return turns


# ---------- ingestion (harness-neutral) ----------

def _read_text(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def _append_turns(turns: Iterable[Turn], out_path: Path = USAGE_PATH) -> int:
    """Append normalized events for new turns. Idempotent: cross-run dedup by msg_id."""
    existing: set[str] = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(json.loads(line).get("msg_id", ""))
            except json.JSONDecodeError:
                continue
    written = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as fh:
        for turn in turns:
            if turn.msg_id in existing:
                continue
            existing.add(turn.msg_id)
            fh.write(json.dumps(turn_to_event(turn), ensure_ascii=False) + "\n")
            written += 1
    return written


def ingest(inputs: Iterable[Path], *, source: str, out_path: Path = USAGE_PATH) -> int:
    """Ingest one or more feed files using the named source adapter."""
    parser = SOURCE_ADAPTERS[source]
    turns: list[Turn] = []
    for path in inputs:
        turns.extend(parser(_read_text(Path(path))))
    return _append_turns(turns, out_path)


def ingest_text(text: str, *, source: str, out_path: Path = USAGE_PATH) -> int:
    """Ingest a feed passed as text (e.g. piped on stdin) using the named source adapter."""
    return _append_turns(SOURCE_ADAPTERS[source](text), out_path)


# ---------- metrics (importable by eval.py; fully harness-neutral) ----------

def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * pct))))]


def cache_metrics(events: list[dict[str, Any]], spike_factor: float = SPIKE_FACTOR) -> dict[str, Any]:
    turns = [t for t in (_turn_from_event(e) for e in events) if t is not None]
    if not turns:
        return {"turns": 0, "cache_hit_ratio": None,
                "cost_per_turn": {"mean": None, "p50": None, "p95": None},
                "cache_write_spikes": []}

    total_read = sum(t.cache_read_tokens for t in turns)
    total_write = sum(t.cache_write_tokens for t in turns)
    total_input = sum(t.input_tokens for t in turns)
    denom = total_read + total_write + total_input
    cache_hit_ratio = (total_read / denom) if denom else None

    costs = [t.cost for t in turns]
    med = median(costs)
    spikes = sorted(
        ({"session_id": t.session_id, "msg_id": t.msg_id, "ts": t.ts,
          "harness": t.harness,
          "cost": round(t.cost, 1), "x_median": round(t.cost / med, 1) if med else None,
          "write_share": round(t.write_share, 3),
          "cache_write_tokens": t.cache_write_tokens, "is_sidechain": t.is_sidechain}
         for t in turns if med and t.cost >= spike_factor * med),
        key=lambda s: s["cost"], reverse=True,
    )
    return {
        "turns": len(turns),
        "cache_hit_ratio": round(cache_hit_ratio, 4) if cache_hit_ratio is not None else None,
        "cost_per_turn": {"mean": round(sum(costs) / len(costs), 1),
                          "p50": round(med, 1), "p95": round(percentile(costs, 0.95), 1)},
        "cost_unit": "input-token-equivalents",
        "weights": {"input": WEIGHT_INPUT, "cache_write": WEIGHT_CACHE_WRITE,
                    "cache_read": WEIGHT_CACHE_READ, "output": WEIGHT_OUTPUT},
        "cache_write_spikes": spikes,
    }


def _load_usage_events(path: Path = USAGE_PATH) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


# ---------- §13.3 context budget (gate-time check) ----------
# Loaded input (tier1+tier2) should fit ~70% of the window, leaving ~30% for output.
DEFAULT_CONTEXT_WINDOW = 200_000  # input-token-equivalents; override per model
OUTPUT_RESERVE = 0.30


def latest_loaded_tokens(events: list[dict[str, Any]]) -> int | None:
    """The most recent turn's input-side prefix (input + cache_read + cache_write) — a
    proxy for 'how full is the context right now', read from the harness usage stream."""
    turns = [t for t in (_turn_from_event(e) for e in events) if t is not None]
    if not turns:
        return None
    return max(turns, key=lambda t: (t.ts or "")).prefix_input


def budget_status(loaded_tokens: int, window: int = DEFAULT_CONTEXT_WINDOW,
                  reserve: float = OUTPUT_RESERVE) -> dict[str, Any]:
    """Check loaded input against the §13.3 budget: ok | warn (>=90% of budget) | over."""
    input_budget = int(window * (1 - reserve))
    utilization = round(loaded_tokens / input_budget, 3) if input_budget else None
    if input_budget and loaded_tokens > input_budget:
        status = "over"
    elif utilization is not None and utilization >= 0.9:
        status = "warn"
    else:
        status = "ok"
    return {"window": window, "reserve": reserve, "input_budget": input_budget,
            "loaded_tokens": loaded_tokens, "headroom": input_budget - loaded_tokens,
            "utilization": utilization, "status": status}


def main() -> int:
    ap = argparse.ArgumentParser(description="Tool-agnostic harness-usage ingestion + cache metrics.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ing = sub.add_parser("ingest", help="Normalize a harness usage feed into .kg-state/usage.jsonl")
    ing.add_argument("--source", choices=sorted(SOURCE_ADAPTERS), required=True,
                     help="Source adapter for the raw feed. 'jsonl' = pre-normalized turn "
                          "events any tool can emit (the tool-agnostic path).")
    ing.add_argument("--input", action="append", default=[], help="Feed file (repeatable).")
    ing.add_argument("--input-dir", default=None, help="Directory of *.jsonl feed files (searched recursively).")
    ing.add_argument("--stdin", action="store_true", help="Read the feed from stdin.")

    rep = sub.add_parser("report", help="Print cache metrics from .kg-state/usage.jsonl")
    rep.add_argument("--json", action="store_true")
    rep.add_argument("--spike-factor", type=float, default=SPIKE_FACTOR)
    bud = sub.add_parser("budget", help="Check loaded context against the §13.3 70/30 budget (exit 1 if over)")
    bud.add_argument("--window", type=int, default=DEFAULT_CONTEXT_WINDOW, help="Context window (input-token-equivalents).")
    bud.add_argument("--reserve", type=float, default=OUTPUT_RESERVE, help="Fraction reserved for output (default 0.30).")
    bud.add_argument("--loaded", type=int, default=None, help="Loaded input tokens (default: latest turn from usage.jsonl).")
    bud.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.cmd == "ingest":
        if args.stdin:
            print(f"ingested {ingest_text(sys.stdin.read(), source=args.source)} "
                  f"new turn event(s) -> {USAGE_PATH}")
            return 0
        inputs = [Path(p) for p in args.input]
        if not inputs and args.input_dir:
            d = Path(args.input_dir)
            if d.is_dir():
                inputs = sorted(d.rglob("*.jsonl"))
        if not inputs:
            print("no feed found — pass --input FILE, --input-dir DIR, or --stdin. "
                  "Point --input-dir at the harness's own session dir (e.g. "
                  "~/.codex/sessions or ~/.claude/projects/<slug>); locations are not "
                  "auto-resolved.", flush=True)
            return 1
        print(f"ingested {ingest(inputs, source=args.source)} new turn event(s) -> {USAGE_PATH}")
        return 0

    if args.cmd == "budget":
        loaded = args.loaded if args.loaded is not None else latest_loaded_tokens(_load_usage_events())
        if loaded is None:
            print("no loaded-token figure — pass --loaded or ingest harness usage first", flush=True)
            return 1
        status = budget_status(loaded, window=args.window, reserve=args.reserve)
        if args.json:
            json.dump(status, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            print(f"budget: {status['status'].upper()}  loaded={status['loaded_tokens']} / "
                  f"{status['input_budget']} input-budget ({status['utilization']}x)  "
                  f"window={status['window']}, reserve={status['reserve']}")
        return 1 if status["status"] == "over" else 0

    m = cache_metrics(_load_usage_events(), spike_factor=args.spike_factor)
    if args.json:
        json.dump(m, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    print(f"turns={m['turns']}  cache_hit_ratio={m['cache_hit_ratio']}  "
          f"cost/turn mean={m['cost_per_turn']['mean']} p95={m['cost_per_turn']['p95']} "
          f"({m.get('cost_unit', 'input-token-equivalents')})")
    for s in m["cache_write_spikes"]:
        print(f"  SPIKE {s['x_median']}x median  cost={s['cost']}  harness={s.get('harness')}  "
              f"write_share={s['write_share']}  sidechain={s['is_sidechain']}  {s['ts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

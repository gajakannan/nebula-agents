#!/usr/bin/env python3
"""Capture agent-CLI token telemetry into an evidence run folder.

Both Codex and Claude Code already record per-turn token accounting in local
JSONL session transcripts. Neither number reaches the evidence package, so a
run's cost is invisible after the fact. This script resolves the session that
produced a run, normalizes the two vendors' differing usage shapes, and writes
`token-usage.json` next to `gate-state.json` in the run folder.

The two vendors do not agree on what `input_tokens` means:

  Codex        input_tokens INCLUDES cached_input_tokens (it is the whole
               context fed to the model that turn).
  Claude Code  input_tokens EXCLUDES cache reads and cache creation; the whole
               context is input + cache_read + cache_creation.

Everything below is normalized to `context_tokens` (total fed to the model) and
`uncached_input_tokens` (the full-price portion), so the two are comparable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _product_root import add_product_root_arg, resolve_product_root  # noqa: E402


SCHEMA_VERSION = 1
ARTIFACT_NAME = "token-usage.json"
DEFAULT_CODEX_ROOT = Path.home() / ".codex" / "sessions"
DEFAULT_CLAUDE_ROOT = Path.home() / ".claude" / "projects"
# Anchored at the start of the command so that greps and docs *mentioning*
# run-gate.py do not register as gate boundaries; the stage must be a real
# gate id (G0, B4.5, FR2) rather than any bare token.
GATE_STAGE_RE = re.compile(
    r"^(?:python3?\s+)?[^\s'\"]*run-gate\.py\s.*?--stage\s+([A-Z]+\d+(?:\.\d+)?)\b"
)


class TelemetryError(ValueError):
    """Raised when telemetry cannot be captured for a run."""


@dataclass
class Turn:
    """One model turn, normalized across vendors.

    Fields typed ``int | None`` are None when the vendor does not report them at
    all. That is deliberately distinct from a measured zero: reading 0 as "no
    cache writes" or "no reasoning" would understate cost.
    """

    timestamp: datetime
    context_tokens: int
    uncached_input_tokens: int
    cached_input_tokens: int
    # 1h cache writes bill at a higher multiple than 5m writes, so the split is
    # cost-bearing and must not be collapsed into the total alone.
    cache_creation_input_tokens: int | None
    cache_creation_1h_input_tokens: int | None
    cache_creation_5m_input_tokens: int | None
    output_tokens: int
    reasoning_output_tokens: int | None


@dataclass
class Session:
    path: Path
    tool: str
    cwd: str | None
    turns: list[Turn] = field(default_factory=list)
    compactions: int = 0
    models: list[str] = field(default_factory=list)
    sidechain_turns: int = 0  # Claude Code subagent turns; always 0 for Codex.

    @property
    def start(self) -> datetime | None:
        return self.turns[0].timestamp if self.turns else None

    @property
    def end(self) -> datetime | None:
        return self.turns[-1].timestamp if self.turns else None


def _parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    value = raw.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def read_codex_session(path: Path) -> Session:
    """Read a Codex `rollout-*.jsonl` transcript.

    Per-turn usage lives at payload.info.last_token_usage on `token_count`
    events. Codex's cumulative total_token_usage equals the sum of the per-turn
    records, so summing here is safe and keeps turn-level granularity.
    """
    session = Session(path=path, tool="codex", cwd=None)
    for record in _iter_jsonl(path):
        rtype = record.get("type")
        payload = record.get("payload") or {}

        if rtype == "session_meta":
            session.cwd = payload.get("cwd")
            continue
        if rtype == "compacted":
            session.compactions += 1
            continue
        if rtype == "turn_context":
            model = payload.get("model")
            if model and model not in session.models:
                session.models.append(model)
            continue

        usage = (payload.get("info") or {}).get("last_token_usage")
        if not isinstance(usage, dict):
            continue
        timestamp = _parse_ts(record.get("timestamp", ""))
        if timestamp is None:
            continue

        total_input = int(usage.get("input_tokens", 0) or 0)
        cached = int(usage.get("cached_input_tokens", 0) or 0)
        session.turns.append(
            Turn(
                timestamp=timestamp,
                # Codex input_tokens is already the full context for the turn.
                context_tokens=total_input,
                uncached_input_tokens=max(total_input - cached, 0),
                cached_input_tokens=cached,
                # Codex reports no cache-write field at all — None, not 0.
                cache_creation_input_tokens=None,
                cache_creation_1h_input_tokens=None,
                cache_creation_5m_input_tokens=None,
                output_tokens=int(usage.get("output_tokens", 0) or 0),
                reasoning_output_tokens=int(usage.get("reasoning_output_tokens", 0) or 0),
            )
        )
    session.turns.sort(key=lambda turn: turn.timestamp)
    return session


def read_claude_session(path: Path) -> Session:
    """Read a Claude Code project transcript.

    One assistant message is split across several JSONL lines (thinking, text,
    tool_use ...) that each repeat an identical `usage` object. Summing raw
    lines overcounts badly, so entries are deduplicated by message id.
    """
    session = Session(path=path, tool="claude-code", cwd=None)
    seen: dict[str, Turn] = {}
    ordered: list[str] = []
    sidechain_turns = 0

    for record in _iter_jsonl(path):
        if session.cwd is None and record.get("cwd"):
            session.cwd = record.get("cwd")
        if record.get("isCompactSummary") or record.get("subtype") == "compact_boundary":
            session.compactions += 1

        message = record.get("message") or {}
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        timestamp = _parse_ts(record.get("timestamp", ""))
        if timestamp is None:
            continue

        model = message.get("model")
        if model and model not in session.models:
            session.models.append(model)

        uncached = int(usage.get("input_tokens", 0) or 0)
        cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
        cache_creation = int(usage.get("cache_creation_input_tokens", 0) or 0)
        # The per-TTL split drives cost: 1h writes bill at a higher multiple
        # than 5m writes. Absent on older transcripts, hence the .get default.
        breakdown = usage.get("cache_creation") or {}
        turn = Turn(
            timestamp=timestamp,
            # Claude input_tokens excludes cache; the real context is the sum.
            context_tokens=uncached + cache_read + cache_creation,
            uncached_input_tokens=uncached,
            cached_input_tokens=cache_read,
            cache_creation_input_tokens=cache_creation,
            cache_creation_1h_input_tokens=int(breakdown.get("ephemeral_1h_input_tokens", 0) or 0),
            cache_creation_5m_input_tokens=int(breakdown.get("ephemeral_5m_input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            # Thinking is billed inside output_tokens and never broken out.
            reasoning_output_tokens=None,
        )

        key = message.get("id") or f"_line{len(ordered)}"
        if key not in seen:
            ordered.append(key)
            if record.get("isSidechain"):
                sidechain_turns += 1
        seen[key] = turn

    session.turns = sorted((seen[key] for key in ordered), key=lambda turn: turn.timestamp)
    session.sidechain_turns = sidechain_turns
    return session


def discover_sessions(codex_root: Path, claude_root: Path, tool: str) -> list[Path]:
    candidates: list[Path] = []
    if tool in ("auto", "codex") and codex_root.is_dir():
        candidates.extend(sorted(codex_root.rglob("rollout-*.jsonl")))
    if tool in ("auto", "claude-code") and claude_root.is_dir():
        candidates.extend(sorted(claude_root.glob("*/*.jsonl")))
    return candidates


def load_session(path: Path) -> Session:
    name = path.name
    if name.startswith("rollout-"):
        return read_codex_session(path)
    return read_claude_session(path)


def _overlap_seconds(a_start, a_end, b_start, b_end) -> float:
    latest_start = max(a_start, b_start)
    earliest_end = min(a_end, b_end)
    return max((earliest_end - latest_start).total_seconds(), 0.0)


def run_window(run_folder: Path) -> tuple[datetime, datetime]:
    """Derive a run's time window from commands.log, falling back to mtimes."""
    log_path = run_folder / "commands.log"
    stamps: list[datetime] = []
    if log_path.is_file():
        for record in _iter_jsonl(log_path):
            parsed = _parse_ts(record.get("timestamp", ""))
            if parsed:
                stamps.append(parsed)
    if stamps:
        return min(stamps), max(stamps)

    manifest = run_folder / "evidence-manifest.json"
    start_src = manifest if manifest.is_file() else run_folder
    start = datetime.fromtimestamp(start_src.stat().st_mtime, tz=timezone.utc)
    end = datetime.fromtimestamp(run_folder.stat().st_mtime, tz=timezone.utc)
    return min(start, end), max(start, end)


def select_session(
    candidates: list[Path], window: tuple[datetime, datetime]
) -> tuple[Session, float]:
    """Pick the session whose turns overlap the run window the most."""
    best: tuple[Session, float] | None = None
    for path in candidates:
        try:
            session = load_session(path)
        except OSError:
            continue
        if not session.turns:
            continue
        overlap = _overlap_seconds(session.start, session.end, window[0], window[1])
        if overlap <= 0:
            continue
        best_so_far = best[1] if best else -1.0
        if overlap > best_so_far:
            best = (session, overlap)
    if best is None:
        raise TelemetryError(
            "no agent session transcript overlaps this run's time window; "
            "pass --session to name one explicitly"
        )
    return best


def gate_phases(run_folder: Path, turns: list[Turn]) -> list[dict[str, object]]:
    """Attribute turns to the gate they were working toward.

    Gate boundaries come from run-gate.py invocations in commands.log; turns
    between one gate and the next are the cost of reaching that next gate.
    """
    log_path = run_folder / "commands.log"
    if not log_path.is_file():
        return []

    boundaries: list[tuple[datetime, str]] = []
    for record in _iter_jsonl(log_path):
        command = record.get("command", "")
        match = GATE_STAGE_RE.search(command)
        if not match:
            continue
        parsed = _parse_ts(record.get("timestamp", ""))
        if parsed:
            boundaries.append((parsed, match.group(1)))
    if not boundaries:
        return []
    boundaries.sort(key=lambda item: item[0])

    phases: list[dict[str, object]] = []
    cursor = turns[0].timestamp if turns else None
    for stamp, stage in boundaries:
        window_turns = [t for t in turns if cursor is not None and cursor <= t.timestamp <= stamp]
        if window_turns:
            phases.append({"gate": stage, "reached_at": stamp.isoformat(), **_totals(window_turns)})
        cursor = stamp

    trailing = [t for t in turns if cursor is not None and t.timestamp > cursor]
    if trailing:
        phases.append({"gate": "post-final-gate", "reached_at": None, **_totals(trailing)})
    return phases


def _sum_optional(values: list[int | None]) -> int | None:
    """Sum reported values, or None when the vendor reports none of them.

    Summing None as 0 would turn "this vendor does not measure it" into a
    measured zero, which is exactly the distinction this field exists to keep.
    """
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _totals(turns: list[Turn]) -> dict[str, object]:
    context = sum(t.context_tokens for t in turns)
    cached = sum(t.cached_input_tokens for t in turns)
    uncached = sum(t.uncached_input_tokens for t in turns)
    output = sum(t.output_tokens for t in turns)
    return {
        "turns": len(turns),
        "context_tokens": context,
        "uncached_input_tokens": uncached,
        "cached_input_tokens": cached,
        "cache_creation_input_tokens": _sum_optional(
            [t.cache_creation_input_tokens for t in turns]
        ),
        "cache_creation_1h_input_tokens": _sum_optional(
            [t.cache_creation_1h_input_tokens for t in turns]
        ),
        "cache_creation_5m_input_tokens": _sum_optional(
            [t.cache_creation_5m_input_tokens for t in turns]
        ),
        "output_tokens": output,
        "reasoning_output_tokens": _sum_optional(
            [t.reasoning_output_tokens for t in turns]
        ),
        "cache_hit_ratio": round(cached / context, 4) if context else 0.0,
        "avg_context_tokens": round(context / len(turns)) if turns else 0,
        "max_context_tokens": max((t.context_tokens for t in turns), default=0),
    }


def build_report(
    *,
    run_id: str,
    session: Session,
    window: tuple[datetime, datetime],
    phases: list[dict[str, object]],
) -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "captured_on": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agent_tool": session.tool,
        # Basename only: absolute session paths leak home directory layout.
        "session_file": session.path.name,
        "models": session.models,
        "run_window": {"start": window[0].isoformat(), "end": window[1].isoformat()},
        "session_window": {
            "start": session.start.isoformat() if session.start else None,
            "end": session.end.isoformat() if session.end else None,
        },
        "compactions": session.compactions,
        "totals": _totals(session.turns),
    }
    sidechain = getattr(session, "sidechain_turns", 0)
    if sidechain:
        report["sidechain_turns"] = sidechain
    if phases:
        report["gate_phases"] = phases
    return report


def manifest_summary(report: dict[str, object]) -> dict[str, object]:
    """The headline block mirrored into the evidence manifest.

    Deliberately a pointer plus headline figures: the per-gate detail stays in
    token-usage.json so the two cannot drift into disagreeing about it. The
    cache-write split is included rather than held back as "detail" — without
    it the block cannot be turned into a cost figure, since the two TTLs bill
    at different multiples.
    """
    totals = report["totals"]
    assert isinstance(totals, dict)
    return {
        "artifact": ARTIFACT_NAME,
        "agent_tool": report["agent_tool"],
        "turns": totals["turns"],
        "context_tokens": totals["context_tokens"],
        "uncached_input_tokens": totals["uncached_input_tokens"],
        "cached_input_tokens": totals["cached_input_tokens"],
        "cache_creation_input_tokens": totals["cache_creation_input_tokens"],
        "cache_creation_1h_input_tokens": totals["cache_creation_1h_input_tokens"],
        "cache_creation_5m_input_tokens": totals["cache_creation_5m_input_tokens"],
        "output_tokens": totals["output_tokens"],
        "cache_hit_ratio": totals["cache_hit_ratio"],
        "compactions": report["compactions"],
    }


def patch_manifest(run_folder: Path, report: dict[str, object]) -> bool:
    """Mirror the headline totals into evidence-manifest.json.

    Returns False when there is no manifest to patch; telemetry is advisory and
    must never block closeout on its own.
    """
    manifest_path = run_folder / "evidence-manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TelemetryError(f"evidence-manifest.json is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise TelemetryError("evidence-manifest.json must contain a JSON object")

    manifest["token_usage"] = manifest_summary(report)
    files = manifest.get("files")
    if isinstance(files, dict):
        files["token_usage"] = ARTIFACT_NAME
    _atomic_write(manifest_path, json.dumps(manifest, indent=2) + "\n")
    return True


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture agent-CLI token telemetry into an evidence run folder."
    )
    parser.add_argument("--run-id", required=True, help="Evidence run id, e.g. 2026-07-19-86ad3248.")
    add_product_root_arg(parser)
    parser.add_argument(
        "--tool",
        choices=("auto", "codex", "claude-code"),
        default="auto",
        help="Which agent CLI produced the run. Default: auto-detect by overlap.",
    )
    parser.add_argument("--session", help="Explicit session transcript path, bypassing discovery.")
    parser.add_argument(
        "--codex-sessions-root",
        default=str(DEFAULT_CODEX_ROOT),
        help="Root of Codex session transcripts.",
    )
    parser.add_argument(
        "--claude-projects-root",
        default=str(DEFAULT_CLAUDE_ROOT),
        help="Root of Claude Code project transcripts.",
    )
    parser.add_argument(
        "--no-gate-phases",
        action="store_true",
        help="Skip per-gate attribution even when commands.log is present.",
    )
    parser.add_argument(
        "--no-patch-manifest",
        action="store_true",
        help="Write token-usage.json without mirroring totals into evidence-manifest.json.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the report instead of writing it into the run folder.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        product_root = resolve_product_root(args.product_root)
        run_folder = product_root / "planning-mds" / "operations" / "evidence" / "runs" / args.run_id
        if not run_folder.is_dir():
            raise TelemetryError(f"run folder does not exist: {run_folder}")

        window = run_window(run_folder)

        if args.session:
            session_path = Path(args.session).expanduser().resolve()
            if not session_path.is_file():
                raise TelemetryError(f"--session is not a file: {args.session}")
            session = load_session(session_path)
            if not session.turns:
                raise TelemetryError(f"session has no token records: {args.session}")
        else:
            candidates = discover_sessions(
                Path(args.codex_sessions_root).expanduser(),
                Path(args.claude_projects_root).expanduser(),
                args.tool,
            )
            if not candidates:
                raise TelemetryError("no session transcripts found under the configured roots")
            session, _ = select_session(candidates, window)

        phases = [] if args.no_gate_phases else gate_phases(run_folder, session.turns)
        report = build_report(run_id=args.run_id, session=session, window=window, phases=phases)
        payload = json.dumps(report, indent=2) + "\n"

        if args.stdout:
            print(payload, end="")
        else:
            _atomic_write(run_folder / ARTIFACT_NAME, payload)
            patched = False
            if not args.no_patch_manifest:
                patched = patch_manifest(run_folder, report)
            totals = report["totals"]
            print(
                f"[OK] {ARTIFACT_NAME} written for {args.run_id} "
                f"({session.tool}, {totals['turns']} turns, "
                f"{totals['context_tokens']:,} context tokens, "
                f"{totals['cache_hit_ratio']:.1%} cached)"
            )
            if not args.no_patch_manifest and not patched:
                print("[WARN] no evidence-manifest.json to patch", file=sys.stderr)
    except TelemetryError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "kg"))

import kg_usage  # noqa: E402


def _turn_event(
    *,
    msg_id: str,
    harness: str = "unknown",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    is_sidechain: bool = False,
) -> dict[str, object]:
    return {
        "ts": "2026-06-16T00:00:00Z", "source": "harness", "harness": harness,
        "session_id": "s1", "msg_id": msg_id, "model": "m",
        "is_sidechain": is_sidechain, "tool": "turn",
        "payload": {
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens, "cache_write_tokens": cache_write_tokens,
        },
    }


# ---- claude-code adapter (one source among peers) ----

def test_claude_adapter_dedupes_and_tags_harness(tmp_path: Path) -> None:
    # one assistant w/ usage, one user, one DUPLICATE assistant id (streaming repeat)
    records = [
        {"type": "assistant", "sessionId": "s1", "timestamp": "2026-06-16T00:00:00Z",
         "isSidechain": False,
         "message": {"id": "msg_A", "model": "claude-opus-4-8",
                     "usage": {"input_tokens": 100, "output_tokens": 20,
                               "cache_read_input_tokens": 800,
                               "cache_creation_input_tokens": 50}}},
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {"type": "assistant", "sessionId": "s1", "timestamp": "2026-06-16T00:00:01Z",
         "isSidechain": False,
         "message": {"id": "msg_A", "model": "claude-opus-4-8",
                     "usage": {"input_tokens": 100, "output_tokens": 20,
                               "cache_read_input_tokens": 800,
                               "cache_creation_input_tokens": 50}}},
    ]
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    turns = kg_usage.parse_claude_transcript(path)

    assert len(turns) == 1
    t = turns[0]
    assert (t.msg_id, t.input_tokens, t.output_tokens) == ("msg_A", 100, 20)
    assert (t.cache_read_tokens, t.cache_write_tokens) == (800, 50)
    assert t.harness == "claude-code"
    assert kg_usage.turn_to_event(t)["harness"] == "claude-code"


# ---- jsonl adapter: the tool-agnostic feed any harness can emit ----

def test_jsonl_adapter_ingests_any_harness(tmp_path: Path) -> None:
    events = [
        {"tool": "turn", "source": "harness", "harness": "codex", "session_id": "r1",
         "msg_id": "m1", "ts": "t", "model": "gpt-x", "is_sidechain": False,
         "payload": {"input_tokens": 100, "output_tokens": 20,
                     "cache_read_tokens": 800, "cache_write_tokens": 0}},
        {"tool": "turn", "harness": "codex", "msg_id": "m1", "payload": {}},  # dup id dropped
        {"tool": "lookup", "msg_id": "x"},  # non-turn ignored
    ]
    feed = tmp_path / "feed.jsonl"
    feed.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    out = tmp_path / "usage.jsonl"

    n = kg_usage.ingest([feed], source="jsonl", out_path=out)

    assert n == 1
    written = json.loads(out.read_text(encoding="utf-8").strip())
    assert written["harness"] == "codex"  # source preserved, not hardcoded to claude
    assert kg_usage.cache_metrics([written])["turns"] == 1  # scores via the same path


def test_ingest_text_neutral_stdin(tmp_path: Path) -> None:
    out = tmp_path / "usage.jsonl"
    event = _turn_event(msg_id="m9", harness="manual", input_tokens=10,
                        cache_read_tokens=30, cache_write_tokens=5)

    n = kg_usage.ingest_text(json.dumps(event) + "\n", source="jsonl", out_path=out)

    assert n == 1
    assert json.loads(out.read_text(encoding="utf-8").strip())["harness"] == "manual"


# ---- codex adapter (peer of claude-code) ----

def test_codex_adapter_maps_token_count(tmp_path: Path) -> None:
    # last_token_usage is per-turn; input includes cached; no cache-write in OpenAI.
    records = [
        {"type": "session_meta", "payload": {"id": "sess-1", "cwd": "/x"}},
        {"type": "event_msg", "timestamp": "t0", "payload": {"type": "token_count", "info": {
            "last_token_usage": {"input_tokens": 28093, "cached_input_tokens": 24448,
                                 "output_tokens": 337, "reasoning_output_tokens": 241},
            "total_token_usage": {"input_tokens": 28093, "output_tokens": 337}}}},
        {"type": "event_msg", "timestamp": "t1", "payload": {"type": "token_count", "info": {
            "last_token_usage": {"input_tokens": 0, "cached_input_tokens": 0,
                                 "output_tokens": 0}}}},  # empty tick -> skipped
    ]
    path = tmp_path / "rollout.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    out = tmp_path / "usage.jsonl"

    n = kg_usage.ingest([path], source="codex", out_path=out)

    assert n == 1  # empty tick dropped
    e = json.loads(out.read_text(encoding="utf-8").strip())
    assert e["harness"] == "codex"
    assert e["session_id"] == "sess-1"
    assert e["msg_id"] == "sess-1:0"
    p = e["payload"]
    assert p["cache_read_tokens"] == 24448
    assert p["input_tokens"] == 28093 - 24448   # uncached input only
    assert p["output_tokens"] == 337            # already includes reasoning
    assert p["cache_write_tokens"] == 0         # OpenAI caching has no write cost


def test_codex_ingest_is_idempotent(tmp_path: Path) -> None:
    records = [
        {"type": "session_meta", "payload": {"id": "sess-2"}},
        {"type": "event_msg", "timestamp": "t0", "payload": {"type": "token_count", "info": {
            "last_token_usage": {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 9}}}},
    ]
    path = tmp_path / "rollout.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    out = tmp_path / "usage.jsonl"

    assert kg_usage.ingest([path], source="codex", out_path=out) == 1
    assert kg_usage.ingest([path], source="codex", out_path=out) == 0  # stable id -> dedup


# ---- metrics (harness-neutral) ----

def test_cache_hit_ratio_math() -> None:
    events = [
        _turn_event(msg_id="a", input_tokens=100, cache_read_tokens=800, cache_write_tokens=50),
        _turn_event(msg_id="b", input_tokens=100, cache_read_tokens=200, cache_write_tokens=50),
    ]
    m = kg_usage.cache_metrics(events)
    # read / (read + write + input) = (800+200) / (1000 + 100 + 200) = 1000/1300
    assert m["turns"] == 2
    assert m["cache_hit_ratio"] == round(1000 / 1300, 4)


def test_cost_formula_matches_weights() -> None:
    # cost = input*1.0 + write*1.25 + read*0.1 + output*5.0
    m = kg_usage.cache_metrics(
        [_turn_event(msg_id="a", input_tokens=100, output_tokens=20,
                     cache_read_tokens=800, cache_write_tokens=50)]
    )
    expected = 100 * 1.0 + 50 * 1.25 + 800 * 0.1 + 20 * 5.0  # = 342.5
    assert m["cost_per_turn"]["p50"] == round(expected, 1)


def test_spike_detection_flags_write_driven_turn() -> None:
    cheap = [_turn_event(msg_id=f"c{i}", input_tokens=100, cache_read_tokens=100)
             for i in range(9)]
    big = _turn_event(msg_id="big", input_tokens=200, cache_write_tokens=40000)
    m = kg_usage.cache_metrics(cheap + [big])

    spikes = m["cache_write_spikes"]
    assert len(spikes) == 1
    assert spikes[0]["msg_id"] == "big"
    assert spikes[0]["x_median"] >= 5.0
    assert spikes[0]["write_share"] > 0.9  # cost driven by the cache write


def test_graceful_degradation_no_turns() -> None:
    empty = kg_usage.cache_metrics([])
    non_turn = kg_usage.cache_metrics([{"tool": "lookup", "payload": {}}])
    for m in (empty, non_turn):
        assert m["turns"] == 0
        assert m["cache_hit_ratio"] is None
        assert m["cost_per_turn"] == {"mean": None, "p50": None, "p95": None}
        assert m["cache_write_spikes"] == []


# ---- ingestion is idempotent across runs ----

def test_ingest_is_idempotent(tmp_path: Path) -> None:
    record = {"type": "assistant", "sessionId": "s1", "timestamp": "2026-06-16T00:00:00Z",
              "isSidechain": False,
              "message": {"id": "msg_A", "model": "claude-opus-4-8",
                          "usage": {"input_tokens": 100, "output_tokens": 20,
                                    "cache_read_input_tokens": 800,
                                    "cache_creation_input_tokens": 50}}}
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps(record) + "\n", encoding="utf-8")
    out = tmp_path / "usage.jsonl"

    first = kg_usage.ingest([transcript], source="claude-code", out_path=out)
    second = kg_usage.ingest([transcript], source="claude-code", out_path=out)

    assert first == 1
    assert second == 0  # dedup by msg_id across runs
    assert len(out.read_text(encoding="utf-8").strip().splitlines()) == 1


# ---- §13.3 context budget check ----

def test_budget_status_thresholds() -> None:
    # window 200k, reserve 0.30 -> input budget 140k
    assert kg_usage.budget_status(100_000)["input_budget"] == 140_000
    assert kg_usage.budget_status(100_000)["status"] == "ok"
    assert kg_usage.budget_status(130_000)["status"] == "warn"   # 130k/140k = 0.929 >= 0.9
    over = kg_usage.budget_status(150_000)
    assert over["status"] == "over" and over["headroom"] < 0


def test_latest_loaded_tokens_uses_most_recent() -> None:
    e1 = _turn_event(msg_id="a", input_tokens=100, cache_read_tokens=800, cache_write_tokens=50)
    e2 = _turn_event(msg_id="b", input_tokens=200, cache_read_tokens=900, cache_write_tokens=0)
    e1["ts"], e2["ts"] = "2026-06-16T00:00:00Z", "2026-06-16T01:00:00Z"  # e2 later
    assert kg_usage.latest_loaded_tokens([e1, e2]) == 200 + 900 + 0     # latest prefix_input
    assert kg_usage.latest_loaded_tokens([]) is None

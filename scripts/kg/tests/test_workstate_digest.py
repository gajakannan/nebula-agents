from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "kg"))

import workstate  # noqa: E402
from kg_common import estimate_tokens  # noqa: E402

STATE = {
    "session": {"role": "architect", "scope": "F0007", "mode": "clean", "run_id": "r1", "started": "t0"},
    "decisions": [
        {"decision_id": 0, "summary": "use temporal", "topic": "orch"},
        {"decision_id": 1, "summary": "use temporal v2", "topic": "orch", "supersedes": [0]},
        {"decision_id": 2, "summary": "add rationale field", "topic": "schema"},
    ],
    "files_touched": [
        {"path": "a.cs", "action": "read"},
        {"path": "b.cs", "action": "read"},
        {"path": "c.cs", "action": "modified"},
        {"path": "d.cs", "action": "created"},
    ],
    "open_questions": [
        {"question": "which LOB?", "resolved": False},
        {"question": "old q", "resolved": True, "answer": "yes"},
    ],
    "escalations": [{"timestamp": "t", "reason": "empty lookup", "nodes": ["entity:x"], "opened_raw": []}],
}


def test_digest_shape() -> None:
    d = workstate.build_digest(copy.deepcopy(STATE))
    assert d["session"]["role"] == "architect" and d["session"]["scope"] == "F0007"
    assert d["done"]["files"] == {"read": 2, "modified": 1, "created": 1}
    assert d["done"]["changed"] == ["c.cs", "d.cs"]                 # reads excluded
    assert d["decided"] == ["use temporal v2", "add rationale field"]  # superseded #0 filtered
    assert d["next"] == ["which LOB?"]                              # open questions = next
    assert d["escalations"] == 1                                    # collapsed to a count


def test_digest_cheaper_than_dump() -> None:
    digest = workstate.build_digest(copy.deepcopy(STATE))
    dump = workstate.compact_state(workstate.ensure_state_shape(copy.deepcopy(STATE)))
    assert estimate_tokens(digest) < estimate_tokens(dump)


def test_digest_minimal_state() -> None:
    d = workstate.build_digest({"session": {"role": "backend"}})
    assert d == {"session": {"role": "backend"}}  # no done/decided/next when nothing happened yet

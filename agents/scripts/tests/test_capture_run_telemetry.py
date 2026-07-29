from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "agents" / "scripts" / "capture-run-telemetry.py"


def load_module():
    spec = importlib.util.spec_from_file_location("capture_run_telemetry", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # dataclasses resolves cls.__module__ through sys.modules, so the module
    # must be registered before exec_module or @dataclass raises.
    sys.modules["capture_run_telemetry"] = module
    spec.loader.exec_module(module)
    return module


crt = load_module()


def write_jsonl(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def codex_turn(ts: str, total_input: int, cached: int, output: int, reasoning: int = 0) -> dict:
    return {
        "type": "event_msg",
        "timestamp": ts,
        "payload": {
            "type": "token_count",
            "info": {
                "last_token_usage": {
                    "input_tokens": total_input,
                    "cached_input_tokens": cached,
                    "output_tokens": output,
                    "reasoning_output_tokens": reasoning,
                }
            },
        },
    }


def claude_turn(ts: str, msg_id: str, uncached: int, cache_read: int, cache_creation: int,
                output: int, block: str = "text") -> dict:
    return {
        "type": "assistant",
        "timestamp": ts,
        "cwd": "/repo",
        "message": {
            "id": msg_id,
            "model": "claude-opus-4-8",
            "content": [{"type": block}],
            "usage": {
                "input_tokens": uncached,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
                "output_tokens": output,
            },
        },
    }


class CodexReaderTests(unittest.TestCase):
    def test_codex_input_tokens_are_treated_as_whole_context(self) -> None:
        """Codex input_tokens INCLUDES cached, so uncached is the difference."""
        with tempfile.TemporaryDirectory() as raw:
            path = write_jsonl(
                Path(raw) / "rollout-x.jsonl",
                [
                    {"type": "session_meta", "timestamp": "2026-01-01T00:00:00Z",
                     "payload": {"cwd": "/repo"}},
                    codex_turn("2026-01-01T00:00:01Z", 1000, 900, 50, 10),
                    codex_turn("2026-01-01T00:00:02Z", 2000, 1800, 60, 20),
                ],
            )
            session = crt.read_codex_session(path)

        self.assertEqual(session.tool, "codex")
        self.assertEqual(session.cwd, "/repo")
        totals = crt._totals(session.turns)
        self.assertEqual(totals["context_tokens"], 3000)
        self.assertEqual(totals["cached_input_tokens"], 2700)
        self.assertEqual(totals["uncached_input_tokens"], 300)
        self.assertEqual(totals["output_tokens"], 110)
        self.assertEqual(totals["reasoning_output_tokens"], 30)

    def test_compaction_events_are_counted(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = write_jsonl(
                Path(raw) / "rollout-x.jsonl",
                [
                    codex_turn("2026-01-01T00:00:01Z", 100, 0, 5),
                    {"type": "compacted", "timestamp": "2026-01-01T00:00:02Z", "payload": {}},
                    {"type": "compacted", "timestamp": "2026-01-01T00:00:03Z", "payload": {}},
                ],
            )
            self.assertEqual(crt.read_codex_session(path).compactions, 2)


class ClaudeReaderTests(unittest.TestCase):
    def test_repeated_message_id_is_counted_once(self) -> None:
        """One assistant message spans several JSONL lines repeating one usage
        object; summing raw lines would multiply the true cost."""
        with tempfile.TemporaryDirectory() as raw:
            path = write_jsonl(
                Path(raw) / "session.jsonl",
                [
                    claude_turn("2026-01-01T00:00:01Z", "msg_1", 2, 1000, 100, 40, "thinking"),
                    claude_turn("2026-01-01T00:00:02Z", "msg_1", 2, 1000, 100, 40, "text"),
                    claude_turn("2026-01-01T00:00:03Z", "msg_1", 2, 1000, 100, 40, "tool_use"),
                ],
            )
            session = crt.read_claude_session(path)

        self.assertEqual(len(session.turns), 1)
        totals = crt._totals(session.turns)
        self.assertEqual(totals["cached_input_tokens"], 1000)
        self.assertEqual(totals["output_tokens"], 40)

    def test_claude_context_sums_uncached_and_cache_fields(self) -> None:
        """Claude input_tokens EXCLUDES cache, unlike Codex."""
        with tempfile.TemporaryDirectory() as raw:
            path = write_jsonl(
                Path(raw) / "session.jsonl",
                [claude_turn("2026-01-01T00:00:01Z", "msg_1", 5, 900, 95, 40)],
            )
            totals = crt._totals(crt.read_claude_session(path).turns)

        self.assertEqual(totals["context_tokens"], 1000)
        self.assertEqual(totals["uncached_input_tokens"], 5)
        self.assertEqual(totals["cache_creation_input_tokens"], 95)

    def test_cache_creation_ttl_split_is_preserved(self) -> None:
        """1h and 5m writes bill at different multiples, so the split must
        survive into the totals rather than being collapsed."""
        with tempfile.TemporaryDirectory() as raw:
            record = claude_turn("2026-01-01T00:00:01Z", "msg_1", 5, 900, 95, 40)
            record["message"]["usage"]["cache_creation"] = {
                "ephemeral_1h_input_tokens": 80,
                "ephemeral_5m_input_tokens": 15,
            }
            path = write_jsonl(Path(raw) / "session.jsonl", [record])
            totals = crt._totals(crt.read_claude_session(path).turns)

        self.assertEqual(totals["cache_creation_input_tokens"], 95)
        self.assertEqual(totals["cache_creation_1h_input_tokens"], 80)
        self.assertEqual(totals["cache_creation_5m_input_tokens"], 15)


class UnavailableFieldTests(unittest.TestCase):
    """A vendor that does not report a field must yield null, not 0 — a
    measured zero and an unmeasured field mean different things for cost."""

    def test_codex_cache_creation_is_null_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = write_jsonl(
                Path(raw) / "rollout-x.jsonl",
                [codex_turn("2026-01-01T00:00:01Z", 1000, 900, 50, 10)],
            )
            totals = crt._totals(crt.read_codex_session(path).turns)

        self.assertIsNone(totals["cache_creation_input_tokens"])
        self.assertIsNone(totals["cache_creation_1h_input_tokens"])
        self.assertIsNone(totals["cache_creation_5m_input_tokens"])
        self.assertEqual(totals["reasoning_output_tokens"], 10)

    def test_claude_reasoning_is_null_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = write_jsonl(
                Path(raw) / "session.jsonl",
                [claude_turn("2026-01-01T00:00:01Z", "msg_1", 5, 900, 95, 40)],
            )
            totals = crt._totals(crt.read_claude_session(path).turns)

        self.assertIsNone(totals["reasoning_output_tokens"])
        self.assertEqual(totals["cache_creation_input_tokens"], 95)

    def test_sum_optional_distinguishes_absent_from_zero(self) -> None:
        self.assertIsNone(crt._sum_optional([None, None]))
        self.assertEqual(crt._sum_optional([0, 0]), 0)
        self.assertEqual(crt._sum_optional([None, 7]), 7)


def turn_at(second: int) -> "crt.Turn":
    """A minimal Turn at a given second — keyword-built so that adding a field
    to Turn does not silently shift positional arguments in these tests."""
    return crt.Turn(
        timestamp=crt._parse_ts(f"2026-01-01T00:00:{second:02d}Z"),
        context_tokens=100,
        uncached_input_tokens=10,
        cached_input_tokens=90,
        cache_creation_input_tokens=0,
        cache_creation_1h_input_tokens=0,
        cache_creation_5m_input_tokens=0,
        output_tokens=5,
        reasoning_output_tokens=0,
    )


class GatePhaseTests(unittest.TestCase):
    def _run_folder(self, tmp: Path, commands: list[dict]) -> Path:
        run_folder = tmp / "runs" / "run-1"
        write_jsonl(run_folder / "commands.log", commands)
        return run_folder

    def test_phases_partition_every_turn_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            run_folder = self._run_folder(
                Path(raw),
                [
                    {"timestamp": "2026-01-01T00:00:05+00:00",
                     "command": "python3 agents/scripts/run-gate.py --action feature --stage G0"},
                    {"timestamp": "2026-01-01T00:00:15+00:00",
                     "command": "python3 agents/scripts/run-gate.py --action feature --stage G1"},
                ],
            )
            turns = [
                turn_at(s)
                for s in (1, 3, 7, 12, 20)
            ]
            phases = crt.gate_phases(run_folder, turns)

        self.assertEqual([p["gate"] for p in phases], ["G0", "G1", "post-final-gate"])
        self.assertEqual(sum(int(p["turns"]) for p in phases), len(turns))

    def test_grep_mentioning_run_gate_is_not_a_boundary(self) -> None:
        """A command that merely greps for run-gate.py must not open a phase."""
        with tempfile.TemporaryDirectory() as raw:
            run_folder = self._run_folder(
                Path(raw),
                [
                    {"timestamp": "2026-01-01T00:00:05+00:00",
                     "command": "rg -n 'run-gate.py|validate.py.*--stage G[01]' commands.log"},
                    {"timestamp": "2026-01-01T00:00:15+00:00",
                     "command": "python3 agents/scripts/run-gate.py --action feature --stage G4"},
                ],
            )
            turns = [
                turn_at(s)
                for s in (1, 10)
            ]
            phases = crt.gate_phases(run_folder, turns)

        self.assertEqual([p["gate"] for p in phases], ["G4"])

    def test_two_letter_and_decimal_gate_ids_are_recognized(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            run_folder = self._run_folder(
                Path(raw),
                [
                    {"timestamp": "2026-01-01T00:00:05+00:00",
                     "command": "python3 agents/scripts/run-gate.py --stage FR2 --action feature-review"},
                    {"timestamp": "2026-01-01T00:00:10+00:00",
                     "command": "python3 agents/scripts/run-gate.py --stage B4.5 --action build"},
                ],
            )
            turns = [
                turn_at(s)
                for s in (1, 7)
            ]
            phases = crt.gate_phases(run_folder, turns)

        self.assertEqual([p["gate"] for p in phases], ["FR2", "B4.5"])


class RunWindowTests(unittest.TestCase):
    def test_window_spans_first_and_last_command(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            run_folder = Path(raw) / "run-1"
            write_jsonl(
                run_folder / "commands.log",
                [
                    {"timestamp": "2026-01-01T10:00:00-04:00", "command": "a"},
                    {"timestamp": "2026-01-01T12:00:00-04:00", "command": "b"},
                ],
            )
            start, end = crt.run_window(run_folder)

        # Local-offset command stamps normalize to UTC for session comparison.
        self.assertEqual(start.isoformat(), "2026-01-01T14:00:00+00:00")
        self.assertEqual(end.isoformat(), "2026-01-01T16:00:00+00:00")


class SelectSessionTests(unittest.TestCase):
    def test_picks_the_session_overlapping_the_run_window(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            unrelated = write_jsonl(
                tmp / "rollout-old.jsonl",
                [codex_turn("2025-01-01T00:00:01Z", 100, 0, 5)],
            )
            wanted = write_jsonl(
                tmp / "rollout-new.jsonl",
                [
                    codex_turn("2026-01-01T00:00:01Z", 100, 0, 5),
                    codex_turn("2026-01-01T01:00:00Z", 100, 0, 5),
                ],
            )
            window = (crt._parse_ts("2026-01-01T00:00:00Z"), crt._parse_ts("2026-01-01T02:00:00Z"))
            session, _ = crt.select_session([unrelated, wanted], window)

        self.assertEqual(session.path.name, wanted.name)

    def test_no_overlap_raises(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = write_jsonl(
                Path(raw) / "rollout-old.jsonl",
                [codex_turn("2025-01-01T00:00:01Z", 100, 0, 5)],
            )
            window = (crt._parse_ts("2026-01-01T00:00:00Z"), crt._parse_ts("2026-01-01T02:00:00Z"))
            with self.assertRaises(crt.TelemetryError):
                crt.select_session([path], window)


class PatchManifestTests(unittest.TestCase):
    def _report(self) -> dict:
        with tempfile.TemporaryDirectory() as raw:
            path = write_jsonl(
                Path(raw) / "rollout-x.jsonl",
                [codex_turn("2026-01-01T00:00:01Z", 1000, 900, 50, 10)],
            )
            session = crt.read_codex_session(path)
            window = (crt._parse_ts("2026-01-01T00:00:00Z"), crt._parse_ts("2026-01-01T00:00:02Z"))
            return crt.build_report(run_id="run-1", session=session, window=window, phases=[])

    def test_patch_adds_token_usage_and_preserves_existing_keys(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            run_folder = Path(raw)
            (run_folder / "evidence-manifest.json").write_text(
                json.dumps({"schema_version": 1, "run_id": "run-1", "status": "draft",
                            "files": {"readme": "README.md"}}),
                encoding="utf-8",
            )
            self.assertTrue(crt.patch_manifest(run_folder, self._report()))
            manifest = json.loads((run_folder / "evidence-manifest.json").read_text())

        self.assertEqual(manifest["status"], "draft")
        self.assertEqual(manifest["files"]["readme"], "README.md")
        self.assertEqual(manifest["files"]["token_usage"], "token-usage.json")
        self.assertEqual(manifest["token_usage"]["context_tokens"], 1000)
        self.assertEqual(manifest["token_usage"]["uncached_input_tokens"], 100)
        self.assertEqual(manifest["token_usage"]["agent_tool"], "codex")

    def test_missing_manifest_is_reported_not_raised(self) -> None:
        """Telemetry is advisory; a missing manifest must not block closeout."""
        with tempfile.TemporaryDirectory() as raw:
            self.assertFalse(crt.patch_manifest(Path(raw), self._report()))

    def test_corrupt_manifest_raises(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            run_folder = Path(raw)
            (run_folder / "evidence-manifest.json").write_text("{not json", encoding="utf-8")
            with self.assertRaises(crt.TelemetryError):
                crt.patch_manifest(run_folder, self._report())

    def test_manifest_summary_matches_template_field_set(self) -> None:
        """The patched block and the shipped template must not drift apart."""
        template = json.loads(
            (REPO_ROOT / "agents" / "templates" / "evidence-manifest-template.json").read_text()
        )
        template_keys = set(template["token_usage"]) - {"_comment"}
        self.assertEqual(set(crt.manifest_summary(self._report())), template_keys)


class ReportTests(unittest.TestCase):
    def test_report_omits_absolute_session_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = write_jsonl(
                Path(raw) / "rollout-x.jsonl",
                [codex_turn("2026-01-01T00:00:01Z", 1000, 900, 50)],
            )
            session = crt.read_codex_session(path)
            window = (crt._parse_ts("2026-01-01T00:00:00Z"), crt._parse_ts("2026-01-01T00:00:02Z"))
            report = crt.build_report(run_id="run-1", session=session, window=window, phases=[])

        self.assertEqual(report["session_file"], "rollout-x.jsonl")
        self.assertNotIn(raw, json.dumps(report))
        self.assertEqual(report["schema_version"], crt.SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()

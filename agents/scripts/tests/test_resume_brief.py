from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "agents" / "scripts" / "resume-brief.py"


def load_module():
    spec = importlib.util.spec_from_file_location("resume_brief", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["resume_brief"] = module
    spec.loader.exec_module(module)
    return module


rb = load_module()


STATUS_MD = """# F0099 Status

## Story Checklist

| Story | Title | Status |
|-------|-------|--------|
| F0099-S0001 | First story | Done |
| F0099-S0002 | Second story | In Progress |
| F0099-S0003 | Third story | To Do |

## Story Signoff Provenance

| Story | Role | Result |
|-------|------|--------|
| F0099-S0001 | Quality Engineer | - |
| F0099-S0002 | Code Reviewer | - |
"""

ACTION_CONTEXT_MD = """# Action Context

## Run Identity

- **run_id:** 2026-07-21-deadbeef

## Assumptions

- The assembly plan is the primary spec.

## Scope Boundaries

- Only the three F0099 stories are in scope.
"""

WORKSTATE_STUB = """#!/usr/bin/env python3
import json, sys
print(json.dumps({
    "session": {"role": "backend-developer", "scope": "F0099-S0002"},
    "decided": ["Exact-match application only"],
    "next": ["Does S0003 need a migration?"],
}))
"""


def build_product(tmp: Path, *, stages: dict | None = None, with_workstate: bool = False) -> Path:
    product = tmp / "product"
    run_folder = product / "planning-mds" / "operations" / "evidence" / "runs" / "run-1"
    feature = product / "planning-mds" / "features" / "F0099-demo"
    run_folder.mkdir(parents=True)
    feature.mkdir(parents=True)

    (run_folder / "gate-state.json").write_text(
        json.dumps({
            "action": "feature",
            "run_id": "run-1",
            "stages": stages or {
                "G0": {"status": "completed"},
                "G1": {"status": "completed"},
                "G2": {"status": "in-progress"},
            },
        }),
        encoding="utf-8",
    )
    (run_folder / "evidence-manifest.json").write_text(
        json.dumps({
            "schema_version": 1,
            "feature_id": "F0099",
            "feature_slug": "demo",
            "status": "in-progress",
            "feature_path_at_run_start": "planning-mds/features/F0099-demo",
            "feature_path_at_closeout": None,
        }),
        encoding="utf-8",
    )
    (run_folder / "action-context.md").write_text(ACTION_CONTEXT_MD, encoding="utf-8")
    (feature / "STATUS.md").write_text(STATUS_MD, encoding="utf-8")

    if with_workstate:
        kg = product / "scripts" / "kg"
        kg.mkdir(parents=True)
        (kg / "workstate.py").write_text(WORKSTATE_STUB, encoding="utf-8")
        (run_folder / "workstate.json").write_text("{}", encoding="utf-8")
    return product


class StageSelectionTests(unittest.TestCase):
    def test_next_stage_is_first_incomplete(self) -> None:
        state = {"stages": {
            "G0": {"status": "completed"},
            "G1": {"status": "completed"},
            "G2": {"status": "pending"},
            "G3": {"status": "pending"},
        }}
        self.assertEqual(rb.next_stage(state), "G2")
        self.assertEqual(rb.completed_stages(state), ["G0", "G1"])

    def test_stages_sort_numerically_not_lexically(self) -> None:
        """G10 must come after G2 — string sort would put it before."""
        state = {"stages": {
            "G10": {"status": "pending"},
            "G2": {"status": "completed"},
            "G4.5": {"status": "completed"},
        }}
        self.assertEqual(rb.completed_stages(state), ["G2", "G4.5"])
        self.assertEqual(rb.next_stage(state), "G10")

    def test_all_complete_returns_none(self) -> None:
        self.assertIsNone(rb.next_stage({"stages": {"G0": {"status": "completed"}}}))


class CurrentStoryTests(unittest.TestCase):
    def test_picks_first_non_terminal_story_from_the_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            feature = Path(raw) / "F0099-demo"
            feature.mkdir()
            (feature / "STATUS.md").write_text(STATUS_MD, encoding="utf-8")
            story = rb.current_story(feature)

        self.assertEqual(story, ("F0099-S0002", "Second story", "In Progress"))

    def test_provenance_matrix_rows_are_not_mistaken_for_stories(self) -> None:
        """STATUS.md has a second table whose rows start with a story id but
        whose second column is a role. Parsing the whole file reports the role
        as the story title."""
        with tempfile.TemporaryDirectory() as raw:
            feature = Path(raw) / "F0099-demo"
            feature.mkdir()
            # Every checklist story is Done, so the only non-terminal rows in
            # the file live in the provenance matrix.
            (feature / "STATUS.md").write_text(
                "## Story Checklist\n\n"
                "| Story | Title | Status |\n|---|---|---|\n"
                "| F0099-S0001 | First story | Done |\n\n"
                "## Story Signoff Provenance\n\n"
                "| Story | Role | Result |\n|---|---|---|\n"
                "| F0099-S0001 | Quality Engineer | - |\n",
                encoding="utf-8",
            )
            self.assertIsNone(rb.current_story(feature))

    def test_missing_status_file_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            self.assertIsNone(rb.current_story(Path(raw)))


class SectionExtractionTests(unittest.TestCase):
    def test_named_sections_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "action-context.md"
            path.write_text(ACTION_CONTEXT_MD, encoding="utf-8")
            found = rb.extract_sections(path, ["Assumptions", "Scope Boundaries"])

        self.assertEqual(set(found), {"Assumptions", "Scope Boundaries"})
        self.assertIn("assembly plan is the primary spec", found["Assumptions"])
        self.assertNotIn("run_id", found["Assumptions"])


class OperationRenderingTests(unittest.TestCase):
    def test_each_operation_kind_is_labelled(self) -> None:
        gate = {"operations": [
            {"run": {"argv": ["python3", "x.py", "--flag"], "cwd": "framework"}},
            {"write": {"artifact": "latest-run.json"}},
            {"checkpoint": {"id": "archive-move", "description": "Move the folder."}},
        ]}
        lines = rb.describe_operations(gate)

        self.assertIn("run `python3 x.py --flag` (cwd: framework)", lines)
        self.assertIn("write `latest-run.json`", lines)
        self.assertTrue(any(line.startswith("CHECKPOINT `archive-move`") for line in lines))


class BriefOutputTests(unittest.TestCase):
    def _brief(self, product: Path, argv_extra: list[str] | None = None) -> str:
        import io
        import contextlib

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = rb.main(
                ["--run-id", "run-1", "--product-root", str(product)] + (argv_extra or [])
            )
        self.assertEqual(code, 0)
        return buffer.getvalue()

    def test_brief_states_position_story_and_guardrails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            product = build_product(Path(raw))
            text = self._brief(product)

        self.assertIn("gates completed:** G0 G1", text)
        self.assertIn("next gate:** G2", text)
        self.assertIn("F0099-S0002", text)
        self.assertIn("Only the three F0099 stories are in scope", text)
        self.assertIn("Do not re-read", text)
        # The guardrail must name the specific files that drove re-reading.
        self.assertIn("validate-feature-evidence.py", text)

    def test_workstate_decisions_surface_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            product = build_product(Path(raw), with_workstate=True)
            text = self._brief(product)

        self.assertIn("Exact-match application only", text)
        self.assertIn("Does S0003 need a migration?", text)

    def test_missing_workstate_says_so_rather_than_failing(self) -> None:
        """Silence would read as 'no decisions were made'; the brief must say
        the decisions were never captured."""
        with tempfile.TemporaryDirectory() as raw:
            product = build_product(Path(raw), with_workstate=False)
            text = self._brief(product)

        self.assertIn("no workstate recorded", text)

    def test_explicit_stage_overrides_the_computed_one(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            product = build_product(Path(raw))
            text = self._brief(product, ["--stage", "G5"])

        self.assertIn("next gate:** G5", text)


class ErrorTests(unittest.TestCase):
    def test_missing_run_folder_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            product = build_product(Path(raw))
            self.assertEqual(
                rb.main(["--run-id", "nope", "--product-root", str(product)]), 2
            )

    def test_unknown_stage_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            product = build_product(Path(raw))
            self.assertEqual(
                rb.main(
                    ["--run-id", "run-1", "--product-root", str(product), "--stage", "ZZ9"]
                ),
                2,
            )


if __name__ == "__main__":
    unittest.main()

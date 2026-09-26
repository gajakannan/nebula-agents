from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "agents" / "scripts" / "append-command-log.py"


def load_module():
    spec = importlib.util.spec_from_file_location("append_command_log", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


acl = load_module()


def product_tree(tmp_path: Path) -> tuple[Path, Path]:
    product_root = tmp_path / "product"
    framework_root = tmp_path / "nebula-agents"
    artifact = product_root / "planning-mds" / "operations" / "evidence" / "runs" / "run-1" / "artifacts" / "out.log"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("ok\n", encoding="utf-8")
    (product_root / "engine").mkdir()
    (framework_root / "agents" / "scripts").mkdir(parents=True)
    return product_root, framework_root


class AppendCommandLogTests(unittest.TestCase):
    def test_product_root_absolute_artifact_normalizes_to_repo_relative(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            product_root, _ = product_tree(tmp_path)
            artifact = product_root / "planning-mds" / "operations" / "evidence" / "runs" / "run-1" / "artifacts" / "out.log"

            self.assertEqual(
                acl.normalize_artifact(str(artifact), product_root),
                "planning-mds/operations/evidence/runs/run-1/artifacts/out.log",
            )

    def test_product_root_placeholder_artifact_normalizes_to_repo_relative(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            product_root, _ = product_tree(Path(raw_tmp))

            self.assertEqual(
                acl.normalize_artifact(
                    "{PRODUCT_ROOT}/planning-mds/operations/evidence/runs/run-1/artifacts/out.log",
                    product_root,
                ),
                "planning-mds/operations/evidence/runs/run-1/artifacts/out.log",
            )

    def test_repo_relative_artifact_remains_repo_relative(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            product_root, _ = product_tree(Path(raw_tmp))

            self.assertEqual(
                acl.normalize_artifact(
                    "planning-mds/operations/evidence/runs/run-1/artifacts/out.log",
                    product_root,
                ),
                "planning-mds/operations/evidence/runs/run-1/artifacts/out.log",
            )

    def test_cwd_under_product_root_normalizes_to_product_label(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            product_root, framework_root = product_tree(Path(raw_tmp))

            self.assertEqual(
                acl.normalize_cwd(str(product_root), product_root, framework_root),
                "{PRODUCT_ROOT}",
            )
            self.assertEqual(
                acl.normalize_cwd(str(product_root / "engine"), product_root, framework_root),
                "{PRODUCT_ROOT}/engine",
            )

    def test_cwd_under_framework_root_normalizes_to_framework_label(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            product_root, framework_root = product_tree(Path(raw_tmp))

            self.assertEqual(
                acl.normalize_cwd(str(framework_root), product_root, framework_root),
                "nebula-agents",
            )
            self.assertEqual(
                acl.normalize_cwd(
                    str(framework_root / "agents" / "scripts"),
                    product_root,
                    framework_root,
                ),
                "nebula-agents/agents/scripts",
            )

    def test_spec_cwd_labels_map_to_stable_labels(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            product_root, framework_root = product_tree(Path(raw_tmp))
            cases = {
                "product": "{PRODUCT_ROOT}",
                "product/engine": "{PRODUCT_ROOT}/engine",
                "framework": "nebula-agents",
                "framework/agents/scripts": "nebula-agents/agents/scripts",
            }
            for raw, expected in cases.items():
                self.assertEqual(acl.normalize_cwd(raw, product_root, framework_root), expected, raw)
            with self.assertRaisesRegex(acl.CommandLogError, "traverse upward"):
                acl.normalize_cwd("framework/../x", product_root, framework_root)

    def test_tmp_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            product_root, _ = product_tree(tmp_path)
            scratch = tmp_path / "scratch.log"
            scratch.write_text("scratch\n", encoding="utf-8")

            with self.assertRaisesRegex(acl.CommandLogError, "scratch artifact paths"):
                acl.normalize_artifact(str(scratch), product_root)

    def test_artifact_outside_product_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            product_root, _ = product_tree(Path(raw_tmp))

            with self.assertRaisesRegex(acl.CommandLogError, "outside product root"):
                acl.normalize_artifact(str(SCRIPT), product_root)

    def test_helper_appends_command_entry_to_commands_log(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            product_root, framework_root = product_tree(tmp_path)
            artifact = product_root / "planning-mds" / "operations" / "evidence" / "runs" / "run-1" / "artifacts" / "out.log"
            log = product_root / "planning-mds" / "operations" / "evidence" / "runs" / "run-1" / "commands.log"

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--log",
                    str(log),
                    "--product-root",
                    str(product_root),
                    "--framework-root",
                    str(framework_root),
                    "--cwd",
                    str(product_root / "engine"),
                    "--command",
                    "python3 scripts/check.py",
                    "--exit-code",
                    "0",
                    "--artifact",
                    str(artifact),
                    "--redaction",
                    "token",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            lines = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["schema_version"], 1)
            self.assertEqual(entry["cwd"], "{PRODUCT_ROOT}/engine")
            self.assertEqual(entry["command"], "python3 scripts/check.py")
            self.assertEqual(entry["exit_code"], 0)
            self.assertEqual(entry["artifacts"], ["planning-mds/operations/evidence/runs/run-1/artifacts/out.log"])
            self.assertEqual(entry["redactions"], ["token"])


if __name__ == "__main__":
    unittest.main()

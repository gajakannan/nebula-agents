"""CLI tests for exec-and-log.py and the run-lifecycle-gates.py reuse (F0007-S0004)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "agents" / "scripts"
EXEC_AND_LOG = SCRIPTS_DIR / "exec-and-log.py"
LIFECYCLE = SCRIPTS_DIR / "run-lifecycle-gates.py"


def _product_root(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "planning-mds").mkdir()
    return tmp_path, tmp_path / "planning-mds" / "commands.log"


def test_exec_and_log_runs_shell_free_and_logs(tmp_path):
    root, log = _product_root(tmp_path)
    payload = "x; $(id) && echo pwned"
    proc = subprocess.run(
        [sys.executable, str(EXEC_AND_LOG), "--log", str(log), "--product-root", str(root),
         "--cwd", "product", "--",
         sys.executable, "-c", "import sys; open('p.txt','w').write(sys.argv[1])", payload],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert (root / "p.txt").read_text() == payload  # literal — no shell ran
    entry = json.loads(log.read_text(encoding="utf-8").strip())
    assert entry["schema_version"] == 1 and entry["exit_code"] == 0


def test_exec_and_log_propagates_nonzero(tmp_path):
    root, log = _product_root(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(EXEC_AND_LOG), "--log", str(log), "--product-root", str(root),
         "--cwd", "product", "--", sys.executable, "-c", "import sys; sys.exit(3)"],
        capture_output=True, text=True)
    assert proc.returncode == 3
    assert json.loads(log.read_text(encoding="utf-8").strip())["exit_code"] == 3


def test_exec_and_log_timeout_returns_124(tmp_path):
    root, log = _product_root(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(EXEC_AND_LOG), "--log", str(log), "--product-root", str(root),
         "--cwd", "product", "--timeout", "0.5", "--",
         sys.executable, "-c", "import time; time.sleep(30)"],
        capture_output=True, text=True, timeout=15)
    assert proc.returncode == 124


def test_exec_and_log_passes_output_through(tmp_path):
    root, log = _product_root(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(EXEC_AND_LOG), "--log", str(log), "--product-root", str(root),
         "--cwd", "product", "--", sys.executable, "-c",
         "import sys; print('to-out'); print('to-err', file=sys.stderr)"],
        capture_output=True, text=True)
    assert proc.returncode == 0
    assert "to-out" in proc.stdout and "to-err" in proc.stderr


def test_exec_and_log_persists_streams_and_records_artifacts(tmp_path):
    root, log = _product_root(tmp_path)
    out = root / "planning-mds" / "artifacts" / "out.txt"
    err = root / "planning-mds" / "artifacts" / "err.txt"
    proc = subprocess.run(
        [sys.executable, str(EXEC_AND_LOG), "--log", str(log), "--product-root", str(root),
         "--cwd", "product", "--stdout", str(out), "--stderr", str(err), "--json", "--",
         sys.executable, "-c",
         "import sys, json; print(json.dumps({'ok': True})); print('warn', file=sys.stderr); sys.exit(1)"],
        capture_output=True, text=True)
    assert proc.returncode == 1
    assert json.loads(out.read_text()) == {"ok": True}
    assert err.read_text().strip() == "warn"
    result = json.loads(proc.stdout)                       # --json output stays parseable
    assert "stdout" not in result and "stderr" not in result
    entry = json.loads(log.read_text(encoding="utf-8").strip())
    assert entry["artifacts"] == ["planning-mds/artifacts/out.txt", "planning-mds/artifacts/err.txt"]
    assert entry["exit_code"] == 1


def test_exec_and_log_rejects_capture_outside_product_root(tmp_path):
    (tmp_path / "p").mkdir()
    root, log = _product_root(tmp_path / "p")
    proc = subprocess.run(
        [sys.executable, str(EXEC_AND_LOG), "--log", str(log), "--product-root", str(root),
         "--cwd", "product", "--stdout", str(tmp_path / "outside.txt"), "--",
         sys.executable, "-c", "print('x')"],
        capture_output=True, text=True)
    assert proc.returncode == 2
    assert "capture_escapes_root" in proc.stdout
    assert not (tmp_path / "outside.txt").exists()


def test_lifecycle_list_regression():
    proc = subprocess.run([sys.executable, str(LIFECYCLE), "--list"],
                          cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert proc.returncode == 0
    assert "Lifecycle stages and required gates" in proc.stdout

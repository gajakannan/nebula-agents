"""Tests for gate_runtime.py (F0007-S0004) — the shared shell-free runtime."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "agents" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import gate_runtime as gr  # noqa: E402


def test_execute_argv_runs_shell_free(tmp_path):
    r = gr.execute_argv([sys.executable, "-c", "print('hi')"], cwd=tmp_path)
    assert r.exit_code == 0 and not r.timed_out and "hi" in r.stdout


def test_metacharacters_stay_one_literal_arg(tmp_path):
    payload = "a; b $(whoami) && rm -rf x | cat > y"
    r = gr.execute_argv(
        [sys.executable, "-c", "import sys; open('out.txt','w').write(sys.argv[1])", payload],
        cwd=tmp_path)
    assert r.exit_code == 0
    assert (tmp_path / "out.txt").read_text() == payload  # no shell expansion whatsoever


def test_timeout_is_detected_and_process_group_killed(tmp_path):
    start = time.monotonic()
    r = gr.execute_argv([sys.executable, "-c", "import time; time.sleep(30)"],
                        cwd=tmp_path, timeout=0.5)
    elapsed = time.monotonic() - start
    assert r.timed_out and elapsed < 10, "timeout must fire promptly, not wait out the sleep"
    assert r.signal == 9 or (r.exit_code is not None and r.exit_code < 0)


def test_missing_executable_named_error(tmp_path):
    with pytest.raises(gr.GateRuntimeError) as exc:
        gr.execute_argv(["definitely-not-a-real-binary-zzz"], cwd=tmp_path)
    assert exc.value.code == "executable_not_found"


def test_capture_false_inherits_streams(tmp_path):
    r = gr.execute_argv([sys.executable, "-c", "print('streamed')"], cwd=tmp_path, capture=False)
    assert r.exit_code == 0 and r.stdout is None


def test_run_operation_unknown_cwd_label(tmp_path):
    op = {"run": {"argv": [sys.executable, "-c", "pass"], "cwd": "bogus"}}
    with pytest.raises(gr.GateRuntimeError) as exc:
        gr.run_operation(op, product_root=tmp_path)
    assert exc.value.code == "unknown_cwd_label"


def test_run_operation_rejects_undeclared_mutation(tmp_path):
    op = {"run": {"argv": [sys.executable, "-c", "pass"], "cwd": "product", "mutates": ["bogus"]}}
    with pytest.raises(gr.GateRuntimeError) as exc:
        gr.run_operation(op, product_root=tmp_path)
    assert exc.value.code == "undeclared_mutation_class"


def test_run_operation_rejects_unresolved_placeholder(tmp_path):
    op = {"run": {"argv": [sys.executable, "-c", "pass", "{MISSING}"], "cwd": "product"}}
    with pytest.raises(gr.GateRuntimeError) as exc:
        gr.run_operation(op, product_root=tmp_path, variables={})
    assert exc.value.code == "unresolved_placeholder"


def test_run_operation_expands_placeholders(tmp_path):
    op = {"run": {"argv": [sys.executable, "-c",
                           "import sys; open('v.txt','w').write(sys.argv[1])", "{FEATURE_ID}"],
                  "cwd": "product"}}
    res = gr.run_operation(op, product_root=tmp_path, variables={"FEATURE_ID": "F0007"})
    assert res["ok"] and (tmp_path / "v.txt").read_text() == "F0007"


def test_run_operation_writes_normalized_telemetry(tmp_path):
    (tmp_path / "planning-mds").mkdir()
    log = tmp_path / "planning-mds" / "commands.log"
    op = {"run": {"argv": [sys.executable, "-c", "open('art.txt','w').write('x')"],
                  "cwd": "product", "expected_artifacts": ["art.txt"]}}
    res = gr.run_operation(op, product_root=tmp_path, run_folder=tmp_path, log_path=log)
    assert res["log_written"] and res["exit_code"] == 0
    entry = json.loads(log.read_text(encoding="utf-8").strip())
    assert entry["schema_version"] == 1
    assert entry["cwd"] == "{PRODUCT_ROOT}"
    assert entry["exit_code"] == 0
    assert entry["artifacts"] == ["art.txt"]  # normalized to product-relative


def test_run_operation_rejects_artifact_outside_product_root(tmp_path):
    (tmp_path / "planning-mds").mkdir()
    log = tmp_path / "planning-mds" / "commands.log"
    op = {"run": {"argv": [sys.executable, "-c", "pass"], "cwd": "product"}}
    with pytest.raises(gr.GateRuntimeError) as exc:
        gr.run_operation(op, product_root=tmp_path, log_path=log,
                         extra_artifacts=["/etc/hostname"])
    assert exc.value.code == "log_write_failed"

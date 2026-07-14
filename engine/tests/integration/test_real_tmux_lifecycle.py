from __future__ import annotations

import json
import os
import secrets
import shlex
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from nebula_agents.domain.enums import ProviderKey
from nebula_agents.domain.models import LaunchDescriptor, serialize_record
from nebula_agents.infrastructure.process import SubprocessRunner
from nebula_agents.infrastructure.tmux import TmuxAdapter


def test_real_tmux_fake_provider_launch_and_attach_reuses_one_process(
    tmp_path: Path, monkeypatch
) -> None:
    """Exercise the real tmux shell seam and attach without launching twice."""

    assert shutil.which("tmux") is not None
    assert shutil.which("script") is not None
    suffix = secrets.token_hex(4)
    run_id = f"2026-07-13-{suffix}"
    session = f"nebula-F0001-{suffix}"
    workspace = tmp_path / "workspace"
    runtime = workspace / ".nebula-agents" / "runtime"
    run_root = runtime / run_id
    run_root.mkdir(parents=True, mode=0o700)
    runtime.chmod(0o700)
    run_root.chmod(0o700)
    counter = run_root / "provider-starts.txt"
    ready = run_root / "provider-ready.txt"
    python = str(Path(sys.executable).resolve())
    fake_provider = Path(__file__).resolve().parents[1] / "fixtures" / "fake_provider.py"
    descriptor = LaunchDescriptor(
        "1.0",
        run_id,
        ProviderKey.CODEX,
        python,
        (
            python,
            str(fake_provider),
            "--mode",
            "wait",
            "--counter",
            str(counter),
            "--ready-file",
            str(ready),
        ),
        str(workspace.resolve()),
        ("PATH", "HOME", "TERM", "LANG"),
        os.getuid(),
        uuid4(),
        datetime.now(UTC),
    )
    descriptor_path = run_root / "launch-descriptor.json"
    descriptor_path.write_text(
        json.dumps(serialize_record(descriptor)), encoding="utf-8"
    )
    descriptor_path.chmod(0o600)
    monkeypatch.setenv(
        "PATH", f"/tmp/f0001-venv/bin:{os.environ.get('PATH', '/usr/bin:/bin')}"
    )
    adapter = TmuxAdapter(SubprocessRunner())
    try:
        adapter.create_session(session, descriptor_path)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not ready.exists():
            time.sleep(0.05)
        assert ready.exists(), "fake provider did not reach its interactive wait state"
        assert adapter.has_session(session)
        assert counter.read_text(encoding="utf-8") == "1"
        assert not descriptor_path.exists(), "session-entry must retire the descriptor"

        subprocess.run(
            [
                "tmux",
                "run-shell",
                "-b",
                "-t",
                session,
                f"sleep 0.3; tmux detach-client -s {session}",
            ],
            check=True,
            timeout=2,
        )
        attached = subprocess.run(
            [
                "script",
                "-qfec",
                shlex.join(("tmux", "attach-session", "-t", session)),
                "/dev/null",
            ],
            cwd=workspace,
            env={
                "PATH": os.environ["PATH"],
                "HOME": os.environ.get("HOME", str(tmp_path)),
                "TERM": "xterm-256color",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=5,
            check=False,
        )
        assert attached.returncode == 0, attached.stdout.decode(errors="replace")
        assert adapter.has_session(session), "attach must not replace or end the session"
        assert counter.read_text(encoding="utf-8") == "1", "attach started a second provider"
    finally:
        subprocess.run(
            ["tmux", "kill-session", "-t", session],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
            check=False,
        )


from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from pathlib import Path
from typing import Sequence

from nebula_agents.domain.models import ProcessResult
from nebula_agents.domain.redaction import StreamingRedactor, sanitize_terminal_text


def _safe_text(value: bytes, limit: int) -> tuple[str, bool]:
    truncated = len(value) > limit
    text = value[:limit].decode("utf-8", errors="replace")
    text, terminal_truncated = sanitize_terminal_text(text, max_chars=limit, max_lines=2_000)
    return text, truncated or terminal_truncated


class _BoundedStream:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.value = bytearray()
        self.redactor = StreamingRedactor()
        self.truncated = False

    def _append(self, payload: bytes) -> None:
        remaining = self.limit - len(self.value)
        if remaining > 0:
            self.value.extend(payload[:remaining])
        if len(payload) > remaining:
            self.truncated = True

    def feed(self, payload: bytes) -> None:
        self._append(self.redactor.feed(payload))

    def finalize(self) -> tuple[str, bool]:
        self._append(self.redactor.finalize())
        text, text_truncated = _safe_text(bytes(self.value), self.limit)
        return text, self.truncated or text_truncated


class SubprocessRunner:
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        timeout_seconds: float,
        capture_limit: int,
        env_names: Sequence[str] = (),
        pass_fds: Sequence[int] = (),
    ) -> ProcessResult:
        if not argv or any(not isinstance(item, str) or not item or "\x00" in item for item in argv):
            raise ValueError("argv must contain non-empty, NUL-free strings")
        if timeout_seconds <= 0 or capture_limit <= 0:
            raise ValueError("timeout and capture limit must be positive")
        if any(not isinstance(fd, int) or isinstance(fd, bool) or fd < 0 for fd in pass_fds):
            raise ValueError("pass_fds must contain non-negative descriptors")
        environment = {name: os.environ[name] for name in env_names if name in os.environ}
        started = time.monotonic()
        process = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
            pass_fds=tuple(pass_fds),
        )
        selector = selectors.DefaultSelector()
        streams = {
            "stdout": _BoundedStream(capture_limit),
            "stderr": _BoundedStream(capture_limit),
        }
        assert process.stdout is not None and process.stderr is not None
        for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        deadline = started + timeout_seconds
        timed_out = False
        drain_deadline: float | None = None
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0 and not timed_out:
                    timed_out = True
                    drain_deadline = time.monotonic() + 0.25
                    if process.poll() is None:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                if drain_deadline is not None and time.monotonic() >= drain_deadline:
                    # A detached descendant may retain inherited pipe handles even
                    # after the command's process group is gone. Never let that
                    # defeat the caller's timeout contract.
                    for key in tuple(selector.get_map().values()):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    break
                events = selector.select(0.05 if timed_out else max(0.0, min(0.05, remaining)))
                for key, _ in events:
                    try:
                        chunk = os.read(key.fileobj.fileno(), 16_384)
                    except BlockingIOError:
                        continue
                    if chunk:
                        streams[key.data].feed(chunk)
                    else:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                if process.poll() is not None and not events:
                    # Pipes will become readable at EOF; keep draining until both
                    # descriptors have been unregistered.
                    continue
            process.wait()
        finally:
            selector.close()
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
        stdout, out_truncated = streams["stdout"].finalize()
        stderr, err_truncated = streams["stderr"].finalize()
        return_code = process.returncode
        if return_code is None:
            return_code = 124 if timed_out else 8
        elif return_code < 0:
            return_code = min(255, 128 + abs(return_code))
        return ProcessResult(
            argv0=Path(argv[0]).name,
            exit_code=124 if timed_out else return_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=max(0, int((time.monotonic() - started) * 1000)),
            timed_out=timed_out,
            truncated=out_truncated or err_truncated,
        )

from __future__ import annotations

import re


REDACTION_MARKER = b"[REDACTED]"
_PRIVATE_BEGIN = re.compile(
    rb"-----BEGIN ([A-Z0-9 ]{0,40}PRIVATE KEY)-----", re.IGNORECASE
)

_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE | re.DOTALL)
    for pattern in (
        rb"Bearer\s+[A-Za-z0-9._~+/=-]{8,4096}",
        rb"(?:sk|pk)-(?:live|test|proj)?-?[A-Za-z0-9_-]{8,4096}",
        rb"(?:ghp_|github_pat_|xox[baprs]-)[_A-Za-z0-9-]{8,4096}",
        rb"AKIA[A-Z0-9]{16}",
        rb"(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|secret)\s*[:=]\s*[^\s,;]{4,4096}",
        rb"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s]{4,4096}",
    )
)


class StreamingRedactor:
    """Redacts credential-like byte sequences before any caller writes output."""

    def __init__(self, overlap: int = 8192) -> None:
        if overlap < 4096:
            raise ValueError("redaction overlap must be at least 4096 bytes")
        self._overlap = overlap
        self._buffer = b""
        self._private_end: bytes | None = None
        self.findings = 0

    def _redact(self, value: bytes) -> bytes:
        for pattern in _PATTERNS:
            value, count = pattern.subn(REDACTION_MARKER, value)
            self.findings += count
        return value

    def feed(self, chunk: bytes) -> bytes:
        if not isinstance(chunk, bytes):
            raise TypeError("redactor input must be bytes")
        self._buffer += chunk
        emitted = bytearray()

        while True:
            if self._private_end is not None:
                end_at = self._buffer.lower().find(self._private_end)
                if end_at < 0:
                    # Content inside an opened private-key block is never emitted.
                    # Retain only enough bytes to recognize an END marker split
                    # across chunks, bounding memory for arbitrarily large input.
                    retained = max(0, len(self._private_end) - 1)
                    if len(self._buffer) > retained:
                        self._buffer = self._buffer[-retained:] if retained else b""
                    return bytes(emitted)
                self._buffer = self._buffer[end_at + len(self._private_end) :]
                self._private_end = None
                continue

            private_begin = _PRIVATE_BEGIN.search(self._buffer)
            if private_begin is not None:
                emitted.extend(self._redact(self._buffer[: private_begin.start()]))
                emitted.extend(REDACTION_MARKER)
                self.findings += 1
                label = private_begin.group(1).lower()
                self._private_end = b"-----end " + label + b"-----"
                self._buffer = self._buffer[private_begin.end() :]
                continue

            if len(self._buffer) <= self._overlap:
                return bytes(emitted)
            cut = len(self._buffer) - self._overlap
            # If a complete match straddles the proposed emission boundary, retain
            # the whole match. Publishing even one raw prefix byte would allow the
            # caller to reconstruct the credential after the next feed/finalize.
            for pattern in _PATTERNS:
                for match in pattern.finditer(self._buffer):
                    if match.start() < cut < match.end():
                        cut = min(cut, match.start())
            safe, self._buffer = self._buffer[:cut], self._buffer[cut:]
            emitted.extend(self._redact(safe))
            return bytes(emitted)

    def finalize(self) -> bytes:
        result = self.feed(b"")
        if self._private_end is None:
            result += self._redact(self._buffer)
        self._buffer = b""
        self._private_end = None
        return result


_CONTROL = re.compile(r"(?:\x1b\[[0-?]*[ -/]*[@-~])|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_terminal_text(value: str, *, max_chars: int = 16_000, max_lines: int = 200) -> tuple[str, bool]:
    clean = _CONTROL.sub("", value)
    lines = clean.splitlines(keepends=True)
    truncated = len(lines) > max_lines
    clean = "".join(lines[:max_lines])
    if len(clean) > max_chars:
        clean = clean[:max_chars]
        truncated = True
    return clean, truncated

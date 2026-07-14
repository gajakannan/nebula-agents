from __future__ import annotations

import pytest

from nebula_agents.domain.redaction import (
    REDACTION_MARKER,
    StreamingRedactor,
    sanitize_terminal_text,
)


def _sentinels() -> tuple[bytes, ...]:
    return (
        b"Bearer " + b"test-only-token-0123456789abcdef",
        b"api_" + b"key=test-only-0123456789abcdef",
        b"ghp_" + b"testonly0123456789abcdef",
        b"AKIA" + b"ABCDEFGHIJKLMNOP",
        b"postgres" + b"://operator:test-only-password@localhost/db",
        b"-----BEGIN TEST " + b"PRIVATE KEY-----\n"
        + b"test-only-private-material"
        + b"\n-----END TEST " + b"PRIVATE KEY-----",
    )


@pytest.mark.parametrize("sentinel", _sentinels())
def test_finalize_redacts_each_required_secret_class(sentinel: bytes) -> None:
    redactor = StreamingRedactor()
    output = redactor.feed(b"before " + sentinel + b" after") + redactor.finalize()
    assert sentinel not in output
    assert REDACTION_MARKER in output
    assert redactor.findings >= 1


@pytest.mark.parametrize("sentinel", _sentinels())
def test_streaming_redaction_never_reconstructs_secret_across_any_chunk_split(
    sentinel: bytes,
) -> None:
    for split in range(1, len(sentinel)):
        redactor = StreamingRedactor()
        emitted = bytearray()
        emitted.extend(redactor.feed(sentinel[:split]))
        emitted.extend(redactor.feed(sentinel[split:]))
        # Force an emission boundary one byte into the sentinel. A safe overlap
        # implementation must not publish the prefix before it can classify the
        # complete token held in the overlap.
        emitted.extend(redactor.feed(b"\n" + b"x" * (8192 - len(sentinel))))
        emitted.extend(redactor.finalize())
        assert sentinel not in bytes(emitted), f"secret leaked at split {split}"


def test_redactor_rejects_non_bytes_and_unsafe_overlap() -> None:
    with pytest.raises(ValueError, match="at least 4096"):
        StreamingRedactor(overlap=128)
    with pytest.raises(TypeError, match="must be bytes"):
        StreamingRedactor().feed("not bytes")  # type: ignore[arg-type]


def test_finalize_is_idempotent_and_does_not_repeat_output() -> None:
    redactor = StreamingRedactor()
    assert redactor.feed(b"ordinary output") == b""
    assert redactor.finalize() == b"ordinary output"
    assert redactor.finalize() == b""


def test_oversized_unterminated_private_key_discards_until_exact_matching_end() -> None:
    redactor = StreamingRedactor()
    emitted = bytearray()
    emitted.extend(redactor.feed(b"before\n-----BEGIN OPENSSH PRIVATE KEY-----\n"))

    private_material = b"test-only-private-material-" * 50_000
    assert len(private_material) > 1_048_576
    for start in range(0, len(private_material), 65_537):
        emitted.extend(redactor.feed(private_material[start : start + 65_537]))

    # A syntactically valid END for a different key kind is still private data.
    emitted.extend(
        redactor.feed(
            b"\n-----END RSA PRIVATE KEY-----\n"
            b"must-remain-discarded-after-bogus-end\n"
        )
    )
    assert private_material[:128] not in emitted
    assert b"must-remain-discarded-after-bogus-end" not in emitted
    assert len(redactor._buffer) < 64

    # Exercise a matching END split across feeds; safe output resumes only once
    # the complete label-exact marker has been recognized.
    emitted.extend(redactor.feed(b"-----END OPENSSH PRIVATE"))
    assert b"OPENSSH PRIVATE" not in emitted
    emitted.extend(redactor.feed(b" KEY-----\nafter-safe\n"))
    emitted.extend(redactor.finalize())

    output = bytes(emitted)
    assert output == b"before\n" + REDACTION_MARKER + b"\nafter-safe\n"
    assert b"test-only-private-material" not in output
    assert b"RSA PRIVATE KEY" not in output
    assert redactor.findings == 1


def test_finalize_discards_an_unterminated_private_key_tail() -> None:
    redactor = StreamingRedactor()

    output = redactor.feed(
        b"safe-prefix\n-----BEGIN TEST PRIVATE KEY-----\nprivate-material"
    )
    output += redactor.finalize()

    assert output == b"safe-prefix\n" + REDACTION_MARKER
    assert b"private-material" not in output
    assert redactor.findings == 1


def test_streaming_scan_handles_multiple_matches_before_emission_boundary() -> None:
    first = b"Bearer first-token-0123456789"
    second = b"Bearer second-token-0123456789"
    redactor = StreamingRedactor()

    output = redactor.feed(first + b" " + second + b" " + b"x" * 8192)
    output += redactor.finalize()

    assert first not in output
    assert second not in output
    assert output.count(REDACTION_MARKER) == 2


def test_terminal_preview_truncates_by_character_limit_without_line_overflow() -> None:
    preview, truncated = sanitize_terminal_text(
        "x" * 100, max_chars=12, max_lines=200
    )

    assert preview == "x" * 12
    assert truncated is True


def test_terminal_preview_strips_controls_and_bounds_lines_and_scalars() -> None:
    text = "\x1b[31mcolored\x1b[0m\x00\n" + "line\n" * 300
    preview, truncated = sanitize_terminal_text(text, max_chars=40, max_lines=5)
    assert "\x1b" not in preview
    assert "\x00" not in preview
    assert len(preview) <= 40
    assert len(preview.splitlines()) <= 5
    assert truncated is True

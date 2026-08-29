from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
from uuid import UUID, uuid4


class ErrorCode(str, Enum):
    USAGE_ERROR = "USAGE_ERROR"
    PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"
    RUNTIME_DIR_DENIED = "RUNTIME_DIR_DENIED"
    PROMPT_NOT_FOUND = "PROMPT_NOT_FOUND"
    PROVIDER_NOT_FOUND = "PROVIDER_NOT_FOUND"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    STALE_REVISION = "STALE_REVISION"
    GATE_BLOCKED = "GATE_BLOCKED"
    VALIDATOR_UNKNOWN = "VALIDATOR_UNKNOWN"
    COMMAND_FAILED = "COMMAND_FAILED"
    STATE_IO = "STATE_IO"
    STATE_CORRUPT = "STATE_CORRUPT"
    SCHEMA_UNSUPPORTED = "SCHEMA_UNSUPPORTED"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    STATE_LOCK_TIMEOUT = "STATE_LOCK_TIMEOUT"
    TIMEOUT = "TIMEOUT"
    PATH_DENIED = "PATH_DENIED"
    TRANSCRIPT_UNAVAILABLE = "TRANSCRIPT_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    # F0003 additions. Each maps to an existing exit class -- contract 1.1 adds no new
    # class (runtime contract, section 4).
    ARTIFACT_NOT_FOUND = "ARTIFACT_NOT_FOUND"          # not-found  -> 4
    PROPOSAL_NOT_FOUND = "PROPOSAL_NOT_FOUND"          # not-found  -> 4
    REDACTION_FAILED = "REDACTION_FAILED"              # gate-blocked -> 7
    PROPOSAL_TARGET_FORBIDDEN = "PROPOSAL_TARGET_FORBIDDEN"  # forbidden -> 5
    EVIDENCE_STALE = "EVIDENCE_STALE"                  # gate-blocked -> 7
    CAPABILITY_BLOCKED = "CAPABILITY_BLOCKED"          # preflight  -> 3
    DIGEST_COLLISION = "DIGEST_COLLISION"              # conflict   -> 6


EXIT_BY_CATEGORY = {
    "usage": 2,
    "preflight": 3,
    "not-found": 4,
    "forbidden": 5,
    "conflict": 6,
    "gate-blocked": 7,
    "command-failed": 8,
    "state-io": 9,
    "timeout": 10,
    "interrupted": 130,
}


@dataclass(slots=True)
class NebulaError(Exception):
    code: ErrorCode
    message: str
    category: str
    remediation: str
    details: tuple[Mapping[str, Any], ...] = ()
    correlation_id: UUID = field(default_factory=uuid4)

    @property
    def exit_code(self) -> int:
        return EXIT_BY_CATEGORY.get(self.category, 8)

    def __str__(self) -> str:
        return self.message


def error(
    code: ErrorCode,
    message: str,
    category: str,
    remediation: str,
    **details: Any,
) -> NebulaError:
    safe_details = (details,) if details else ()
    return NebulaError(code, message, category, remediation, safe_details)

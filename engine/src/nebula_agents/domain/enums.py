from __future__ import annotations

from enum import Enum


class ProviderKey(str, Enum):
    CODEX = "codex"
    CLAUDE = "claude"


class Role(str, Enum):
    LOCAL_OPERATOR = "LocalOperator"
    REVIEWER = "Reviewer"
    SYSTEM = "System"


class Action(str, Enum):
    PROBE = "Probe"
    LAUNCH = "Launch"
    ATTACH = "Attach"
    READ_STATE = "ReadState"
    RUN_VALIDATOR = "RunValidator"
    DECIDE_GATE = "DecideGate"
    CONFIGURE_TRANSCRIPT = "ConfigureTranscript"


class RunStatus(str, Enum):
    PREFLIGHT_PENDING = "PreflightPending"
    LAUNCHING = "Launching"
    ACTIVE = "Active"
    DETACHED_OR_EXITED = "DetachedOrExited"
    FAILED = "Failed"
    EXITED = "Exited"
    UNKNOWN = "Unknown"


class GateStatus(str, Enum):
    PENDING = "Pending"
    BLOCKED = "Blocked"
    APPROVED = "Approved"
    HELD = "Held"
    UNKNOWN = "Unknown"


class DecisionKind(str, Enum):
    APPROVE = "Approve"
    HOLD = "Hold"


class TranscriptStatus(str, Enum):
    DISABLED = "Disabled"
    ACTIVE = "Active"
    FAILED = "Failed"
    COMPLETED = "Completed"


class RedactionStatus(str, Enum):
    NOT_RUN = "NotRun"
    PASSED = "Passed"
    REDACTED = "Redacted"
    FAILED = "Failed"


class ArtifactStatus(str, Enum):
    PENDING = "Pending"
    AVAILABLE = "Available"
    MISSING = "Missing"
    MOVED = "Moved"
    MALFORMED = "Malformed"
    DENIED = "Denied"
    STALE = "Stale"


class ValidatorKey(str, Enum):
    STORIES = "stories"
    TRACKERS = "trackers"
    TEMPLATES = "templates"


class PromptAction(str, Enum):
    PLAN = "plan"
    FEATURE = "feature"
    BUILD = "build"
    REVIEW = "review"
    VALIDATE = "validate"

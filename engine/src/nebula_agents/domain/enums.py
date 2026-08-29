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
    # F0003 additions. RunValidator keeps its F0001 meaning -- "execute an allowlisted
    # validator", the `validate` command alone -- because it does not describe indexing,
    # summarizing, or drafting. Overloading it was rejected as plan-review finding H1.
    INDEX_EVIDENCE = "IndexEvidence"
    DRAFT_PROPOSAL = "DraftProposal"
    # Deliberately separate from DraftProposal. Drafting is safe to run automatically;
    # deciding is not. One capability covering both would let an automated caller approve
    # its own proposals -- an escalation path closed here by construction (ADR-009).
    DECIDE_PROPOSAL = "DecideProposal"


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


# --------------------------------------------------------------------------- #
# F0003 vocabularies
# --------------------------------------------------------------------------- #
class ArtifactKind(str, Enum):
    """The closed set of evidence artifact kinds (runtime contract 1.1, section 3)."""

    TRANSCRIPT = "transcript"
    COMMAND_LOG = "command-log"
    VALIDATOR_OUTPUT = "validator-output"
    MANIFEST = "manifest"
    STATUS = "status"
    METRIC = "metric"
    LEARNING_PROPOSAL = "learning-proposal"


class SourceRoot(str, Enum):
    """An approved root that can own an artifact (ADR-006).

    `key` is the two-character discriminator that appears in an artifact ID. It is a
    persisted contract, not a display detail: an ID is parsed by consumers, so these
    values cannot change without a contract version bump.
    """

    WORKSPACE = "workspace"
    RUNTIME = "runtime"
    EVIDENCE = "evidence"

    @property
    def key(self) -> str:
        return _ROOT_KEYS[self]


_ROOT_KEYS = {
    SourceRoot.WORKSPACE: "ws",
    SourceRoot.RUNTIME: "rt",
    SourceRoot.EVIDENCE: "ev",
}


class ArtifactRedactionStatus(str, Enum):
    """Redaction state of an indexed artifact.

    Deliberately NOT merged with F0001's `RedactionStatus`, which uses
    `NotRun|Passed|Redacted|Failed` for transcript capture. These are different
    vocabularies describing different things, and F0001's record shape may not change
    under contract 1.1. `artifact_redaction_of` maps one to the other.
    """

    PASS = "Pass"
    FAIL = "Fail"
    PENDING = "Pending"
    NOT_REQUIRED = "NotRequired"


class RetrievalPolicy(str, Enum):
    LOCAL_ONLY = "LocalOnly"
    SUMMARY_ONLY = "SummaryOnly"
    BLOCKED = "Blocked"
    MISSING = "Missing"


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"
    UNKNOWN = "unknown"


class SummaryStatus(str, Enum):
    """`PARTIAL` exists so a smaller summary never looks complete.

    When a size limit would require dropping a failure marker, the summary is `Partial`
    rather than `Pass` (ADR-008). Failure markers are never dropped for size.
    """

    PASS = "Pass"
    FAILED = "Failed"
    BLOCKED = "Blocked"
    UNSUPPORTED = "Unsupported"
    PARTIAL = "Partial"


class ProposalStatus(str, Enum):
    DRAFT = "Draft"
    ACCEPTED = "Accepted"
    EDITED = "Edited"
    REJECTED = "Rejected"
    ARCHIVED = "Archived"


class ProposalDecisionKind(str, Enum):
    """The four `learn decide --decision` values. `Draft` is a status, never a decision."""

    ACCEPTED = "Accepted"
    EDITED = "Edited"
    REJECTED = "Rejected"
    ARCHIVED = "Archived"

    @property
    def requires_reason(self) -> bool:
        return self in (ProposalDecisionKind.REJECTED, ProposalDecisionKind.ARCHIVED)


class ReviewerRole(str, Enum):
    """Who may decide a proposal, resolved from its target document -- not from the run."""

    ARCHITECT = "architect"
    SECURITY = "security"
    PRODUCT_MANAGER = "product-manager"


class CapabilityName(str, Enum):
    LAUNCH = "launch"
    ATTACH = "attach"
    TRANSCRIPT = "transcript"
    STATUS_PROBE = "status_probe"
    APPROVAL_VISIBILITY = "approval_visibility"
    FALLBACK = "fallback"


class CapabilityRequirement(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    UNSUPPORTED = "unsupported"
    FALLBACK = "fallback"


class ProbeResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class LaunchDecision(str, Enum):
    ALLOWED = "allowed"
    ALLOWED_WITH_FALLBACK = "allowed_with_fallback"
    BLOCKED = "blocked"


class ProviderMode(str, Enum):
    TMUX_NATIVE = "tmux-native"
    MANAGED_EXEC = "managed-exec"
    MANAGED_SDK = "managed-sdk"
    UNAVAILABLE = "unavailable"


class MetricName(str, Enum):
    """Closed set, so a consumer never meets an unknown key (BLUEPRINT 5.2)."""

    RUN_DURATION_SECONDS = "run_duration_seconds"
    GATE_WAIT_SECONDS = "gate_wait_seconds"
    VALIDATOR_PASS_COUNT = "validator_pass_count"
    VALIDATOR_FAIL_COUNT = "validator_fail_count"
    LATEST_FAILING_VALIDATOR = "latest_failing_validator"
    TRANSCRIPT_HEALTH = "transcript_health"
    EVIDENCE_FRESHNESS = "evidence_freshness"
    ARTIFACT_COUNT = "artifact_count"
    BLOCKED_LAUNCH_COUNT = "blocked_launch_count"


class MetricKind(str, Enum):
    COUNT = "count"
    DURATION_SECONDS = "duration_seconds"
    CATEGORY = "category"
    IDENTIFIER = "identifier"


class Confidence(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


def artifact_redaction_of(status: RedactionStatus) -> ArtifactRedactionStatus:
    """Total map from F0001's transcript vocabulary to F0003's artifact vocabulary.

    Total by construction: every `RedactionStatus` member has an entry, asserted by
    `test_artifact_redaction_mapping_is_total`. A new F0001 member added without a
    mapping fails that test rather than silently defaulting to `Pass`.
    """
    return _REDACTION_MAP[status]


_REDACTION_MAP = {
    RedactionStatus.NOT_RUN: ArtifactRedactionStatus.PENDING,
    RedactionStatus.PASSED: ArtifactRedactionStatus.PASS,
    RedactionStatus.REDACTED: ArtifactRedactionStatus.PASS,
    RedactionStatus.FAILED: ArtifactRedactionStatus.FAIL,
}

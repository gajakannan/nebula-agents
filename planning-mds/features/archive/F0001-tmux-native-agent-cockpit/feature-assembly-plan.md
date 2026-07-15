# Feature Assembly Plan — F0001: Tmux-Native Agent Cockpit

**Created:** 2026-07-13
**Author:** Architect Agent
**Status:** Completed and archived after G8 closeout
**Active Remediation Run:** `2026-07-14-b885d64c` (`rerun_of: 2026-07-13-1cfbc5a0`)
**Run:** `2026-07-13-1cfbc5a0`

## Overview

F0001 adds a local Python 3.11+ CLI/TUI that launches an already-authenticated Codex or Claude CLI in one tmux session per run, persists a crash-safe local run registry, watches governed evidence, enforces explicit gate decisions, and optionally captures a redact-before-write transcript. The repository has no existing application runtime, so the vertical slice introduces one package under `engine/` while preserving the approved no-HTTP, no-database, no-MCP, no-provider-SDK boundary.

The implementation uses only typed argv execution. The sole tmux shell seam is the constant `nebula-agents session-entry --descriptor <path>` command; `session-entry` revalidates the owner-only descriptor and calls `os.execvpe`. Presentation is `argparse` plus a stdlib `curses` renderer over the same application response records used by JSON output.

## Governing Decisions

- Python package root: `engine/`; import package: `nebula_agents`; console command: `nebula-agents`.
- Minimum Python: 3.11. Runtime dependency: `jsonschema>=4.18,<5`; test dependency: `pytest>=9.0.3,<10`, `pytest-cov>=5,<7`. Pytest 9.0.3 is the security floor because it fixes CVE-2025-71176; the remediation audit makes the earlier `<9` planning range unsafe.
- Runtime state root: `<workspace>/.nebula-agents/runtime` or the canonical `NEBULA_AGENTS_RUNTIME_DIR` override.
- Registry: atomic `run.json` snapshot plus append-only `events.jsonl`, both mode `0600`, under a mode `0700` root.
- TUI: stdlib `curses`; no third-party UI framework and no screen scraping of provider panes.
- Provider probes: executable discovery, bounded version/help output, and a provider-supported non-secret login-status probe only when installed behavior is verified. An ambiguous auth result is `authentication_attention_needed`, never a login attempt.
- Transcript filter overlap: 8 KiB; preview limit: 16,000 Unicode scalar values and 200 lines, whichever is lower; output is redacted before the first append.
- Watch interval: 500 ms; duplicate observation debounce: 100 ms; tmux-missing reconciliation requires two failed probes separated by 1 second.
- AI scope: none. Invoking a native provider CLI is process orchestration, not a new LLM workflow, prompt design, MCP surface, or model policy.

## Build Order

| Step | Scope | Stories | Rationale |
|------|-------|---------|-----------|
| 1 | Package, contracts, domain records, errors, serializers | S0001-S0006 | Establishes stable inward-facing types before adapters. |
| 2 | Identity, policy, process, provider, schema, and preflight adapters | S0001, S0006 | Proves the trust and environment boundary before launch. |
| 3 | Atomic store, launch descriptor, tmux launch/attach, recovery reducer | S0002, S0003, S0005 | Creates the durable native-session slice. |
| 4 | Evidence watcher, validator runner, gate eligibility/decision services | S0003, S0004, S0006 | Adds governed lifecycle behavior over durable runs. |
| 5 | Streaming redaction and transcript lifecycle | S0005 | Isolates the highest-risk output path after session durability exists. |
| 6 | CLI formatting and curses TUI | S0001-S0006 | Projects tested use cases without moving enforcement into presentation. |
| 7 | Unit, integration, contract, security, docs, and package smoke tests | S0001-S0006 | Closes the vertical slice and produces G2/G3 evidence. |

## Existing Code (Must Be Modified)

This repository has no populated self-hosted code knowledge graph and no F0001 runtime source. The paths below come from direct raw-artifact inspection at G0; there are no existing runtime methods to rewrite.

| File | Current State | F0001 Change |
|------|---------------|--------------|
| `planning-mds/schemas/f0001-launch-descriptor.schema.json` | Does not exist | **Create at G0** — exact owner-only session-entry descriptor contract. |
| `planning-mds/architecture/data-model.md` | Lists four F0001 schemas | **Expand at G0** — include the launch descriptor schema. |
| `planning-mds/architecture/f0001-cli-contract.md` | Defines the descriptor boundary but not its field-level schema | **Expand at G0** — link the new descriptor schema. |
| `planning-mds/features/F0001-tmux-native-agent-cockpit/STATUS.md` | Overall `Planned`; G0 not started | **Update throughout** — `In Progress`, G0 evidence, story progress, and append-only signoffs. |
| `planning-mds/features/F0001-tmux-native-agent-cockpit/GETTING-STARTED.md` | Architecture-first setup only | **Expand at implementation** — install, doctor, launch, attach, validation, recovery, and test commands. |
| `planning-mds/features/F0001-tmux-native-agent-cockpit/README.md` | Approved product/architecture overview | **Expand at implementation** — concrete entry point, state layout, and operational limitations. |
| `planning-mds/features/REGISTRY.md` | F0001 `Planned` | **Update at start/closeout** — `In Progress`, then terminal closeout state. |
| `planning-mds/features/ROADMAP.md` | F0001 `Planned` in Now | **Update at start/closeout** — reflect current execution state. |
| `planning-mds/BLUEPRINT.md` | F0001 `Planned / Now` | **Update at start/closeout** — reflect feature lifecycle and story completion. |

## New Files

| File | Layer | Purpose |
|------|-------|---------|
| `engine/pyproject.toml` | Packaging | Python metadata, dependencies, `nebula-agents` entry point, pytest/coverage configuration. |
| `engine/src/nebula_agents/__init__.py` | Package | Contract version and package metadata. |
| `engine/src/nebula_agents/__main__.py` | Presentation | `python -m nebula_agents` entry point. |
| `engine/src/nebula_agents/bootstrap.py` | Composition | Explicit construction of ports, adapters, and application services. |
| `engine/src/nebula_agents/domain/enums.py` | Domain | Provider, run, gate, transcript, artifact, action, and error enums. |
| `engine/src/nebula_agents/domain/models.py` | Domain | Immutable records matching the approved JSON contracts. |
| `engine/src/nebula_agents/domain/errors.py` | Domain | Stable error codes/categories and exit mapping. |
| `engine/src/nebula_agents/domain/transitions.py` | Domain | Pure session, gate, and transcript transition guards/reducers. |
| `engine/src/nebula_agents/domain/redaction.py` | Domain | Pure streaming redaction state and shared secret-pattern rules. |
| `engine/src/nebula_agents/application/ports.py` | Application | Protocols for providers, tmux, processes, repository, identity, clock, schema, watcher, and transcript pipe. |
| `engine/src/nebula_agents/application/authorization.py` | Application | Default-deny local ABAC decision logic. |
| `engine/src/nebula_agents/application/preflight.py` | Application | `doctor` orchestration and sanitized readiness result. |
| `engine/src/nebula_agents/application/runs.py` | Application | Launch, attach, session reconciliation, and recovery use cases. |
| `engine/src/nebula_agents/application/gates.py` | Application | Validator execution, eligibility, hold/resume/approve use cases. |
| `engine/src/nebula_agents/application/transcripts.py` | Application | Transcript enable/complete/fail/preview use cases. |
| `engine/src/nebula_agents/application/queries.py` | Application | Read-only sessions, status, evidence, and TUI projections. |
| `engine/src/nebula_agents/infrastructure/config.py` | Infrastructure | Workspace/runtime resolution, allowlists, timeouts, watched paths. |
| `engine/src/nebula_agents/infrastructure/identity.py` | Infrastructure | OS UID/GID/username subject resolution. |
| `engine/src/nebula_agents/infrastructure/policy_store.py` | Infrastructure | Schema-validated mode-0600 local policy loading and initialization. |
| `engine/src/nebula_agents/infrastructure/schema_registry.py` | Infrastructure | Draft 2020-12 JSON Schema loading/validation from `planning-mds/schemas`. |
| `engine/src/nebula_agents/infrastructure/process.py` | Infrastructure | No-shell bounded subprocess execution. |
| `engine/src/nebula_agents/infrastructure/providers.py` | Infrastructure | Codex/Claude adapters and provider registry. |
| `engine/src/nebula_agents/infrastructure/tmux.py` | Infrastructure | Session create/probe/attach/pipe operations. |
| `engine/src/nebula_agents/infrastructure/filesystem_store.py` | Infrastructure | Lock, event append/fsync, atomic snapshot, backups, replay. |
| `engine/src/nebula_agents/infrastructure/watcher.py` | Infrastructure | Portable polling watcher and debounce. |
| `engine/src/nebula_agents/infrastructure/transcript.py` | Infrastructure | Tmux pipe filter and bounded redacted preview. |
| `engine/src/nebula_agents/presentation/cli.py` | Presentation | Argument grammar, command dispatch, error/exit mapping. |
| `engine/src/nebula_agents/presentation/formatters.py` | Presentation | Stable JSON envelope and accessible table rendering. |
| `engine/src/nebula_agents/presentation/tui.py` | Presentation | Keyboard/resize-safe curses session/gate/evidence/transcript screens. |
| `engine/src/nebula_agents/presentation/session_entry.py` | Presentation boundary | Hidden descriptor-validation and `execvpe` subcommand. |
| `engine/tests/unit/*.py` | Quality | Pure domain/application tests described below. |
| `engine/tests/integration/*.py` | Quality | Filesystem, process, real-tmux, restart, and transcript tests. |
| `engine/tests/contract/*.py` | Quality | JSON Schema, CLI JSON envelope, exit-code, and table/JSON parity tests. |
| `engine/tests/security/*.py` | Quality/Security | Injection, containment, permissions, authorization, and no-secret-sentinel tests. |
| `engine/tests/fixtures/fake_provider.py` | Quality | Deterministic interactive provider executable controlled by safe argv. |

---

## Step 1 — Package, Domain, and Contract Foundation (S0001-S0006)

### Complete Domain Types

`engine/src/nebula_agents/domain/enums.py` defines `str, Enum` values exactly matching the four approved public schemas:

```python
class ProviderKey(str, Enum): CODEX = "codex"; CLAUDE = "claude"
class Role(str, Enum): LOCAL_OPERATOR = "LocalOperator"; REVIEWER = "Reviewer"; SYSTEM = "System"
class Action(str, Enum): PROBE = "Probe"; LAUNCH = "Launch"; ATTACH = "Attach"; READ_STATE = "ReadState"; RUN_VALIDATOR = "RunValidator"; DECIDE_GATE = "DecideGate"; CONFIGURE_TRANSCRIPT = "ConfigureTranscript"
class RunStatus(str, Enum): PREFLIGHT_PENDING = "PreflightPending"; LAUNCHING = "Launching"; ACTIVE = "Active"; DETACHED_OR_EXITED = "DetachedOrExited"; FAILED = "Failed"; EXITED = "Exited"; UNKNOWN = "Unknown"
class GateStatus(str, Enum): PENDING = "Pending"; BLOCKED = "Blocked"; APPROVED = "Approved"; HELD = "Held"; UNKNOWN = "Unknown"
class DecisionKind(str, Enum): APPROVE = "Approve"; HOLD = "Hold"
class TranscriptStatus(str, Enum): DISABLED = "Disabled"; ACTIVE = "Active"; FAILED = "Failed"; COMPLETED = "Completed"
class RedactionStatus(str, Enum): NOT_RUN = "NotRun"; PASSED = "Passed"; REDACTED = "Redacted"; FAILED = "Failed"
class ArtifactStatus(str, Enum): PENDING = "Pending"; AVAILABLE = "Available"; MISSING = "Missing"; MOVED = "Moved"; MALFORMED = "Malformed"; DENIED = "Denied"; STALE = "Stale"
class ValidatorKey(str, Enum): STORIES = "stories"; TRACKERS = "trackers"; TEMPLATES = "templates"
class PromptAction(str, Enum): PLAN = "plan"; FEATURE = "feature"; BUILD = "build"; REVIEW = "review"; VALIDATE = "validate"
```

`engine/src/nebula_agents/domain/models.py` contains the following complete immutable record surface; serializers convert UTC `datetime` values to `Z` strings and enum members to their values:

```python
@dataclass(frozen=True, slots=True)
class Actor:
    uid: int
    username: str
    role: Role
    display_label: str | None

@dataclass(frozen=True, slots=True)
class GateDecision:
    decision: DecisionKind
    reason: str | None
    actor: Actor
    decided_at: datetime
    record_revision: int

@dataclass(frozen=True, slots=True)
class GateSnapshot:
    gate_id: str | None
    status: GateStatus
    evidence_ready: bool
    required_evidence: tuple[str, ...]
    decision: GateDecision | None

@dataclass(frozen=True, slots=True)
class ValidatorResult:
    validator_key: ValidatorKey
    exit_code: int
    duration_ms: int
    summary: str
    artifact_path: str | None
    completed_at: datetime
    command_template: str
    gate_id: str | None
    validated_revision: int | None
    evidence_digest: str | None

@dataclass(frozen=True, slots=True)
class ArtifactObservation:
    relative_path: str
    status: ArtifactStatus
    observed_at: datetime
    size_bytes: int | None

@dataclass(frozen=True, slots=True)
class TranscriptState:
    status: TranscriptStatus
    redaction_status: RedactionStatus
    path: str | None
    preview: str | None
    redaction_findings: int

@dataclass(frozen=True, slots=True)
class RunRecord:
    schema_version: str
    revision: int
    run_id: str
    feature_id: str
    story_id: str | None
    provider_key: ProviderKey
    tmux_session: str
    workspace_root: str
    prompt_contract: str
    prompt_action: PromptAction
    status: RunStatus
    owner: Actor
    evidence_root: str | None
    gate: GateSnapshot
    latest_validator: ValidatorResult | None
    artifacts: tuple[ArtifactObservation, ...]
    transcript: TranscriptState
    audit_log_path: str
    last_event_sequence: int
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None

@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    schema_version: str
    run_id: str
    sequence: int
    event_type: str
    occurred_at: datetime
    actor: Actor
    correlation_id: UUID
    payload: Mapping[str, JsonValue]

@dataclass(frozen=True, slots=True)
class Probe:
    key: str
    status: str
    executable_path: str | None
    version: str | None
    remediation_category: str | None

@dataclass(frozen=True, slots=True)
class PreflightCheck:
    key: str
    status: str
    message: str

@dataclass(frozen=True, slots=True)
class PreflightResult:
    schema_version: str
    probed_at: datetime
    workspace_root: str
    runtime_dir: str
    prompt_contract_path: str | None
    overall_status: str
    tmux: Probe
    providers: tuple[Probe, ...]
    checks: tuple[PreflightCheck, ...]
    planning_docs_path: str | None
    missing_paths: tuple[str, ...]
```

### Error Contract

`NebulaError(code: ErrorCode, message: str, category: str, remediation: str, details: tuple[Mapping[str, JsonValue], ...], correlation_id: UUID)` is the only expected application exception. `presentation/cli.py` maps error categories to the approved exits: usage 2, preflight 3, not-found 4, forbidden 5, conflict 6, gate-blocked 7, command-failed 8, state-I/O 9, timeout 10, interrupted 130. Unexpected exceptions become a redacted `INTERNAL_ERROR` at exit 8; traceback is emitted only with a developer-only test flag and never in JSON mode.

### Serialization and Schema Guard

`serialize_record(value: object) -> dict[str, JsonValue]` and `deserialize_run_record(document: Mapping[str, JsonValue]) -> RunRecord` are deterministic. Every persistence write and machine response validates against a schema before publication. Unknown major schema versions and additional fields fail with `SCHEMA_UNSUPPORTED` or `STATE_CORRUPT`; invalid snapshots are preserved.

---

## Step 2 — Preflight, Identity, Policy, and Provider Boundary (S0001, S0006)

### Application Ports

```python
class Clock(Protocol):
    def now(self) -> datetime: ...

class IdentityPort(Protocol):
    def current_actor(self) -> Actor: ...

class SchemaPort(Protocol):
    def validate(self, schema_name: str, document: Mapping[str, JsonValue]) -> None: ...

class ProcessPort(Protocol):
    def run(self, argv: Sequence[str], *, cwd: Path, timeout_seconds: float, capture_limit: int, env_names: Sequence[str] = ()) -> ProcessResult: ...

class ProviderAdapter(Protocol):
    @property
    def key(self) -> ProviderKey: ...
    def probe(self, workspace_root: Path) -> Probe: ...
    def build_interactive_argv(self, workspace_root: Path, prompt_text: str) -> tuple[str, ...]: ...
    def classify_early_exit(self, exit_code: int, redacted_output: str) -> str: ...

class TmuxPort(Protocol):
    def probe(self) -> Probe: ...
    def has_session(self, session_name: str) -> bool: ...
    def create_session(self, session_name: str, descriptor_path: Path) -> None: ...
    def attach(self, session_name: str) -> int: ...
    def configure_pipe(self, session_name: str, filter_argv: Sequence[str] | None) -> None: ...
```

### Preflight Logic

`PreflightService.run(workspace_root: Path, runtime_dir_override: Path | None, provider_hint: ProviderKey | None, prompt_action: PromptAction | None) -> PreflightResult` performs, in order:

1. Canonicalize the workspace, project the canonical `planning-mds` path, and require `planning-mds/features`, `agents/templates/prompts/evidence-contract`, and every requested prompt path to remain within the workspace; missing contract paths are returned as a bounded workspace-relative list.
2. Resolve the runtime root; create it with `0700` only when absent, never loosen an existing mode, and record `RuntimeDirectoryInitialized` only when a run context later exists. Permission failures return `RUNTIME_DIR_DENIED`/exit 3.
3. Probe tmux and the selected provider(s) with `shutil.which`, bounded no-shell subprocesses, and a 1-second timeout per probe.
4. Never read provider credential files, API-key environment values, auth caches, shell history, or account contents. Authentication ambiguity is `authentication_attention_needed`.
5. Validate the preflight JSON document and return exit 0 only when tmux, workspace, runtime, prompt, and at least the selected provider are ready.

Codex and Claude argv construction remains adapter-owned. Implementation verifies installed `--help` text in G1 before locking flags; tests assert that common application code contains no provider-specific flags. Prompt content is one argv value and comes only from the committed action prompt allowlist.

### Authorization

`AuthorizationService.authorize(subject: Actor, action: Action, resource: AuthorizationResource, context: AuthorizationContext) -> AuthorizationDecision` defaults to deny. `LocalOperator` may mutate only owned runs. `Reviewer` reads and runs allowlisted validators; launch, attach, gate hold/approve, and transcript configuration require the matching policy grant. Policy/identity/schema errors deny. Authorization is re-evaluated under the run lock before every mutation; TUI control visibility is never enforcement.

---

## Step 3 — Persistence, Launch, Attach, and Recovery (S0002, S0003, S0005)

### Repository Contract

```python
class RunRepository(Protocol):
    def list(self, status: RunStatus | None = None) -> tuple[RunRecord, ...]: ...
    def load(self, run_id: str) -> RunRecord: ...
    def create(self, record: RunRecord, event: RuntimeEvent) -> RunRecord: ...
    def commit(self, *, expected_revision: int, next_record: RunRecord, event: RuntimeEvent) -> RunRecord: ...
    def recover(self, run_id: str) -> RunRecord: ...

@dataclass(frozen=True, slots=True)
class LaunchRequest:
    feature_id: str
    story_id: str | None
    provider_key: ProviderKey
    prompt_action: PromptAction
    requested_run_id: str | None
    run_label: str | None
    transcript_enabled: bool
    expected_revision: int | None
```

All IDs are parsed before I/O. The feature folder must resolve uniquely; story prefix must match feature; prompt action must resolve to an allowlisted evidence-contract prompt. Generated run IDs use local date plus cryptographic 8-hex suffix; tmux name is `nebula-F0001-<suffix>`.

### Launch Descriptor

`LaunchDescriptor(schema_version, run_id, provider_key, executable_path, argv, cwd, inherited_env_names, owner_uid, correlation_id, created_at)` validates against `f0001-launch-descriptor.schema.json`. It is written mode `0600` under the run directory. `session_entry.main(argv: Sequence[str] | None = None) -> int` checks descriptor ancestry, mode, owner UID, schema, executable equality with `argv[0]`, canonical cwd, and env-name allowlist, then calls `os.execvpe(executable_path, argv, filtered_environment)`. Values are never turned into shell text.

### Launch Logic

`RunService.launch(request: LaunchRequest, actor: Actor) -> RunRecord`:

1. Run fresh selected-provider preflight and authorize `Launch`.
2. Reject existing run folder, active tmux-name collision, unknown feature/story/action, invalid label, or transcript enablement without permission.
3. Write an initial `Launching` snapshot and `LaunchRequested` event at revision 0/sequence 1.
4. Build/write the validated descriptor and call `TmuxPort.create_session` with only the constant entry helper command.
5. Probe the exact session. On success, commit `RunLaunched`, status `Active`, revision 1, sequence 2, and `last_seen_at`. On create/early-exit failure, commit `LaunchFailed`, status `Failed`; never present it as active.
6. Delete the descriptor after the entry helper acknowledges validation or the launch becomes terminal; preserve only a sanitized command template.

`RunService.attach(run_id: str, actor: Actor) -> int` authorizes `Attach`, reloads the run, requires the exact recorded tmux session, appends `SessionAttached`, and delegates the terminal. It never calls a provider adapter or creates a session.

`RunService.reconcile(run_id: str, actor: Actor) -> RunRecord` requires two tmux misses one second apart before `SessionMissing`/`DetachedOrExited`. Reappearance of the exact session emits `SessionRecovered`; it never launches a substitute. `RunRepository.recover` validates the current snapshot, falls back to the newest valid same-directory backup, replays the contiguous event suffix deterministically, preserves corrupt files, and emits `StateRecoveryApplied`. No valid snapshot/event prefix returns `STATE_CORRUPT`/exit 9.

### Persistence Failure Injection

Integration tests inject failure after event flush, after temporary snapshot flush, after `os.replace`, and before directory `fsync`. Recovery must yield one contiguous event stream, one valid snapshot, and no duplicated semantic mutation. Advisory locks use `fcntl.flock` on POSIX/WSL; timeout is 5 seconds and maps to `STATE_LOCK_TIMEOUT`/exit 10.

---

## Step 4 — Watchers, Validators, and Gate Decisions (S0003, S0004, S0006)

### Watcher and Validator Ports

```python
class EvidenceWatcher(Protocol):
    def observe_once(self, run: RunRecord, paths: Sequence[str]) -> tuple[ArtifactObservation, ...]: ...

class ValidatorRunner(Protocol):
    def run(self, key: ValidatorKey, *, workspace_root: Path, feature_id: str, run_id: str, timeout_seconds: float) -> ValidatorResult: ...

@dataclass(frozen=True, slots=True)
class GateDecisionRequest:
    run_id: str
    gate_id: str
    decision: DecisionKind
    reason: str | None
    display_label: str | None
    expected_revision: int
```

The validator allowlist resolves to argv arrays only:

- `stories`: `python3 agents/product-manager/scripts/validate-stories.py --product-root <workspace> planning-mds/features/F0001-tmux-native-agent-cockpit`
- `trackers`: `python3 agents/product-manager/scripts/validate-trackers.py --product-root <workspace> --skip-feature-evidence`
- `templates`: `python3 agents/scripts/validate_templates.py`

No caller supplies executable paths, flags, cwd, or shell fragments. `GateService.run_validator(run_id: str, key: ValidatorKey, actor: Actor) -> RunRecord` authorizes, emits `ValidatorStarted`, runs with a 120-second timeout and bounded/redacted output, writes the detailed result under the evidence package when configured, then commits `ValidatorCompleted`, `ValidatorTimedOut`, or `ValidatorCancelled`. The result records only a safe allowlisted command template and binds success to the current gate, validated record revision, and SHA-256 digest of current required evidence plus semantic manifest eligibility. Previous results remain in events/artifacts while `latest_validator` is replaced.

### Gate Eligibility and Decisions

`GateService.decide(request: GateDecisionRequest, actor: Actor) -> RunRecord` reloads under lock, authorizes `DecideGate`, validates expected revision, and freshly rechecks semantic manifest eligibility, required evidence, and validator binding/digest before approval. It requires a known gate, `Pending` state, readable/fresh required evidence, and exit 0 from each required validator at the current relevant revision. `Hold` requires a nonblank reason after control-character stripping and shared secret redaction. `Approve` requires explicit confirmation supplied by presentation; it is idempotent only for the same gate/revision/actor/decision tuple.

Failed eligibility emits `GateDecisionBlocked`; authorization failure emits `AuthorizationDenied`; neither writes a decision. Successful decisions emit `GateApproved` or `GateHeld`. Resume emits `GateResumed` and returns to `Pending`; it never approves automatically.

### Evidence Observation

The baseline watcher polls every 500 ms and debounces identical notifications for 100 ms. Paths derive only from feature/action contracts and the run roots. Missing, moved, malformed, denied, and stale observations retain last valid metadata, publish an update, and block affected gates without terminating the provider. Repeated identical errors do not append duplicate audit events until status or relevant metadata changes.

---

## Step 5 — Transcript and Recovery Context (S0005)

`TranscriptService.enable(run_id: str, actor: Actor, expected_revision: int) -> RunRecord` authorizes `ConfigureTranscript`, requires an active/recoverable recorded session, validates contained mode-0600 output, initializes the shared redactor, configures tmux pipe capture, and commits `TranscriptEnabled`. Transcript defaults to `Disabled`; there is no implicit launch-time enable unless the explicit `--transcript` option was supplied and authorized.

`StreamingRedactor.feed(chunk: bytes) -> bytes` retains an 8 KiB overlap, normalizes only enough terminal framing for matching, replaces credential/private-key/bearer/API-key/connection-string matches with stable markers, and never exposes matched bytes in exceptions. `finalize() -> bytes` flushes the remaining redacted overlap. Only returned redacted bytes are appended.

`TranscriptService.preview(run_id: str, actor: Actor) -> TranscriptProjection` reads only a `Passed` or `Redacted` transcript, limits output to 16,000 scalar values and 200 lines, strips unsafe control sequences, and returns path guidance only when policy permits. Ordinary redactor/pipe/write failure closes output, commits `TranscriptFailed`, blocks preview, but leaves attach available. Clean disable or session exit emits `TranscriptCompleted`. Terminal state requires a positively inactive pipe. If failed compensation cannot durably record possibly-live capture as `Active`, the application terminates the immutable owning tmux session and verifies absence before returning `STATE_IO`.

Security tests split every sentinel at each possible byte boundary and assert it never occurs in snapshot, event, error, command, transcript, or preview output.

---

## Step 6 — CLI and Terminal UI (S0001-S0006)

### CLI Grammar

| Command | Inputs | Application call | Success/Failure |
|---------|--------|------------------|-----------------|
| `doctor` | `--provider`, `--action`, `--format` | `PreflightService.run` | 0 ready; 2 invalid input; 3 blocked/attention/denied. |
| `launch` | `--feature`, `--provider`, `--action`, optional `--story`, `--run-id`, `--label`, `--transcript`, `--format` | `RunService.launch` | 0 active; 3 preflight; 5 policy; 6 collision; 8 provider/tmux failure; 9 I/O. |
| `attach` | `--run-id` | `RunService.attach` | 0/child result; 4 missing; 5 denied; never launches. |
| `sessions` | optional `--status`, `--format` | `QueryService.sessions` | Bounded read, no event. |
| `status` | `--run-id`, `--format` | `QueryService.status` | Read-only projection, stale tmux shown explicitly. |
| `evidence` | `--run-id`, `--format` | `QueryService.evidence` | Read-only observations and known paths. |
| `validate` | `--run-id`, `--validator`, `--format` | `GateService.run_validator` | Validator exit 1..125 is preserved; runtime errors use stable classes. |
| `tui` | optional `--run-id` | Query/use-case services | Full-screen projection; mutations still enforced in application. |
| `session-entry` | hidden `--descriptor` | Descriptor validator then `execvpe` | Internal boundary; not shown in ordinary help. |
| `transcript-filter` | hidden `--run-id`, `--path` | Streaming redactor | Internal tmux pipe process. |

All data-bearing commands accept `--format table|json`. JSON uses `{contract_version, command, generated_at, data}` or the approved error envelope. Human tables use text/symbol plus color, never color alone. Output lists are bounded to 100 records by default. Control characters are removed from labels and error messages.

### TUI Screen Contract

The 80x24 baseline has four pure-projection views: session list, session detail/recovery, gate/validator dashboard, and evidence/transcript detail. Keys are `j/k` or arrows to move, `Enter` to inspect/confirm, `l` launch, `a` attach, `v` validate, `g` gate action, `t` transcript action, `r` refresh/reconcile, `q` quit, and `?` help. `KEY_RESIZE` recomputes layout without mutation or selection loss. Mutating keys open a confirmation view that names the run, action, revision, and evidence summary before dispatch.

---

## Mutation Traceability

| Screen / Entry Point | User Action | Service Method | Entity / Carrier | Authorization | Concurrency | Validation Failure | Audit / Timeline | Test Expectation |
|----------------------|-------------|----------------|------------------|---------------|-------------|--------------------|------------------|------------------|
| `doctor` | Initialize missing runtime root | `PreflightService.run` | Runtime directory | `Probe` | Atomic owner-only mkdir | `RUNTIME_DIR_DENIED`, exit 3 | No run event; result reports initialization | Repeat is idempotent and stores no secret. |
| TUI/`launch` | Launch native provider | `RunService.launch` | `RunRecord`, descriptor, tmux session | `Launch`; owner role | Unique IDs + run lock | `PREFLIGHT_BLOCKED`, `FORBIDDEN`, `CONFLICT` | `LaunchRequested`, then `RunLaunched`/`LaunchFailed` | Reload shows same run and one provider process. |
| `attach`/TUI | Attach existing session | `RunService.attach` | Existing `RunRecord` | `Attach` | Fresh tmux probe under lock | `SESSION_NOT_FOUND`, `FORBIDDEN` | `SessionAttached` | Fake adapter is never called; tmux identity reused. |
| Poller | Reconcile artifacts/session | `RunService.reconcile`, watcher | `RunRecord.artifacts/status` | System actor on owned configured root | Revision/retry; semantic dedupe | Explicit observation state | `ArtifactObserved`/`ArtifactUnavailable`/`SessionMissing`/`SessionRecovered` | Restart retains state and avoids error floods. |
| Gate dashboard/`validate` | Run allowlisted validator | `GateService.run_validator` | `latest_validator`, artifact | `RunValidator` | Fresh revision; no shell | `VALIDATOR_UNKNOWN`, timeout, command failure | Started + terminal validator event | Earlier event remains after rerun. |
| Gate dashboard | Hold/resume/approve | `GateService.decide`/`resume` | `GateSnapshot` | `DecideGate` + contextual grants | Required `expected_revision` | `GATE_BLOCKED`, `STALE_REVISION`, `FORBIDDEN` | Blocked/denied or immutable decision event | Missing evidence and failed validator cannot approve. |
| Session detail | Enable/complete transcript | `TranscriptService.enable`/`complete` | `TranscriptState`, redacted file | `ConfigureTranscript` | Fresh revision + exact tmux session | containment/mode/redactor errors | Enabled/completed/failed event | Ordinary failure leaves attach usable; an unresolvable hidden-capture mismatch terminates and verifies absence of the owning session. No raw sentinel. |
| Recovery view | Recover snapshot/reattach | `RunRepository.recover`, `RunService.attach` | Snapshot/event projection | `ReadState`, then `Attach` if chosen | Lock + contiguous replay | `STATE_CORRUPT`, `SESSION_NOT_FOUND` | `StateRecoveryApplied`/`RecoveryAttempted` | No process starts during recovery. |

## Authorization Enforcement

- Resource: local run aggregate; actions: `Probe`, `Launch`, `Attach`, `ReadState`, `RunValidator`, `DecideGate`, `ConfigureTranscript`.
- Attributes: caller UID/GIDs/role, run owner UID, workspace root, session/gate/transcript state, decision kind, validator key, expected revision.
- Pattern: local default-deny ABAC implemented in application code and backed by `f0001-local-policy.schema.json`. It is Casbin-compatible in tuple shape but F0001 does not add a Casbin runtime dependency or policy server.
- Every mutation rechecks policy under lock. Unknown identity/role/action, malformed/missing policy, stale record, or path escape denies.

## Audit Event Mapping

| Operation | Success event | Failure/blocked event | Sanitized payload keys |
|-----------|---------------|-----------------------|------------------------|
| Launch | `LaunchRequested`, `RunLaunched` | `LaunchFailed`, `AuthorizationDenied` | provider key, feature/story, action, tmux session, error category |
| Attach/reconcile | `SessionAttached`, `SessionRecovered`, `SessionExited` | `SessionMissing`, `AuthorizationDenied` | tmux session, status; no terminal content |
| Evidence watch | `ArtifactObserved` | `ArtifactUnavailable` | relative path, observation status, size |
| Validator | `ValidatorStarted`, `ValidatorCompleted` | `ValidatorTimedOut`, `ValidatorCancelled`, `AuthorizationDenied` | allowlist key, exit, duration, artifact path |
| Gate | `GateApproved`, `GateHeld`, `GateResumed` | `GateDecisionBlocked`, `AuthorizationDenied` | gate, decision, reason category, record revision |
| Transcript | `TranscriptEnabled`, `TranscriptCompleted` | `TranscriptFailed`, `AuthorizationDenied` | status, redaction count, contained relative path |
| Recovery | `RecoveryAttempted`, `StateRecoveryApplied` | operation error only when no valid run context | snapshot revision, replayed sequence range |

## Scope Breakdown

| Layer | Required Work | Owner | Status |
|------|----------------|-------|--------|
| Core runtime (`engine/src/nebula_agents/domain`, `application`, `infrastructure`) | Records, guards, ports, persistence, providers, tmux, watcher, validator, transcript | Backend Developer | Planned |
| Terminal presentation (`engine/src/nebula_agents/presentation`) | CLI, JSON/table formatters, curses screens, session entry/filter helpers | Frontend Developer, within the same Python package | Planned |
| AI (`neuron/`, prompts, MCP) | No changes; native provider invocation is not AI implementation scope | N/A | Not in scope |
| Quality (`engine/tests`) | Unit, contract, real-tmux integration, failure injection, security sentinels | Quality Engineer | Planned |
| Local package/runtime | `engine/pyproject.toml`, clean-install and console-entry smoke, Python/tmux/provider preflight | DevOps deployability check; role not required because no deployment topology changes | Planned |
| Security | Policy, path/mode, argv, redaction, dependency/secrets/SAST scan review | Security Reviewer | Planned |

## Dependency Order

```text
Architect G0: exact contracts + plan + descriptor schema
  -> Backend 1: domain/errors/serialization/ports
  -> Backend 2: preflight/policy/provider/process
  -> Backend 3: repository/tmux/launch/recovery
       [Core checkpoint: no-shell launch + restart recovery green]
  -> Backend 4: watcher/validator/gate/transcript
  -> Frontend: CLI/formatters/curses/session-entry/filter projections
       [Presentation checkpoint: table/JSON parity + 80x24/resize green]
  -> QE: full unit/contract/integration/security suite + coverage
  -> DevOps: clean venv install, entry-point, doctor/package smoke
  -> Code + Security review
```

Implementation roles may run concurrently only where paths do not overlap; shared domain/application signatures land before adapters/presentation consume them. Shared-semantic drift routes to Architect, not an implementation role.

## Integration Checkpoints

### After Step 2 — Environment Boundary

- [ ] `doctor --format json` validates against the preflight schema for Codex, Claude, missing tmux, missing provider, auth attention, and denied runtime root.
- [ ] No probe reads credential files or secret environment values; output capture is bounded/redacted.
- [ ] Policy defaults deny and reviewer grants enable only the named operation.

### After Step 3 — Durable Native Session

- [ ] Real tmux plus fake provider proves unique launch, detach, attach reuse, early exit, collision handling, and zero second-provider starts.
- [ ] Descriptor metacharacters remain one argv value; application/adapters never use `shell=True`.
- [ ] Restart and four persistence failure seams recover to a schema-valid snapshot and contiguous event stream.

### After Steps 4-5 — Governed Runtime

- [ ] Evidence changes arrive within one second; missing/denied/malformed paths block the affected gate without crashing.
- [ ] Failed/absent validators and stale revisions cannot approve; hold requires a reason; decisions survive restart.
- [ ] Transcript chunk-boundary sentinels are redacted before disk; capture failure does not disable attach.

### After Step 6 — User Slice

- [ ] Every public command has table/JSON parity, documented exits, bounded output, and no raw traceback/secrets.
- [ ] TUI is keyboard-operable at 80x24, handles resize, pairs symbols/text with color, and uses application services for every mutation.
- [ ] Full lifecycle works: doctor -> launch -> list/status -> watch -> validate -> hold/approve -> transcript -> restart -> attach/recover.

## Acceptance-Criteria Test Matrix

| Story | Unit/Contract | Integration/E2E proof |
|-------|---------------|-----------------------|
| S0001 | probe classification, path validation, JSON schema, exit mapping | installed CLI doctor with ready/missing/attention/denied fixtures; no secret sentinel persisted |
| S0002 | ID/session naming, descriptor schema, launch guards | real tmux + fake provider launch/collision/early-exit/reattach; provider start counter remains one |
| S0003 | serializer/reducer, observation transitions, debounce | restart reload, changed/deleted/denied/malformed evidence, tmux disappearance/recovery |
| S0004 | validator allowlist, gate eligibility, ABAC, stale revision | validator pass/fail/timeout/rerun; blocked approve; hold/resume/approve survives restart |
| S0005 | streaming redaction every split, preview bound, transcript transitions | real tmux pipe capture; permission/redactor failure isolation; restart attach and transcript review |
| S0006 | query purity, error envelope, table/JSON parity | sessions/status/evidence/doctor/validate from a fresh process; denied attach guidance and missing run |

Coverage target is at least 85% line coverage for `engine/src/nebula_agents`, with 100% branch coverage for transition guards, authorization decisions, descriptor validation, and streaming-redaction boundary cases. No coverage waiver is planned.

## Security and Runtime Evidence

- Dependency scan: `python -m pip check` in the clean test environment plus an advisory scan when an available locked scanner can consume `engine/pyproject.toml`.
- Secrets scan: repository/diff scan using the framework security tooling; raw report under `artifacts/security/`.
- SAST: framework `security-audit.py` and targeted no-`shell=True`/unsafe-path checks; raw report under `artifacts/security/`.
- DAST: waived because the approved feature exposes no listening network service or HTTP target; Security Reviewer records the no-target rationale.
- Runtime preflight: Python version, import/entry point, `tmux -V`, provider executable/help behavior, clean runtime directory, and real-tmux fixture readiness.
- Deployability: clean virtual environment install from `engine/`, `nebula-agents --help`, `doctor`, package build metadata, and no undeclared external service.

## Knowledge-Graph Binding Plan

Predicted semantic capabilities:

- `F0001.NativeSessionPreflight`
- `F0001.TmuxSessionLifecycle`
- `F0001.LocalRunRegistry`
- `F0001.EvidenceAndGateControl`
- `F0001.RedactedTranscriptRecovery`
- `F0001.ReadOnlyRunQueries`

Expected source glob is `engine/src/nebula_agents/**/*.py`, with tests under `engine/tests/**/*.py`. Intended bindings would be authored under `planning-mds/kg-source/bindings/F0001.yaml` and canonical nodes under `planning-mds/kg-source/nodes/` only if this product adopts the compiled semantic-graph layout before G7.

Current repository reality: `planning-mds/kg-source/`, `scripts/kg/compile.py`, and `scripts/kg/validate.py` do not exist, and `TRACKER-GOVERNANCE.md` explicitly records no populated self-hosted KG. G7 therefore must not fabricate generated graph files. At G7 the Architect will re-audit repository governance and either bind the as-built source through an adopted compiler contract or record the repository-level bootstrap limitation as a blocking closeout condition requiring explicit governance resolution.

## Risks and Blockers

| Item | Severity | Mitigation | Owner |
|------|----------|------------|-------|
| Tmux constructs commands through a shell boundary | High | Constant helper command, contained descriptor, argv revalidation, injection tests | Backend + Security |
| Transcript may contain secrets split across chunks | High | 8 KiB overlap, shared patterns, redact-before-write, exhaustive split tests, opt-in default | Backend + Security |
| Provider CLI flags/auth probes change | Medium | Adapter isolation, G1 installed-help verification, non-secret ambiguous fallback | Backend |
| Event append succeeds but snapshot replace fails | High | Deterministic reducer, backups, fsync order, failure-injection recovery tests | Backend + QE |
| Curses/tmux behavior varies by terminal | Medium | POSIX/WSL scope, 80x24 target, resize tests, direct tmux fallback | Frontend + QE |
| Feature scope exceeds a small slice | Medium | Preserve one package/no server/no MCP/no analytics; implement build order with checkpoints | Architect |
| Repository lacks the G7 compiled KG contract | High at closeout | Re-audit at G7; do not fake graph evidence; require governance/bootstrap resolution before G8 | Architect + PM |

## JSON Serialization Convention

- UTF-8, camel-free snake_case keys exactly matching committed schemas.
- UTC timestamps serialize as RFC 3339 with `Z`; readers accept equivalent offset timestamps then normalize to UTC.
- Enum values serialize exactly as approved strings; unknown values fail closed.
- Tuples serialize as arrays; UUIDs serialize lowercase hyphenated; filesystem paths serialize canonical strings.
- `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))` is used for durable JSONL events; snapshots use stable two-space indentation plus final newline.
- Public envelopes use `contract_version: "1.0"`; persisted records use `schema_version: "1.0"`.

## Composition Registration

`bootstrap.build_application(workspace_root: Path, runtime_override: Path | None = None) -> Application` constructs a single `Application` dataclass containing `preflight`, `runs`, `gates`, `transcripts`, and `queries`. It registers `SystemClock`, `OsIdentity`, `JsonSchemaRegistry`, `LocalPolicyStore`, `SubprocessRunner`, `CodexAdapter`, `ClaudeAdapter`, `TmuxAdapter`, `FilesystemRunRepository`, `PollingEvidenceWatcher`, and `TmuxTranscriptAdapter`. Domain and application modules never import infrastructure or presentation modules.

## Casbin Policy Sync

None. F0001 implements the approved local default-deny ABAC tuple directly and persists `policy.json` against `f0001-local-policy.schema.json`. No Casbin policy file or embedded resource is introduced.

## Run and Release Checklist

- [ ] `python3 -m venv <temp>` and clean `pip install -e 'engine[test]'` succeed.
- [ ] `python -m pytest engine/tests/unit engine/tests/contract` passes.
- [ ] `python -m pytest engine/tests/integration engine/tests/security` passes with real tmux and fake providers.
- [ ] `python -m pytest --cov=nebula_agents --cov-report=term-missing --cov-report=xml:<run>/artifacts/coverage/coverage.xml` meets targets.
- [ ] JSON Schema meta-validation and all contract fixtures pass.
- [ ] `nebula-agents --help`, `doctor`, `sessions`, and a fake-provider launch/attach/recovery smoke pass from the clean environment.
- [ ] Dependency, secrets, SAST, and DAST/no-target evidence are recorded.
- [ ] Feature evidence stages G1-G6 pass before G4/G5 approval/signoff progression as defined by the action contract.
- [ ] Architect reconciles as-built semantics at G7; PM alone performs G8 tracker/archive/publish closeout.

## G3 Remediation Addendum — 2026-07-14

This addendum is the execution contract for run `2026-07-14-b885d64c`. It preserves the approved Phase B architecture and remediates the blocking G3 verdict from run `2026-07-13-1cfbc5a0`; it does not reopen product scope or bypass G0-G3.

### Required Closure Work

| ID | Required outcome | Primary ownership | Mandatory proof |
|----|------------------|-------------------|-----------------|
| R1 | Human `doctor` output includes workspace, planning, runtime, prompt, tmux executable, and provider executable paths. All machine-readable checked and missing paths are absolute. | Presentation + Backend | Table/JSON parity tests and ready/missing-path CLI probes. |
| R2 | Failed/exited runs never advertise attach; failure after tmux creation compensates the external session and persists a terminal, attach-disabled state without an orphan provider. | Backend | Forced commit-failure and provider-exit integration tests, including real tmux where applicable. |
| R3 | Every evidence entry point uses the same last-valid reconciliation policy; JSON, YAML, and governed Markdown failures are categorized as malformed; the production watch set includes the complete required artifact set and expected missing paths. | Backend | Public service, CLI, watcher, malformed-format, deletion, and restart tests. |
| R4 | Validator scripts and governed feature/story/evidence inputs are ancestry-checked, reject symlinks, and are opened/used through descriptor-bound stable reads where validation and use must be atomic. | Backend + Architect | Symlink-escape, replacement-race, descriptor validation, and allowlist tests. |
| R5 | Transcript completion is crash-consistent: external piping and durable terminal state reconcile after commit failure; completed and failed worker sidecars are recoverable; worker/sidecar failures produce a durable sanitized reason; unavailable liveness proof cannot authorize terminal state; failed truthful-Active compensation terminates and verifies absence of the owning session. | Backend | Commit-failure, sidecar-failure, restart, completed-sidecar, failed-reason, strict tmux-probe, double-prepublication, and verified session-termination tests. |
| R6 | Corrupt snapshots remain discoverable and can reach recovery through supported CLI and TUI actions. Recovery shows the last gate, last audit event, transcript path when safe, and an explicit sanitized command. | Backend + Presentation | Corrupt-snapshot list/CLI/TUI/restart tests and table/JSON parity. |
| R7 | The official coverage artifact records branch coverage. Transition guards, authorization decisions, descriptor validation, and streaming-redaction boundary branches reach 100%, with no coverage waiver. | Quality Engineer | Branch-enabled XML plus risk-area measurement and test mapping. |
| R8 | `engine/pyproject.toml` and this plan use the audited `pytest>=9.0.3,<10` contract. The prior `<9` range is superseded because every pytest version through 9.0.2 is affected by CVE-2025-71176. | Architect + Backend + Quality Engineer | Metadata assertion, clean install/pip check, clean dependency audit, and full suite on pytest 9.0.3 or newer. |
| R9 | `NEBULA_AGENTS_PRODUCT_ROOT` is honored consistently by CLI/TUI composition, while explicit invocation input takes precedence and cwd remains the documented fallback. | Presentation + Backend | Non-repository-cwd doctor/launch/status tests and installed-CLI smoke. |
| R10 | Successful `launch` output makes the interaction model explicit by printing the exact `tui --run-id` and `attach --run-id` next steps without auto-attaching or starting a second provider. | Presentation | Human-output snapshot plus JSON non-regression and provider-start-count test. |

### Ownership And Concurrency

- Backend owns `engine/src/nebula_agents/domain/**`, `application/**`, and `infrastructure/**` for R2-R5 and the core portions of R1/R6/R9.
- Presentation owns `engine/src/nebula_agents/presentation/**` for the visible portions of R1/R6/R9/R10 and must consume application services rather than duplicate policy.
- Quality Engineering owns `engine/tests/**` and the branch-enabled G2 evidence. Implementation roles may add a narrowly local regression test only when needed to land a source contract, but QE owns final mapping and coverage closure.
- Architect owns this addendum, cross-layer signatures, descriptor-bound path decisions, and G0/G7 reconciliation. Security and Code Review remain independent G3 verdict owners.
- The existing operator demo session `nebula-F0001-c3a640c7` is outside test ownership and must not be killed, renamed, attached, or reused by automated checks.

### Remediation Gate Rules

1. G1 must pass before any remediation test, security scan, or runtime mutation. Test tmux sessions use unique remediation-only names and are always cleaned up.
2. G2 requires the full suite, a focused real-tmux lifecycle, forced failure seams for R2/R4/R5/R6, clean package metadata, and an official branch-enabled coverage XML.
3. G3 requires a fresh independent code-review report and security-review report in the new run. Prior verdicts are inputs, not reusable passing evidence.
4. Any remaining Critical or High finding blocks G4. No user approval is inferred from authorization to start this remediation run.
5. The repository still lacks the self-hosted KG/compiler contract; the documented G7 governance limitation remains unchanged and must not be represented as generated graph evidence.

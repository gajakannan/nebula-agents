# Feature Assembly Plan — F0003: Local Agent Runtime Control Plane

**Created:** 2026-08-29
**Author:** Architect Agent
**Status:** Draft
**Run:** `2026-08-29-16075bda`
**Phase B approval:** `2026-08-29T11:15:45-04:00` (BLUEPRINT §5.9); ADR-005…009 `Accepted`

## Overview

F0003 turns F0001's tmux-native cockpit into a governed local control plane. It adds twelve
`nebula-agents` subcommands, a dependency-free stdio MCP surface of six read-only tools, a
per-run artifact index with stable IDs, deterministic rule-based summaries, derived runtime
metrics, and a review-gated learning-proposal workflow.

It **extends the existing package** — no service, daemon, port, database, or new required
dependency (ADR-005). All new code lands in `engine/src/nebula_agents/` across the same four
layers F0001 established, and the existing 514 engine tests must continue to pass unmodified.

The one structural change to existing code is S0007's query/command split, which is a Phase B
interface commitment rather than a refactor of convenience: the MCP adapter is constructed
with a query-only facade, and that is what makes the read-only guarantee structural instead of
a per-handler promise (ADR-007).

## Governing Decisions

- Package root `engine/`; import package `nebula_agents`; console command `nebula-agents`.
  Contract version `1.1`, additive over F0001's `1.0` — no F0001 command, exit-code class,
  record, or schema changes (ADR-005).
- **No new runtime dependency.** `mcp serve` implements the stdio protocol directly, mirroring
  the in-repo precedent `scripts/kg/mcp_server.py`. `engine/pyproject.toml` gains nothing
  required, which makes S0003's "MCP SDK unavailable" edge case unreachable rather than
  handled (ADR-007).
- Artifact identity is `{run_id}/{artifact_kind}/{root_key}-{path_digest12}` where `root_key`
  ∈ `ws|rt|ev` and the digest is SHA-256 over the canonical POSIX path **relative to the
  owning root**. Owning root = the **longest** resolved approved root that is an ancestor;
  ties break `runtime > evidence > workspace`. Digest length is fixed at 12 (ADR-006, M2).
- `content_hash` is a full SHA-256 attribute for duplicate linking and staleness. It is
  deliberately **not** identity, which is what lets two byte-identical artifacts keep
  distinct IDs (ADR-006).
- Summaries are rule-based extraction. **No model call participates**, and determinism is
  asserted by fixture (ADR-008). Failure markers are never dropped for size; when truncation
  would drop one, `summary_status` becomes `Partial`.
- Learning proposals are inert. `learn review` drafts only; `learn decide` records a decision
  and **never opens the target document**. Rejection is sticky, pinned to source
  `content_hash` (ADR-009).
- Three new authorization actions — `IndexEvidence`, `DraftProposal`, `DecideProposal` —
  rather than overloading `RunValidator`, which keeps its F0001 meaning (the `validate`
  command alone). `DecideProposal`'s resource is the **target document, not the run**.
- **CLI-only.** F0003 ships no screens; a terminal-UI presentation belongs to F0008
  (PRD *UX / Surfaces*, BLUEPRINT §5.8).
- AI scope: none. Rule-based extraction and MCP transport are not LLM workflows.

## Build Order

| Step | Scope | Stories | Rationale |
|------|-------|---------|-----------|
| 1 | Query/command facade split over F0001's existing services | S0007 | Prerequisite for S0003. Must land first and alone, so the 514-test regression boundary is unambiguous. |
| 2 | Domain records, enums, identity, and containment rules | S0002, S0004, S0005, S0006 | Establishes inward-facing types before any adapter. |
| 3 | Artifact index store and `evidence index|list|show` | S0004 | The index is what every later surface reads. |
| 4 | Provider capability probes and the `wrap` launch guard | S0001, S0002 | Completes the operator launch path over durable identity. |
| 5 | Deterministic summarizers and `evidence summarize` | S0005 | Isolates the redaction-sensitive extraction path once artifacts have IDs. |
| 6 | Metrics derivation and the learning-proposal workflow | S0006 | Consumes every prior record; `metrics` is derived, never authoritative. |
| 7 | Stdio MCP adapter over the query facade | S0003 | Last, because it exposes what Steps 2-6 produce and depends on Step 1's facade. |
| 8 | Contract, security, determinism, and package smoke tests | S0001-S0007 | Closes the slice and produces G2/G5 evidence. |

Step 1 before Step 7 is a hard ordering: the MCP adapter cannot be constructed with a
query-only facade that does not yet exist.

## Existing Code (Must Be Modified)

Paths resolved from `engine/src/nebula_agents/` and confirmed against
`planning-mds/knowledge-graph/code-index.yaml` via `scripts/kg/lookup.py F0003`.

| File | Current State | F0003 Change |
|------|---------------|--------------|
| `domain/enums.py` | 11 enums; `Action` has 7 members; `RedactionStatus` has 4 | **Expand** — add 3 `Action` members; add `ArtifactKind`, `SourceRoot`, `RetrievalPolicy`, `FreshnessStatus`, `SummaryStatus`, `ProposalStatus`, `CapabilityName`, `CapabilityRequirement`, `ProbeResult`, `LaunchDecision`, `MetricName` |
| `domain/models.py` | 30 frozen slotted dataclasses + serializer helpers | **Expand** — add 5 record types and their nested types; reuse `serialize_record`/`_utc_text` unchanged |
| `domain/path_contracts.py` | Workspace/runtime containment helpers | **Expand** — add three-root longest-match resolution and `artifact_id` derivation |
| `domain/errors.py` | `NebulaError` hierarchy mapped to exit classes | **Expand** — add F0003 codes (`REDACTION_FAILED`, `ARTIFACT_NOT_FOUND`, `DIGEST_COLLISION`, `PROPOSAL_TARGET_FORBIDDEN`, `EVIDENCE_STALE`, `CAPABILITY_BLOCKED`) |
| `application/queries.py` | `QueryService`, 6 public read methods | **Expand** — becomes the query facade; gains artifact, summary, metric, and proposal reads. Must remain mutation-free by construction |
| `application/runs.py` | `RunService`, 889 lines, launch/attach/reconcile/observe/recover | **Modify (S0007 only)** — reachable through the command facade; no behavior change, no event-shape change |
| `application/ports.py` | 11 `Protocol` ports | **Expand** — add `ArtifactIndexStore`, `SummaryExtractor`, `ProposalStore`, `CapabilityProbe` |
| `application/authorization.py` | Default-deny ABAC over `Action` | **Expand** — 3 new actions; `DecideProposal` resolves its resource from the proposal's `target_document` |
| `infrastructure/config.py` | `RuntimeConfig` with `workspace_root`, `runtime_root`, `schema_root`, `feature_root`, `prompt_root`, `runs_root` | **Expand** — add `evidence_root` (the third approved root), `capability_report_max_age_seconds`, `summary_size_limit_bytes` |
| `infrastructure/filesystem_store.py` | `FilesystemRunRepository`; atomic write + per-run lock + monotonic revision | **Reuse pattern** — new `FilesystemArtifactIndex` and `FilesystemProposalStore` reuse the same lock/temp/fsync/replace discipline (ADR-002) |
| `infrastructure/providers.py` | `CodexAdapter`, `ClaudeAdapter` implementing `ProviderAdapter.probe` | **Expand** — emit a full `ProviderCapabilityReport` rather than a bare `Probe` |
| `infrastructure/schema_registry.py` | `JsonSchemaRegistry` over `planning-mds/schemas` | **No change** — the 6 F0003 schemas are already committed and resolve by name |
| `presentation/cli.py` | `argparse`; 9 subcommands; envelope emit + exit mapping | **Expand** — add `wrap`, `providers`, `evidence`, `metrics`, `learn`, `mcp`; reuse `_emit_success`/`_error_exit` unchanged |
| `presentation/formatters.py` | Table/JSON projection of application records | **Expand** — table renderers for the 5 new record types |
| `bootstrap.py` | `Application` dataclass; `build_application()` wires 13 collaborators | **Modify** — `Application` splits into `queries` and `commands` facades; registers the 4 new adapters |

**No F0001 test is modified.** S0007's acceptance criterion is explicit: the existing 514
tests pass unchanged, with no test rewritten to accommodate the new structure.

## New Files

| File | Layer | Purpose |
|------|-------|---------|
| `domain/artifacts.py` | Domain | `ArtifactIndexEntry`, artifact-ID derivation, root selection, containment |
| `domain/summaries.py` | Domain | `ArtifactSummary`, `SummaryMarker`, ordering and truncation invariants |
| `domain/capabilities.py` | Domain | `ProviderCapabilityReport`, `Capability`, launch-guard decision rule |
| `domain/proposals.py` | Domain | `LearningProposal`, `ProposalDecision`, sticky-rejection rule, allowlist |
| `domain/metrics.py` | Domain | `RuntimeMetricSnapshot`, `DerivedFrom`, the closed metric-name set |
| `application/commands.py` | Application | `CommandService` — the command facade (S0007) |
| `application/evidence.py` | Application | `EvidenceService` — index and summarize |
| `application/capabilities.py` | Application | `CapabilityService` — probe, report, launch guard |
| `application/learning.py` | Application | `LearningService` — draft and decide |
| `application/metrics.py` | Application | `MetricsService` — derivation only |
| `infrastructure/artifact_index.py` | Infrastructure | `FilesystemArtifactIndex` — atomic per-run `artifacts.json` |
| `infrastructure/summarizers.py` | Infrastructure | Per-kind rule-based extractors |
| `infrastructure/proposal_store.py` | Infrastructure | `FilesystemProposalStore` — proposal + append-only decisions |
| `infrastructure/capability_probe.py` | Infrastructure | Bounded, redacted provider probes |
| `presentation/mcp_server.py` | Presentation | Stdio MCP adapter, constructed with the query facade only |

---

## Step 1 — Application Query/Command Split (S0007)

This step **moves no logic**. It introduces two facades over the services that already exist
and re-points the composition root. Its correctness boundary is the existing test suite.

### Modified Files

| File | Change |
|------|--------|
| `application/queries.py` | `QueryService` becomes the query facade; add the mutation-free guard |
| `application/commands.py` | **New** — `CommandService` aggregates `RunService`, `GateService`, `TranscriptService` |
| `bootstrap.py` | `Application` exposes `queries` and `commands`; nothing else reaches a service directly |

### Facade Definitions

```python
# engine/src/nebula_agents/application/commands.py
@dataclass(frozen=True, slots=True)
class CommandService:
    """Every operation that writes a record or appends a runtime event.

    Authorization is evaluated inside the underlying services exactly as it was
    before the split; this facade adds no check and removes none.
    """
    runs: RunService
    gates: GateService
    transcripts: TranscriptService
    evidence: EvidenceService        # Step 3
    capabilities: CapabilityService  # Step 4
    learning: LearningService        # Step 6
```

```python
# engine/src/nebula_agents/application/queries.py
class QueryService:
    """Read-only projections. No method may write to the filesystem, append a
    runtime event, or change run, gate, transcript, artifact, or proposal state.

    Enforced by test_query_facade_is_mutation_free, which fails the build when a
    method name matches the mutating-verb set.
    """
```

### The mutation-free guard

`QueryService` carries an explicit class attribute enumerating its public surface:

```python
    QUERY_SURFACE: ClassVar[frozenset[str]] = frozenset({
        "sessions", "status", "evidence", "recovery_candidates", "recovery_status",
        "artifacts", "artifact", "summary", "metrics", "proposals", "proposal",
        "gate_status", "validator_status",
    })
```

The guard test asserts three things, and adding a mutating method to the query facade must
fail at least one:

1. `public_methods(QueryService) == QueryService.QUERY_SURFACE` — a new method that is not
   declared fails immediately.
2. No name in `QUERY_SURFACE` begins with a mutating verb
   (`create|write|commit|append|decide|index|summarize|draft|launch|attach|recover|configure|observe|reconcile`).
3. Executing every `QUERY_SURFACE` method against a temp runtime leaves the runtime tree
   byte-identical — same file set, same mtimes, same `events.jsonl` length.

Assertion 3 is the one that catches a query that lazily initializes state, which is S0007's
named edge case.

### Edge cases resolved here

| Case | Resolution |
|------|------------|
| `reconcile` reads live tmux, then persists a corrected status | **Command.** A probe that only reports is a query; `QueryService._fresh()` already reconciles in memory without committing, and must stay that way |
| First-run runtime-directory creation on a read path | Moves to `PreflightService` (command path). A query against a missing runtime root returns an empty projection, it does not create |
| Validator execution records its result | **Command.** The query facade exposes only the persisted `latest_validator` |
| A caller needs both facades | Receives both explicitly. Neither facade holds a reference to the other |

### Audit-stream invariance

The acceptance criterion is byte-identical audit output for an identical operation sequence.
Proof obligation for G2: run the existing integration suite against a fixed clock and UID,
capture `events.jsonl` for every run folder before and after the split, and assert equality.
Query-facade operations must append **no** event at all.

---

## Step 2 — Domain Records, Identity, and Containment (S0002, S0004, S0005, S0006)

### New Files

| File | Layer |
|------|-------|
| `domain/artifacts.py` | Domain |
| `domain/summaries.py` | Domain |
| `domain/capabilities.py` | Domain |
| `domain/proposals.py` | Domain |
| `domain/metrics.py` | Domain |

### Added enum members

```python
# domain/enums.py — additive only; no existing member changes value
class Action(str, Enum):
    ...                                   # F0001's 7 members unchanged
    INDEX_EVIDENCE = "IndexEvidence"
    DRAFT_PROPOSAL = "DraftProposal"
    DECIDE_PROPOSAL = "DecideProposal"

class ArtifactKind(str, Enum):
    TRANSCRIPT = "transcript"; COMMAND_LOG = "command-log"
    VALIDATOR_OUTPUT = "validator-output"; MANIFEST = "manifest"
    STATUS = "status"; METRIC = "metric"; LEARNING_PROPOSAL = "learning-proposal"

class SourceRoot(str, Enum):
    WORKSPACE = "workspace"; RUNTIME = "runtime"; EVIDENCE = "evidence"
    @property
    def key(self) -> str:
        return {"workspace": "ws", "runtime": "rt", "evidence": "ev"}[self.value]

class RetrievalPolicy(str, Enum):
    LOCAL_ONLY = "LocalOnly"; SUMMARY_ONLY = "SummaryOnly"
    BLOCKED = "Blocked"; MISSING = "Missing"

class FreshnessStatus(str, Enum):
    FRESH = "fresh"; STALE = "stale"; MISSING = "missing"; UNKNOWN = "unknown"

class SummaryStatus(str, Enum):
    PASS = "Pass"; FAILED = "Failed"; BLOCKED = "Blocked"
    UNSUPPORTED = "Unsupported"; PARTIAL = "Partial"

class ProposalStatus(str, Enum):
    DRAFT = "Draft"; ACCEPTED = "Accepted"; EDITED = "Edited"
    REJECTED = "Rejected"; ARCHIVED = "Archived"
```

`RedactionStatus` in the F0003 schemas uses `Pass|Fail|Pending|NotRequired`, while F0001's
`domain.enums.RedactionStatus` uses `NotRun|Passed|Redacted|Failed`. **These are different
vocabularies for different records and must not be merged** — merging would change an F0001
record shape, which contract version `1.1` forbids. Add
`ArtifactRedactionStatus(str, Enum)` for the F0003 records and a total mapping function
`artifact_redaction_of(RedactionStatus) -> ArtifactRedactionStatus` with an exhaustive test.

### Artifact identity

```python
# domain/artifacts.py
APPROVED_ROOT_ORDER: Final = (SourceRoot.RUNTIME, SourceRoot.EVIDENCE, SourceRoot.WORKSPACE)

def resolve_owning_root(
    artifact_path: Path,
    roots: Mapping[SourceRoot, Path],
) -> tuple[SourceRoot, Path]:
    """Longest-match root selection (ADR-006).

    1. Every root and the artifact path are already canonical (symlinks resolved).
    2. The owning root is the longest root that is an ancestor of the artifact.
    3. Ties break runtime > evidence > workspace via APPROVED_ROOT_ORDER.
    4. No ancestor -> PathContainmentError, recorded as a policy violation.
    """

def derive_artifact_id(
    run_id: str, kind: ArtifactKind, artifact_path: Path, roots: Mapping[SourceRoot, Path],
) -> str:
    root, root_path = resolve_owning_root(artifact_path, roots)
    relative = artifact_path.relative_to(root_path).as_posix()
    digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:12]
    return f"{run_id}/{kind.value}/{root.key}-{digest}"
```

Symlinks are resolved **before** the containment check, never after. Callers pass
`artifact_id` opaquely; `root_key` must not be parsed to reconstruct a path.

### Records

```python
@dataclass(frozen=True, slots=True)
class ArtifactIndexEntry:
    artifact_id: str
    run_id: str
    artifact_kind: ArtifactKind
    source_root: SourceRoot          # persisted, so an entry is self-describing
    source_path: str                 # relative to source_root, POSIX
    created_at: datetime
    redaction_status: ArtifactRedactionStatus
    retrieval_policy: RetrievalPolicy
    summary_path: str | None = None
    content_hash: str | None = None  # full SHA-256; NOT identity
    freshness_status: FreshnessStatus = FreshnessStatus.FRESH
    superseded_by: str | None = None
    related_gate: str | None = None
    validator_name: str | None = None
    size_bytes: int | None = None
```

`ArtifactSummary`, `ProviderCapabilityReport`, `LearningProposal`, and
`RuntimeMetricSnapshot` mirror their committed schemas field-for-field. All are
`frozen=True, slots=True`, matching every existing record in `domain/models.py`, and all
serialize through the existing `serialize_record`.

### Domain invariants (pure, no I/O)

| Invariant | Rule |
|-----------|------|
| Redaction gating | `redaction_status == Fail` **forces** `retrieval_policy = Blocked`. Constructed, not checked at the call site |
| Freshness | An artifact absent at retrieval becomes `freshness_status = missing` and **keeps its entry and ID**, so references stay resolvable |
| Supersession | An artifact moved within a run is delete-plus-add; the prior ID is recorded in `superseded_by` |
| Digest collision | Two distinct relative paths yielding the same 12-hex digest within one `(run_id, kind, root)` raise `DigestCollisionError` (exit 6). Never overwrite |
| Metric closure | `metric_name` is a closed set; an unknown name is a construction error, so a consumer never meets an unknown key |
| Proposal allowlist | `target_document` must be inside the committed allowlist at **generation**, so `learn decide` never evaluates an out-of-allowlist path |
| Sticky rejection | A `Rejected` proposal is not regenerated unless the source `content_hash` set changes |

---

## Step 3 — Artifact Index Store and Retrieval (S0004)

### New Files

| File | Layer |
|------|-------|
| `application/evidence.py` | Application |
| `infrastructure/artifact_index.py` | Infrastructure |

### Port

```python
# application/ports.py
class ArtifactIndexStore(Protocol):
    def load(self, run_id: str) -> ArtifactIndexDocument: ...
    def commit(self, *, run_id: str, expected_revision: int,
               entries: tuple[ArtifactIndexEntry, ...]) -> ArtifactIndexDocument: ...
```

### Storage

One atomic JSON document per run at `{runtime_root}/runs/{run_id}/artifacts.json`, written
with ADR-002's discipline exactly as `run.json` is: per-run lock, monotonic `revision`,
same-directory temporary file, `fsync`, atomic replace, corrupt files preserved as
`artifacts.json.corrupt-{ts}`. Mode `0600` in a `0700` directory.

The index is a **projection**: losing it costs a re-index, never evidence. Re-indexing is
idempotent — the recovery path, not a repair procedure.

### Logic flow

```
EvidenceService.index(run_id, paths, actor) -> tuple[ArtifactIndexEntry, ...]
```

1. Authorize `IndexEvidence` against the run resource. Deny → exit 5.
2. Resolve each path canonically with symlinks resolved.
3. `resolve_owning_root` → no ancestor raises `PathContainmentError`, recorded as a policy
   violation (**not** a crash), exit 5.
4. `derive_artifact_id`; a collision within `(run_id, kind, root)` raises exit 6.
5. Compute `content_hash`; link duplicates by hash while keeping distinct IDs.
6. Determine `redaction_status`, then derive `retrieval_policy` from it.
7. Commit under lock at `expected_revision`; monotonic bump.
8. Append one `ArtifactIndexed` runtime event per entry (indexing changes review evidence).
9. Return entries.

### HTTP Responses

N/A — F0003 exposes no HTTP API (BLUEPRINT §5.5). Exit codes and the error envelope are the
equivalent contract; see the runtime contract §4-§5.

| Exit | Condition |
|------|-----------|
| 0 | Entries indexed |
| 2 | Unknown `artifact_kind`, malformed `artifact_id` |
| 4 | Unknown run |
| 5 | Path outside approved roots; authorization denied |
| 6 | Digest collision within run, kind, and root |
| 9 | Index write failure; unreadable runtime directory |

---

## Step 4 — Provider Capability Matrix and Wrapped Launch (S0001, S0002)

### Logic flow

```
CapabilityService.probe(provider_key, actor) -> ProviderCapabilityReport
```

1. Authorize `Probe`.
2. Run each capability probe under a per-provider timeout → `pass|fail|timeout|skipped`.
3. **Redact probe output before persistence.** A version string that looks secret-bearing is
   redacted rather than stored.
4. Compute `launch_decision`: `allowed` when every `required` capability passes;
   `allowed_with_fallback` when a failing required capability has an explicit fallback;
   otherwise `blocked` with `blocked_reason`.
5. Persist atomically per provider with `report_generated_at`.

```
CommandService.wrap(request, actor) -> RunProjection
```

`wrap` supersedes nothing. It is preflight + capability guard + F0001's existing
`RunService.launch` + registration, as one operator step:

1. Preflight (existing `PreflightService`).
2. Load the latest report. Older than `capability_report_max_age_seconds` → re-probe, or warn
   when policy permits stale acceptance.
3. `launch_decision == blocked` → **exit 3** with remediation, and append a sanitized
   `LaunchBlocked` event. Exit 3 distinguishes a capability block from a policy denial (5)
   and a provider failure (8).
4. Delegate to `RunService.launch` — unchanged, no credential body ever persisted.
5. Register, then index the launch artifacts (Step 3).

---

## Step 5 — Deterministic Summaries (S0005)

### Extraction rules — no model call participates

One extractor per `artifact_kind`, each pure over `(bytes, ArtifactIndexEntry)`:

| Kind | Preserved |
|------|-----------|
| `transcript` | User prompts, approval moments, tool-call attention points, recovery markers — in redacted form |
| `command-log` | Command order, duration when available, exit code, failed commands |
| `validator-output` | Command, exit code, pass/fail, failed rule names, remediation hints |
| `manifest`, `status`, `metric` | Declared fields and their values, no prose |

### Truncation rule

Large input truncates **passing noise with counts**, and `truncation_count` records how much.
**Failure markers are never dropped for size.** When a size limit would require dropping one,
`summary_status` becomes `Partial` rather than `Pass` — a smaller summary must never look
complete.

### Status resolution

| Condition | `summary_status` |
|-----------|------------------|
| Clean extraction | `Pass` |
| Truncation would drop a failure marker | `Partial` |
| Run interrupted, input incomplete | `Partial` + `last_observed_marker` |
| Binary or unsupported kind | `Unsupported` (records retrieval metadata only) |
| Strong secret indicators | `Blocked`, and the artifact's `retrieval_policy` becomes `Blocked` |
| Extraction raised | `Failed` — the artifact **stays indexed** |

### Determinism proof

`rule_set_version` is stamped on every summary. The G2 fixture corpus asserts byte-identical
output across two runs, two processes, and two interpreter versions, with `key_events` and
`failure_markers` ordered by `ordinal`.

---

## Step 6 — Metrics and Learning Proposals (S0006)

### Metrics are derived, never authoritative

```
MetricsService.snapshot(run_id, actor) -> RuntimeMetricSnapshot
```

Recomputed on every call from run state and the artifact index. `derived_from` pins
`run_revision` and `artifact_index_revision`, so recomputability is **checkable rather than
asserted**; a snapshot taken at older revisions is superseded, not wrong. A metric that does
not apply to a run is emitted with `applicable: false`, never omitted and never zero.

Closed metric set: `run_duration_seconds`, `gate_wait_seconds`, `validator_pass_count`,
`validator_fail_count`, `latest_failing_validator`, `transcript_health`,
`evidence_freshness`, `artifact_count`, `blocked_launch_count`.

### Proposal drafting

```
LearningService.review(run_id, scope, actor) -> tuple[LearningProposal, ...]
```

1. Authorize `DraftProposal`.
2. Generate **only** from failed or incomplete run evidence. A clean run reports "no proposal
   generated" and exits 0 — that is a success, not an error.
3. Stale or missing evidence blocks generation at **exit 7** (gate blocked), until resolved.
4. A target outside the allowlist is refused **at generation** — exit 5.
5. Multiple failures mapping to one proposal group their `source_artifact_ids`.
6. A `Rejected` proposal whose source `content_hash` set is unchanged is **not** regenerated.
7. Proposals are written in `Draft`. They are inert artifacts.

### Proposal decisions

```
learn decide <proposal-id> --decision accept|edit|reject|archive [--reason ...] [--patch-plan ...]
```

`--reason` is **required** for `reject` and `archive`. Decisions are append-only: a later
decision appends, it never rewrites an earlier one. `accept` records the decision and an
optional `--patch-plan`; it **does not open the target document**. Applying an accepted
proposal is outside F0003's automated scope.

Authorization resolves the resource from the proposal's `target_document`:

| Target class | Authorized role |
|--------------|-----------------|
| Security guidance | Security Reviewer |
| Architecture and process | Architect |
| Planning process | Product Manager |

**Owning the run does not confer the right to decide its proposals.** `DraftProposal` granted
alone cannot reach `learn decide`.

---

## Step 7 — Read-Only MCP Surface (S0003)

### Construction is the guarantee

```python
# presentation/mcp_server.py
class McpServer:
    def __init__(self, queries: QueryService, clock: Clock) -> None:
        """Constructed with the query facade ONLY.

        No mutating service is reachable from here. Adding a mutating tool requires
        changing the facade this adapter is constructed with — a visible architectural
        edit, not a new handler (ADR-007).
        """
```

Defense in depth is deliberate: every tool call **also** evaluates authorization with action
`ReadState`. A policy misconfiguration alone must not widen the surface, and neither
mechanism is a substitute for the other.

### Tools — names are a public contract

| Tool | Input | Returns |
|------|-------|---------|
| `nebula_session_list` | optional `status`, `limit` | Run IDs with sanitized status |
| `nebula_session_status` | `run_id` | Provider, action, feature, gate, validator, evidence summary, attach guidance when permitted |
| `nebula_gate_status` | `run_id` | Gate state and decision records |
| `nebula_validator_status` | `run_id` | Latest validator results |
| `nebula_evidence_list` | `run_id`; optional `kind`, `cursor` | Artifact IDs, kinds, summaries, freshness, retrieval availability |
| `nebula_evidence_show` | `artifact_id` | Redacted summary and retrieval metadata; **never raw artifact bytes** |

Renaming one breaks host configuration. List responses are paged via `next_cursor`; no tool
returns an unbounded transcript or log.

### Errors

Structured, from the committed `f0003-mcp-response` enum — `NOT_FOUND`, `FORBIDDEN`,
`REDACTION_FAILED`, `RUNTIME_UNREADABLE`, `WORKSPACE_NOT_CONFIGURED`, `INVALID_INPUT`. No
stack traces, no paths outside approved roots, no credentials.

`nebula_evidence_show` refuses content whenever `redaction_status` is not `Pass`, returning
`REDACTION_FAILED` rather than a partial body.

---

## Mutation Traceability

| Entry Point | User Action | Service Method | Record | Authorization | Concurrency | Validation Failure | Audit Event | Test Expectation |
|-------------|-------------|----------------|--------|---------------|-------------|--------------------|-------------|------------------|
| `wrap` | Launch guarded native session | `CommandService.wrap` | `RunRecord` + capability report read | `Launch`; owner only | Unique run ID + run lock | `CAPABILITY_BLOCKED` exit 3; `FORBIDDEN` 5; `CONFLICT` 6 | `LaunchRequested`, `RunLaunched` \| `LaunchBlocked` | Blocked launch persists no session and writes a sanitized audit entry |
| `providers doctor` | Probe providers | `CapabilityService.probe` | `ProviderCapabilityReport` | `Probe` | Atomic per-provider write | probe `timeout` → exit 10 | `CapabilityProbed` | Secret-like version text is redacted before persistence |
| `evidence index` | Index artifacts | `EvidenceService.index` | `ArtifactIndexEntry` | `IndexEvidence` | Per-run lock, `expected_revision` | outside roots → 5; collision → 6 | `ArtifactIndexed` | Re-index is idempotent; IDs stable across restart |
| `evidence summarize` | Summarize artifact or run | `EvidenceService.summarize` | `ArtifactSummary` + index update | `IndexEvidence` | Same lock as index | `Failed` status keeps the artifact indexed | `ArtifactSummarized` \| `SummaryFailed` | Byte-identical for the same fixture |
| `learn review` | Draft proposals | `LearningService.review` | `LearningProposal` (`Draft`) | `DraftProposal` | Atomic proposal write | stale evidence → 7; bad target → 5 | `ProposalDrafted` | Clean run drafts nothing and exits 0 |
| `learn decide` | Accept/edit/reject/archive | `LearningService.decide` | Append-only `ProposalDecision` | `DecideProposal` **against `target_document`** | Append-only; no rewrite | missing `--reason` on reject/archive → 2 | `ProposalDecided` | Run owner without the target role is denied |
| `evidence list\|show`, `metrics`, `learn list\|show`, all MCP tools | Read | `QueryService.*` | None | `ReadState` | None | `NOT_FOUND` 4; `REDACTION_FAILED` | **None — reads create no runtime events** | Runtime tree byte-identical after every read |

## Authorization Enforcement

- Actions: F0001's `Probe`, `Launch`, `Attach`, `ReadState`, `RunValidator`, `DecideGate`,
  `ConfigureTranscript`, plus F0003's `IndexEvidence`, `DraftProposal`, `DecideProposal`.
- `RunValidator` keeps its F0001 meaning — the `validate` command alone. It is **not**
  widened to cover indexing, summarizing, or drafting.
- `DecideProposal` is the one action whose resource is not the run. Its resource attribute is
  the proposal's `target_document` path; the action verb is the same regardless of who holds
  it.
- `DraftProposal` and `DecideProposal` are deliberately separate capabilities. Drafting is
  safe to run automatically; deciding is not. One capability covering both would let an
  automated caller approve its own proposals — an escalation path closed here by
  construction rather than by policy text.
- Every mutation rechecks policy under lock. Unknown identity, role, or action; malformed or
  missing policy; stale record; or path escape all deny.
- Reference: `planning-mds/security/f0001-authorization-model.md` § *F0003 Action Extensions*.

## Audit Event Mapping

| Operation | Success event | Failure/blocked event | Sanitized payload keys |
|-----------|---------------|-----------------------|------------------------|
| Wrapped launch | `LaunchRequested`, `RunLaunched` | `LaunchBlocked`, `LaunchFailed`, `AuthorizationDenied` | provider, action, feature, blocked capability, decision |
| Capability probe | `CapabilityProbed` | `CapabilityProbeTimedOut` | provider, capability, probe result, duration; **never raw version output** |
| Artifact index | `ArtifactIndexed` | `ArtifactPolicyViolation`, `AuthorizationDenied` | artifact ID, kind, source root, policy result |
| Summarize | `ArtifactSummarized` | `SummaryFailed`, `SummaryBlocked` | artifact ID, summary status, redaction status, rule-set version |
| Proposal draft | `ProposalDrafted` | `ProposalBlocked`, `AuthorizationDenied` | proposal ID, source artifact IDs, target document, confidence |
| Proposal decision | `ProposalDecided` | `AuthorizationDenied` | proposal ID, decision, reviewer role, timestamp |
| Reads / all MCP tools | **none** | none | Reads create no runtime events (BLUEPRINT §5.3) |

## Scope Breakdown

| Layer | Required Work | Owner | Status |
|-------|---------------|-------|--------|
| Core runtime (`domain`, `application`, `infrastructure`) | 5 records, identity/containment, 4 adapters, 5 services, facade split | Backend Developer | Planned |
| Terminal presentation (`presentation`) | 12 subcommands, table renderers, stdio MCP adapter | Backend Developer, same package — **no UI framework, no screens** | Planned |
| AI (`neuron/`, prompts, models) | None. Rule-based extraction is not an LLM workflow (ADR-008) | N/A | Not in scope |
| Quality (`engine/tests`) | Determinism fixtures, facade guard, containment, authorization, MCP contract | Quality Engineer | Planned |
| Local package/runtime | No new required dependency; console-entry smoke | DevOps deployability check | Planned |
| Security | Path containment, redaction, probe output, allowlist, MCP boundary | Security Reviewer | Planned |

## Dependency Order

```text
Step 1 (Backend):   query/command facade split — S0007, alone, 514 tests unchanged
  ──── Checkpoint A: audit stream byte-identical; query facade mutation-free ────
Step 2 (Backend):   domain records, artifact identity, containment
Step 3 (Backend):   artifact index store + evidence index|list|show
  ──── Checkpoint B: IDs stable across restart; re-index idempotent ────
Step 4 (Backend):   capability probes + wrap launch guard
Step 5 (Backend):   deterministic summarizers + evidence summarize
  ──── Checkpoint C: byte-identical summaries; failure markers never dropped ────
Step 6 (Backend):   metrics derivation + learning proposal workflow
  ──── Checkpoint D: DecideProposal denied to run owner lacking target role ────
Step 7 (Backend):   stdio MCP adapter over the query facade
  ──── Checkpoint E: no mutating service reachable from McpServer ────
Step 8 (QE):        contract, security, determinism, package smoke
```

## Integration Checkpoints

### Checkpoint A — After Step 1 (S0007)

- [ ] All 514 existing engine tests pass **unmodified**
- [ ] `events.jsonl` byte-identical before and after the split for a fixed operation sequence
- [ ] Query-facade operations append zero runtime events
- [ ] Adding a mutating method to `QueryService` fails the build
- [ ] Running every query method leaves the runtime tree byte-identical
- [ ] Neither facade holds a reference to the other

### Checkpoint B — After Step 3 (S0004)

- [ ] `artifact_id` is stable across re-index, restart, and a moved runtime root
- [ ] Longest-match root selection is correct under all three nesting configurations
- [ ] Tie-break `runtime > evidence > workspace` is exercised by a test with colliding roots
- [ ] A path outside all approved roots records a policy violation and does not crash
- [ ] Duplicate content yields distinct IDs linked by `content_hash`
- [ ] A digest collision raises exit 6 and never overwrites

### Checkpoint C — After Step 5 (S0005)

- [ ] Summaries byte-identical across two runs, two processes, two interpreter versions
- [ ] A truncation that would drop a failure marker yields `Partial`, not `Pass`
- [ ] No model call is reachable from any extractor (asserted by import-graph test)
- [ ] `redaction_status = Fail` blocks summary exposure through both CLI and MCP

### Checkpoint D — After Step 6 (S0006)

- [ ] Metrics recompute identically from the pinned `derived_from` revisions
- [ ] A clean run generates no proposal and exits 0
- [ ] A rejected proposal is not regenerated while source `content_hash` is unchanged
- [ ] The run owner, lacking the target-document role, is denied `DecideProposal`
- [ ] `learn decide --decision accept` does not open the target document

### Checkpoint E — After Step 7 (S0003)

- [ ] `McpServer` cannot reach any mutating service (asserted structurally)
- [ ] Every tool evaluates `ReadState` in addition to the facade guarantee
- [ ] All six tool names match the contract exactly
- [ ] Responses are paged and schema-conformant; errors carry no stack traces

### Cross-Story Verification

- [ ] Full lifecycle: `providers doctor` → `wrap` → run → `evidence index` → `evidence
      summarize` → `metrics` → `learn review` → `learn decide`
- [ ] All three new actions enforced; reviewer denied each by default
- [ ] Runtime events for the full lifecycle are correct and ordered
- [ ] Error envelope consistent with F0001 (`contract_version`, `command`, `generated_at`)
- [ ] A `1.0` client keeps working; it simply does not see the added commands

## Acceptance-Criteria Test Matrix

| Story | Criterion | Test |
|-------|-----------|------|
| S0001 | `wrap` records provider/workspace/action/feature/runtime dir/session ref | `integration/test_wrap_launch.py` |
| S0001 | Blocked capability, stale session, metadata-write failure, denied runtime dir | `unit/test_wrap_guards.py` |
| S0002 | Four requirement levels × four probe results | `unit/test_capability_matrix.py` |
| S0002 | Secret-like version output redacted before persistence | `security/test_probe_redaction.py` |
| S0003 | Six tools; read-only structural; not-found; unreadable runtime; redaction failure | `contract/test_mcp_tools.py` |
| S0004 | ID stability, root selection, containment, duplicates, collision | `unit/test_artifact_identity.py` |
| S0005 | Determinism across kinds; unsupported; blocked; partial | `contract/test_summary_determinism.py` |
| S0006 | Metric closure and `derived_from` recomputability | `unit/test_metrics_derivation.py` |
| S0006 | No-failure run, stale evidence, blocked target, sticky rejection | `unit/test_learning_proposals.py` |
| S0007 | 514 existing tests unchanged; facade mutation-free; audit byte-identical | `contract/test_facade_split.py` |

## Security and Runtime Evidence

- Artifact index and proposal store are owner-only `0600` inside `0700` directories.
- Path containment uses resolved canonical ancestry, **symlinks resolved before the check**.
- Probe output is redacted before persistence; no raw version string is stored.
- Proposals cannot name a target outside the committed allowlist.
- MCP responses carry no stack traces, no paths outside approved roots, no credentials.
- Required scans: dependency, secrets, SAST. **DAST is not applicable** — F0003 opens no
  port and runs no server (BLUEPRINT §5.8); record the waiver with an Architect owner, as
  F0001 did.

## Knowledge-Graph Binding Plan

At G7 the Architect binds as-built source to the six capabilities, four entities, and two
workflows already declared in `planning-mds/kg-source/features/F0003.yaml`. Bindings are
authored as **shards under `kg-source/`** and compiled — `canonical-nodes.yaml`,
`feature-mappings.yaml`, `code-index.yaml`, and the REGISTRY/ROADMAP regions are generated
files and must never be hand-edited. `validate.py --check-reproducible` enforces this.

Feature status moves `planned → in-progress` in the shard at G0 and `→ done` at G8.

## Risks and Blockers

| Item | Severity | Mitigation | Owner |
|------|----------|------------|-------|
| S0007 changes shared application structure ahead of every other story | High | Land alone, first; the 514-test suite and byte-identical audit stream are the regression boundary | Backend |
| Two `RedactionStatus` vocabularies (F0001 vs F0003 schemas) | Medium | Separate enums plus a total mapping with an exhaustive test; merging them would break contract `1.1` | Backend |
| 12-hex digest collision within a run | Medium | Raise exit 6 rather than overwrite; collision is detectable and loud | Backend |
| Hand-rolled MCP protocol drifts from the spec | Medium | Pin the targeted protocol revision and its conformance fixtures at G0; ADR-007's adapter boundary makes an SDK swap local | Architect |
| M1 open: `mcp install` vs documented manual host configuration | Medium | **Must be answered before S0003 is built**; does not block Steps 1-6 | PM |
| L1 open: S0001's open question unreconciled against ADR-005 | Low | Reconcile during Step 4 authoring | PM |
| Summary rule sets under-specified for real transcripts | Medium | Fixture corpus authored before extractors; `rule_set_version` allows evolution without silent change | QE |

## JSON Serialization Convention

Inherits F0001's convention unchanged: UTF-8, snake_case keys matching committed schemas,
RFC 3339 UTC with `Z`, enums serialized exactly as approved strings, tuples as arrays,
canonical path strings. Durable JSONL events use
`json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))`; snapshots use
two-space indentation plus a final newline.

F0003 additions: public envelopes use `contract_version: "1.1"`; persisted F0003 records use
`schema_version: "1.0"`. All six F0003 schemas set `additionalProperties: false`, so additive
evolution requires a new schema version and explicit dual-read support.

## DI Registration Changes

`bootstrap.build_application()` gains four adapters — `FilesystemArtifactIndex`,
`FilesystemProposalStore`, rule-based summary extractors, and the capability prober — and
five services. The returned `Application` exposes exactly two facades:

```python
@dataclass(frozen=True, slots=True)
class Application:
    queries: QueryService     # read-only, given to McpServer
    commands: CommandService  # every mutation
    identity: OsIdentity
```

Domain and application modules never import infrastructure or presentation modules. The MCP
adapter is constructed as `McpServer(queries=app.queries, clock=clock)` — passing
`app.commands` to it is the architectural edit ADR-007 makes visible.

## Casbin Policy Sync

None. F0003 extends F0001's local default-deny ABAC directly against
`f0001-local-policy.schema.json`. No Casbin runtime dependency, policy file, or embedded
resource is introduced.

## Integration Checklist

- [ ] Runtime contract `1.1` compatibility validated against the F0001 `1.0` surface
- [ ] Six committed JSON schemas validate every emitted record
- [ ] Test cases mapped to acceptance criteria (see matrix above)
- [ ] Framework vs solution boundary reviewed — F0003 is product scope under `engine/`; no
      `agents/**` drift
- [ ] Mutation traceability completed for all seven mutating entry points
- [ ] Read-only surfaces proven to write nothing, not merely asserted to
- [ ] Run/deploy instructions updated

## Run and Release Checklist

- [ ] Clean `pip install -e 'engine[test]'` succeeds with **no new required dependency**
- [ ] `python -m pytest engine` — 514 pre-existing tests pass unmodified, plus F0003 tests
- [ ] Determinism fixtures pass on Python 3.11, 3.12, and 3.14 (the CI matrix)
- [ ] `nebula-agents --help` lists the twelve added commands
- [ ] `nebula-agents mcp serve` responds to a scripted stdio session with no host installed
- [ ] JSON Schema meta-validation and all contract fixtures pass
- [ ] Six lifecycle gates, `kg --check-drift`, and `--check-reproducible` pass
- [ ] Dependency, secrets, SAST recorded; DAST waiver recorded with Architect owner
- [ ] Feature evidence G1-G6 pass before G4/G5 progression
- [ ] Architect reconciles as-built semantics at G7; PM alone performs G8 closeout

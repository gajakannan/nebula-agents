# Nebula Agents Local Runtime Data Model

## Scope

This model covers F0001 local state, plus the F0003 control-plane records added in §"F0003 Control-Plane Records". It is filesystem-backed and single-host. F0003 adds an artifact index, summaries, metrics, and learning records without changing the F0001 run identity contract.

## Aggregate and Record Model

| Record | Identity | Purpose | Mutability |
|--------|----------|---------|------------|
| `RunRecord` | `run_id` | Aggregate snapshot for one native provider run | Atomic replacement; revision increases by one |
| `GateSnapshot` | `(run_id, gate_id)` | Current gate eligibility and status | Replaced only through guarded transitions |
| `ValidatorResult` | `(run_id, gate_id, validator_key, completed_at)` | Latest validator projection, safe command template, validated revision, and evidence digest | Latest projection replaces; full history stays in events/artifacts |
| `ArtifactObservation` | `(run_id, relative_path)` | Last observed evidence state | Replaced by watcher reconciliation |
| `TranscriptState` | `run_id` | Capture, redaction, path, and preview status | Guarded state transitions |
| `RuntimeEvent` | `(run_id, sequence)` | Immutable audit/timeline evidence | Append-only |
| `ProviderProbe` | `(provider_key, probed_at)` | Non-secret readiness result | Replaceable diagnostic record |
| `LocalPolicy` | `policy_version` | OS identity to role/action grants | Atomic replacement after validation |

## RunRecord Fields

| Field | Type | Rules |
|-------|------|-------|
| `schema_version` | string | `1.0` for the initial contract |
| `revision` | integer | Starts at 0; increments exactly once per successful snapshot mutation |
| `run_id` | string | `YYYY-MM-DD-8hex`; unique in the runtime directory |
| `feature_id` | string | `F####`; must resolve to a feature planning folder |
| `story_id` | string/null | `F####-S####`; when present, feature prefix must match |
| `provider_key` | enum | `codex` or `claude` in F0001 |
| `tmux_session` | string | `nebula-F####-8hex`; unique among nonterminal runs |
| `workspace_root` | absolute path | Canonical directory containing `planning-mds/features` |
| `prompt_contract` | path | Canonical file inside approved workspace/framework roots |
| `prompt_action` | enum | `plan`, `feature`, `build`, `review`, or `validate` |
| `status` | enum | `PreflightPending`, `Launching`, `Active`, `DetachedOrExited`, `Failed`, `Exited`, `Unknown` |
| `owner` | object | OS UID and resolved username; display label optional |
| `evidence_root` | absolute path/null | Must resolve within workspace evidence or approved runtime root |
| `gate` | `GateSnapshot` | Current lifecycle gate projection |
| `latest_validator` | `ValidatorResult`/null | Latest allowlisted validator execution, bound to its gate, record revision, and evidence digest |
| `artifacts` | array | Unique by normalized relative path |
| `transcript` | `TranscriptState` | Disabled by default; terminal failures retain a nullable, sanitized `failure_reason` bounded to 256 characters |
| `audit_log_path` | absolute path | Per-run owner-only JSONL file |
| `last_event_sequence` | integer | Must equal the latest accepted event sequence |
| `created_at`, `updated_at` | UTC date-time | Created is immutable; updated advances with revision |
| `last_seen_at` | UTC date-time/null | Last successful tmux/provider observation |

## RuntimeEvent Fields

| Field | Type | Rules |
|-------|------|-------|
| `schema_version` | string | `1.0` |
| `run_id` | string | Matches the owning `RunRecord` |
| `sequence` | integer | Starts at 1 and is contiguous per run |
| `event_type` | string enum | Stable event name such as `RunLaunched`, `GateHeld`, or `AuthorizationDenied` |
| `occurred_at` | UTC date-time | Set by injected clock at commit time |
| `actor` | object | OS UID, username, role, optional display label |
| `correlation_id` | string | One ID per user/application operation |
| `payload` | object | Event-specific, bounded, sanitized, no credential or raw transcript values |

## Relationships

```mermaid
erDiagram
    RUN_RECORD ||--|| GATE_SNAPSHOT : tracks
    RUN_RECORD ||--o| VALIDATOR_RESULT : caches_latest
    RUN_RECORD ||--o{ ARTIFACT_OBSERVATION : observes
    RUN_RECORD ||--|| TRANSCRIPT_STATE : controls
    RUN_RECORD ||--o{ RUNTIME_EVENT : audits
    LOCAL_POLICY ||--o{ ACTION_GRANT : contains
    ACTION_GRANT }o--o{ RUN_RECORD : authorizes

    RUN_RECORD {
        string run_id PK
        int revision
        string provider_key
        string tmux_session UK
        string status
        datetime created_at
        datetime updated_at
    }
    GATE_SNAPSHOT {
        string gate_id
        string status
        bool evidence_ready
    }
    VALIDATOR_RESULT {
        string validator_key
        int exit_code
        string command_template
        string gate_id
        int validated_revision
        string evidence_digest
        datetime completed_at
    }
    ARTIFACT_OBSERVATION {
        string relative_path
        string status
        datetime observed_at
    }
    TRANSCRIPT_STATE {
        string status
        string redaction_status
        string path
    }
    RUNTIME_EVENT {
        int sequence PK
        string event_type
        string actor_id
        datetime occurred_at
    }
```

## Persistence Layout

```text
.nebula-agents/runtime/                  mode 0700
  policy.json                            mode 0600
  preflight/<provider>.json              mode 0600
  runs/<run-id>/
    run.json                             atomic current snapshot, mode 0600
    events.jsonl                         append-only audit, mode 0600
    run.lock                             per-run advisory lock
    launch.json                          transient descriptor, mode 0600
    transcript.redacted.log              optional, mode 0600
```

The default may be overridden by `NEBULA_AGENTS_RUNTIME_DIR`, but all resolved paths must remain in an explicitly approved runtime root.

## Preflight Projection

`PreflightResult` includes the canonical workspace and runtime paths, the canonical `planning_docs_path` when `planning-mds` exists, the selected evidence-contract prompt path, a bounded absolute `missing_paths` list, tmux/provider probes, detailed checks, and the overall readiness classification. Absolute missing paths match the other machine-readable path fields and give the operator an unambiguous remediation target. Doctor/preflight projects these values without creating runtime state; the first authorized mutation performs owner-only initialization.

## Atomicity and Concurrency

1. Acquire the per-run exclusive lock.
2. Read and validate `run.json` against the schema.
3. Verify `expected_revision` when the caller supplied one.
4. Evaluate authorization and domain transition guards against the fresh record.
5. Append and `fsync` the sanitized event record.
6. Write the next snapshot to a same-directory temporary file, flush and `fsync` it, then `os.replace` the target and `fsync` the directory.
7. Release the lock and publish an in-process update notification.

If step 6 fails after the event append, recovery replays the event into the last valid snapshot. Event handlers must therefore be deterministic and idempotent by `(run_id, sequence)`.

## Retention and Deletion

F0001 does not delete or soft-delete run records. Manual removal is an operator filesystem action outside the application contract. Automated retention, archive indexes, and cross-run analytics belong to F0003.

F0003 adds no deletion path either. Its artifact index and summaries are regenerable projections and may be discarded safely. Learning proposals accumulate and need a retention policy fixed at feature G0 (ADR-009).

## F0003 Control-Plane Records

| Record | Identity | Purpose | Mutability |
|--------|----------|---------|------------|
| `ProviderCapabilityReport` | `(provider_key, report_generated_at)` | Capability matrix consumed by the launch guard | Atomic replacement; freshness by age |
| `ArtifactIndexEntry` | `artifact_id` = `{run_id}/{artifact_kind}/{root_key}-{12 hex path digest}` | Stable handle from summaries, MCP, and proposals to local evidence | Replaced by idempotent re-index |
| `ArtifactSummary` | `summary_id` | Deterministic rule-extracted projection of one artifact | Regenerable; replaced wholesale |
| `RuntimeMetricSnapshot` | `(run_id, metric_generated_at)` | Derived run health view | Derived; never authoritative |
| `LearningProposal` | `proposal_id` | Draft correction awaiting review | Status transitions; decisions append-only |

**Identity rule (ADR-006).** `artifact_id` derives from the artifact's canonical path *relative to its owning approved root*, not its content. The owning root is the longest of the three approved roots (workspace, runtime, evidence) that is an ancestor of the artifact, with ties broken runtime > evidence > workspace; it is persisted as `source_root` and abbreviated in the ID as `ws`/`rt`/`ev`. Longest-match keeps the result stable when the roots nest — the evidence root and the default runtime directory both sit inside the workspace, and `NEBULA_AGENTS_RUNTIME_DIR` can move the runtime root outside it. An artifact under no approved root is refused at indexing with a policy violation.

Re-indexing the same artifact therefore yields the same ID, while two artifacts with identical bytes keep distinct IDs. `content_hash` is a separate full SHA-256 attribute used for duplicate linking and staleness detection, never for identity. A truncated-digest collision within one run, kind, and root raises a conflict rather than overwriting. Relocating an approved root re-homes the artifacts under it and changes those IDs; re-indexing is the migration.

**Exposure rule.** `redaction_status` and `retrieval_policy` are index attributes, so an exposure decision never requires reading the artifact. `redaction_status: Fail` forces `retrieval_policy: Blocked`.

**Persistence layout additions:**

```text
.nebula-agents/runtime/                  mode 0700
  providers/<provider>.report.json       mode 0600
  runs/<run-id>/
    artifacts.json                       atomic artifact index, mode 0600
    summaries/<artifact-id-digest>.json  mode 0600
    proposals/<proposal-id>.json         mode 0600
    proposals/decisions.jsonl            append-only, mode 0600
```

The artifact index follows the same commit discipline as `run.json`: per-run lock, revision check, same-directory temporary file, `fsync`, atomic replace, corrupt files preserved.

## Schema Sources

- `planning-mds/schemas/f0001-run-record.schema.json`
- `planning-mds/schemas/f0001-runtime-event.schema.json`
- `planning-mds/schemas/f0001-preflight-result.schema.json`
- `planning-mds/schemas/f0001-local-policy.schema.json`
- `planning-mds/schemas/f0001-launch-descriptor.schema.json`
- `planning-mds/schemas/f0003-capability-report.schema.json`
- `planning-mds/schemas/f0003-artifact-index.schema.json`
- `planning-mds/schemas/f0003-artifact-summary.schema.json`
- `planning-mds/schemas/f0003-learning-proposal.schema.json`
- `planning-mds/schemas/f0003-mcp-response.schema.json`

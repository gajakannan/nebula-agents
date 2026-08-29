# F0003 Runtime Control-Plane Contract

## Contract Identity

- Command: `nebula-agents` (F0003 extends the F0001 console script; see ADR-005)
- Contract version: `1.1` — additive over the F0001 `1.0` CLI contract
- Scope: local POSIX/WSL operation
- Transport: process argv, stdout/stderr, exit status, local JSON/JSONL files, and MCP
  over stdio on a host-spawned child process
- HTTP/OpenAPI: not applicable; F0003 runs no server and opens no port

F0003 adds commands and one MCP surface. It changes no F0001 command, exit-code class, or
record shape. Machine output keeps the F0001 envelope: `contract_version`, `command`,
`generated_at`, and either `data` or `error`.

## 1. Added Commands

| Command | Required input | Mutation | Authorization | Success result |
|---------|----------------|----------|---------------|----------------|
| `wrap <provider>` | `--action`, `--feature`; optional `--story`, `--run-id`, `--transcript` | Creates run, event stream, launch descriptor, session | `Launch` | Run summary with attach guidance |
| `providers doctor` | none; optional `--provider` | Writes a capability report | `Probe` | Capability matrix with per-probe results and freshness |
| `evidence index` | `--run-id`; optional `--path` | Writes artifact index entries | `IndexEvidence` | Indexed artifact IDs and policy results |
| `evidence list` | `--run-id` | None | `ReadState` | Artifact IDs, kinds, summaries, freshness, retrieval availability |
| `evidence show` | `<artifact-id>` | None | `ReadState` | Redacted summary and retrieval metadata |
| `evidence summarize` | `--run-id` or `<artifact-id>` | Writes summary artifacts; updates the index | `IndexEvidence` | Summary IDs and per-artifact status |
| `metrics` | `--run-id` | None | `ReadState` | Run duration, gate wait, validator counts, transcript health, evidence freshness |
| `learn review` | `--run-id`; optional `--scope` | Writes proposal artifacts in `Draft` | `DraftProposal` | Proposal IDs with source artifact IDs and confidence |
| `learn list` | optional `--run-id`, `--status` | None | `ReadState` | Proposals with status, target document, source artifact IDs |
| `learn show` | `<proposal-id>` | None | `ReadState` | Proposal detail, evidence excerpts, decision history |
| `learn decide` | `<proposal-id>`, `--decision`, `--reason`; optional `--patch-plan` | Appends a decision record; sets `proposal_status` | `DecideProposal` | Recorded decision with reviewer role and timestamp |
| `mcp serve` | none | None | `ReadState` | Serves MCP over stdio until the host closes it |

`wrap` supersedes nothing: F0001's `launch` remains the primitive, and `wrap` is preflight
plus capability guard plus `launch` plus registration, as one operator step.

### Proposal decisions

`learn review` only drafts. Decisions are recorded by `learn decide`, a separate command
with separate authorization (ADR-009) — there is no flag on `learn review` that decides,
and none that applies. `--decision` takes exactly one of `accept`, `edit`, `reject`,
`archive`; `--reason` is required for `reject` and `archive`. Decision records are
append-only: a later decision appends, it never rewrites an earlier one.

Applying an accepted proposal remains outside F0003's automated scope. `learn decide
--decision accept` records the decision and an optional `--patch-plan`; it does not open
the target document.

F0003 is **CLI-only** and ships no screens. A terminal-UI presentation of these commands
belongs to F0008.

## 2. MCP Tools

All six tools are read-only, and that is structural: the MCP adapter is constructed with a
query-only application facade, so no mutating service is reachable through it (ADR-007).

| Tool | Input | Returns |
|------|-------|---------|
| `nebula_session_list` | optional `status`, `limit` | Active and recent run IDs with sanitized status |
| `nebula_session_status` | `run_id` | Provider, action, feature, gate, validator, evidence summary, attach guidance when permitted |
| `nebula_gate_status` | `run_id` | Current gate state and decision records |
| `nebula_validator_status` | `run_id` | Latest validator results |
| `nebula_evidence_list` | `run_id`; optional `kind`, `cursor` | Artifact IDs, kinds, summaries, freshness, retrieval availability |
| `nebula_evidence_show` | `artifact_id` | Redacted summary and retrieval metadata; never raw artifact bytes |

Tool names are a public contract — renaming one breaks host configuration. Every response
carries `contract_version` and a schema-conformant body. List responses are paged; no tool
returns an unbounded transcript or log.

`nebula_evidence_show` refuses content whenever `redaction_status` is not `Pass`, returning
a structured redaction-failure error instead.

## 3. Input Rules

F0001's rules hold unchanged (`run_id` is `YYYY-MM-DD-8hex`, `feature` is `F####`, `story`
is `F####-S####`, `provider` is `codex` or `claude`). F0003 adds:

- `artifact_id`: `{run_id}/{artifact_kind}/{root_key}-{12 hex}`, where `root_key` is `ws`,
  `rt`, or `ev` (ADR-006). Callers pass it opaquely; it is never a filesystem path, and
  `root_key` must not be parsed to reconstruct one.
- `artifact_kind`: exactly one of `transcript`, `command-log`, `validator-output`,
  `manifest`, `status`, `metric`, `learning-proposal`.
- `proposal_id`: allocated by `learn review`; opaque to callers.
- `--decision`: exactly one of `accept`, `edit`, `reject`, `archive`. `--reason` is
  required for `reject` and `archive`.
- `--path` for `evidence index`: must resolve inside the run's workspace, runtime, or
  evidence root. Symlinks are resolved before the containment check, never after.
- `--scope` for `learn review`: a bounded enumeration, not free text.

No F0003 input accepts an executable path, command fragment, or shell string.

## 4. Exit Codes

F0003 reuses the F0001 classes without addition. Mappings specific to F0003:

| Exit | Class | F0003 examples |
|------|-------|----------------|
| 2 | Usage/validation | Unknown artifact kind, malformed artifact ID |
| 3 | Preflight blocked | Required provider capability failed with no fallback |
| 4 | Not found | Unknown run, artifact, or proposal |
| 5 | Forbidden | Reviewer attempted `wrap`; proposal target outside the allowlist |
| 6 | Conflict | Duplicate run ID; artifact-ID digest collision within run, kind, and root |
| 7 | Gate blocked | Proposal generation blocked on stale or missing evidence |
| 9 | State I/O | Artifact index write failure; unreadable runtime directory |
| 10 | Timeout | Provider probe exceeded its configured timeout |

A blocked launch caused by a failed required capability is exit 3, distinguishing it from
a policy denial (5) and a provider failure (8).

## 5. Error Shape

Identical to F0001, with F0003 codes:

```json
{
  "contract_version": "1.1",
  "command": "evidence show",
  "generated_at": "2026-08-19T18:00:00Z",
  "error": {
    "code": "REDACTION_FAILED",
    "message": "The artifact summary is withheld because redaction did not complete.",
    "category": "evidence_blocked",
    "details": [{"artifact_id": "2026-08-19-1a2b3c4d/transcript/rt-9f2c1a8e0b47", "redaction_status": "Fail"}],
    "remediation": "Re-run evidence summarize after resolving the redaction failure.",
    "correlation_id": "0b7c1d2e-3f40-4a51-9b62-7c83d94e5f60"
  }
}
```

Errors never include environment values, credential-file contents, raw transcript text,
unredacted subprocess output, or stack traces.

## 6. Record Contracts

F0003 adds five record types alongside F0001's `RunRecord`, `RuntimeEvent`, and
`LocalPolicy`:

| Record | Owner | Persistence |
|--------|-------|-------------|
| `ProviderCapabilityReport` | `providers doctor` | Atomic JSON per provider, with `report_generated_at` for freshness |
| `ArtifactIndexEntry` | `evidence index` | Atomic JSON index per run (ADR-006) |
| `ArtifactSummary` | `evidence summarize` | One summary artifact per source artifact (ADR-008) |
| `RuntimeMetricSnapshot` | `metrics` | Derived; recomputable from run state and index, with `derived_from` pinning the revisions used |
| `LearningProposal` | `learn review` | Proposal artifact plus append-only decision records (ADR-009) |

All five are filesystem/CLI contracts rather than HTTP resources. Metrics are derived, not
authoritative: they must be recomputable from runtime state and the artifact index.

## 7. Capability Guard

`wrap` consults the latest `ProviderCapabilityReport` before launching:

- Each capability is `required`, `optional`, `unsupported`, or `fallback`.
- Each probe result is `pass`, `fail`, `timeout`, or `skipped`.
- Launch proceeds only when every `required` capability passes or has an explicit
  `fallback`. Otherwise launch is blocked (exit 3) with remediation, and a sanitized audit
  entry is appended.
- A report older than the configured max age triggers a re-probe, or a warning when
  policy permits stale acceptance.
- Probe output is redacted before persistence; a version string that looks secret-bearing
  is redacted rather than stored.

## 8. JSON Schemas

- Capability report: `planning-mds/schemas/f0003-capability-report.schema.json`
- Artifact index: `planning-mds/schemas/f0003-artifact-index.schema.json`
- Artifact summary: `planning-mds/schemas/f0003-artifact-summary.schema.json`
- Learning proposal: `planning-mds/schemas/f0003-learning-proposal.schema.json`
- Runtime metric snapshot: `planning-mds/schemas/f0003-metric-snapshot.schema.json`
- MCP response envelope: `planning-mds/schemas/f0003-mcp-response.schema.json`

## 9. Compatibility

`1.1` is additive over `1.0`: no F0001 command, exit-code class, or record shape changes.
Readers must reject unknown major versions and may ignore unknown additive fields only
where the schema permits. F0003 schemas set `additionalProperties: false`, so additive
evolution requires a new schema version and explicit dual-read support, exactly as in
F0001.

### The one F0001 schema change `1.1` makes

`f0001-runtime-event.schema.json` gains eleven members in its `event_type` enum:
`ArtifactIndexed`, `ArtifactPolicyViolation`, `ArtifactSummarized`, `SummaryFailed`,
`SummaryBlocked`, `CapabilityProbed`, `CapabilityProbeTimedOut`, `LaunchBlocked`,
`ProposalDrafted`, `ProposalBlocked`, `ProposalDecided`.

This is recorded rather than hidden, because an earlier revision of this section claimed
`1.1` made *no* F0001 schema change at all. That claim could not hold: BLUEPRINT §5.3
requires indexing, summarization, and proposal drafting to append runtime events, and the
`event_type` enum is closed. The three statements — no schema change, closed enum, new
events — are mutually exclusive, and implementation is where that surfaced.

The change is **backward-compatible for data**: every event written under `1.0` remains
valid, and no field, type, or existing member changed. It is **not** transparent to a
strict `1.0` reader, which will reject an event type it does not know. A reader that must
tolerate both should treat an unrecognised `event_type` as opaque rather than invalid.

Extending the enum was chosen over a separate `f0003-runtime-event` schema because both
break a strict `1.0` reader identically — the events share one `events.jsonl` — and a
second schema over the same stream adds machinery without adding compatibility.

A client written against `1.0` continues to work; it simply does not see the added
commands. An MCP host configured for these six tools must tolerate additive fields in
responses.

# Gate Decisions — F0003-local-agent-runtime-control-plane run 2026-08-29-16075bda

> One row per gate evaluated. Rows are added as gates execute; G1-G8 are not yet reached.

## Gate Decisions

| Gate | Decision | Decider | Timestamp | Rationale | Blocking | Follow-up |
|------|----------|---------|-----------|-----------|----------|-----------|
| G0 | PASS | Architect | 2026-08-29T11:35:30-04:00 | Assembly plan authored and validated against the approved Phase B package; all 7 stories covered, no blocking plan finding | No | M1 gates Step 7 (S0003); MCP protocol revision pinned at Step 7; L1 reconciled at Step 4 |
| G1 | PASS | DevOps | 2026-08-29T11:48:38-04:00 | Environment, tmux, providers, schemas, and the ADR-006 root rule verified; 514 engine tests pass on all three CI-matrix interpreters | No | `RuntimeConfig` lacks `evidence_root` — already an assembly-plan row, not a blocker |

Decisions: `PASS`, `PASS WITH RECOMMENDATIONS`, `FAIL`, `SKIP`. Blocking values: `Yes` / `No`.

## G0 Scope Declarations

Recorded here because two manifest flags were set deliberately rather than by default.

| Flag | Value | Reason |
|------|-------|--------|
| `runtime_bearing` | `true` | Implementation lands in `engine/**`; G1 runtime preflight is required |
| `frontend_in_scope` | `false` | F0003 is CLI-only and ships no screens (BLUEPRINT §5.8); a terminal UI belongs to F0008 |
| `deployment_config_changed` | `false` | No new required dependency and no packaging change (ADR-005, ADR-007) |
| `security_sensitive_scope` | `false` **at G0**, set `true` at G2 | The flag is not stage-gated: setting it true requires the four scan classes to already have run or carry a complete waiver, which is impossible before code exists. It is set at G2, the QE→Security handoff, when the scans actually run. **This does not weaken the Security Reviewer requirement**, which comes independently from STATUS.md *Required Signoff Roles* via `effective_required_roles` |

The last row is a sequencing decision, not a scope reduction. F0003 is security-sensitive —
redaction, path containment, authorization, and the MCP read-only boundary are all in scope,
and the Security Reviewer signoff is required at G3 onward regardless of this boolean.

## Carried Findings

| ID | Severity | Item | Gates |
|----|----------|------|-------|
| M1 | Medium | `nebula-agents mcp install` versus documented manual host configuration | Must be answered before Step 7 (S0003). Does not block Steps 1-6 |
| — | Medium | MCP protocol revision and conformance fixtures not yet pinned | Pin during Step 7 authoring |
| L1 | Low | S0001's open question unreconciled against ADR-005 | Reconcile during Step 4 authoring |

## Step 3 Findings — raised by implementation, not by review

### S3-F1 (High) — `1.1` cannot be "no F0001 schema changes"

Three approved statements are mutually exclusive:

| Source | Statement |
|--------|-----------|
| Runtime contract §9 | `1.1` is additive: "no F0001 command, exit-code class, record, or **schema** changes" |
| BLUEPRINT §5.3 | "Indexing, summarization, and proposal drafting [create runtime events]" |
| `f0001-runtime-event.schema.json` | `event_type` is a **closed enum** of 24 F0001 values |

F0003 cannot append `ArtifactIndexed` without changing that enum, and cannot omit the
event without contradicting BLUEPRINT §5.3.

**Resolved in code, pending Architect confirmation.** The enum gains eleven F0003 members
and runtime-contract §9 is corrected to record it as the one F0001 schema change `1.1`
makes. Every event written under `1.0` stays valid and no field, type, or existing member
changed — but a **strict `1.0` reader will reject an event type it does not know**, so the
change is backward-compatible for data and not transparent to readers.

A separate `f0003-runtime-event` schema was considered and rejected: both options break a
strict `1.0` reader identically, because the events share one `events.jsonl`, and a second
schema over the same stream adds machinery without adding compatibility.

**Owner: Architect.** Confirm at G3, or direct a different resolution. This is a published
compatibility contract, not an implementation detail.

### S3-F2 (Low) — a G1 row was wrong, and is corrected in place

`g1-runtime-preflight.md` recorded that the six F0003 schemas "load through the existing
`JsonSchemaRegistry` with **no registry change**". The registry allowlisted `f0001-` names
only, so every F0003 name was refused; the G1 probe asserted only that *an* error was
raised and read a refusal as a validation.

Corrected in the G1 artifact with the reasoning kept, and replaced by a test that requires
each F0003 schema to **load** and a non-allowlisted name, a traversal attempt, and a
non-schema file to be **refused**. No blocker was missed and the G1 verdict is unchanged.

## Step 4 Findings

### S4-F1 (Medium) — a blocked launch has no run to append an audit entry to

Runtime contract §7 and the assembly plan both say a blocked launch "appends a sanitized
audit entry". In this codebase an audit entry is a `RuntimeEvent` in a run's
`events.jsonl`, and every append goes through `RunRepository.commit`, which requires an
existing run record.

But the guard runs **before** `launch` — deliberately, so a blocked launch persists no
session and creates no run. There is therefore no run to append to, and creating one just
to record that nothing was created would defeat the property the ordering exists to
protect.

**Resolved as:** the persisted `ProviderCapabilityReport` is the durable sanitized record.
It is atomic, owner-only, carries `launch_decision: blocked` with `blocked_reason` and the
failing capability, and is what `providers doctor` reads back. A test asserts it is
written even on the blocked path.

**This is an interpretation, not a literal reading.** "Audit entry" elsewhere in this
codebase means a runtime event. Two alternatives were considered and rejected: creating a
run to hold the event (defeats "creates no run"), and adding a runtime-level event log
outside any run (a new persistence surface, which ADR-005 constrains).

**Owner: Architect.** Confirm at G3, or direct a run-less audit log. Carried alongside
S3-F1, which is also a contract-text question rather than an implementation defect.

### Note — `providers doctor` exits 3 when a provider is blocked

A diagnostic must describe an unusable environment rather than refuse to run in one, so
`doctor` reports the blocked provider and exits 3 rather than raising. This mirrors
F0001's `doctor`, which returns 3 on a non-ready overall status instead of erroring.

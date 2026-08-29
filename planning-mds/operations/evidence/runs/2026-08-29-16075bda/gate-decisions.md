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

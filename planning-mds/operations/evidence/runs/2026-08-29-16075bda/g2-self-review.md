# G2 Self-Review — F0003

**Run:** `2026-08-29-16075bda` · **Owner:** Quality Engineer · **Date:** 2026-08-29
Self-review against the approved Phase B package before external review at G3.

## Scope Review

F0003 delivers seven stories across eight build steps, all implemented. Scope matches the
approved Phase B package: twelve added commands and six read-only MCP tools, no service,
no daemon, no port, no screens. Nothing outside `engine/**`, `docs/`, and this run folder
was touched, apart from the deliberate `event_type` enum extension recorded as S3-F1.

### Scope reconciliation

The G2 judgment requires the manifest's conditional booleans to be reconciled against
discovered scope **first**. Reconciled:

| Boolean | Value | Basis |
|---------|-------|-------|
| `runtime_bearing` | `true` | Implementation is in `engine/**` |
| `security_sensitive_scope` | `false` → **`true` at this gate** | Redaction, path containment, authorization, and the MCP boundary are all in scope. Deferred from G0 because the check is not stage-gated and demands scan evidence that did not exist; the scans have now run |
| `frontend_in_scope` | `false` | CLI-only; F0003 ships no screens (BLUEPRINT §5.8) |
| `deployment_config_changed` | `false` | No new required dependency, no packaging or topology change |

The `security_sensitive_scope` flip is a **false → true** change, which the judgment says
forces the corresponding required role and artifact. Security Reviewer was already
required via STATUS.md, so the effective role set does not change; `security-review-report.md`
becomes required at G3, which is where it belongs.

## Acceptance Criteria Review

Every story's acceptance criteria are mapped to the test that closes it in
`artifacts/test-coverage/acceptance-criteria-map.md`. All seven stories are covered; the
map states its three known gaps rather than implying completeness.

## Architecture conformance

Each ADR checked against what was built, not against the plan.

| Decision | Built as decided? |
|----------|-------------------|
| ADR-005 — extends the package, no service | Yes. One console script, no daemon, no port, no new required dependency — asserted by `test_package_contract.py` and a clean install |
| ADR-006 — root-scoped identity, longest match, 12 hex | Yes. Executable in `domain/artifacts.py`; tie-break exercised |
| ADR-007 — dependency-free stdio MCP, query-only facade | Yes. Read-only asserted at instance **and** import level; clean install serves six tools with no MCP SDK |
| ADR-008 — rule-based summaries, no model call | Yes. Structural: no summarizer can import an HTTP client, socket, or model SDK |
| ADR-009 — inert proposals, allowlisted targets, sticky rejection | Yes. `accept` never opens the target — asserted by checking the path is never created |

Layering holds: `test_layering.py` fails the build on any outward import. It was added
after a real violation of mine, not pre-emptively.

## Contract conformance

Contract `1.1` is additive: F0001's nine commands still parse and behave identically, and
the 514 F0001 tests pass unmodified. **One F0001 schema did change** — `event_type` gained
eleven members — which is finding S3-F1, recorded in `gate-decisions.md` and corrected in
runtime-contract §9 rather than left contradicting it.

## Implementation Risks

## Recommendations

Four findings need an Architect or Security decision. None blocks G2; all are recorded in
full in `gate-decisions.md`.

- [high] Confirm the `event_type` enum extension as the one F0001 schema change contract `1.1` makes, or direct another resolution; a strict `1.0` reader rejects event types it does not know (S3-F1) — owner: Architect; follow-up: decide at G3 before code review closes
- [medium] Confirm that the persisted capability report satisfies "a blocked launch appends a sanitized audit entry", or direct a run-less audit log (S4-F1) — owner: Architect; follow-up: decide at G3 before code review closes
- [low] Reclassify `doctor` outside a workspace from `SCHEMA_INVALID` exit 9 to a preflight/setup error exit 3; pre-existing F0001 behaviour (S9-F2) — owner: Architect; follow-up: F0001 backlog, not this run
- [low] Reconcile the G2 artifact name between `feature.yaml` (`g2-deployability-check.md`) and the validator (`deployability-check.md`) (S9-F3) — owner: Architect; follow-up: F0007 pilot report

## Validation Evidence

730 tests green on Python 3.11.15, 3.12.13, and 3.14.4; line coverage 92.25%, branch
82.71%. Four security scan classes run or waived, with the secrets triage recorded in the
scan artifact. Six lifecycle gates pass; `kg --check-reproducible` OK; deep feature-evidence
validation passes at G1 and G2. Evidence: `test-execution-report.md`, `coverage-report.md`,
`artifacts/test-results/`, `artifacts/security/`.

## What I would flag to a reviewer about my own work

- **Two defects were invisible to their own layer's tests** — the `infer_kind` seam bug and
  the layering violation. Both now have a lane that would catch a recurrence, but the
  pattern is worth a reviewer's attention: unit coverage at 95% did not prevent either.
- **`atomic.py` is the lowest-covered module at 84%**, and the gap is OS-error branches
  that cannot be provoked without fault injection. I chose not to mock them; a reviewer may
  disagree.
- **The MCP surface has no third-party host conformance run.** It is exercised in-process
  and as a real subprocess against the protocol shape this repository already serves.

## Result

PASS WITH RECOMMENDATIONS

Implementation matches the approved architecture, the test and coverage evidence is
complete, and the findings above are routed rather than resolved here.

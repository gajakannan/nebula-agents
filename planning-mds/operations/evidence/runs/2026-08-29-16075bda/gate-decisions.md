# Gate Decisions — F0003-local-agent-runtime-control-plane run 2026-08-29-16075bda

> One row per gate evaluated. Rows are added as gates execute; G1-G8 are not yet reached.

## Gate Decisions

| Gate | Decision | Decider | Timestamp | Rationale | Blocking | Follow-up |
|------|----------|---------|-----------|-----------|----------|-----------|
| G0 | PASS | Architect | 2026-08-29T11:35:30-04:00 | Assembly plan authored and validated against the approved Phase B package; all 7 stories covered, no blocking plan finding | No | M1 gates Step 7 (S0003); MCP protocol revision pinned at Step 7; L1 reconciled at Step 4 |
| G1 | PASS | DevOps | 2026-08-29T11:48:38-04:00 | Environment, tmux, providers, schemas, and the ADR-006 root rule verified; 514 engine tests pass on all three CI-matrix interpreters | No | `RuntimeConfig` lacks `evidence_root` — already an assembly-plan row, not a blocker |
| G2 | PASS WITH RECOMMENDATIONS | Quality Engineer | 2026-08-29T23:24:14-04:00 | 730 tests green on 3.11/3.12/3.14; line 92.25%, branch 82.7%; four security scan classes run or waived; one deployability defect found and fixed | No | S9-F1 fixed; S9-F2 recorded for the F0001 owner; S3-F1/S4-F1 carried to G3 |
| G3 | PASS WITH RECOMMENDATIONS | Code Reviewer + Security Reviewer | 2026-08-29T23:40:01-04:00 | Severity ACCEPTABLE (critical 0, high 0) via gate_policy standard profile. One HIGH security finding raised and FIXED within the cycle | No | SEC-1 fixed; CR-1 needs an architecture decision at G4; S3-F1 and SEC-1 are both additive F0001 schema changes |
| G4 | PASS | Operator | 2026-08-29T23:45:10-04:00 | Severity ACCEPTABLE; all four carried decisions confirmed (S3-F1, SEC-1, S4-F1, CR-1) | No | CR-1's confirmation is a standing pattern decision for future F0003 stores |

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

## Step 8 — test and evidence closure

Test and coverage evidence is produced; **no gate decision is recorded here.** G2 is the
QE gate and has not run. What follows is the material G2 will assess.

| Measure | Value |
|---------|-------|
| Tests | **709** — 0 failures, 0 errors, 0 skipped |
| Of which F0003 | 192 |
| Interpreters | 3.11.15, 3.12.13, 3.14.4 — all green |
| Line coverage | 92.22% (5480/5942), minimum 85% |
| Branch coverage | 82.64% (1438/1740) |

Artifacts: `artifacts/test-results/junit.xml`, `artifacts/test-results/coverage.xml`,
`artifacts/test-coverage/acceptance-criteria-map.md`.

### The coverage audit states its gaps rather than implying completeness

`acceptance-criteria-map.md` maps every story's acceptance criteria to the test that
closes it, and names three things that are **not** covered:

1. **S0003 is entirely unimplemented and untested** — blocked on M1. No partial
   implementation exists to mislead a reader, and the `f0003-mcp-response` schema is
   recorded as deliberately unexercised.
2. The lifecycle test patches the provider and tmux seams. A real provider process is
   exercised only by F0001's `test_real_tmux_lifecycle.py`, which runs and does not skip.
   F0003 adds no new subprocess path.
3. `gate_wait_seconds` approximates from the gate's `updated_at`. A dedicated
   gate-transition timestamp would be exact.

### Two checks added at Step 8 that did not exist

- **Packaging contract.** ADR-005 and ADR-007 both rest on "no new required dependency",
  which is a claim about a file that changes. `test_package_contract.py` asserts the
  dependency set, the console entry point, and that no F0003 module imports anything
  outside the standard library and `jsonschema`. Verified separately against a genuinely
  clean 3.11 install carrying only `jsonschema` and its transitive deps.
- **Full operator lifecycle through the CLI.** Every layer had passing tests when
  `infer_kind` misfiled `validator.txt` as `status`, because the defect lived in the seam
  between two correct layers. `test_f0003_lifecycle.py` runs the operator's real path —
  `providers doctor → wrap → index → summarize → metrics → learn review → decide` — and
  asserts the artifact kinds explicitly, which is where that class of defect shows up.

### `security_sensitive_scope` remains false

It flips at **G2**, when QE runs the four scan classes. The flag is not stage-gated, so
setting it earlier would demand scan evidence that does not exist yet. The Security
Reviewer signoff is required from G3 regardless, via STATUS.md. Recorded at G0 and
unchanged.

### S8-F1 (Low) — committed evidence referenced a file `.gitignore` excluded

`.gitignore` carried a repo-root rule `coverage.xml`, intended for build output. It also
matched `planning-mds/operations/evidence/runs/*/artifacts/test-results/coverage.xml`, so
every run's coverage artifact was silently excluded from the commit while its manifest
recorded the path, byte count, and SHA-256.

**F0001's archived evidence has the same dangling reference** — runs
`2026-07-13-1cfbc5a0` and `2026-07-14-b885d64c` both name a `coverage.xml` that was never
committed. The local files still exist and their SHA-256 **matches the recorded hash
exactly** in both cases, so they are the genuine artifacts rather than stale rebuilds.
They are committed here, which makes an archived, signed-off evidence package resolvable
for the first time.

Fixed with a negation scoped to the evidence path only; build output stays ignored.

Worth noting how it surfaced: not by review, and not by `validate-feature-evidence` —
which does not verify that `test_results.artifacts` paths resolve, the way it does for
`scm.diff_artifact` and `security_scans`. It surfaced because `git status` after staging
showed the file missing. **That validator gap is a framework finding for F0007's pilot
report**: a manifest can name a test artifact that is not in the repository and still
pass every stage.

## Step 7 — read-only MCP surface · Checkpoint E met · M1 RESOLVED

### M1 resolved 2026-08-29 — documented manual host configuration

There is **no `mcp install` subcommand**. Writing a host's configuration file would put
Nebula inside a trust boundary it does not own: that file governs which processes the host
spawns, it frequently sits alongside credentials for other servers, and its format is the
vendor's to change. An installer would have to locate it by guesswork, merge without
clobbering unrelated entries, and track each host's schema — and getting any of that
subtly wrong is worse than a documented paste.

Recorded in `docs/mcp-host-configuration.md` and in S0003's *Open Questions*. **L1 is
resolved in the same pass**: ADR-005 already decided the entry point question, and the
built code is the evidence — the commands live behind the F0001 console script, which
contract `1.1` extends and never replaces.

**Both plan-review findings carried open since 2026-08-19 are now closed.**

| Checkpoint E criterion | Result |
|------------------------|--------|
| `McpServer` cannot reach any mutating service | PASS — asserted at instance **and** import level |
| Every tool evaluates `ReadState` in addition to the facade guarantee | PASS — via `QueryService` |
| All six tool names match the contract exactly | PASS — pinned literally |
| Responses are paged and schema-conformant; errors carry no stack traces | PASS |

### S7-F1 (Low) — the schema was right and my first design was wrong

`f0003-mcp-response` pins `tool_name` to the six-name enum, so an error envelope naming an
*unknown* tool cannot be schema-conformant. My first implementation returned exactly that.

That is the schema being right, not restrictive: an unknown tool is not a tool *result*,
it is a protocol error, and it belongs at the JSON-RPC layer as `-32601`. Keeping it in
the envelope would have forced either a non-conformant response or a dishonest
`tool_name`. Moved; every envelope is now schema-conformant by construction.

Found by validating responses against the committed schema in test. Reading alone would
not have caught it — the envelope looked correct.

### ADR-007's premise, demonstrated rather than asserted

A genuinely clean 3.11 install carrying only `jsonschema` and its transitive dependencies
serves all six tools. No MCP SDK is present, which is what makes S0003's "MCP SDK
unavailable" edge case unreachable rather than handled.

The troubleshooting command printed in `docs/mcp-host-configuration.md` was executed
verbatim, as was the alternate `python -m nebula_agents mcp serve` form. Both work as
documented.

## G2 — self-review, QE, and deployability

**PASS WITH RECOMMENDATIONS.** 730 tests green on all three interpreters; line 92.25%,
branch 82.71%. Artifacts: `g2-self-review.md`, `test-plan.md`, `test-execution-report.md`,
`coverage-report.md`, `deployability-check.md`.

### Scope booleans reconciled first, as the gate requires

`security_sensitive_scope` **false → true**. Deferred at G0 because the check is not
stage-gated and would have demanded scan evidence that did not exist; the scans have now
run. The flip forces the Security Reviewer role, which STATUS.md already required, so the
effective role set is unchanged and `security-review-report.md` becomes required at G3 —
where it belongs.

### Security scans — executed, and triaged rather than waved through

| Class | Result | Detail |
|-------|--------|--------|
| Dependency | **clean** | `pip-audit` over the 6-package runtime closure of a clean install. 0 vulnerabilities |
| Secrets | **clean** | `detect-secrets` over `engine/`, the run folder, and `docs/`. 7 candidates, **all triaged in the artifact** |
| SAST | **findings** | `bandit` over `engine/src`: 0 HIGH, 0 MEDIUM, 17 LOW |
| DAST | **waived** | No listening port or HTTP target exists. Architect-owned waiver, 2026-08-29 |

Every secrets candidate was reviewed and the reasoning recorded in the scan artifact
itself: synthetic redaction fixtures, their echoes in pytest **parametrize IDs** inside
`junit.xml`, and the manifest's own SHA-256 digests. None was ever a live credential.
Worth naming as a pattern: a test parametrized over a *real* value would land it in
committed evidence exactly the same way.

**One SAST LOW was mine and was real.** `bandit` B101 flagged an `assert` guarding the MCP
handler map against the published tool contract. `python -O` strips asserts, so that
invariant would silently vanish in an optimised run and ship a surface not matching the
contract. Replaced with an unconditional check and verified under `-O`. The remaining 17
are pre-existing F0001 (typed-argv subprocess, deliberate `try/except/pass` where an audit
failure must not become access) or false positives (`B105` on enum members literally named
`Pass`).

### S9-F1 (Medium) — found and fixed at this gate

Outside a configured workspace, every MCP tool returned **success with an empty result**.
A host pointed at the wrong directory produced an empty session list and an empty evidence
list — indistinguishable from a real run with no evidence, so a reviewer would read "this
run has nothing" rather than "I am in the wrong tree".

`docs/mcp-host-configuration.md` already documented `WORKSPACE_NOT_CONFIGURED` for this
case. **The documentation was right and the code was not.** A workspace probe was added,
the tools now return that error, and three tests cover it.

Found by *running* the documented troubleshooting steps from outside a workspace rather
than reading them. Documentation that has not been executed is a guess.

### S9-F2 (Low) — recorded, deliberately not fixed

`nebula-agents doctor` outside a workspace reports `SCHEMA_INVALID` — "Restore the
committed schema" — and exits 9. Nothing is corrupt; the operator is in the wrong
directory. The correct class is preflight/setup, exit 3.

Pre-existing F0001 behaviour in the schema registry's load path. Reclassifying an F0001
error is a contract change owned by whoever owns that path, and the 514-test boundary
makes it a reviewed change rather than a drive-by. The MCP documentation no longer sends
operators to `doctor` for this diagnosis.

### S9-F3 (Low) — framework finding, for F0007's pilot report

`agents/actions/spec/feature.yaml` declares the G2 artifact as
**`g2-deployability-check.md`**; `validate-feature-evidence.py` requires
**`deployability-check.md`**. The names disagree. The validator's name is authoritative in
practice — it is what fails the gate — and is what F0001 used, so that is what is written
here. The spec's `artifacts` list is not what the gate enforces.

This is the fourth framework finding this pilot has produced, after the vacuous mid-flight
gate validation, the unverified `test_results.artifacts` references, and the `.gitignore`
exclusion of committed evidence.

## G3 — code and security review

**PASS WITH RECOMMENDATIONS.** `gate_policy.py --profile standard` computes **ACCEPTABLE**
from critical 0 / high 0 across both domains, `requires_justification: false`. Computed,
not asserted.

### SEC-1 (High) — raised and fixed inside this review cycle

`learn decide` took `--role` from the command line, and the check compared that
**declared** role to the role the target document requires — never asking whether the
actor held it. Demonstrated: a `LocalOperator` who owned the run passed `--role architect`
and accepted a proposal targeting `SOLUTION-PATTERNS.md`.

That defeats the security model's central claim about this action — *owning the run does
not confer the right to decide its proposals* — and reopens the escalation path ADR-009's
`DraftProposal`/`DecideProposal` split exists to close, from the other side: the split
stops one capability covering both, but a caller-supplied role made the second
self-granting.

**Fixed.** The role is derived from the target document and verified against
`proposal_grants` in the `0600` policy file; `--role` is removed, because a role the
caller can name is a role the caller can claim. Deny by default. Three tests cover it,
including that a grant for one target class does not carry to another.

This required a **second additive change to an F0001 schema** —
`f0001-local-policy.schema.json` gains `proposal_grants`. Unavoidable: `reviewer_grants`
is closed and `bindings` knows only `LocalOperator|Reviewer|System`, so expressing
per-target-class decision authority needs new policy state. Same class as S3-F1, and
carried to the Architect with it.

### CR-1 (Medium) — an architecture decision, not a code fix

The artifact index and the audit event commit in **separate** transactions against
different stores. If the second fails — a stale run revision is the realistic case — the
projection advances without an audit entry, and BLUEPRINT §5.3 requires that event.

Medium rather than high: the index is a projection, re-indexing is idempotent and is the
documented recovery path, and the failure is loud rather than silent. Not fixed here
because the options are a two-phase commit across two stores, or folding the index into
the run record — and the second contradicts ADR-006's decision to keep the index separate.

### Two low findings

CR-2: stale-evidence blocking is run-wide, so one missing artifact silences the whole run's
learning. Matches S0006's acceptance criterion exactly; noted because it is stricter than a
reader expects. CR-3: `gate_wait_seconds` uses a proxy timestamp.

### For the Architect at G4

| ID | Severity | Decision |
|----|----------|----------|
| S3-F1 | High | Confirm the `event_type` enum extension |
| SEC-1 | High (fixed) | Confirm `proposal_grants` as the second additive F0001 schema change |
| S4-F1 | Medium | Confirm the capability report as the blocked-launch audit record |
| CR-1 | Medium | Settle whether projection-store commits and their audit events must be atomic |

S3-F1 and SEC-1 together are the whole of contract `1.1`'s non-transparency to a strict
`1.0` reader. Both are additive; neither changes an existing field, type, or member.

### S10-F1 (Low) — framework finding: artifact references are parsed greedily

`artifact_references()` matches `[^\s)\]]+` after the path prefix, so it stops only at
whitespace, `)`, or `]`. A reference written the natural way in prose —
`` `artifacts/security/bandit-sast.json`. `` — is extracted **with its closing backtick
and full stop attached**, and then fails to resolve.

Three reports had to be rewritten to bare paths on their own lines. The requirement is not
stated in any template, and the failure mode is a confusing "artifact is missing" for a
file that plainly exists.

Fifth framework finding from this pilot. Worth pairing with the earlier one that
`test_results.artifacts` manifest paths are **not** checked at all: prose references are
validated strictly while structured manifest references are not validated whatsoever.

## G4 — Approval

**APPROVED.** Recorded 2026-08-29T23:45:10-04:00 on the operator's explicit confirmation.

`gate_policy.py --profile standard` computes **ACCEPTABLE** — critical 0, high 0,
`requires_justification: false`. No mitigation token is required, because no high finding
remains open: SEC-1 was fixed inside the G3 review cycle with regression tests, and S3-F1
is confirmed below rather than carried.

### The four decisions, as confirmed

| ID | Decision confirmed |
|----|--------------------|
| **S3-F1** (High) | The `event_type` enum extension **is** the one F0001 schema change contract `1.1` makes. Runtime-contract §9 records it, including that a strict `1.0` reader rejects event types it does not know. Data written under `1.0` stays valid |
| **SEC-1** (High, fixed) | `proposal_grants` in `f0001-local-policy.schema.json` is confirmed as the second additive F0001 schema change. No smaller fix exists: `reviewer_grants` is closed and `bindings` knows only `LocalOperator|Reviewer|System` |
| **S4-F1** (Medium) | The persisted `ProviderCapabilityReport` **is** the durable sanitized record for a blocked launch. The guard runs before any run exists, so there is nothing to append a runtime event to, and creating a run to record that none was created would defeat the property the ordering protects |
| **CR-1** (Medium) | Projection-store commits and their audit events are **not** required to be atomic. Repairable divergence is the accepted pattern for F0003's stores: the index is a projection, re-indexing is idempotent and is the documented recovery path, and the failure is loud rather than silent |

### What CR-1's confirmation settles going forward

It is a standing decision, not a one-off: any future F0003 store may commit its projection
and its audit event separately, provided the projection is rebuildable and the failure
surfaces to the caller. A store that fails either condition does not get this treatment.

### Contract consequence, accepted

S3-F1 and SEC-1 together are the whole of where contract `1.1` is not transparent to a
strict `1.0` reader. Both are additive — no existing field, type, or enum member changed —
and both are now recorded in the documents a reader consults rather than discoverable only
from a diff.

### Low findings, accepted without action

S7-F1 and S8-F1 are resolved in code. S9-F2 (`doctor` misreports outside a workspace) and
S9-F3 / S10-F1 (framework inconsistencies) are routed to their owners and do not gate this
feature.

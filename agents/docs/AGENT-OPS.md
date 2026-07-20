# Agent Ops

The framework-level reference for the **evidence and telemetry** every
orchestrated run captures: what each run records, where it lands, who
writes which artifact, and at which gate.

This is the single source of truth for the evidence/telemetry contract.
The orchestration contract, manual runbook, ROUTER, and AGENT-USE link
here instead of restating it. The machine-checkable source of truth is the
validator (`agents/product-manager/scripts/validate-feature-evidence.py`);
this doc is the human-readable contract behind it.

## Why It Exists

Every action a builder runs — planning, a feature slice, a review, a test
pass — produces decisions and command output that are otherwise lost the
moment the session ends. Without a recorded package, a later agent (or a
human auditor) cannot answer "was this gate actually run?", "what command
proved the tests passed?", "who signed off, and on what evidence?", or
"what changed and was it security-reviewed?".

Agent Ops is that record. Each run writes a structured **evidence
package**: a manifest, role/gate reports, an append-only command log, and
a lifecycle-gate log. The package is the contract surface — gate decisions
must be backed by recorded evidence, not by prose assertions. A validator reads
the package at every stage so gaps are caught *during* the run, not at
closeout.

Two profiles exist:

- **Base run** — any non-feature/manual run (operator `validate`, ad-hoc
  preflight, release rehearsal). Six base files, no manifest.
- **Feature package** — a completed terminal feature run. The full
  package: manifest, role reports, signoff, closeout, and a `latest-run.json`
  pointer.

Evidence is a **retrieval/audit aid over the run** — raw artifacts (code,
PRDs, ADRs, `STATUS.md`, trackers) remain authoritative on conflict.

## Retrieval Policy

Evidence under `{PRODUCT_ROOT}/planning-mds/operations/**` is cold archive.
Agents must honor `{PRODUCT_ROOT}/.agentignore` before broad product discovery
and must not bulk-read or broad-search operations evidence by default.

The supported retrieval path is index-first: read `operations/evidence/README.md`,
then feature `latest-run.json`, then the selected run's
`evidence-manifest.json`. Open raw reports, logs, screenshots, and
`artifacts/**` only when an explicit audit, validation, closeout, failure
triage, or user request requires that exact artifact. When a formal action run
bypasses `.agentignore`, record the reason and path in `artifact-trace.md`.
The full policy lives in `agents/docs/AGENTIGNORE.md`.

## Mental Model

```
{PRODUCT_ROOT}/planning-mds/operations/evidence/
│
├── runs/
│  └── {run-id}/                    ← CANONICAL RUN PACKAGE
│        ├ README.md                  6 base files
│        ├ action-context.md          run identity, inputs, stage
│        ├ artifact-trace.md          what was read / written / generated
│        ├ gate-decisions.md          every gate: decision, decider, why
│        ├ commands.log     ◀──────── JSON-Lines telemetry (append-only)
│        ├ lifecycle-gates.log
│        ├ evidence-manifest.json     feature runs only
│        ├ feature-action-execution.md
│        ├ g0-assembly-plan-validation.md   (Architect)
│        ├ g1-runtime-preflight.md          (DevOps, if runtime_bearing)
│        ├ g2-self-review.md
│        ├ test-plan.md / test-execution-report.md / coverage-report.md  (QE)
│        ├ deployability-check.md           (DevOps)
│        ├ code-review-report.md            (Code Reviewer)
│        ├ security-review-report.md        (Security, if required)
│        ├ signoff-ledger.md                (PM)
│        ├ pm-closeout.md                   (PM)
│        └ artifacts/  coverage/ diffs/ test-results/ security/ screenshots/
│
├── features/
│  └── F####-{slug}/                ← FEATURE INDEX
│        latest-run.json              pointer → approved run + manifest
│
├── frontend-quality/             ← GLOBAL LANES (referenced, not replaced)
└── frontend-ux/
```

**Three rules to internalise:**

1. **The manifest is the index; the validator is the judge.** Every
   feature run carries `evidence-manifest.json` declaring required roles,
   gate results, scope booleans, files, omissions, and waivers. The
   validator cross-checks the manifest against the filesystem, the reports,
   and `STATUS.md` — prose alone never satisfies a gate.
2. **Gates write evidence; closeout publishes it.** Artifacts are created
   and updated at the gate that owns them (G0→G8), not at the action
   level. The closeout step is what flips a run to `approved` and writes
   the `latest-run.json` pointer.
3. **`STATUS.md` signoff is append-only and authoritative.** The current
   verdict per `(story, role)` is the latest row, computed as a view — rows
   are never mutated or deleted. `signoff-ledger.md` may summarize current
   rows but must not contradict them.

## The Gate Timeline: Who Writes What, When

Within a feature run, evidence is created and updated as the run advances
through lifecycle gates. This is the "how each action updates the package"
view: each gate adds or finalizes specific artifacts; the two logs are
appended at every gate.

```
 G0 ───────▶ G1 ──────▶ G2 ──────────▶ G3 ──────────▶ G5 ─────────▶ G6 ─────────▶ G8 / closeout
 │           │          │              │              │               │               │
 manifest    g1-runtime g2-self-review code-review    STATUS.md        feature-action  pm-closeout.md
 (draft)     -preflight test-plan      -report        signoff rows     -execution.md   manifest→approved
 g0-assembly (if rt-    test-execution security-review signoff-ledger   candidate       patch prior→superseded
 -plan-      bearing)   coverage       (if required)   .md              manifest        latest-run.json (write)
 validation             deployability                                                   tracker/KG/template
 README/                -check                                                          results → logged
 action-                 │              │              │               │
 context/                │              │              │               │
 artifact-    [ commands.log + lifecycle-gates.log appended at every gate ──────────────────────────▶ ]
 trace/
 gate-
 decisions
 ▲ Owners:  Architect(G0) · DevOps(G1, deployability) · QE(test*, coverage) ·
            Code Reviewer(G3) · Security(G3 if required) · PM(G5 signoff, G8 closeout) ·
            Feature orchestrator(execution, self-review)
```

Supersession order at closeout is **mandatory** (G8): run
`patch-prior-manifest.py` first (prior approved manifests → `superseded`),
*then* write `latest-run.json`. Patching first means a partial failure
leaves the recoverable "no approved pointer" state, never the
harder-to-repair "two approved manifests" state.

Non-feature actions never run the full feature lane — they produce only the
base run package:

| Action | Profile | Produces |
|--------|---------|----------|
| `init`, `plan`, `plan-review` | base run | 6 base files |
| `review`, `validate`, `test`, `document`, `blog` | base run | 6 base files (+ `validate` adds its three validation reports) |
| `feature` (completion) | feature package | full package + `latest-run.json` |
| `build` (when it archives a delivered feature) | feature package | full package + `latest-run.json` |

`validate` runs write `pm-validation-report.md`,
`architect-validation-report.md`, and `implementation-validation-report.md`
into the **base run** path — never into a feature package.

## Package Anatomy

All paths are relative to `{PRODUCT_ROOT}`. Templates for every file below
live at `agents/templates/` (e.g. `feature-evidence-readme-template.md`,
`evidence-manifest-template.json`, `pm-closeout-template.md`,
`commands-log-template.md`).

### Base run files (both profiles)

| File | Required headings | Purpose |
|------|-------------------|---------|
| `README.md` | `Run Summary`, `Status`, `Evidence Index`, `Validation Summary`, `Open Follow-ups` | Human entry point; status must match the manifest |
| `action-context.md` | `Run Identity`, `Inputs`, `Assumptions`, `Scope Boundaries`, `Lifecycle Stage` | What ran, with what inputs, at which stage |
| `artifact-trace.md` | `Artifacts Read`, `Artifacts Created Or Updated`, `Generated Evidence`, `External Or Global Evidence References`, `Omissions And Waivers` | Path-accurate trace of every artifact touched |
| `gate-decisions.md` | `Gate Decisions` (gate, decision, decider, timestamp, rationale, blocking, follow-up) | Every gate decision with rationale |
| `commands.log` | JSON-Lines (see Telemetry below) | Append-only command record |
| `lifecycle-gates.log` | `Lifecycle Gate Run`, `Command`, `Stage`, `Exit Code`, `Result`, `Output References`, `Skipped Gates` | Output of `run-lifecycle-gates.py` |

Required-heading checks are **structural** — the heading must be present
even when its body is empty (use `None`). Heading matching is
case-insensitive and whitespace-insensitive, but word order and
punctuation must match.

### Feature package files (added on top of the base files)

| Artifact | Owner | Gate | Required when |
|----------|-------|------|---------------|
| `evidence-manifest.json` | Orchestrator / PM | G0 / G6 / G8 | every feature run |
| `latest-run.json` | PM | G8 | approved completed terminal feature |
| `feature-action-execution.md` | Orchestrator | G6 | every feature run |
| `g0-assembly-plan-validation.md` | Architect | G0 | every feature run |
| `g1-runtime-preflight.md` | DevOps / orchestrator | G1 | `runtime_bearing = true` |
| `g2-self-review.md` | Orchestrator | G2 | every feature run |
| `test-plan.md`, `test-execution-report.md`, `coverage-report.md` | QE | G2/G5 | every completed terminal feature |
| `deployability-check.md` | DevOps / orchestrator | G2/G5 | every completed terminal feature |
| `code-review-report.md` | Code Reviewer | G3/G5 | every completed terminal feature |
| `security-review-report.md` | Security | G3/G5 | Security required or `security_sensitive_scope = true` |
| `signoff-ledger.md` | PM | G5/G6 | every completed terminal feature |
| `pm-closeout.md` | PM | G8 | every completed terminal feature |
| `artifacts/{coverage,diffs,test-results,security,screenshots}/` | QE / FE / orchestrator | varies | when that artifact class exists |

`coverage-report.md` must exist even when coverage is waived. The `diffs/`
artifact is required for implementation-changing runs (manifest
`scm.diff_artifact` must resolve and list the changed files).

## The Manifest

`evidence-manifest.json` is the machine-readable index for a feature run.
It declares the run's identity, scope, required roles, gate and role
results, the file map, and any omissions/waivers. Schema example lives in
`agents/templates/evidence-manifest-template.json`. Key fields:

- **Identity:** `feature_id`, `feature_slug`, `run_id`, `status`
  (`approved` / `superseded` / draft), `recorded_on`,
  `contract_effective_date`, `feature_path_at_run_start` /
  `_at_closeout`, `feature_state`, `rerun_of`.
- **Change scope:** `changed_paths[]`, `scm.{base_ref, head_ref, diff_artifact}`.
- **Scope booleans (below):** drive which evidence is required.
- **Results:** `required_roles[]`, `gate_results{}`, `role_results{}`, `files{}`.
- **Security scans:** `security_scans{}` — required when `security_sensitive_scope = true` (see *Security scan handoff* below).
- **Escape hatches:** `omissions[]`, `waivers{}`.

### Scope booleans

Booleans are mandatory so the validator never has to infer conditional
evidence from prose. Each `true` forces downstream evidence; the validator
cross-checks them against `changed_paths[]` (case-sensitive glob match).

| Boolean | Set `true` when… | Forces |
|---------|------------------|--------|
| `runtime_bearing` | runtime code/tests/migrations/Docker/CI/app-config/frontend/backend/AI changed | `g1-runtime-preflight.md` |
| `deployment_config_changed` | Dockerfiles, compose, CI deploy, env contracts, migrations, startup, secrets/config, topology changed | DevOps required; rollback/config notes in `deployability-check.md` |
| `frontend_in_scope` | UI, routes, tokens, fetching, forms, a11y, or `experience/**` changed | feature-level frontend test notes (global lanes may be linked, not substituted) |
| `security_sensitive_scope` | authn/authz, session/token, permissions, tenant/data boundary, secrets, audit logging, PII, dependency/container exposure, or external trust boundary changed | Security required; `security-review-report.md` |

A `false` boolean contradicted by a matching `changed_paths[]` entry fires
`scope_boolean_false_with_changed_paths_fails`. Products may strengthen the
path-class→boolean mapping (additively) in
`planning-mds/operations/evidence/README.md` under `Path Class Extensions`.

### Security scan handoff (QE → Security)

Security scanning is a split responsibility, recorded once in
`security_scans{}` so neither role can assume the other did it:

- **QE is Responsible (R)** for *running* the four scan classes and publishing
  raw output under `artifacts/security/`: `dependency` (e.g. `pnpm audit`,
  `dotnet list package --vulnerable`), `secrets` (Gitleaks), `sast` (Semgrep —
  zero-infra; SonarQube is release-cadence reporting, not this gate),
  `dast` (OWASP ZAP). QE records each result in `security_scans{}`.
- **Security is Accountable (A)** for *interpreting* those artifacts —
  threat model, exploitability, severity — and owns the verdict in
  `security-review-report.md`. A Security `PASS` is only defensible when every
  scan class either ran with a resolvable artifact or carries a complete waiver.

Each class is one of:

```json
"sast": {"ran": true,  "result": "clean",   "artifact": "artifacts/security/sast-semgrep.sarif", "waiver": null}
"dast": {"ran": false, "result": "not_run", "artifact": null, "waiver": {"reason": "no running target", "owner": "DevOps", "approved_on": "2026-06-01"}}
```

When `security_sensitive_scope = true` **and** the run's
`contract_effective_date >= 2026-05-25`, the validator requires all four
classes to be backed-or-waived. A scanner that is unavailable is recorded as a
waiver (never silently skipped). Rules: `security_scans_missing_fails`,
`security_scan_class_missing_fails`, `security_scan_unbacked_fails` (claimed
`ran` with no resolvable artifact), `security_scan_unwaived_skip_fails` (did not
run, no complete waiver). Runs on earlier contract dates are exempt.

## Telemetry: the Command Log

`commands.log` is **JSON Lines** — one JSON object per non-empty line,
append-only across the whole run:

```json
{"schema_version":1,"timestamp":"2026-05-19T14:20:00-04:00","cwd":"{PRODUCT_ROOT}","command":"pnpm test","exit_code":0,"artifacts":["…/artifacts/test-results/pnpm-test.log"],"redactions":[]}
```

| Field | Notes |
|-------|-------|
| `schema_version` | supported integer |
| `timestamp` | ISO 8601 with timezone or `Z` |
| `cwd` | repo-relative or `{PRODUCT_ROOT}` preferred; absolute paths warn unless justified in `artifact-trace.md` → `Run Environment` |
| `command` | non-empty, sanitized |
| `exit_code` | integer |
| `artifacts` | paths produced; resolve where committed |
| `redactions` | names of redacted fields/token classes |

**Secret scanning is mandatory and self-contained.** The validator scans a
per-record surface (`command` + `artifacts` strings) against named patterns
in `agents/product-manager/scripts/secret_patterns.json` — bearer tokens,
cookies, private keys, raw connection strings, access keys (single-line
regex), and `env_dump` / `env_file_contents` (multi-line scanners). The
pattern file is the maintained source of truth and is loaded at startup;
products may extend it (name conflicts error). Public scanners like
`detect-secrets`/`trufflehog` may inform the pattern set but are **not**
invoked at runtime, so validation stays deterministic. Each class has a
must-detect and must-not-detect (redaction-marker) acceptance set proven by
fixtures.

## Verdicts & Recommendations

Canonical **passing** verdicts: `PASS`, `PASS WITH RECOMMENDATIONS`,
`APPROVED`, `APPROVED WITH RECOMMENDATIONS`. Canonical **blocking**
verdicts: `FAIL`, `REQUEST CHANGES`, `REJECTED`. `NOT_REQUIRED` is valid
only for non-required roles/gates.

Recommendations under a `WITH RECOMMENDATIONS` verdict must each be a
discrete, parseable item in the role report:

```
- [severity] <text> — owner: <name-or-role>; follow-up: <ticket | deferred-to-story | explicit-deferred-no-followup>
```

Severity is exactly one of `low` / `medium` / `high` / `critical`. `low`
and `medium` need disposition (owner + follow-up). `high` and `critical`
are **blocking** — they cannot be closeout-passing unless `pm-closeout.md`
explicitly mitigates them via the **PM Acceptance Line**:

```
- Accepted: <identifier> — <type-specific details>
```

The PM Acceptance Line is the one canonical form for *every* PM acceptance
(coverage waiver → identifier `coverage`; validator-defect waiver →
the rule ID; unknown waiver key → the key; high/critical recommendation →
recommendation ID/text with a `mitigation:` prefix). The validator accepts
`—` or `-` as the separator and is case-insensitive on `Accepted:` and
`mitigation:`.

## Validation & Stages

The validator is stage-aware so gaps surface during the run:

```bash
# in-progress / candidate (latest-run.json does not exist yet)
python3 agents/product-manager/scripts/validate-feature-evidence.py \
  --product-root {PRODUCT_ROOT} --feature F#### --run-id YYYY-MM-DD-xxxxxxxx --stage G2

# final closeout (requires latest-run.json)
python3 agents/product-manager/scripts/validate-feature-evidence.py \
  --product-root {PRODUCT_ROOT} --feature F#### --stage closeout
```

| Stage | Newly required at this stage |
|-------|------------------------------|
| `G0` | evidence root + run folder, draft manifest, the 4 base markdown files, parseable (possibly empty) `commands.log`/`lifecycle-gates.log`, `g0-assembly-plan-validation.md` |
| `G1` | `g1-runtime-preflight.md` when `runtime_bearing` |
| `G2` | `g2-self-review.md`, `test-plan.md`, `test-execution-report.md`, `coverage-report.md`, `deployability-check.md` |
| `G3` | `code-review-report.md`, `security-review-report.md` (when required) |
| `G5` | current `STATUS.md` story signoff + `signoff-ledger.md` |
| `G6` | `feature-action-execution.md` + candidate manifest |
| `G8` / `closeout` | `pm-closeout.md`, finalized `approved` manifest, `latest-run.json`, tracker/story-index/KG/template results logged |

Run selection: `--run-id` is required for `G0`–`G5`; `G6` accepts
either an explicit `--run-id` (candidate) or `latest-run.json` (approved);
`G8`/`closeout` require `latest-run.json`. To avoid circular deps,
`validate-trackers.py` may only call feature-evidence validation at
`--stage G6`. `--json` (stdout) or `--json-out PATH` (file) produce
machine-readable output; combining them errors.

## Eligibility: Who Is Governed

The contract applies to **completed terminal** feature runs governed by the
effective date (`2026-05-19`). The validator emits skip counts rather than
failing for out-of-scope features.

| Feature state | Behavior |
|---------------|----------|
| Archived completed, `Archived Date < 2026-05-19` | Skip evidence validation (counted) |
| Archived completed, `Archived Date >= 2026-05-19` | Require canonical package |
| Active Done, parseable `Closeout review date < 2026-05-19` | Skip with warning |
| Active Done, closeout date `>= 2026-05-19` or missing | Require canonical package |
| Active / In Progress / Planned (non-terminal) | No completion evidence required |
| Retired (Abandoned / Superseded) | Skip (counted); metadata validated by `validate-trackers.py` |
| Reopened historical with `Evidence Reentry Date >= 2026-05-19` | Require canonical package at new closeout |

Eligibility is decided from registry/`STATUS.md` fields only — never from
filesystem timestamps or git history.

## Waivers, Omissions & Deferrals

| Mechanism | For | Never for | Record |
|-----------|-----|-----------|--------|
| Omission | non-required role/gate artifacts | baseline QE/Code Reviewer, G0, G2, deployability, signoff, PM closeout, manifest, base files | manifest `omissions[]` (reason, approver, date) |
| Coverage waiver | missing/below-target detail in a present `coverage-report.md` | a missing `coverage-report.md` file | `waivers.coverage` + PM Acceptance Line (`coverage`) |
| Runtime-preflight omission | `runtime_bearing = false` only | `runtime_bearing = true` | manifest omission + deployability note |
| Security-report omission | non-security-sensitive, Security not required | `security_sensitive_scope = true` | manifest omission + PM approval |
| Security-scan waiver | a scan class that could not run (scanner unavailable, no DAST target) | a finding from a scan that *did* run | `security_scans.<class>.waiver` (reason, owner, approved_on) |
| Deferred follow-up | non-blocking recommendations PM accepts | unresolved blockers, critical findings | role report disposition + `pm-closeout.md` |
| Validator-defect waiver | a rule that can't be satisfied due to a known validator bug | rules whose violation is a real evidence gap | `waivers.validator_defect` + `Validator Defects` subsection naming each rule ID with owner + target date |

## Cross-Artifact Consistency

The validator enforces agreement across sources — mismatches fail. The
high-value invariants:

- **Identity:** same `F####` and `run_id` across registry, `STATUS.md`,
  evidence root, manifest, and `latest-run.json`.
- **Roles & verdicts:** `STATUS.md` required roles (+ forced roles) match
  manifest `required_roles`/`role_results`; report verdicts match manifest.
- **Signoff:** `signoff-ledger.md` never contradicts current `STATUS.md` rows.
- **Closeout path:** registry folder matches manifest `feature_path_at_closeout`.
- **Changed paths:** no material changed path omitted from the manifest
  where machine-checkable (cross-checked vs `scm.diff_artifact`, trace, reports).
- **Supersession:** exactly one `approved` manifest per feature in steady
  state; two fire `two_approved_runs_without_supersession_fails`.

## Frontend Global Lanes

`planning-mds/operations/evidence/frontend-quality/` and `frontend-ux/`
remain valid global lanes. They may be **referenced** from feature
evidence but never **substitute** for feature-level notes — a
frontend-in-scope feature's `test-execution-report.md` must still carry
feature-level frontend checks. `frontend-quality/latest-run.json` follows
the `latest-run.json` schema above, minus `feature_id`; UX audits match
`^ux-audit-\d{4}-\d{2}-\d{2}\.md$`.

## Health Checks & Failure Modes

| Symptom | Cause | Response |
|---------|-------|----------|
| `missing_manifest_fails` / `missing_latest_run_fails` | required index absent | create from template; manifest at G0, latest-run at G8 |
| `commands_log_malformed_json_fails` | a log line isn't valid JSON | fix the offending line; logger should append objects only |
| `commands_log_secret_pattern_fails` | unredacted secret in `command`/`artifacts` | redact and record the class in `redactions` |
| `scope_boolean_false_with_changed_paths_fails` | boolean contradicts changed paths | set the boolean `true` (and add the forced evidence) or correct `changed_paths` |
| `*_missing_*_fails` for a role report | gate artifact not written | write the report at its gate from the matching template |
| `signoff_ledger_disagrees_fails` | ledger summarizes stale rows | recompute from the latest `STATUS.md` rows |
| `two_approved_runs_without_supersession_fails` | closeout didn't patch prior manifest | run `patch-prior-manifest.py`, then re-validate |
| `blocking_language_with_pass_fails` | high/critical recommendation not mitigated | add a PM Acceptance Line with `mitigation:` or downgrade the verdict |

On conflict, **raw artifacts win** (code, `STATUS.md`, trackers, ADRs).
Fix the source first, then the evidence record in the same change set.

## For Framework Maintainers

Adding a required artifact:

1. Add it to the package shape (Mental Model) and the Package Anatomy table
   with owner + gate + "required when".
2. Add a row to the manifest `files{}` map and (if gated) `gate_results{}`.
3. Add a template under `agents/templates/`.
4. Add a validator rule + a positive and a negative fixture under
   `agents/product-manager/scripts/tests/fixtures/feature-evidence/`, and a
   `rule-fixture-map` entry (every rule needs both a positive and negative
   fixture).
5. If it is conditional, add the controlling scope boolean or eligibility row.

Adding a secret-pattern class: add it to `secret_patterns.json` with its
must-detect/must-not-detect acceptance set and a fixture sub-case under
`commands_log_secret_pattern_fails`.

Adding a validator stage or rule: extend
`validate-feature-evidence.py`, give the rule a stable ID, and add it to the
Stages table and the fixture closure map.

## Cross-References

- `agents/docs/ORCHESTRATION-CONTRACT.md` — action I/O, gate activation,
  and lifecycle stages; its Auditability section defers evidence detail here.
- `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md` — operator procedure for
  manual runs; defers artifact/heading definitions here.
- `agents/docs/AGENT-USE.md` — session setup and prompt patterns; defers the
  evidence contract here.
- `agents/docs/KNOWLEDGE-GRAPH.md` — sibling subsystem reference (the KG is
  a retrieval index; Agent Ops is the run-evidence record).
- `agents/product-manager/scripts/validate-feature-evidence.py` — the
  executable source of truth; `patch-prior-manifest.py`,
  `validate-trackers.py`, and `secret_patterns.json` support it.
- `agents/scripts/run-lifecycle-gates.py` — produces `lifecycle-gates.log`.
- `agents/templates/` — templates for every artifact named above.
- `{PRODUCT_ROOT}/planning-mds/operations/evidence/` — the live evidence
  for a given product (data only; no docs).

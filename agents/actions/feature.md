# Action: Feature

## User Intent

Build a single feature as a complete vertical slice (backend + frontend + tests + deployability checks) that can be deployed and tested independently. Ideal for incremental delivery.

## Agent Flow

```
Architect (Implementation Orchestration)
  ↓
(Backend Developer + Frontend Developer + AI Engineer [if AI scope] + Quality Engineer + DevOps)
  ↓ [Parallel Implementation]
[SELF-REVIEW GATE: Each agent validates their work]
  ↓
Code Reviewer + Security
  ↓ [Parallel Reviews]
[Review Gate: resolve critical findings]
  ↓
[APPROVAL GATE: User reviews and approves]
  ↓
[SIGNOFF GATE: required reviewer evidence verified]
  ↓
[CANDIDATE EVIDENCE GATE: pre-closeout evidence + tracker validation]
  ↓
Architect (Knowledge-Graph Reconciliation)
  ↓ [ARCHITECT KG GATE: bind the as-built source into the graph for future runs]
[PRODUCT MANAGER CLOSEOUT: status, archive, supersession, tracker sync, story index]
  ↓
Feature Complete
```

**Flow Type:** Mixed (architect-led orchestration kickoff, parallel implementation including deployability checks, parallel code+security reviews, single approval gate, required signoff verification, pre-closeout candidate evidence validation, a post-build architect knowledge-graph reconciliation, and PM closeout including tracker sync; AI Engineer runs when feature includes AI scope)

---

## Contract (generated — the spec is the source of truth)

The fixed procedure for this action — gates, artifacts, ordering, typed commands,
ownership, forbidden actions, stop conditions, and conflict resolution — is declared
once in [`agents/actions/spec/feature.yaml`](spec/feature.yaml) and compiled into the
operator/automation prompt pair at
`agents/templates/prompts/evidence-contract/feature-operator-friendly.md` and
`feature-automation-safe.md`. Regenerate with `python3 agents/scripts/render-prompts.py`;
the `prompt_drift` lifecycle gate fails if the committed prompts drift from the spec.
**Edit the spec, not this doc or the generated prompts.**

Run the mechanics through the scripts (do not hand-transcribe them here):

- Session setup + evidence skeleton — `python3 agents/scripts/init-run.py --action feature --feature {FEATURE_ID} --product-root {PRODUCT_ROOT}`
- Gate execution (ordered ops, durable checkpoints, telemetry) — `python3 agents/scripts/run-gate.py --action feature --stage <G0..G8> ...` (`--list` prints the ordered runbook)
- Severity arithmetic at the approval gate — `python3 agents/scripts/gate_policy.py --profile standard ...`

Evidence lives under `{PRODUCT_ROOT}/planning-mds/operations/evidence/` per the Feature
Evidence Contract in `CONSUMER-CONTRACT.md`; per-gate acceptance is
`validate-feature-evidence.py --stage <Gn>` (invoked by `run-gate.py`).

### Gate flow

G0 Architect assembly plan → G1 Runtime preflight → G2 Self-review + QE + deployability
→ G3 Code + security review → G4 Approval → G5 Signoff → G6 Candidate validation
→ G7 Architect KG reconciliation → G8 PM closeout.

Ownership in brief (the full map is in the spec's `ownership:`): the **product-manager**
owns closeout, trackers, and final status; the **architect** owns the assembly plan,
shared semantics, and G7 KG reconciliation; **implementation** agents (backend, frontend,
AI, QE, DevOps) own their runtime layer and role reports, and route shared-semantics
changes back to the architect. Per-step judgment follows below.

## Runtime Execution Boundary

- The builder runtime orchestrates feature flow and gates; keep it stack-agnostic.
- Stack-specific compile/test/lint/security execution must run in application runtime containers (or CI jobs built from those container definitions).
- Review and approval decisions must cite evidence produced by those application runtime executions.

## Runtime Preflight & Failure Triage (Mandatory)

Before any compile/test/lint/security scan command:

1. Verify required application runtime containers/jobs are running and healthy.
   - Example (containerized stacks): `docker compose ps` + health checks/log probe.
   - Non-containerized stacks: run the equivalent runtime readiness command(s).
2. Record preflight evidence path (command + timestamp + result) in the feature execution log.
3. If runtime is unavailable, restore runtime first, then re-run preflight before executing feature validation commands.

If a validation command fails with runtime symptoms (for example connection refused, DNS/network resolution errors, dependency service unavailable, missing container):

1. **Stop code edits immediately.**
2. Classify failure as `runtime-blocked` in feature execution notes.
3. Re-run runtime preflight and restore runtime health.
4. Re-run the same failed validation command **without code changes**.
5. Only treat it as a code defect if failure persists after runtime is healthy.

---

## Execution Steps

### Step 0: Architect-Led Feature Assembly Planning

**Execution Instructions:**

1. **Activate Architect agent** by reading `agents/architect/SKILL.md`
2. **Read context:**
   - Feature stories in `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/F{NNNN}-S{NNNN}-{slug}.md`
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` scope and constraints
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - `{PRODUCT_ROOT}/planning-mds/api/` contracts for this feature
3. **Produce feature assembly plan:**
   - Required backend/frontend/AI changes for this feature only
   - Integration checkpoints and dependency order
   - Test and release checklist for the vertical slice
   - **Knowledge-Graph Binding Plan** — the *intended* semantic-graph delta: which capabilities/canonical nodes this feature is expected to add or extend, and the anticipated binding glob(s) (`kg-source/bindings/**`). This is a prediction, not a contract; it is the baseline the `G7` reconciliation diffs the as-built source against. "No new nodes; reuses existing semantics" is a valid declaration.
4. **Output artifacts:**
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/feature-assembly-plan.md` (canonical per-feature execution plan; use `agents/templates/feature-assembly-plan-template.md`)
   - Update `{PRODUCT_ROOT}/planning-mds/architecture/feature-assembly-plan.md` to reference the feature-local plan from the umbrella cross-feature sequencing view
5. **Initialize signoff requirements in feature status:**
   - Update `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` section `Required Signoff Roles`
   - Mark baseline required roles as `Yes`: `Quality Engineer`, `Code Reviewer`
   - Add risk-based required roles (`Security Reviewer`, `DevOps`, `Architect`) when scope warrants

**Completion Criteria for Step 0:**
- [ ] Feature assembly plan exists
- [ ] Feature scope and handoffs are explicit
- [ ] Integration/test checkpoints defined
- [ ] Required signoff role matrix initialized in feature `STATUS.md`

---

### Step 0.5: Assembly Plan Validation

**Execution Instructions:**

Validate the feature assembly plan before parallel implementation:

- [ ] Scope split matches feature story requirements
- [ ] Dependencies between agents are identified
- [ ] Integration checkpoints are feasible
- [ ] No missing or conflicting artifact ownership

Validator:
- Code Reviewer or a second Architect review (lightweight checklist is sufficient)

---

### Step 1: Parallel Feature Implementation

**Execution Instructions:**

Execute these agents **in parallel** for the specific feature. Run AI Engineer when the feature touches `{PRODUCT_ROOT}/neuron/`, LLM workflows, prompts, or MCP.
All stack-specific execution (compile/tests/scans) must run in application runtime containers produced for this project.

Mandatory preflight before implementation validation runs:
- [ ] Runtime preflight executed and recorded per `Runtime Preflight & Failure Triage (Mandatory)`

**AI Scope Checklist — include AI Engineer if ANY apply:**
- [ ] Story mentions LLM, AI, or machine learning behavior
- [ ] Story requires MCP server/tool/resource work
- [ ] Story involves prompts, agent behavior, or tool orchestration
- [ ] Story changes files under `{PRODUCT_ROOT}/neuron/`
- [ ] Story requires model selection, cost controls, or guardrails

#### 1a. Backend Developer (Feature Scope)
1. **Activate Backend Developer agent** by reading `agents/backend-developer/SKILL.md`
2. **Read context:**
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 4 (architecture for this feature)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - User stories for THIS FEATURE ONLY
3. **Execute responsibilities (feature-scoped):**
   - Implement domain entities for this feature
   - Create or update EF Core entities
   - Generate migration (if schema changes needed)
   - Implement API endpoints for this feature
   - Write application services for feature business logic
   - Create unit tests for feature domain logic
   - Write integration tests for feature API endpoints
4. **Follow SOLUTION-PATTERNS.md:**
   - Casbin ABAC for authorization
   - ActivityTimelineEvent for mutations
   - ProblemDetails for errors
   - Clean architecture layers
   - Audit fields, soft delete
5. **Outputs (feature-specific):**
   - Domain entities (created or updated)
   - EF Core migration (if needed)
   - API endpoints (controllers)
   - Application services
   - Unit tests
   - Integration tests
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` updates (Backend Progress section, validation evidence)
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/GETTING-STARTED.md` updates (key files, seed data, verification steps)

#### 1b. Frontend Developer (Feature Scope)
1. **Activate Frontend Developer agent** by reading `agents/frontend-developer/SKILL.md`
2. **Read context:**
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 3 (screens for this feature)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - API contracts for THIS FEATURE ONLY
   - `agents/frontend-developer/references/ux-audit-ruleset.md`
3. **Execute responsibilities (feature-scoped):**
   - Create React components for feature screens
   - Implement forms for this feature (React Hook Form + AJV with JSON Schema)
   - Set up TanStack Query hooks for feature API calls
   - Add routing for feature screens
   - Style with Tailwind + shadcn/ui
   - Write component tests
   - Apply and pass UX rule-set checks for this feature's UI changes
4. **Follow SOLUTION-PATTERNS.md:**
   - React Hook Form for forms
   - AJV + JSON Schema for validation
   - TanStack Query for API
   - Tailwind + shadcn/ui for styling
   - UX rule-set compliance (`agents/frontend-developer/references/ux-audit-ruleset.md`)
5. **Outputs (feature-specific):**
   - React components (feature screens)
   - Form implementations
   - TanStack Query hooks
   - Routing updates
   - Component tests
   - UX audit evidence for this feature (command output + dark/light verification notes)
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` updates (Frontend Progress section, validation evidence)
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/GETTING-STARTED.md` updates (key files, verification steps)

#### 1c. AI Engineer (Feature Scope, if AI scope)
1. **Activate AI Engineer agent** by reading `agents/ai-engineer/SKILL.md`
2. **Read context:**
   - AI-related user stories for THIS FEATURE
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - Existing `{PRODUCT_ROOT}/neuron/` code and interfaces
3. **Execute responsibilities (feature-scoped):**
   - Implement AI workflow/prompt/tool logic for this feature
   - Add/modify MCP resources/tools if the feature requires them
   - Add runtime guardrails (validation, retries, error handling)
   - Add tests for AI behavior and integrations
4. **Follow SOLUTION-PATTERNS.md:**
   - No hardcoded secrets
   - Explicit integration contracts with backend/frontend
   - Observable AI behavior (logs/metrics)
5. **Outputs (feature-specific):**
   - `{PRODUCT_ROOT}/neuron/` feature implementation
   - AI tests
   - Prompt/config updates
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` updates (AI Progress section, validation evidence)
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/GETTING-STARTED.md` updates (AI runtime / setup notes)

#### 1d. Quality Engineer (Feature Scope)
1. **Activate Quality Engineer agent** by reading `agents/quality-engineer/SKILL.md`
2. **Read context:**
   - User stories for THIS FEATURE with acceptance criteria
   - Workflows for THIS FEATURE
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
3. **Execute responsibilities (feature-scoped):**
   - Create test plan for this feature
   - Write E2E test for feature happy path
   - Write E2E test for feature error scenarios
   - Validate feature acceptance criteria coverage
   - Generate coverage report for feature code
   - When host browser dependencies block Playwright (for example `libnspr4`/`libnss3` missing), run Playwright in the project runtime container (for example official Playwright Docker image matching repo `@playwright/test` version), then record the container command and result in feature execution evidence
   - **When `security_sensitive_scope = true`:** you are Responsible for *running* the four security scan classes (`dependency`, `secrets`, `sast`, `dast`) via `agents/security/scripts/*.sh` in application runtime containers, writing raw output under `{RUN_ID}/artifacts/security/`, and recording each in the manifest `security_scans{}` block (`ran`/`result`/`artifact`, or `ran: false` + waiver with `reason`/`owner`/`approved_on` for an unavailable scanner). Security owns the verdict — do not skip a class silently (the validator's `security_scan_*` rules fail it).
4. **Follow SOLUTION-PATTERNS.md:**
   - Developers own unit/component and endpoint integration tests
   - QE validates coverage and closes critical cross-tier gaps
   - E2E tests for feature workflows
5. **Outputs (feature-specific):**
   - Test plan for feature
   - E2E tests (happy path + errors)
   - Feature test coverage report
   - When `security_sensitive_scope = true`: `artifacts/security/` raw scan outputs + populated `security_scans{}` manifest block (handed to Security for the verdict)
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` updates (QE feature-level signoff entry, validation evidence paths)

#### 1e. DevOps (Feature Deployability Check)
1. **Activate DevOps agent** by reading `agents/devops/SKILL.md`
2. **Read context:**
   - Feature assembly plan (`{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/feature-assembly-plan.md`)
   - Umbrella sequencing/reference plan (`{PRODUCT_ROOT}/planning-mds/architecture/feature-assembly-plan.md`) when cross-feature dependency context is needed
   - Existing deployment artifacts (`docker-compose*.yml`, Dockerfiles, runtime configs)
   - Feature-specific runtime requirements from backend/frontend/AI outputs
3. **Execute responsibilities (feature-scoped):**
   - Verify feature can run in application runtime containers without breaking existing services
   - Update runtime/deployment configuration when feature introduces new dependencies
   - Validate environment-variable contract updates for this feature
   - Run feature-level container build/start smoke checks and capture evidence paths
4. **Outputs (feature-specific):**
   - Deployment/runtime config updates (if required)
   - Feature deployability check summary with executed command evidence
   - Updated env var documentation for new feature requirements
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` updates (deployability evidence, Cross-Cutting checklist items)

**Completion Criteria for Step 1:**
- [ ] All required agents completed feature implementation (Backend, Frontend, Quality, DevOps, and AI Engineer if AI scope)
- [ ] Feature code compiles/builds successfully in application runtime containers
- [ ] Runtime preflight evidence recorded before validation command execution
- [ ] No critical errors

---

### Step 2: SELF-REVIEW GATE (Agent Validation)

**Execution Instructions:**

Each agent validates their feature work:

Before self-review checks:
- [ ] Re-run runtime preflight and confirm validation environment is healthy
- [ ] If runtime failures are detected, mark `runtime-blocked`, fix runtime, and re-run unchanged validation commands before editing code

1. **Backend Developer self-review:**
   - [ ] Feature API endpoints implemented per contracts
   - [ ] Feature domain logic complete and tested
   - [ ] Unit tests passing for feature logic
   - [ ] Integration tests passing for feature endpoints
   - [ ] SOLUTION-PATTERNS.md followed
   - [ ] Feature acceptance criteria met
   - [ ] Migration applies successfully (if created)

2. **Frontend Developer self-review:**
   - [ ] Feature screens implemented per specs
   - [ ] Feature forms work with validation
   - [ ] API integration works for feature
   - [ ] Component tests passing
   - [ ] SOLUTION-PATTERNS.md followed
   - [ ] UX rule-set checks passed for this feature (`agents/frontend-developer/references/ux-audit-ruleset.md`)
   - [ ] `pnpm --dir {PRODUCT_ROOT}/experience lint`, `lint:theme`, `build`, and `test` passed
   - [ ] `pnpm --dir {PRODUCT_ROOT}/experience test:visual:theme` passed when style/theme changed
   - [ ] Feature acceptance criteria met

3. **AI Engineer self-review (if AI scope):**
   - [ ] AI feature behavior meets acceptance criteria
   - [ ] AI tests passing in AI runtime container
   - [ ] MCP/tool interfaces validated (if used)
   - [ ] Safety/cost/observability controls in place

4. **Quality Engineer self-review:**
   - [ ] Feature test plan complete
   - [ ] E2E tests passing for feature in application runtime containers
   - [ ] Coverage adequate for feature code
   - [ ] All feature acceptance criteria testable

5. **DevOps self-review:**
   - [ ] Feature deployability checks executed in application runtime containers
   - [ ] Runtime config/env-var changes documented and versioned
   - [ ] No runtime orchestration regressions introduced by the feature

**If any self-review fails:**
- Agent fixes issues
- Re-runs self-review
- Repeats until passing

**Gate Criteria:**
- [ ] Architect confirms feature output matches Step 0 plan
- [ ] All required agents pass self-review for feature
- [ ] All feature tests passing in application runtime containers
- [ ] Runtime preflight evidence attached for failed and passing validation runs
- [ ] Feature deployability evidence recorded by DevOps
- [ ] Feature works end-to-end

---

### Step 3: Execute Reviews (Parallel)

**Execution Instructions:**

Run these review agents in parallel:

#### 3a. Code Reviewer

1. **Activate Code Reviewer agent** by reading `agents/code-reviewer/SKILL.md`

2. **Read context:**
   - Feature code produced in Step 1
   - Application runtime validation outputs (test, lint, SAST, dependency scan reports)
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` (feature requirements)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - Feature user stories with acceptance criteria

3. **Execute code review (feature-focused):**
   - Review feature code structure
   - Check SOLID principles in feature code
   - Validate clean architecture boundaries
   - Review feature test coverage and quality
   - Identify code smells in feature
   - Validate feature acceptance criteria met
   - Check SOLUTION-PATTERNS.md compliance
   - Assess vertical slice completeness

4. **Produce feature code review report:**
   ```markdown
   # Feature Code Review Report

   Feature: [Feature Name]

   ## Summary
   - Assessment: [APPROVED / APPROVED WITH RECOMMENDATIONS / REJECTED]
   - Files reviewed: [count]
   - Issues found: [count by severity]

   ## Vertical Slice Completeness
   - [ ] Backend complete (API endpoints functional)
   - [ ] Frontend complete (screens functional)
   - [ ] AI layer complete (if AI scope)
   - [ ] Tests complete (unit, integration, E2E)
   - [ ] Can be deployed independently

   ## Findings
   - Critical: [list]
   - High: [list]
   - Medium: [list]
   - Low: [list]

   ## Pattern Compliance
   - [ ] Clean architecture respected
   - [ ] SOLID principles followed
   - [ ] SOLUTION-PATTERNS.md applied
   - [ ] Test coverage ≥80% for feature logic

   ## Acceptance Criteria
   - [ ] All feature ACs met
   - [ ] Edge cases handled
   - [ ] Error scenarios covered

   ## Recommendation
   [APPROVE / REQUEST CHANGES / REJECT]
   ```

**Code Review Outputs:**
- Feature code review report
- Approval or rejection

#### 3b. Security

1. **Activate Security agent** by reading `agents/security/SKILL.md`

2. **Read context:**
   - Feature code produced in Step 1
   - Application runtime validation outputs (test, lint, SAST, dependency scan reports)
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` (feature requirements)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - Feature user stories with acceptance criteria
   - Existing `{PRODUCT_ROOT}/planning-mds/security/` artifacts (if present)
   - QE's `security_scans{}` manifest block and raw outputs under `{RUN_ID}/artifacts/security/`

3. **Execute security review (feature-focused):**
   - Check OWASP Top 10 risks relevant to this feature
   - Verify authorization coverage for feature endpoints/actions
   - Validate input/output validation and error leakage controls
   - Check secrets/config handling (no hardcoded secrets)
   - Validate audit logging coverage for mutations
   - **You are Accountable for the scan verdict:** confirm `security_scans{}` covers all four classes (`dependency`, `secrets`, `sast`, `dast`), each either run with a resolvable artifact or carrying a complete waiver. A missing or unbacked class is a finding — do not `PASS` over it. Read the `artifacts/security/` outputs and apply exploitability/severity judgment the tools cannot; re-run any scanner yourself for deeper analysis when warranted.

4. **Produce feature security review report:**
   ```markdown
   # Feature Security Review Report

   Feature: [Feature Name]

   ## Summary
   - Assessment: [PASS / PASS WITH RECOMMENDATIONS / FAIL]
   - Findings: [count by severity]

   ## Findings
   - Critical: [list]
   - High: [list]
   - Medium: [list]
   - Low: [list]

   ## Control Checks
   - [ ] Authorization coverage complete
   - [ ] Input validation enforced
   - [ ] No secrets in code
   - [ ] Auditability requirements met

   ## Recommendation
   [APPROVE / FIX CRITICAL / FIX HIGH / REJECT]
   ```

**Security Review Outputs:**
- Feature security review report
- Vulnerability findings and remediation guidance

---

### Step 4: APPROVAL GATE (Feature Review)

**Execution Instructions:**

1. **Present combined review results to user:**
   ```
   ═══════════════════════════════════════════════════════════
   Feature Reviews Complete
   ═══════════════════════════════════════════════════════════

   Feature: [Feature Name]
   Code Reviewer Status: [APPROVED / APPROVED WITH RECOMMENDATIONS / REJECTED]
   Security Status: [PASS / PASS WITH RECOMMENDATIONS / FAIL]

   ✓ Vertical Slice Completeness
     - Backend: [Complete/Incomplete]
     - Frontend: [Complete/Incomplete]
     - AI: [N/A/Complete/Incomplete]
     - Tests: [Complete/Incomplete]
     - Deployable: [Yes/No]

   Issues Found:
     - Critical: [count]
     - High: [count]
     - Medium: [count]
     - Low: [count]

   Security Findings:
     - Critical: [count]
     - High: [count]
     - Medium: [count]
     - Low: [count]

   ✓ Pattern Compliance
     - Clean Architecture: [Yes/No]
     - SOLID Principles: [Yes/No]
     - SOLUTION-PATTERNS.md: [Yes/No]
     - Test Coverage: [percentage]% (feature code)

   ✓ Acceptance Criteria
     - [count]/[total] feature ACs met
     - Edge cases: [Handled/Needs work]
     - Errors: [Covered/Needs work]

   ═══════════════════════════════════════════════════════════
   Review Details:
   [Link to feature code review report]
   [Link to feature security review report]
   ═══════════════════════════════════════════════════════════
   ```

2. **Present approval checklist:**
   ```
   Feature Approval Checklist:
   - [ ] Feature is a complete vertical slice
   - [ ] Backend implementation complete
   - [ ] Frontend implementation complete
   - [ ] AI implementation complete (if AI scope)
   - [ ] Tests cover feature completely with evidence from application runtime containers
   - [ ] No critical issues (approval blocked if any remain)
   - [ ] High-severity issues fixed OR approved with mitigation justification
   - [ ] SOLUTION-PATTERNS.md followed
   - [ ] All feature acceptance criteria met
   - [ ] Feature can be deployed independently
   ```

3. **Enforce approval gate based on combined findings severity:**
   ```
   total_critical = code_critical + security_critical
   total_high = code_high + security_high

   IF total_critical > 0:
     STATUS: ❌ BLOCKED
     OPTIONS: ["fix critical", "reject"]
     APPROVE_ENABLED: false

   ELSE IF total_high > 0:
     STATUS: ⚠️ WARNING
     OPTIONS: ["fix issues", "approve with justification", "reject"]
     APPROVE_ENABLED: true (requires justification)

   ELSE:
     STATUS: ✓ ACCEPTABLE
     OPTIONS: ["approve", "fix issues", "reject"]
     APPROVE_ENABLED: true
   ```

4. **Handle user response:**
   - **If "fix critical":**
     - Identify critical issues to fix
     - Agents fix issues
     - Return to Step 3 (re-run code and security reviews)

   - **If "fix issues":**
     - Identify selected issues to fix
     - Agents fix issues
     - Return to Step 3 (re-run code and security reviews)

   - **If "approve with justification":**
     - Capture explicit mitigation justification for remaining high issues
     - Log decision with mitigation plan
     - Proceed to Step 5 (Signoff Gate)

   - **If "approve":**
     - Proceed to Step 5 (Signoff Gate)

   - **If "reject":**
     - Capture feedback
     - Return to Step 0 (re-plan and re-implement feature)

   - **If user input is not in current state's allowed options:**
     - Do not transition
     - Re-present current state and allowed options

5. After an approving decision is recorded in `gate-decisions.md`, run scoped G4 validation before signoff:
   - `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G4`

**Gate Criteria:**
- [ ] Code + security critical issues = 0 before approval is enabled
- [ ] High issues fixed or approved with explicit mitigation justification
- [ ] Feature is complete vertical slice
- [ ] User decision recorded with rationale when required
- [ ] `validate-feature-evidence.py --stage G4` exits 0 before signoff

---

### Step 5: SIGNOFF GATE (Mandatory)

**Execution Instructions:**

Before setting feature status to `Done` or moving to archive, verify role signoffs:

1. Read `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md`:
   - `Required Signoff Roles` matrix (planning baseline)
   - `Story Signoff Provenance` (execution evidence)
2. For every role marked `Required = Yes`, confirm ledger has:
   - a row per story in scope
   - `PASS` (or `APPROVED`) verdict
   - reviewer identity
   - review date
   - concrete evidence path(s) to solution artifacts under `{PRODUCT_ROOT}/planning-mds/operations/evidence/**`
3. If any required role is missing or non-pass:
   - Block feature closeout
   - Route back to the owning reviewer role
4. Only after all required signoffs pass:
   - Proceed to candidate evidence validation (Step 6 / gate `G6`)

**Gate Criteria:**
- [ ] Every required signoff role has a passing ledger entry
- [ ] Every required signoff includes reviewer/date/evidence
- [ ] No `Done`/`Archived` transition occurs without passing required signoffs

---

### Step 6: CANDIDATE EVIDENCE VALIDATION (Mandatory)

**Gate `G6`.** Runs after signoff (`G5`), before the architect KG reconciliation (`G7`) and PM closeout (`G8`). This is the pre-closeout candidate checkpoint: confirm the run's evidence is complete and internally consistent **before** any closeout mutation (archive move, supersession, `latest-run.json`). No PM closeout actions occur here.

**Execution Instructions:**

1. Confirm all `G0`–`G5` evidence artifacts exist and their verdicts are passing.
2. Write `feature-action-execution.md` with a gate-by-gate timeline of the run.
3. Confirm the manifest is a pre-closeout candidate: `status: in-progress`, `gate_results` through `signoff` present, and `pm_closeout` / `tracker_sync` absent or `required: false` (no `latest-run.json` yet).
4. Run candidate stage validation:
   - `python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID} --stage G6`
5. Run tracker validation (it internally calls feature-evidence at `--stage G6`) and append the result to `lifecycle-gates.log`:
   - `python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}`

**Gate Criteria:**
- [ ] All `G0`–`G5` evidence present with passing verdicts
- [ ] `feature-action-execution.md` complete with a gate-by-gate timeline
- [ ] Manifest is a valid pre-closeout candidate (no closeout artifacts yet)
- [ ] `validate-feature-evidence.py --stage G6` exits 0
- [ ] Scoped `validate-trackers.py --feature {FEATURE_ID} --run-id {RUN_ID}` passes and its result is recorded in `lifecycle-gates.log`

---

### Step 7: ARCHITECT KNOWLEDGE-GRAPH RECONCILIATION (Mandatory)

**Gate `G7`.** Runs after signoff (`G5`) and candidate validation (`G6`), before PM closeout (`G8`). The graph is now reconciled against the **as-built** source — what actually shipped, not what G0 predicted — so the knowledge-graph the *next* feature's architect reads at G0 is correct. This gate owns the **semantic** graph only; it binds **code** paths (`experience/...`, `api/...`, etc.) that do **not** move during the closeout archive step, so it is safe to run before the move.

**Execution Instructions:**

1. **Activate Architect agent** by reading `agents/architect/SKILL.md`.
2. Diff the as-built source against the graph's G0 declaration (the `feature-assembly-plan.md` "Knowledge-Graph Binding Plan", if present) to find the binding delta — capabilities, modules, or shared semantics that emerged during implementation.
3. For every new source surface that represents a capability or shared semantic, add or update its **binding shard** in `{PRODUCT_ROOT}/planning-mds/kg-source/bindings/**`. Bind by **directory glob** where a cohesive folder represents one capability (e.g. `experience/src/features/forms/**`), not file-by-file. Existing globs that already cover new files need no change — confirm coverage rather than duplicating.
4. If the feature introduced new canonical nodes or rationale (`WHY`) entries, add **node shards** to `{PRODUCT_ROOT}/planning-mds/kg-source/nodes/**` (logical `F####/` doc refs only). If it introduced none, state that explicitly. Then run `compile.py` — it regenerates `code-index.yaml`/`canonical-nodes.yaml` (never hand-edit them).
5. Regenerate and validate all code-path-derived generated layers: `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions`. This refreshes `symbol-index.yaml`, `unbound-but-referenced.yaml`, and `decisions-index.yaml`; it is mandatory even when the authored KG files appear unchanged. (Editing a bound method body without first consulting `lookup.py --symbol` / `hint.py --symbol` is forbidden — the symbol layer keeps edits narrow.)
6. Run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` and resolve any errors. Do **not** run `--write-coverage-report` here — coverage binds feature-doc paths that the PM closeout archive move will relocate; regenerating it now re-stales it on the move. Coverage regeneration is a `G8` step, after the move.
7. Record the outcome in `kg-reconciliation.md` (template: `agents/templates/kg-reconciliation-template.md`): the binding delta applied, new/affirmed canonical nodes, and the green generated-layer + drift validator results.

**Completion Criteria:**
- [ ] Architect agent activated for the reconciliation
- [ ] `code-index.yaml` bindings exist for every new capability/shared-semantic source surface (glob-based; existing coverage confirmed, not duplicated)
- [ ] New canonical nodes/rationale recorded in `canonical-nodes.yaml`, or "none introduced" stated explicitly
- [ ] `validate.py --regenerate-symbols --check-symbols --regenerate-decisions --check-decisions` exits 0
- [ ] `validate.py --check-drift` exits 0
- [ ] `coverage-report.yaml` was **not** regenerated at this gate (deferred to `G8`, post-archive-move)
- [ ] `kg-reconciliation.md` written

---

### Step 8: PRODUCT MANAGER CLOSEOUT (Mandatory)

**Execution Instructions:**

1. **Activate Product Manager agent** by reading `agents/product-manager/SKILL.md`
2. Reconcile feature closure artifacts:
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` (final status, deferred follow-ups, mitigation notes)
   - `STATUS.md` required signoff matrix + story signoff provenance entries
   - `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md` (status/path transitions, including archive moves)
   - `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md` (Now/Next/Later/Completed placement)
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` (feature/story status labels and links, if changed)
3. For completed features (`Overall Status: Done`), move the feature folder to archive when appropriate:
   - From `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/`
   - To `{PRODUCT_ROOT}/planning-mds/features/archive/F{NNNN}-{slug}/`
   - Then update impacted feature-local links and registry paths
4. If ontology-backed planning exists for the feature, update feature/path/status references in:
   - `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`
5. Record any orphaned stories, deferred follow-ups, or explicit mitigation carry-overs before final validation
6. **Knowledge-graph: verify, then regenerate the path-sensitive layer (do not author bindings here):**
   - The **semantic** graph shards (`kg-source/bindings/**`, `kg-source/nodes/**`, compiled to `code-index.yaml`/`canonical-nodes.yaml`) were authored by the Architect at `G7` and `kg-reconciliation.md` records it. Closeout **verifies** the compiled graph is green — it does not author shards. If a binding gap is discovered now (a capability surface the `G7` pass missed), route back to the Architect for a `G7` delta pass (author shards + recompile) rather than editing the graph in closeout.
   - After the archive folder move (step 3) and the feature-shard `path:`/`status:` edit + `compile.py` (step 4), regenerate the **path-sensitive** coverage layer: `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report`. (Because logical `F####/` refs resolve through the shard `path:`, the archive move needs no doc-ref repoint anywhere — the F0005 payoff.)
   - Run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` to confirm the post-move graph is green.
7. **Publish the approved run** in the supersession-and-publish order (see "Closeout Supersession-And-Publish Sequence"): run `patch-prior-manifest.py` to mark prior approved manifests `superseded`, then write `latest-run.json` pointing at this run, then finalize the manifest to `status: approved`.
8. **Tracker sync:** regenerate the story rollup when story files moved/changed (`python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/`), then run final closeout validation (`python3 agents/product-manager/scripts/validate-feature-evidence.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --stage closeout`) and scoped tracker validation (`python3 agents/product-manager/scripts/validate-trackers.py --product-root {PRODUCT_ROOT} --feature {FEATURE_ID} --run-id {RUN_ID}`). Treat any tracker drift as blocking and re-run after repair.

**Completion Criteria:**
- [ ] Product Manager closeout executed after signoff and `G7` architect KG reconciliation passed
- [ ] Final feature status and archive decision recorded
- [ ] Deferred follow-ups and mitigation notes captured
- [ ] `feature-mappings.yaml` status/path updated for the archive move (lifecycle-coupled, PM-owned)
- [ ] `kg-reconciliation.md` present and its semantic-graph checks green (verified, not re-authored, by closeout)
- [ ] `coverage-report.yaml` regenerated **after** the archive move
- [ ] `validate.py --check-drift` exits 0 on the post-move graph
- [ ] Prior approved manifests patched to `superseded` and `latest-run.json` written (supersession-and-publish order)
- [ ] REGISTRY/ROADMAP/BLUEPRINT synchronized; STORY-INDEX regenerated if story files changed
- [ ] Final `validate-feature-evidence.py --stage closeout` and scoped `validate-trackers.py --feature {FEATURE_ID} --run-id {RUN_ID}` pass (tracker results recorded in `lifecycle-gates.log`)

---

### Step 9: Feature Complete

**Execution Instructions:**

Present completion summary:

```
═══════════════════════════════════════════════════════════
Feature Complete! ✓
═══════════════════════════════════════════════════════════

Feature: [Feature Name]

Application Assembly:
  ✓ Architect
    - Feature assembly plan created
    - Dependencies and checkpoints validated

Implementation:
  ✓ Backend Developer
    - [count] entities created/updated
    - [count] API endpoints implemented
    - [count] unit tests passing
    - [count] integration tests passing

  ✓ Frontend Developer
    - [count] components created
    - [count] screens implemented
    - [count] forms with validation
    - Component tests passing

  ✓ Quality Engineer
    - Test plan complete
    - [count] E2E tests passing
    - [percentage]% coverage for feature code

  ✓ DevOps
    - Feature deployability checks passed
    - Runtime configuration updates verified
    - Evidence paths recorded

  ✓ AI Engineer (if AI scope)
    - [count] AI workflows/prompts delivered
    - [count] AI tests passing

Code Review:
  ✓ Code Reviewer: APPROVED
  ✓ Vertical slice complete
  ✓ Acceptance criteria met
  Status: APPROVED

Security Review:
  ✓ Security Agent: PASS
  ✓ No critical vulnerabilities (high findings fixed or justified)
  ✓ Authorization and validation checks complete
  Status: PASS

Closeout:
  ✓ Required signoff ledger complete
  ✓ Product Manager closeout recorded
  ✓ Trackers and story index synchronized

═══════════════════════════════════════════════════════════
Next Steps:
═══════════════════════════════════════════════════════════

Feature is ready to:
1. Merge to main branch
2. Deploy to staging
3. Get stakeholder feedback

To continue building:
- Run "feature" action for next feature
- Run "build" action for remaining features
- Run "document" action to update docs

Feature delivered! ✓
═══════════════════════════════════════════════════════════
```

---

## Validation Criteria

**Overall Feature Action Success:**
- [ ] Feature assembly plan created and followed
- [ ] Feature is complete vertical slice (backend + frontend + tests + DevOps deployability checks + AI when in scope)
- [ ] All feature tests passing in application runtime containers
- [ ] AI tests passing (if AI scope) in AI runtime container
- [ ] Code review approved
- [ ] Security review approved
- [ ] Signoff gate passed for all required reviewer roles
- [ ] All feature acceptance criteria met
- [ ] Feature can be deployed independently
- [ ] User decision recorded per gate rules
- [ ] Product Manager closeout completed
- [ ] Tracker sync gate passed (REGISTRY/ROADMAP/STORY-INDEX/BLUEPRINT/STATUS)

---

## Prerequisites

Before running feature action:
- [ ] Plan action completed for this feature (stories + architecture signed off; the `feature-assembly-plan.md` is NOT a prerequisite — this action authors it at G0 Step 0)
- [ ] Feature has clear user stories with acceptance criteria
- [ ] Feature scope is small (2-5 days of work)
- [ ] SOLUTION-PATTERNS.md exists
- [ ] Tracker governance contract available (`{PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md`, seeded from `agents/templates/tracker-governance-template.md` when missing)
- [ ] AI scope is explicit (if feature includes AI behavior)
- [ ] User is available for approval

---

## Vertical Slicing Best Practices

### What Makes a Good Vertical Slice?

1. **Complete:** Includes backend, frontend, tests, deployability checks, and AI layer changes when AI scope exists
2. **Deployable:** Can be released independently
3. **Testable:** Has clear acceptance criteria
4. **Small:** Can be completed in 2-5 days
5. **Valuable:** Delivers user value on its own

### Good Feature Examples
- ✅ "View customer list with pagination"
- ✅ "Create new order with required fields"
- ✅ "Search accounts by name"
- ✅ "View activity timeline for an account"

### Bad Feature Examples (Too Large - Break Down!)
- ❌ "Build entire customer management module"
- ❌ "Implement full order processing workflow"
- ❌ "Complete onboarding process"

### Not Vertical Slices
- ❌ "Create all database tables" (not vertical)
- ❌ "Build all backend APIs" (not vertical)
- ❌ "Create all forms" (not vertical)

---

## Example Usage

### Scenario 1: Customer List Feature
```
User: "Run the feature action for customer list with pagination"

Agent Runtime: [Reads feature.md]
Agent Runtime: "I'll implement the customer list feature as a vertical slice..."

[Step 0: Feature assembly planning]
  Architect:
    - Feature scope and dependencies mapped
    - Ownership assigned for backend/frontend/AI/test tasks

[Step 1: Parallel implementation]
  Backend Developer:
    - GET /api/customers endpoint with pagination
    - CustomerService.ListAsync method
    - Unit tests for service
    - Integration tests for endpoint

  Frontend Developer:
    - CustomerList component
    - TanStack Query hook for fetching customers
    - Pagination controls
    - Component tests

  Quality Engineer:
    - E2E test: View customer list
    - E2E test: Navigate pages
    - Test plan for customer list

  DevOps:
    - Container smoke test for feature runtime
    - Validate env var and compose changes
    - Record deployability evidence

[Step 2: Self-review - all pass]

[Step 3: Parallel reviews]
Agent Runtime: "Code and security reviews complete. Results:
  - Vertical slice: Complete
  - Issues: 2 medium (naming conventions)
  - Security findings: 0 critical, 0 high, 1 low
  - Test coverage: 85%
  - Acceptance criteria: All met
  - Recommendation: APPROVED WITH RECOMMENDATIONS"

[Step 4: Approval gate]
Agent Runtime: "Feature review complete. Do you approve? (approve/fix issues/reject)"

User: "approve"

Agent Runtime: "Required signoffs are complete, PM closeout and tracker sync passed. Customer list with pagination is ready to merge."
```

### Scenario 2: Iteration After Rejection
```
User: "Run the feature action for customer search"

[Steps 0.5-3 execute]

[Step 4: Approval gate]
Agent Runtime: "Feature review results:
  - Issues: 1 critical (missing authorization check)
  - Recommendation: FIX CRITICAL"

User: "fix critical"

Agent Runtime: "Fixing authorization check..."
[Backend Developer adds authorization]

[Step 3: Re-review]
Agent Runtime: "Code and security reviews updated. Results:
  - Authorization: Fixed
  - Security status: PASS
  - Recommendation: APPROVED"

[Step 4: Re-approval]
Agent Runtime: "Do you approve now?"

User: "approve"

Agent Runtime: "Required signoffs are complete, PM closeout and tracker sync passed. Feature ready."
```

---

## Related Actions

- **Before:** [plan action](./plan.md) - Plan the feature
- **Alternative:** [build action](./build.md) - Build multiple features together
- **After:** [document action](./document.md) - Document the feature
- **After:** [blog action](./blog.md) - Blog about the feature

---

## Notes

- Feature action is the **recommended way** to build incrementally
- Each feature should be merged to main after approval
- Features can build on each other (dependencies allowed)
- Prefer small, frequent features over large batches
- Feature action ensures true vertical slicing discipline
- Security review is part of the feature action (run `review` action separately for deeper audit scope when needed)
- DevOps deployability check is included; use `build` action for broader infra redesign across multiple features
- Critical findings block approval; high findings require explicit mitigation justification if approved
- Signoff must pass before PM closeout, and PM closeout must finish before final tracker sync

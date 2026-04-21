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
[PRODUCT MANAGER CLOSEOUT: status, archive, follow-up reconciliation]
  ↓
[TRACKER SYNC GATE: trackers and story index validated]
  ↓
Feature Complete
```

**Flow Type:** Mixed (architect-led orchestration kickoff, parallel implementation including deployability checks, parallel code+security reviews, single approval gate, required signoff verification, PM closeout, and final tracker sync; AI Engineer runs when feature includes AI scope)

---

## Retrieval Contract

Retuned by `python3 {PRODUCT_ROOT}/scripts/kg/eval.py`; do not hand-edit without running eval.

```yaml
tier_defaults:
  feature:
    clean:           { start_tier: 1, max_auto_tier: 2 }
    drift-reconcile: { start_tier: 3, max_auto_tier: 4 }
```

- `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py <feature-id>` is a first-pass scope resolver and retrieval aid, not an authoritative source of truth.
- Raw artifacts win on conflict: `feature-assembly-plan.md`, stories, ADRs, API contracts, schemas, and policy artifacts outrank KG output.
- Navigate instead of eager-loading: open linked raw artifacts only when the current gate, review, or drift repair needs them.

## Context Files

Load in this order when the work is feature-scoped:

1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/feature.md`
5. `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/feature-assembly-plan.md`
6. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml`
7. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml`
8. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`
9. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/code-index.yaml`
10. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/coverage-report.yaml`
11. `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/**`

## On-Demand Paths

- `{PRODUCT_ROOT}/planning-mds/api/<openapi-spec>.yaml`
- `{PRODUCT_ROOT}/planning-mds/security/authorization-matrix.md`
- `{PRODUCT_ROOT}/planning-mds/security/policies/policy.csv`
- `{PRODUCT_ROOT}/planning-mds/knowledge-graph/*.yaml` beyond what `lookup.py` already returned
- `agents/<role>/references/**` only after a matching `agents/ROUTER.md` row

## Primary Spec

- `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/feature-assembly-plan.md` is the canonical execution spec for feature implementation
- When the assembly plan conflicts with raw story text, follow the feature assembly plan and log the reconciliation

## Ownership Contract

- `product-manager` owns feature closeout, trackers, `STATUS.md` final state, archive moves, and `feature-mappings.yaml` path/status updates
- `architect` owns `feature-assembly-plan.md`, ADRs, canonical shared semantics, API contracts, schemas, and authorization artifacts
- Implementation roles edit their runtime layers and shared feature evidence surfaces only
- Shared-semantics changes route back to `architect`; other roles flag drift instead of redefining it

## Forbidden

- Hand-enumerating schemas, ADRs, or contract files when `lookup.py` output is available
- Treating lookup/KG mappings as authoritative over raw artifacts
- Editing code without prior `hint.py <path>`
- Editing shared semantics without prior `blast.py <node-id>`
- Continuing after a runtime-blocked failure without re-running runtime preflight
- Skipping any gate from `G0` through `G4.7`
- Declaring done without the explicit Product Manager role switch at `G4.6`
- Widening scope outside the current feature
- Climbing past `max_auto_tier` without recording `workstate.py escalate`

## Gate Contract

- `G0 ARCHITECT ASSEMBLY PLAN VALIDATION` — Step 0 and Step 0.5
- `G1 RUNTIME PREFLIGHT` — Runtime Preflight & Failure Triage
- `G2 SELF-REVIEW` — Step 2 Agent Validation
- `G3 CODE + SECURITY REVIEW` — Step 3 Parallel Reviews
- `G4 APPROVAL` — Step 4 Feature Review
- `G4.5 SIGNOFF` — Step 4.5 Required reviewer evidence verification
- `G4.6 PM CLOSEOUT` — Step 4.6 Product Manager closeout and archive reconciliation
- `G4.7 TRACKER SYNC` — Step 4.7 Final tracker validation

## Stop Conditions

- Runtime preflight fails and cannot be restored
- A critical code or security finding remains after one review cycle
- Required signoff is missing reviewer, date, or evidence
- A non-architect attempts to edit architect-owned canonical semantics
- Scope drifts outside the declared feature boundary
- `validate.py` or `validate.py --check-drift` fails and cannot be repaired within scope
- `INSUFFICIENT_CONTEXT`: `lookup.py` returns empty scope for a declared in-scope node, or only ambiguous / low-confidence (`inferred`, `confidence < 0.5`) matches on a node about to be edited, or the workflow needs to climb past `max_auto_tier`; halt the current gate, invoke `workstate.py escalate <reason> --nodes ... --opened-raw ...`, open the raw artifacts, and do not proceed with weak matches

## Exit Validation

Run in this order:

1. Applicable backend / frontend / AI / QE runtime commands for changed surfaces, with evidence paths recorded under `{PRODUCT_ROOT}/planning-mds/operations/evidence/**`
2. `python3 agents/product-manager/scripts/validate-trackers.py`
3. `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/` when stories changed
4. `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` when KG changed
5. `python3 {PRODUCT_ROOT}/scripts/kg/validate.py`
6. `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift`
7. `python3 agents/scripts/validate_templates.py`

---

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
4. **Follow SOLUTION-PATTERNS.md:**
   - Developers own unit/component and endpoint integration tests
   - QE validates coverage and closes critical cross-tier gaps
   - E2E tests for feature workflows
5. **Outputs (feature-specific):**
   - Test plan for feature
   - E2E tests (happy path + errors)
   - Feature test coverage report
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

3. **Execute security review (feature-focused):**
   - Check OWASP Top 10 risks relevant to this feature
   - Verify authorization coverage for feature endpoints/actions
   - Validate input/output validation and error leakage controls
   - Check secrets/config handling (no hardcoded secrets)
   - Validate audit logging coverage for mutations
   - Run dependency/container vulnerability scans in application runtime containers (or CI jobs built from them)

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
     - Proceed to Step 4.5 (Signoff Gate)

   - **If "approve":**
     - Proceed to Step 4.5 (Signoff Gate)

   - **If "reject":**
     - Capture feedback
     - Return to Step 0 (re-plan and re-implement feature)

   - **If user input is not in current state's allowed options:**
     - Do not transition
     - Re-present current state and allowed options

**Gate Criteria:**
- [ ] Code + security critical issues = 0 before approval is enabled
- [ ] High issues fixed or approved with explicit mitigation justification
- [ ] Feature is complete vertical slice
- [ ] User decision recorded with rationale when required

---

### Step 4.5: SIGNOFF GATE (Mandatory)

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
   - Proceed to Product Manager closeout

**Gate Criteria:**
- [ ] Every required signoff role has a passing ledger entry
- [ ] Every required signoff includes reviewer/date/evidence
- [ ] No `Done`/`Archived` transition occurs without passing required signoffs

---

### Step 4.6: PRODUCT MANAGER CLOSEOUT (Mandatory)

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
6. **Knowledge-graph validation:**
   - Confirm implementation agents added `code-index.yaml` bindings for new source files created during the feature. If bindings are missing, add them now.
   - Run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` and resolve any errors before proceeding.
   - If the feature introduced new canonical nodes or rationale entries, confirm they are present in `canonical-nodes.yaml`.

**Completion Criteria:**
- [ ] Product Manager closeout executed after signoff passed
- [ ] Final feature status and archive decision recorded
- [ ] Deferred follow-ups and mitigation notes captured
- [ ] Ontology feature mapping updated if closeout changes feature path/status
- [ ] Code-index bindings exist for new source files introduced by this feature
- [ ] `validate.py --check-drift` exits 0

---

### Step 4.7: TRACKER SYNC GATE (Mandatory)

**Execution Instructions:**

Validate the closeout updates before declaring feature completion:

1. Regenerate story rollup when story files changed:
   - `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/`

2. Validate consistency:
   - `python3 agents/product-manager/scripts/validate-trackers.py`

3. If validation fails:
   - Treat as a blocking issue
   - Fix tracker drift and re-run validation before completion

**Gate Criteria:**
- [ ] Feature STATUS reflects final approved state
- [ ] Product Manager closeout executed before tracker validation
- [ ] Completed feature folders are moved to `{PRODUCT_ROOT}/planning-mds/features/archive/`
- [ ] REGISTRY/ROADMAP/BLUEPRINT are synchronized
- [ ] STORY-INDEX regenerated if story files changed
- [ ] Tracker validation passes

---

### Step 5: Feature Complete

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
- [ ] Plan action completed for this feature
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

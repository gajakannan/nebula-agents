# Action: Build

## User Intent

Implement planned features by generating production-quality code, tests, and deployment configurations with comprehensive review and approval gates.

## Agent Flow

```
Architect (Implementation Orchestration)
  ↓
(Backend Developer + Frontend Developer + AI Engineer [if AI scope] + Quality Engineer + DevOps)
  ↓ [Parallel Implementation]
[SELF-REVIEW GATE: Each agent validates their work]
  ↓
Code Reviewer
  ↓
[APPROVAL GATE: User reviews code quality]
  ↓
Security
  ↓
[APPROVAL GATE: User reviews security findings]
  ↓
[SIGNOFF GATE: required reviewer evidence verified]
  ↓
[PRODUCT MANAGER CLOSEOUT: delivered-feature reconciliation]
  ↓
[TRACKER SYNC GATE: trackers and story index validated]
  ↓
Build Complete
```

**Flow Type:** Mixed (architect-led orchestration kickoff, parallel implementation, sequential reviews with approval gates, required signoff verification, PM closeout, and final tracker sync)

---

## Runtime Execution Boundary

- The builder runtime orchestrates roles, gates, and artifact flow. Keep it stack-agnostic.
- Stack-specific compile/test/security execution must run in application runtime containers (or CI jobs built from those container definitions).
- Store executable evidence (test, lint, SAST, dependency scan outputs) under solution artifacts and use it in review gates.

---

## Execution Steps

### Step 0: Architect-Led Assembly Planning

**Execution Instructions:**

1. **Activate Architect agent** by reading `agents/architect/SKILL.md`
2. **Read context:**
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`
   - `{PRODUCT_ROOT}/planning-mds/features/` (feature folders with colocated stories)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - `{PRODUCT_ROOT}/planning-mds/api/`
3. **Produce assembly plan:**
   - Build order for vertical slices
   - Explicit backend/frontend/AI handoffs
   - Integration checkpoints for QA and DevOps
   - Clear definition of "done" for each slice
4. **Output artifact:**
   - `{PRODUCT_ROOT}/planning-mds/architecture/application-assembly-plan.md` (use `agents/templates/application-assembly-plan-template.md`)

**Completion Criteria for Step 0:**
- [ ] Application assembly plan exists
- [ ] Scope split across implementation agents is explicit
- [ ] Integration checkpoints defined

---

### Step 0.5: Assembly Plan Validation

**Execution Instructions:**

Validate the assembly plan before parallel implementation begins:

- [ ] Scope split matches story requirements
- [ ] Dependencies between agents are identified
- [ ] Integration checkpoints are feasible
- [ ] No missing or conflicting artifact ownership

Validator:
- Code Reviewer or a second Architect review (lightweight checklist is sufficient)

---

### Step 1: Parallel Implementation

**Execution Instructions:**

Execute these agents **in parallel** (all working simultaneously). Run AI Engineer when stories include AI/LLM/MCP scope.
All stack-specific execution (compile/tests/scans) must run in application runtime containers produced for this project.

**AI Scope Checklist — include AI Engineer if ANY apply:**
- [ ] Story mentions LLM, AI, or machine learning behavior
- [ ] Story requires MCP server/tool/resource work
- [ ] Story involves prompts, agent behavior, or tool orchestration
- [ ] Story changes files under `{PRODUCT_ROOT}/neuron/`
- [ ] Story requires model selection, cost controls, or guardrails

#### 1a. Backend Developer
1. **Activate Backend Developer agent** by reading `agents/backend-developer/SKILL.md`
2. **Read context:**
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 4 (architecture, data model, API contracts)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - `{PRODUCT_ROOT}/planning-mds/features/` (user stories to implement)
3. **Execute responsibilities:**
   - Implement domain entities matching data model
   - Create EF Core DbContext and entities
   - Generate and apply database migrations
   - Implement API endpoints per contracts
   - Write application services and business logic
   - Create repository implementations
   - Own and maintain backend unit tests (≥80% coverage for business logic)
   - Own and maintain backend integration tests for implemented API endpoints
4. **Follow SOLUTION-PATTERNS.md:**
   - Use Casbin ABAC for authorization
   - Create ActivityTimelineEvent for all mutations
   - Use ProblemDetails for errors
   - Follow clean architecture layers
   - Include audit fields on all entities
   - Implement soft delete
5. **Outputs:**
   - C# domain models and entities
   - EF Core migrations
   - ASP.NET Core controllers/endpoints
   - Application services
   - Repository implementations
   - Unit tests
   - Integration tests
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` updates (Backend Progress section, validation evidence)
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/GETTING-STARTED.md` updates (key files, seed data, verification steps)

#### 1b. Frontend Developer
1. **Activate Frontend Developer agent** by reading `agents/frontend-developer/SKILL.md`
2. **Read context:**
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 3 (screens, user stories)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - `{PRODUCT_ROOT}/planning-mds/api/` (OpenAPI contracts to implement against)
   - `agents/frontend-developer/references/ux-audit-ruleset.md`
3. **Execute responsibilities:**
   - Create React components for screens
   - Implement forms with React Hook Form + AJV (JSON Schema) validation
   - Set up TanStack Query for API calls
   - Implement routing and navigation
   - Style with Tailwind + shadcn/ui components
   - Write component tests
   - Apply and pass UX rule-set checks for changed UI flows
4. **Follow SOLUTION-PATTERNS.md:**
   - React Hook Form for all forms
   - AJV + JSON Schema for validation
   - TanStack Query for API calls
   - Tailwind + shadcn/ui for styling
   - UX rule-set compliance (`agents/frontend-developer/references/ux-audit-ruleset.md`)
5. **Outputs:**
   - React components (pages, layouts, features)
   - TypeScript types and interfaces
   - TanStack Query hooks
   - Form implementations
   - Routing configuration
   - Component tests
   - UX audit evidence (required command outputs + dark/light validation notes)
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` updates (Frontend Progress section, validation evidence)
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/GETTING-STARTED.md` updates (key files, verification steps)

#### 1c. Quality Engineer
1. **Activate Quality Engineer agent** by reading `agents/quality-engineer/SKILL.md`
2. **Read context:**
   - `{PRODUCT_ROOT}/planning-mds/features/` (acceptance criteria from colocated story files)
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 4.4 (workflows)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
3. **Execute responsibilities:**
   - Create test plan mapping stories to test cases
   - Validate developer-owned unit/integration test coverage and identify risk gaps
   - Add cross-tier integration tests when story-critical gaps remain
   - Write E2E tests for critical workflows
   - Generate coverage and quality-gate reports
   - Publish quality recommendation with blocking/non-blocking issues
4. **Follow SOLUTION-PATTERNS.md:**
   - Developers own unit/component and service-level integration tests
   - QE owns cross-tier integration, E2E, and regression validation
   - ≥80% unit coverage for business logic
   - E2E tests for critical workflows
5. **Outputs:**
   - Test plan document
   - Test coverage gap analysis and remediation checklist
   - Cross-tier integration and E2E test suites
   - Coverage and quality-gate reports
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` updates (QE feature-level signoff entry, validation evidence paths)

#### 1d. DevOps
1. **Activate DevOps agent** by reading `agents/devops/SKILL.md`

2. **Follow three-phase workflow:**

   **Phase 1: Code Inspection & Discovery**
   - Scan `{PRODUCT_ROOT}/engine/` to detect backend framework and dependencies
   - Scan `{PRODUCT_ROOT}/experience/` to detect frontend framework and build tool
   - Scan `{PRODUCT_ROOT}/neuron/` to detect AI layer (if exists)
   - Identify database connections and configuration
   - Map service dependencies
   - Extract environment variable requirements
   - Document infrastructure needs (database, caching, queues)
   - **Output:** Discovery summary with detected services and dependencies

   **Phase 2: Deployment Architecture Design**
   - Choose deployment pattern based on discovered services:
     * API-Only (backend + database)
     * 3-Tier (backend + frontend + database)
     * AI-Enabled 3-Tier (backend + frontend + AI + database)
   - Consult architecture references:
     * Read `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
     * Read `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 4 (NFRs)
     * Read `agents/devops/references/containerization-guide.md`
   - Define service specifications (runtime, ports, dependencies, env vars)
   - Document deployment targets (dev, staging, prod)
   - Create deployment architecture template:
     * File: `{PRODUCT_ROOT}/planning-mds/architecture/deployment-architecture.md`
     * Use: `agents/templates/deployment-architecture-template.md`
   - **Output:** `{PRODUCT_ROOT}/planning-mds/architecture/deployment-architecture.md`
   - **Optional Approval Gate:** User reviews deployment architecture before config generation

   **Phase 3: Configuration Generation**
   - Generate `docker-compose.yml` based on deployment architecture
   - Generate Dockerfiles for each detected service:
     * `{PRODUCT_ROOT}/engine/Dockerfile` (multi-stage build for backend)
     * `{PRODUCT_ROOT}/experience/Dockerfile` (node build + nginx runtime)
     * `{PRODUCT_ROOT}/neuron/Dockerfile` (Python with dependencies, if exists)
   - Generate `.env.example` with all required environment variables
   - Generate deployment scripts:
     * `scripts/dev-up.sh` (start development environment)
     * `scripts/dev-down.sh` (stop development environment)
     * `scripts/health-check.sh` (verify services)
   - Generate supporting configs (nginx.conf, .dockerignore)
   - Update deployment-architecture.md with references to generated files
   - **Output:** All Docker configurations and deployment scripts

3. **Verification:**
   - Test `docker-compose up` works
   - Verify all services start and pass health checks
   - Test inter-service communication
   - Validate environment variable configuration

4. **Outputs:**
   - `{PRODUCT_ROOT}/planning-mds/architecture/deployment-architecture.md` (Phase 2)
   - `docker-compose.yml` (Phase 3)
   - `Dockerfile` for each service (Phase 3)
   - `.env.example` (Phase 3)
   - Deployment scripts in `scripts/` (Phase 3)
   - Supporting configuration files (Phase 3)
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` updates (deployability evidence, Cross-Cutting checklist items)

**Reference:** `agents/devops/references/containerization-guide.md` - Full three-phase workflow guide

#### 1e. AI Engineer (if AI scope)
1. **Activate AI Engineer agent** by reading `agents/ai-engineer/SKILL.md`
2. **Read context:**
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` (AI-related stories and constraints)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - `{PRODUCT_ROOT}/planning-mds/features/` (AI feature acceptance criteria in story files)
   - Existing `{PRODUCT_ROOT}/neuron/` code (if present)
3. **Execute responsibilities:**
   - Implement AI features in `{PRODUCT_ROOT}/neuron/` (model integration, prompts, workflows, tools)
   - Implement MCP servers/resources when required by stories
   - Add guardrails (input/output validation, retries/timeouts, error handling)
   - Add observability (decision/tool-call logs and usage tracking)
   - Write unit/integration tests for AI components
4. **Follow SOLUTION-PATTERNS.md:**
   - Keep configuration in environment/config files (no hardcoded secrets)
   - Align AI behavior and outputs with story acceptance criteria
   - Keep interfaces explicit for backend/frontend integration
5. **Outputs:**
   - `{PRODUCT_ROOT}/neuron/` implementation updates
   - AI configs and prompt templates
   - MCP server/tool definitions (if needed)
   - AI unit/integration tests
   - `{PRODUCT_ROOT}/neuron/README.md` updates (if behavior or setup changed)
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` updates (AI Progress section, validation evidence)
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/GETTING-STARTED.md` updates (AI runtime / setup notes)

**Completion Criteria for Step 1:**
- [ ] All required agents have completed their work (Backend, Frontend, Quality, DevOps, and AI Engineer if AI scope)
- [ ] Code compiles/builds successfully in application runtime containers
- [ ] No critical errors or blockers

---

### Step 2: SELF-REVIEW GATE (Agent Validation)

**Execution Instructions:**

Each agent validates their own work before proceeding to code review:

1. **Backend Developer self-review:**
   - [ ] All API endpoints implemented per contracts
   - [ ] Domain logic complete and tested
   - [ ] Unit test coverage ≥80% for business logic
   - [ ] Integration tests passing for all endpoints
   - [ ] SOLUTION-PATTERNS.md followed (ABAC, audit, timeline events)
   - [ ] All acceptance criteria met
   - [ ] Code compiles and runs in backend application runtime container

2. **Frontend Developer self-review:**
   - [ ] All screens implemented per specs
   - [ ] Forms work with validation
   - [ ] API integration successful
   - [ ] Component tests passing
   - [ ] SOLUTION-PATTERNS.md followed (React Hook Form, AJV, TanStack Query)
   - [ ] UX rule-set checks passed for touched UI (`agents/frontend-developer/references/ux-audit-ruleset.md`)
   - [ ] `pnpm --dir {PRODUCT_ROOT}/experience lint`, `lint:theme`, `build`, and `test` passed
   - [ ] `pnpm --dir {PRODUCT_ROOT}/experience test:visual:theme` passed when style/theme changed
   - [ ] All acceptance criteria met
   - [ ] No console errors

3. **Quality Engineer self-review:**
   - [ ] Test plan complete
   - [ ] Developer-owned unit/integration suites reviewed and gaps dispositioned
   - [ ] Cross-tier integration and E2E tests passing in application runtime containers
   - [ ] Coverage and quality-gate reports generated
   - [ ] Critical workflows have E2E tests
   - [ ] Quality gate recommendation documented

4. **DevOps self-review:**
   - [ ] Phase 1 complete: Code inspection summary documented
   - [ ] Phase 2 complete: `{PRODUCT_ROOT}/planning-mds/architecture/deployment-architecture.md` created
   - [ ] Phase 3 complete: All configuration files generated
   - [ ] Docker containers build successfully (`docker-compose build`)
   - [ ] All services start correctly (`docker-compose up`)
   - [ ] Health checks pass for all services
   - [ ] Inter-service communication works (frontend → backend → database)
   - [ ] Environment variables documented in `.env.example`
   - [ ] Deployment architecture matches detected code structure

5. **AI Engineer self-review (if AI scope):**
   - [ ] AI workflows/prompts implemented per stories
   - [ ] MCP resources/tools functional (if required)
   - [ ] AI unit/integration tests passing in AI runtime container
   - [ ] Cost/safety/observability controls implemented
   - [ ] No hardcoded API keys or secrets

**If any self-review fails:**
- Agent fixes issues
- Re-runs self-review
- Repeats until passing

**Gate Criteria:**
- [ ] Architect confirms assembled output matches Step 0 plan
- [ ] All required agents pass self-review
- [ ] All tests passing in application runtime containers
- [ ] Application runtime services start and run successfully

---

### Step 3: Execute Code Reviewer

**Execution Instructions:**

1. **Activate Code Reviewer agent** by reading `agents/code-reviewer/SKILL.md`

2. **Read context:**
   - All code produced in Step 1
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` (requirements and architecture)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - `{PRODUCT_ROOT}/planning-mds/features/` (acceptance criteria in colocated story files)

3. **Execute code review responsibilities:**
   - Review code structure and organization
   - Check SOLID principles adherence
   - Validate clean architecture boundaries
   - Review test coverage and quality
   - Identify code smells and anti-patterns
   - Check naming conventions and readability
   - Validate acceptance criteria mapping
   - Review error handling patterns
   - Check for over-engineering or under-engineering
   - Validate SOLUTION-PATTERNS.md compliance

4. **Produce code review report:**
   ```markdown
   # Code Review Report

   ## Summary
   - Overall assessment: [APPROVED / APPROVED WITH RECOMMENDATIONS / REJECTED]
   - Files reviewed: [count]
   - Issues found: [count by severity]

   ## Findings

   ### Critical Issues (must fix before approval)
   - [List critical issues]

   ### High Priority (should fix)
   - [List high priority issues]

   ### Medium Priority (nice to have)
   - [List medium priority issues]

   ### Low Priority (optional)
   - [List low priority suggestions]

   ## Pattern Compliance
   - [ ] Clean architecture layers respected
   - [ ] SOLID principles followed
   - [ ] SOLUTION-PATTERNS.md patterns applied
   - [ ] Test coverage adequate (≥80%)

   ## Acceptance Criteria
   - [ ] All user story ACs met
   - [ ] Edge cases handled
   - [ ] Error scenarios covered

   ## Recommendation
   [APPROVE / REQUEST CHANGES / REJECT]
   ```

**Code Review Outputs:**
- Code review report
- List of findings with severity
- Approval or rejection with rationale

---

### Step 4: APPROVAL GATE (Code Review)

**Execution Instructions:**

1. **Present code review results to user:**
   ```
   ═══════════════════════════════════════════════════════════
   Code Review Complete
   ═══════════════════════════════════════════════════════════

   Reviewer: Code Reviewer Agent
   Status: [APPROVED / APPROVED WITH RECOMMENDATIONS / REJECTED]

   Files Reviewed: [count]
   Issues Found:
     - Critical: [count]
     - High: [count]
     - Medium: [count]
     - Low: [count]

   ✓ Pattern Compliance
     - Clean Architecture: [Yes/No]
     - SOLID Principles: [Yes/No]
     - SOLUTION-PATTERNS.md: [Yes/No]
     - Test Coverage: [percentage]%

   ✓ Acceptance Criteria
     - [count]/[total] user stories fully met
     - Edge cases: [Handled/Needs work]
     - Error scenarios: [Covered/Needs work]

   ═══════════════════════════════════════════════════════════
   Review Details:
   [Link to code review report]
   ═══════════════════════════════════════════════════════════
   ```

2. **Present approval checklist:**
   ```
   Code Review Approval Checklist:
   - [ ] No critical issues (critical findings must be fixed before approval)
   - [ ] High-severity issues are either fixed or approved with mitigation justification
   - [ ] Code follows SOLID principles
   - [ ] Clean architecture boundaries respected
   - [ ] Test coverage evidence captured from application runtime containers
   - [ ] SOLUTION-PATTERNS.md patterns followed
   - [ ] Acceptance criteria met
   - [ ] Code is maintainable and readable
   ```

3. **Enforce code-review gate based on severity:**

   **Gate Decision Logic:**
   ```
   IF critical_issues > 0:
     STATUS: ❌ BLOCKED
     MESSAGE: "Critical code quality issues MUST be fixed before security review."
     OPTIONS: ["Fix Critical Issues", "Reject"]
     APPROVE_ENABLED: false

   ELSE IF high_issues > 0:
     STATUS: ⚠️ WARNING
     MESSAGE: "High-severity code issues found. Recommend fixing before approval."
     OPTIONS: ["Fix High Issues (Recommended)", "Approve with Justification", "Reject"]
     APPROVE_ENABLED: true (requires justification)

   ELSE:
     STATUS: ✓ ACCEPTABLE
     MESSAGE: "No critical/high code quality issues found."
     OPTIONS: ["Approve", "Fix Issues Anyway", "Reject"]
     APPROVE_ENABLED: true
   ```

4. **Handle user response:**
   - **If "Fix Critical Issues":**
     - Identify critical issues
     - Agents fix issues
     - Return to Step 3 (re-run code review)

   - **If "Fix High Issues (Recommended)" or "Fix Issues Anyway":**
     - Identify selected issues
     - Agents fix issues
     - Return to Step 3 (re-run code review)

   - **If "Approve with Justification":**
     - Require explicit justification for remaining high issues
     - Log decision and mitigation plan
     - Proceed to Step 5 (Security Review)

   - **If "Approve":**
     - Proceed to Step 5 (Security Review)

   - **If "Reject":**
     - Capture feedback
     - Return to Step 0 (re-plan and re-implement with feedback)

   - **If user input is not in `OPTIONS` for current gate state:**
     - Do not transition
     - Re-present current gate state and valid options

**Gate Criteria:**
- [ ] Critical code issues = 0 (approval blocked otherwise)
- [ ] High issues fixed or approved with explicit justification
- [ ] User decision recorded with rationale when required

---

### Step 5: Execute Security Review

**Execution Instructions:**

1. **Activate Security agent** by reading `agents/security/SKILL.md`

2. **Read context:**
   - All code produced in Step 1
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 4.5 (authorization model)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - `{PRODUCT_ROOT}/planning-mds/security/` (threat model, if exists)

3. **Execute security review responsibilities:**
   - Scan for OWASP Top 10 vulnerabilities:
     1. Injection (SQL, command, XSS)
     2. Broken authentication
     3. Sensitive data exposure
     4. XML external entities
     5. Broken access control
     6. Security misconfiguration
     7. Cross-site scripting (XSS)
     8. Insecure deserialization
     9. Components with vulnerabilities
     10. Insufficient logging
   - Review authorization implementation (Casbin ABAC)
   - Check input validation and sanitization
   - Review secrets management (no hardcoded secrets)
   - Validate audit logging completeness
   - Review error messages (no info leakage)
   - Check HTTPS/TLS configuration
   - Validate CORS policies
   - Run dependency/container vulnerability scans in application runtime containers (or CI jobs built from them)

4. **Produce security review report:**
   ```markdown
   # Security Review Report

   ## Summary
   - Overall assessment: [PASS / PASS WITH RECOMMENDATIONS / FAIL]
   - Vulnerabilities found: [count by severity]

   ## OWASP Top 10 Assessment
   - [X] Injection: [PASS / FAIL]
   - [X] Broken Authentication: [PASS / FAIL]
   - [X] Sensitive Data Exposure: [PASS / FAIL]
   - [X] XML External Entities: [PASS / FAIL]
   - [X] Broken Access Control: [PASS / FAIL]
   - [X] Security Misconfiguration: [PASS / FAIL]
   - [X] XSS: [PASS / FAIL]
   - [X] Insecure Deserialization: [PASS / FAIL]
   - [X] Vulnerable Components: [PASS / FAIL]
   - [X] Insufficient Logging: [PASS / FAIL]

   ## Findings

   ### Critical (must fix immediately)
   - [List critical security issues]

   ### High (fix before production)
   - [List high severity issues]

   ### Medium (should fix)
   - [List medium severity issues]

   ### Low (best practices)
   - [List low severity recommendations]

   ## Authorization Review
   - [ ] ABAC implementation correct
   - [ ] All endpoints protected
   - [ ] Per-endpoint authorization enforced

   ## Recommendation
   [APPROVE / FIX CRITICAL / FIX HIGH / REJECT]
   ```

**Security Review Outputs:**
- Security review report
- OWASP Top 10 assessment
- Vulnerability findings with severity and remediation
- Approval or rejection

---

### Step 6: APPROVAL GATE (Security Review)

**Execution Instructions:**

1. **Present security review results to user:**
   ```
   ═══════════════════════════════════════════════════════════
   Security Review Complete
   ═══════════════════════════════════════════════════════════

   Reviewer: Security Agent
   Status: [PASS / PASS WITH RECOMMENDATIONS / FAIL]

   Vulnerabilities Found:
     - Critical: [count]
     - High: [count]
     - Medium: [count]
     - Low: [count]

   ✓ OWASP Top 10 Assessment
     - Injection: [PASS/FAIL]
     - Broken Authentication: [PASS/FAIL]
     - Sensitive Data Exposure: [PASS/FAIL]
     - Broken Access Control: [PASS/FAIL]
     - [... remaining items]

   ✓ Authorization
     - ABAC implementation: [Correct/Needs work]
     - Endpoint protection: [Complete/Incomplete]
     - Server-side enforcement: [Yes/No]

   ✓ Audit Logging
     - All mutations logged: [Yes/No]
     - Timeline events: [Yes/No]

   ═══════════════════════════════════════════════════════════
   Review Details:
   [Link to security review report]
   ═══════════════════════════════════════════════════════════
   ```

2. **Present approval checklist:**
   ```
   Security Approval Checklist:
   - [ ] No critical vulnerabilities
   - [ ] No high-severity issues (or acceptable with mitigation plan)
   - [ ] OWASP Top 10 compliance
   - [ ] Authorization correctly implemented
   - [ ] No hardcoded secrets
   - [ ] Audit logging complete
   - [ ] Input validation comprehensive
   ```

3. **Enforce security gate based on findings severity:**

   **Gate Decision Logic:**

   The security gate enforces different rules based on severity of findings:

   ```
   IF critical_issues > 0:
     STATUS: ❌ BLOCKED
     MESSAGE: "Critical security issues MUST be fixed. Cannot proceed."
     OPTIONS: ["Fix Critical Issues", "Cancel Build"]
     APPROVE_ENABLED: false

   ELSE IF high_issues > 0:
     STATUS: ⚠️ WARNING
     MESSAGE: "High-severity security issues found. Recommend fixing before approval."
     OPTIONS: ["Fix Issues (Recommended)", "Approve with Justification", "Cancel Build"]
     APPROVE_ENABLED: true (requires justification)

   ELSE IF medium_issues > 0 OR low_issues > 0:
     STATUS: ✓ ACCEPTABLE
     MESSAGE: "Only medium/low severity issues found. Safe to approve."
     OPTIONS: ["Approve", "Fix Issues Anyway", "Cancel Build"]
     APPROVE_ENABLED: true

   ELSE:
     STATUS: ✓ CLEAN
     MESSAGE: "No security issues found. Safe to proceed."
     OPTIONS: ["Approve"]
     APPROVE_ENABLED: true
   ```

4. **Present gate to user with appropriate options:**

   **Scenario A: Critical Issues Found (BLOCKING)**
   ```
   ❌ SECURITY GATE: BLOCKED

   Critical security issues found:
   - [CRITICAL] SQL Injection vulnerability in CustomerController.cs:45
   - [CRITICAL] Hardcoded API key in appsettings.json:12

   High severity issues:
   - [HIGH] Missing authentication on /api/admin endpoint

   ❌ Cannot proceed until critical issues are resolved.

   Options:
   [Fix Critical Issues] [Cancel Build]
   ```

   **Handling:**
   - **"Fix Critical Issues":**
     - Return to appropriate developer agents to fix issues
     - Re-run Security review (return to Step 5)
     - Repeat until critical issues = 0

   - **"Cancel Build":**
     - Abort build action
     - User can restart with `build` action later

   ---

   **Scenario B: High Issues Only (WARNING - Approval Requires Justification)**
   ```
   ⚠️ SECURITY GATE: WARNING

   High severity issues found:
   - [HIGH] Missing rate limiting on authentication endpoints
   - [HIGH] Weak password policy (min length: 6)

   Medium/Low issues:
   - [MEDIUM] CORS policy too permissive
   - [LOW] Missing security headers

   ⚠️ Recommend fixing high-severity issues before approval.

   Options:
   [Fix Issues (Recommended)] [Approve with Justification] [Cancel Build]
   ```

   **Handling:**
   - **"Fix Issues (Recommended)":**
     - Return to developer agents to fix issues
     - Re-run Security review

   - **"Approve with Justification":**
     - Require user to provide justification:
       ```
       Why are you approving with high-severity issues?
       [ User enters reason: "These are planned for Phase 2 per ADR-015" ]
       ```
     - Log approval decision with justification to audit trail
     - Proceed to Step 6.75 (Signoff Gate)

   - **"Cancel Build":**
     - Abort build action

   ---

   **Scenario C: Medium/Low Issues Only (ACCEPTABLE)**
   ```
   ✓ SECURITY GATE: ACCEPTABLE

   Medium severity issues:
   - [MEDIUM] CORS policy could be more restrictive
   - [MEDIUM] Session timeout could be shorter

   Low severity issues:
   - [LOW] Missing X-Content-Type-Options header
   - [LOW] Verbose error messages in dev mode

   ✓ No critical or high-severity issues. Safe to approve.

   Options:
   [Approve] [Fix Issues Anyway] [Cancel Build]
   ```

   **Handling:**
   - **"Approve":**
     - Proceed to Step 6.75 (Signoff Gate)

   - **"Fix Issues Anyway":**
     - Return to developer agents to fix issues
     - Re-run Security review

   - **"Cancel Build":**
     - Abort build action

   ---

   **Scenario D: No Issues (CLEAN)**
   ```
   ✓ SECURITY GATE: CLEAN

   No security issues found.

   ✅ All security checks passed:
   - No SQL injection vulnerabilities
   - No hardcoded secrets
   - Authentication properly implemented
   - Authorization enforced on all endpoints
   - Input validation comprehensive
   - OWASP Top 10 compliance verified

   Options:
   [Approve]
   ```

   **Handling:**
   - **"Approve":**
     - Proceed to Step 6.75 (Signoff Gate)

5. **Machine-Readable Gate State:**

   Orchestrators must be able to programmatically determine gate state:

   ```json
   {
     "gate": "security_review",
     "status": "blocked" | "warning" | "acceptable" | "clean",
     "findings": {
       "critical": 2,
       "high": 1,
       "medium": 3,
       "low": 5
     },
     "can_approve": false,
     "requires_justification": false,
     "available_actions": ["fix_critical_issues", "cancel"],
     "blocking_issues": [
       {
         "severity": "critical",
         "type": "sql_injection",
         "location": "CustomerController.cs:45",
         "description": "Unsanitized user input in SQL query"
       },
       {
         "severity": "critical",
         "type": "hardcoded_secret",
         "location": "appsettings.json:12",
         "description": "API key hardcoded in configuration"
       }
     ]
   }
   ```

**Gate Criteria (Enforcement Rules):**
- ❌ **BLOCKED:** If critical issues > 0, approval is DISABLED (no override possible)
- ⚠️ **WARNING:** If high issues > 0 (and critical = 0), approval ENABLED but requires justification
- ✓ **ACCEPTABLE:** If only medium/low issues, approval ENABLED without restriction
- ✓ **CLEAN:** If no issues, approval ENABLED

**Contract Compliance:**
This security gate enforcement aligns with the orchestration contract quality-gate model:
- Critical issues = Block (must be fixed, no override) ✅
- High issues = Warn (user can approve with justification) ✅
- Medium/Low issues = Acceptable (proceed, track for later) ✅

**Audit Log Requirements:**
- Log all gate decisions with timestamp, user, severity counts
- For "Approve with Justification", log the justification text
- For "Fix Critical Issues", log which issues were identified
- Append to `{PRODUCT_ROOT}/planning-mds/.audit/gate-decisions.jsonl`

**Example Audit Log Entry:**
```json
{
  "gate": "security_review",
  "timestamp": "2026-02-07T15:30:00Z",
  "user": "user@example.com",
  "decision": "blocked",
  "findings": {
    "critical": 2,
    "high": 1,
    "medium": 3,
    "low": 5
  },
  "action_taken": "fix_critical_issues",
  "blocking_issues": [
    "SQL Injection in CustomerController.cs:45",
    "Hardcoded API key in appsettings.json:12"
  ]
}
```

---

### Step 6.5: Performance Validation (Informational)

**Execution Instructions:**

If `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 4 defines measurable NFR targets, validate implementation against them and record results:

- [ ] API latency target (for example p95)
- [ ] Throughput/concurrency target
- [ ] Frontend performance targets (for example Core Web Vitals) when applicable

This is an informational gate for release readiness reporting and does not block progression by itself.

---

### Step 6.75: SIGNOFF GATE (Mandatory)

**Execution Instructions:**

Before Build Complete, verify required role signoffs across delivered features:

1. Read `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` for each delivered feature:
   - `Required Signoff Roles` matrix
   - `Story Signoff Provenance`
2. For every required role across the build scope, confirm:
   - each in-scope story has a passing signoff row
   - reviewer/date/evidence are present
   - evidence paths point to solution artifacts, not `agents/**`
3. If any required signoff is missing or non-pass:
   - Block build closeout
   - Route back to the owning reviewer role

**Gate Criteria:**
- [ ] Every required signoff role has a passing ledger entry for delivered scope
- [ ] Signoff evidence is complete for every in-scope story
- [ ] No feature is marked `Done`/`Archived` without passing required signoffs

---

### Step 6.9: PRODUCT MANAGER CLOSEOUT (Mandatory)

**Execution Instructions:**

1. **Activate Product Manager agent** by reading `agents/product-manager/SKILL.md`
2. Reconcile delivered-feature closure artifacts:
   - `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/STATUS.md` for each delivered feature
   - `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md` for status/path transitions
   - `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md` for sequencing/completion placement
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` feature/story status snapshot (if changed)
3. For completed features, move folders to `{PRODUCT_ROOT}/planning-mds/features/archive/` when appropriate and update impacted path references
4. If ontology-backed planning exists for touched features, update feature/path/status references in:
   - `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`
5. Record deferred follow-ups, known mitigations, and orphaned story handling before tracker validation
6. **Knowledge-graph validation:**
   - Confirm implementation agents added `code-index.yaml` bindings for new source files created during the build. If bindings are missing, add them now.
   - Run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift` and resolve any errors before proceeding.
   - If the build introduced new canonical nodes or rationale entries, confirm they are present in `canonical-nodes.yaml`.

**Completion Criteria:**
- [ ] Product Manager closeout executed after signoff passed
- [ ] Delivered features have final status/archive decisions recorded
- [ ] Deferred follow-ups and mitigation carry-overs captured
- [ ] Ontology feature mappings updated if closeout changes feature path/status
- [ ] Code-index bindings exist for new source files introduced during this build
- [ ] `validate.py --check-drift` exits 0

---

### Step 6.95: TRACKER SYNC GATE (Mandatory)

**Execution Instructions:**

Validate the closeout updates before Build Complete:

1. Regenerate story index when story files changed:
   - `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/`

2. Validate tracker coherence:
   - `python3 agents/product-manager/scripts/validate-trackers.py`

3. If validation fails:
   - Treat as blocking
   - Fix tracker drift and re-run until passing

**Gate Criteria:**
- [ ] STATUS files updated for delivered features
- [ ] Product Manager closeout executed before tracker validation
- [ ] REGISTRY/ROADMAP/BLUEPRINT synchronized
- [ ] STORY-INDEX regenerated when required
- [ ] Tracker validation passes

---

### Step 7: Build Complete

**Execution Instructions:**

Present completion summary:

```
═══════════════════════════════════════════════════════════
Build Action Complete! ✓
═══════════════════════════════════════════════════════════

Application Assembly:
  ✓ Architect
    - Assembly plan created
    - Cross-agent handoffs validated
    - Integration checkpoints tracked

Implementation (Parallel):
  ✓ Backend Developer
    - [count] entities implemented
    - [count] API endpoints created
    - [percentage]% unit test coverage
    - [count] integration tests passing

  ✓ Frontend Developer
    - [count] components created
    - [count] screens implemented
    - [count] forms with validation
    - Component tests passing

  ✓ Quality Engineer
    - Test plan complete
    - [count] E2E tests created
    - All tests passing

  ✓ DevOps
    - Docker containers ready
    - docker-compose configured
    - Deployment scripts created

  ✓ AI Engineer (if AI scope)
    - [count] AI workflows/prompts implemented
    - [count] MCP tools/resources added
    - [count] AI tests passing

Code Review:
  ✓ Code Reviewer: APPROVED
  ✓ Pattern compliance verified
  ✓ Test coverage adequate
  Status: APPROVED

Security Review:
  ✓ Security Agent: APPROVED
  ✓ OWASP Top 10: PASS
  ✓ Authorization: Correct
  Status: APPROVED

Closeout:
  ✓ Required signoff ledger complete
  ✓ Product Manager closeout recorded
  ✓ Trackers and story index synchronized

═══════════════════════════════════════════════════════════
Next Steps:
═══════════════════════════════════════════════════════════

1. Run application runtime stack: docker-compose up
2. Test features manually
3. Run "document" action to generate docs
4. Deploy to staging environment

All features implemented and approved! ✓
═══════════════════════════════════════════════════════════
```

---

## Validation Criteria

**Overall Build Action Success:**
- [ ] Application assembly plan created and followed
- [ ] All required implementation agents completed work (including AI Engineer when AI scope exists)
- [ ] All tests passing (unit, integration, E2E) in application runtime containers
- [ ] AI tests passing (if AI scope) in AI runtime container
- [ ] Code review approved
- [ ] Security review approved
- [ ] Signoff gate passed for all required reviewer roles
- [ ] Application runtime containers run successfully
- [ ] All acceptance criteria met
- [ ] Product Manager closeout completed
- [ ] Tracker sync gate passed (REGISTRY/ROADMAP/STORY-INDEX/BLUEPRINT/STATUS)

---

## Prerequisites

Before running build action:
- [ ] Plan action completed (requirements + architecture defined)
- [ ] SOLUTION-PATTERNS.md exists and is up-to-date
- [ ] Tracker governance contract available (`{PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md`, seeded from `agents/templates/tracker-governance-template.md` when missing)
- [ ] User stories have clear acceptance criteria
- [ ] User is available for approval gates

---

## Related Actions

- **Before:** [plan action](./plan.md) - Define what to build
- **Alternative:** [feature action](./feature.md) - Build single feature incrementally
- **After:** [document action](./document.md) - Generate documentation
- **Quality:** [test action](./test.md) - Additional testing focus
- **Quality:** [review action](./review.md) - Additional review focus

---

## Notes

- Build action implements ALL features in scope (use feature action for incremental)
- Implementation agents work in parallel for efficiency
- Reviews are sequential to ensure quality gates
- Critical issues block approval; high issues require explicit mitigation justification if approved
- Can re-run steps if approval gates fail
- All patterns in SOLUTION-PATTERNS.md must be followed
- Signoff must pass before PM closeout, and PM closeout must finish before final tracker sync

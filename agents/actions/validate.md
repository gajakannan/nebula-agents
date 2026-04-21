# Action: Validate

## User Intent

Validate that requirements, architecture, and implementation are aligned and that all artifacts are complete and consistent.

## Agent Flow

```
Product Manager (requirements validation) + Architect (architecture validation)
  ↓ [Parallel Validation]
[SELF-REVIEW GATE: Each agent checks their report completeness]
  ↓
[APPROVAL GATE: User reviews findings and decides next steps]
  ↓
Validation Complete
```

**Flow Type:** Parallel validation with approval gate

---

## Runtime Execution Boundary

- The builder runtime orchestrates the validation flow and gate decisions; it remains stack-agnostic.
- If implementation validation is in scope, stack-specific checks (compile, test, schema comparison) must run in application runtime containers (or CI jobs built from those container definitions).
- Validation reports cite evidence from builder-side artifact inspection and (when applicable) application runtime execution.

---

## Execution Steps

### Step 1: Parallel Validation

**Execution Instructions:**

Execute these validation agents **in parallel**. The user specifies scope: `requirements`, `architecture`, `implementation`, or `all`.

#### 1a. Product Manager (Requirements Validation)

1. **Activate Product Manager agent** by reading `agents/product-manager/SKILL.md`

2. **Read context:**
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` (all sections)
   - `{PRODUCT_ROOT}/planning-mds/features/` (feature folders with colocated PRDs, stories, STATUS)
   - `{PRODUCT_ROOT}/planning-mds/domain/glossary.md`
   - `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md`
   - `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md`

3. **Execute requirements validation:**

   **Completeness Check:**
   - [ ] BLUEPRINT.md Section 3 subsections 3.1-3.5 all filled
   - [ ] No TODO or placeholder text
   - [ ] Every feature has a folder with PRD.md, README.md, STATUS.md, GETTING-STARTED.md
   - [ ] Every feature has at least one story file

   **Vision and Non-goals Clarity:**
   - [ ] Vision is 1-2 sentences with a clear outcome
   - [ ] Non-goals are explicit (what we are NOT building)
   - [ ] Success metrics defined

   **Persona Validation:**
   - [ ] Each persona has name, role, goals, pain points
   - [ ] Personas represent actual target users
   - [ ] Primary vs secondary personas identified

   **Feature Traceability:**
   - [ ] Every feature maps to a persona need
   - [ ] No features without clear user value
   - [ ] Features prioritized (MVP vs future)

   **Story Testability (per story):**
   - [ ] Has "As a / I want / So that" structure
   - [ ] Acceptance criteria are specific and measurable
   - [ ] No banned words: "should", "might", "easy", "fast", "secure" (without specifics)
   - [ ] Performance criteria quantified (< Xms, not "fast")
   - [ ] Error scenarios specified ("if X fails, then Y")
   - [ ] Edge cases identified (empty lists, max values, nulls)
   - [ ] Dependencies documented

   **Anti-Pattern Detection — flag these as issues:**
   - ❌ "System should be fast" → ✅ "API responses < 200ms p95"
   - ❌ "Users can upload files" → ✅ "Users can upload PDF/PNG (max 10MB)"
   - ❌ "Secure authentication" → ✅ "JWT tokens, HTTPS only, session timeout 30min"
   - ❌ "Easy to use interface" → ✅ "3-click maximum to create customer"
   - ❌ "Dashboard is intuitive" → ✅ "Dashboard shows: revenue chart, top 5 customers, recent orders"

   **Screen Specs:**
   - [ ] Each screen has purpose, layout, key elements
   - [ ] Screens support user stories
   - [ ] Navigation between screens defined

   **Consistency:**
   - [ ] No conflicting requirements
   - [ ] Consistent terminology (aligned with glossary)
   - [ ] Clear priorities (no "all are critical")
   - [ ] No invented business rules (all rules trace to user needs or constraints)
   - [ ] Assumptions documented explicitly

4. **Produce requirements validation report:**
   ```markdown
   # Requirements Validation Report

   Scope: [Feature-specific / Full project]
   Date: [Date]

   ## Summary
   - Assessment: [VALID / VALID WITH RECOMMENDATIONS / ISSUES FOUND]
   - Sections checked: [count]
   - Issues found: [count by severity]

   ## Findings by Severity

   ### Critical (blocks building)
   1. [Description]
      - Location: [file/section]
      - Impact: [why this blocks progress]
      - Recommendation: [how to fix]

   ### High (should fix before building)
   [Same format]

   ### Medium (address when convenient)
   [Same format]

   ### Low (suggestions)
   [Same format]

   ## Checklist Results
   - Completeness: [PASS/FAIL — details]
   - Traceability: [PASS/FAIL — details]
   - Testability: [PASS/FAIL — details]
   - Consistency: [PASS/FAIL — details]

   ## Recommendation
   [PROCEED / FIX ISSUES FIRST / RE-PLAN]
   ```

#### 1b. Architect (Architecture Validation)

1. **Activate Architect agent** by reading `agents/architect/SKILL.md`

2. **Read context:**
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` (all sections)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - `{PRODUCT_ROOT}/planning-mds/architecture/decisions/` (ADRs)
   - `{PRODUCT_ROOT}/planning-mds/api/` (API contracts)
   - `{PRODUCT_ROOT}/planning-mds/features/` (story acceptance criteria)

3. **Execute architecture validation:**

   **Completeness Check:**
   - [ ] BLUEPRINT.md Section 4 subsections complete
   - [ ] Service/module boundaries defined
   - [ ] Data model complete with relationships
   - [ ] API contracts exist for all story-driven endpoints
   - [ ] Authorization model covers all resources and actions
   - [ ] Workflow state machines specified
   - [ ] NFRs measurable and achievable
   - [ ] ADRs exist for key decisions

   **Requirements Alignment:**
   - [ ] Architecture satisfies all Phase A requirements
   - [ ] Every user story has a corresponding API endpoint or UI path
   - [ ] Data model supports all features
   - [ ] Authorization model supports all personas

   **Pattern Compliance (when SOLUTION-PATTERNS.md exists):**
   - [ ] Authorization pattern followed (for example Casbin ABAC)
   - [ ] Audit fields included on all mutable entities
   - [ ] API endpoints follow defined naming convention
   - [ ] Errors follow ProblemDetails or specified error pattern
   - [ ] Clean architecture layers respected
   - [ ] Workflow transitions are append-only (if applicable)
   - [ ] All mutations create timeline events (if applicable)

   **Implementation Alignment (when code exists):**
   - [ ] Database schema matches data model
   - [ ] API endpoints match contracts
   - [ ] Domain entities match architecture
   - [ ] No architectural drift

4. **Produce architecture validation report:**
   ```markdown
   # Architecture Validation Report

   Scope: [Architecture-only / Architecture + Implementation alignment]
   Date: [Date]

   ## Summary
   - Assessment: [VALID / VALID WITH RECOMMENDATIONS / ISSUES FOUND]
   - Areas checked: [count]
   - Issues found: [count by severity]

   ## Findings by Severity

   ### Critical (fundamental architecture flaws)
   [Same format as requirements report]

   ### High (significant gaps)
   [Same format]

   ### Medium (minor inconsistencies)
   [Same format]

   ### Low (optimization opportunities)
   [Same format]

   ## Checklist Results
   - Completeness: [PASS/FAIL — details]
   - Requirements Alignment: [PASS/FAIL — details]
   - Pattern Compliance: [PASS/FAIL — details]
   - Implementation Alignment: [PASS/FAIL / NOT IN SCOPE — details]

   ## Recommendation
   [PROCEED / FIX ISSUES FIRST / RE-ARCHITECT]
   ```

**Completion Criteria for Step 1:**
- [ ] All in-scope validations completed
- [ ] Reports generated with findings by severity

---

### Step 1.5: SELF-REVIEW GATE (Report Quality)

**Execution Instructions:**

Each agent validates their report before presenting to the user:

1. **Product Manager self-review:**
   - [ ] All relevant sections of BLUEPRINT.md checked
   - [ ] Every feature folder inspected
   - [ ] Story testability validated per story (not just sampled)
   - [ ] Findings cite specific files and sections
   - [ ] Severity assignments follow the defined severity levels

2. **Architect self-review:**
   - [ ] All architecture artifacts inspected
   - [ ] Requirements alignment checked against actual story acceptance criteria
   - [ ] Pattern compliance checked against SOLUTION-PATTERNS.md (not generic rules)
   - [ ] Implementation alignment checked against actual code (when in scope)
   - [ ] Findings cite specific files and sections

**If any self-review fails:**
- Agent corrects their report
- Re-runs self-review
- Repeats until passing

**Gate Criteria:**
- [ ] Both reports are complete and cite specific evidence
- [ ] Severity assignments are consistent between reports
- [ ] No placeholder or generic findings (all are specific)

---

### Step 2: APPROVAL GATE (Validation Results)

**Execution Instructions:**

1. **Present combined validation results to user:**
   ```
   ═══════════════════════════════════════════════════════════
   Validation Complete
   ═══════════════════════════════════════════════════════════

   REQUIREMENTS VALIDATION
   ─────────────────────────────────────────────────────────
   Status: [VALID / VALID WITH RECOMMENDATIONS / ISSUES FOUND]

   Issues Found:
     - Critical: [count]
     - High: [count]
     - Medium: [count]
     - Low: [count]

   Checklist:
     - Completeness: [PASS/FAIL]
     - Traceability: [PASS/FAIL]
     - Testability: [PASS/FAIL]
     - Consistency: [PASS/FAIL]

   ARCHITECTURE VALIDATION
   ─────────────────────────────────────────────────────────
   Status: [VALID / VALID WITH RECOMMENDATIONS / ISSUES FOUND]

   Issues Found:
     - Critical: [count]
     - High: [count]
     - Medium: [count]
     - Low: [count]

   Checklist:
     - Completeness: [PASS/FAIL]
     - Requirements Alignment: [PASS/FAIL]
     - Pattern Compliance: [PASS/FAIL]
     - Implementation Alignment: [PASS/FAIL / N/A]

   ═══════════════════════════════════════════════════════════
   Detailed Reports:
   - Requirements: [location]
   - Architecture: [location]
   ═══════════════════════════════════════════════════════════
   ```

2. **Compute gate state from combined findings:**

   **Gate Decision Logic:**
   ```
   total_critical = req_critical + arch_critical
   total_high = req_high + arch_high

   IF total_critical > 0:
     STATUS: ❌ BLOCKED
     MESSAGE: "Critical validation issues found. Must fix before proceeding."
     OPTIONS: ["Fix Critical Issues", "Cancel"]
     APPROVE_ENABLED: false

   ELSE IF total_high > 0:
     STATUS: ⚠️ WARNING
     MESSAGE: "High-severity validation issues found. Recommend fixing."
     OPTIONS: ["Fix Issues (Recommended)", "Acknowledge and Proceed", "Cancel"]
     APPROVE_ENABLED: true (requires acknowledgment)

   ELSE:
     STATUS: ✓ VALID
     MESSAGE: "Validation passed. Safe to proceed."
     OPTIONS: ["Proceed", "Fix Issues Anyway", "Cancel"]
     APPROVE_ENABLED: true
   ```

3. **Machine-readable gate state:**

   Orchestrators must be able to programmatically determine gate state:

   ```json
   {
     "gate": "validation",
     "status": "blocked" | "warning" | "valid",
     "findings": {
       "requirements": {
         "critical": 0,
         "high": 2,
         "medium": 1,
         "low": 3
       },
       "architecture": {
         "critical": 0,
         "high": 1,
         "medium": 2,
         "low": 0
       }
     },
     "checklists": {
       "completeness": "pass",
       "traceability": "pass",
       "testability": "fail",
       "consistency": "pass",
       "requirements_alignment": "pass",
       "pattern_compliance": "pass",
       "implementation_alignment": "not_in_scope"
     },
     "can_proceed": true,
     "requires_acknowledgment": true,
     "available_actions": ["fix_issues", "acknowledge_and_proceed", "cancel"]
   }
   ```

4. **Handle user response:**
   - **If "Fix Critical Issues" or "Fix Issues (Recommended)" or "Fix Issues Anyway":**
     - Identify issues to fix
     - Direct user to appropriate action (plan for requirements issues, architect for architecture issues)
     - Re-run validate action after fixes

   - **If "Acknowledge and Proceed":**
     - Log acknowledgment with remaining high issues
     - Proceed to Step 3

   - **If "Proceed":**
     - Proceed to Step 3

   - **If "Cancel":**
     - End validate action
     - User decides next steps

   - **If user input is not in current state's allowed options:**
     - Do not transition
     - Re-present current state and allowed options

**Gate Criteria:**
- [ ] Both validations completed
- [ ] Combined critical issues = 0 before proceed is enabled
- [ ] High-issue acknowledgment includes explicit acceptance
- [ ] User decision logged

---

### Step 3: Validation Complete

**Execution Instructions:**

Present completion summary:

```
═══════════════════════════════════════════════════════════
Validation Complete! ✓
═══════════════════════════════════════════════════════════

Requirements Validation:
  Status: [VALID / ISSUES FOUND]
  - Completeness: [PASS/FAIL]
  - Traceability: [PASS/FAIL]
  - Testability: [PASS/FAIL]
  - Consistency: [PASS/FAIL]
  Issues: [count critical] critical, [count high] high,
          [count medium] medium, [count low] low

Architecture Validation:
  Status: [VALID / ISSUES FOUND]
  - Completeness: [PASS/FAIL]
  - Requirements Alignment: [PASS/FAIL]
  - Pattern Compliance: [PASS/FAIL]
  - Implementation Alignment: [PASS/FAIL / N/A]
  Issues: [count critical] critical, [count high] high,
          [count medium] medium, [count low] low

User Decision: [PROCEED / FIX ISSUES / CANCELLED]

═══════════════════════════════════════════════════════════
Next Steps:
═══════════════════════════════════════════════════════════

If validation passed:
1. Run "build" action to implement all features
2. Run "feature" action to implement incrementally

If issues were found:
1. Run "plan" action to fix requirements issues
2. Run architect phase to fix architecture issues
3. Re-run "validate" action to confirm fixes

Validation reports saved to: {PRODUCT_ROOT}/planning-mds/validation/
═══════════════════════════════════════════════════════════
```

---

## Validation Criteria

**Overall Validate Action Success:**
- [ ] All in-scope validations completed (requirements, architecture, implementation)
- [ ] Reports generated with severity-classified findings
- [ ] Self-review gate passed (reports cite specific evidence)
- [ ] User reviewed findings and made explicit decision
- [ ] If proceeded with high issues: acknowledgment recorded
- [ ] Validation reports saved to `{PRODUCT_ROOT}/planning-mds/validation/`

---

## Prerequisites

Before running validate action:
- [ ] `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` exists with planning content
- [ ] Architecture artifacts exist (for architecture validation)
- [ ] Optional: Implementation code exists (for implementation alignment)
- [ ] User has specified validation scope

---

## Validation Severity Levels

### Critical
- Missing required BLUEPRINT sections
- Major contradictions between requirements
- Fundamental architecture flaws
- Security model gaps (no authorization defined)
- Data model cannot support required features

### High
- Incomplete specifications (sections with TODOs)
- Ambiguous requirements (banned words without specifics)
- Missing API contracts for planned features
- Unmet acceptance criteria (implementation validation)
- NFRs not measurable

### Medium
- Minor inconsistencies between documents
- Optimization opportunities
- Documentation gaps
- Non-critical naming issues

### Low
- Style suggestions
- Nice-to-have improvements
- Alternative approaches worth considering

---

## Example Usage

### Scenario 1: Pre-Build Validation
```
User: "Validate architecture before we start building"

Agent Runtime: [Reads validate.md]
Agent Runtime: "I'll run requirements and architecture validation in parallel..."

[Step 1: Parallel validation]
Product Manager:
  - Validates BLUEPRINT.md Section 3
  - Checks 12 stories across 4 features
  - Report: VALID WITH RECOMMENDATIONS
    - 0 critical, 1 high (story F0003-S0002 has vague AC), 2 medium

Architect:
  - Validates BLUEPRINT.md Section 4
  - Checks API contracts, data model, authorization
  - Report: VALID
    - 0 critical, 0 high, 1 medium (missing ADR for caching strategy)

[Step 1.5: Self-review — both reports cite specific files and sections]

[Step 2: Approval gate]
Agent Runtime: "Validation complete.
  Requirements: VALID WITH RECOMMENDATIONS (1 high issue)
  Architecture: VALID (1 medium issue)

  ⚠️ High issue: Story F0003-S0002 acceptance criteria uses
  'should be fast' — needs specific latency target.

  Options: fix issues (recommended) / acknowledge and proceed / cancel"

User: "fix issues"

Agent Runtime: "Recommended fix: Update F0003-S0002 with specific
  performance criteria. Re-run validate after fixing."
```

### Scenario 2: Implementation Alignment Check
```
User: "Validate that our implementation matches the plan"

Agent Runtime: "Running full validation including implementation alignment..."

[Step 1: Parallel validation]
Product Manager:
  - Validates requirements: VALID
  - Checks implementation: 3/5 stories implemented, all AC met

Architect:
  - Validates architecture: VALID
  - Checks implementation alignment:
    - Database schema: Matches data model
    - API endpoints: 2 endpoints missing authorization middleware
    - Domain entities: Aligned
  - Report: ISSUES FOUND (2 high)

[Step 1.5: Self-review — pass]

[Step 2: Approval gate]
Agent Runtime: "Validation complete.
  Requirements: VALID (3/5 stories implemented, all AC met)
  Architecture: ISSUES FOUND
    - 2 HIGH: Missing authorization on GET /api/tasks and
      DELETE /api/tasks/:id

  ⚠️ Recommend fixing before proceeding.
  Options: fix issues (recommended) / acknowledge and proceed / cancel"

User: "fix issues"

Agent Runtime: "Authorization gaps identified. Run 'feature' or 'build'
  action to add authorization middleware to affected endpoints."
```

### Scenario 3: Clean Full Validation
```
User: "Validate entire project"

[Step 1: Parallel validation — all checks pass]

[Step 1.5: Self-review — pass]

[Step 2: Approval gate]
Agent Runtime: "Validation complete.
  Requirements: VALID (0 issues)
  Architecture: VALID (0 issues)
  Implementation Alignment: VALID (0 issues)

  ✓ All checks passed. Safe to proceed.
  Options: proceed / cancel"

User: "proceed"

Agent Runtime: "Validation passed! Ready for build or feature action."
```

---

## Related Actions

- **Before Building:** Run validate after [plan action](./plan.md)
- **During Building:** Run validate to check alignment
- **After Building:** Run validate before deployment
- **Continuous:** Run validate regularly to catch drift

---

## Notes

- Validate action is non-destructive (read-only analysis)
- Can be run at any phase of the project
- Use validation scripts in `agents/*/scripts/` when available
- Validation reports should be saved to `{PRODUCT_ROOT}/planning-mds/validation/`
- Re-run after fixing issues to confirm resolution
- Validate does not modify code or planning artifacts — it only reports findings

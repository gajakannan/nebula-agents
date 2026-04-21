# Action: Review

## User Intent

Perform comprehensive code quality and security review on implemented features or the entire codebase with approval gates.

## Agent Flow

```
(Code Reviewer + Security)
  ↓ [Parallel Reviews]
[APPROVAL GATE: User reviews findings and decides next steps]
  ↓
Review Complete
```

**Flow Type:** Parallel reviews with single approval gate

---

## Runtime Execution Boundary

- The builder runtime orchestrates review flow and gate decisions; it remains stack-agnostic.
- Stack-specific compile/test/lint/security execution must run in application runtime containers (or CI jobs built from those container definitions).
- Review gate decisions must reference evidence generated from those application runtime executions.

---

## Execution Steps

### Step 1: Parallel Reviews

**Execution Instructions:**

Execute these review agents **in parallel**:

#### 1a. Code Reviewer
1. **Activate Code Reviewer agent** by reading `agents/code-reviewer/SKILL.md`

2. **Read context:**
   - Source code (backend, frontend, and `{PRODUCT_ROOT}/neuron/` when AI scope exists)
   - Test suites
   - Application runtime validation outputs (test, lint, SAST, dependency scan reports)
   - Coverage artifacts and any explicit layer-skip justifications
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` (requirements and architecture)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - `agents/frontend-developer/references/ux-audit-ruleset.md` (for frontend UX compliance checks)
   - User stories with acceptance criteria

3. **Execute code review:**
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
   - Validate frontend UX rule-set compliance when UI code changed

4. **Produce code review report:**
   ```markdown
   # Code Quality Review Report

   Scope: [Specific feature / PR / Full codebase]
   Date: [Date]

   ## Summary
   - Assessment: [APPROVED / APPROVED WITH RECOMMENDATIONS / CONDITIONAL / REJECTED]
   - Files reviewed: [count]
   - Total issues: [count]

   ## Findings by Severity

   ### Critical Issues (must fix before approval)
   1. [Issue description]
      - Location: [file:line]
      - Impact: [explanation]
      - Recommendation: [how to fix]

   ### High Priority (should fix)
   [Similar format]

   ### Medium Priority (nice to have)
   [Similar format]

   ### Low Priority (optional improvements)
   [Similar format]

   ## Pattern Compliance
   - [ ] Clean architecture layers respected
   - [ ] SOLID principles followed
   - [ ] SOLUTION-PATTERNS.md patterns applied
   - [ ] Frontend UX rule-set checks passed (if frontend changed)
   - [ ] Naming conventions consistent
   - [ ] Error handling appropriate

   ## Evidence Summary
   - Runtime validation outputs reviewed: [list]
   - Coverage artifact path(s): [path / missing]
   - Layer exceptions / skips: [none / justified / missing justification]

   ## Test Quality
   - Unit test coverage: [percentage]%
   - Integration test coverage: [assessment]
   - E2E test coverage: [assessment]
   - Fast-layer proof for changed behavior: [adequate / missing / justified]
   - Test quality: [Good / Needs improvement]

   ## Acceptance Criteria
   - [ ] All user story ACs met
   - [ ] Edge cases handled
   - [ ] Error scenarios covered

   ## Code Metrics
   - Cyclomatic complexity: [Average: X, Max: Y]
   - Lines of code: [count]
   - Technical debt estimate: [hours/days]

   ## Recommendation
   [APPROVE / APPROVE WITH MINOR CHANGES / FIX CRITICAL FIRST / REJECT]

   ## Action Items
   1. [Priority action item]
   2. [Priority action item]
   ```

5. **Outputs:**
   - Code quality review report
   - List of findings with severity
   - Metrics and recommendations

#### 1b. Security Reviewer
1. **Activate Security agent** by reading `agents/security/SKILL.md`

2. **Read context:**
   - Source code (backend and frontend)
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 4.5 (authorization model)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - `{PRODUCT_ROOT}/planning-mds/security/` (threat model, if exists)

3. **Execute security review:**
   - **OWASP Top 10 scan:**
     1. A01 Broken Access Control
     2. A02 Cryptographic Failures
     3. A03 Injection
     4. A04 Insecure Design
     5. A05 Security Misconfiguration
     6. A06 Vulnerable and Outdated Components
     7. A07 Identification and Authentication Failures
     8. A08 Software and Data Integrity Failures
     9. A09 Security Logging and Monitoring Failures
     10. A10 Server-Side Request Forgery (SSRF)
   - Review authorization implementation (Casbin ABAC)
   - Check input validation and sanitization
   - Review secrets management (no hardcoded secrets)
   - Validate audit logging completeness
   - Review error messages (no information leakage)
   - Check HTTPS/TLS configuration
   - Validate CORS policies
   - Review dependency vulnerabilities

4. **Produce security review report:**
   ```markdown
   # Security Review Report

   Scope: [Specific feature / Full codebase]
   Date: [Date]

   ## Summary
   - Assessment: [PASS / PASS WITH RECOMMENDATIONS / CONDITIONAL PASS / FAIL]
   - Vulnerabilities found: [count]
   - Risk level: [Low / Medium / High / Critical]

   ## OWASP Top 10 Assessment

   ### 1. A01 Broken Access Control
   - Status: [PASS / FAIL]
   - Findings: [details]

   ### 2. A02 Cryptographic Failures
   - Status: [PASS / FAIL]
   - Findings: [details]

   ### 3. A03 Injection
   - Status: [PASS / FAIL]
   - Findings: [details]

   ### 4. A04 Insecure Design
   - Status: [PASS / FAIL]
   - Findings: [details]

   ### 5. A05 Security Misconfiguration
   - Status: [PASS / FAIL]
   - Findings: [details]

   ### 6. A06 Vulnerable and Outdated Components
   - Status: [PASS / FAIL]
   - Findings: [details]

   ### 7. A07 Identification and Authentication Failures
   - Status: [PASS / FAIL]
   - Findings: [details]

   ### 8. A08 Software and Data Integrity Failures
   - Status: [PASS / FAIL]
   - Findings: [details]

   ### 9. A09 Security Logging and Monitoring Failures
   - Status: [PASS / FAIL]
   - Findings: [details]

   ### 10. A10 Server-Side Request Forgery (SSRF)
   - Status: [PASS / FAIL]
   - Findings: [details]

   ## Vulnerability Findings

   ### Critical (fix immediately - actively exploitable)
   1. [Vulnerability description]
      - CVE/CWE: [reference]
      - Location: [file:line]
      - Exploit scenario: [how it could be exploited]
      - Remediation: [how to fix]

   ### High (fix before production)
   [Similar format]

   ### Medium (should fix)
   [Similar format]

   ### Low (best practice recommendations)
   [Similar format]

   ## Authorization Review
   - [ ] ABAC implementation correct
   - [ ] All endpoints protected
   - [ ] Per-endpoint authorization enforced
   - [ ] Server-side enforcement only
   - [ ] No client-side trust

   ## Audit & Compliance
   - [ ] All mutations create timeline events
   - [ ] Workflow transitions logged
   - [ ] User actions auditable
   - [ ] Sensitive data protected

   ## Secrets Management
   - [ ] No hardcoded secrets
   - [ ] Environment variables used
   - [ ] Secrets not in version control

   ## Recommendation
   [APPROVE / FIX CRITICAL / FIX HIGH / REJECT]

   ## Remediation Plan
   1. [Priority action]
   2. [Priority action]
   ```

5. **Outputs:**
   - Security review report
   - OWASP Top 10 assessment
   - Vulnerability findings with remediation
   - Compliance checklist
   - Save report under `{PRODUCT_ROOT}/planning-mds/security/reviews/` (for example: `security-review-YYYY-MM-DD.md`)

**Completion Criteria for Step 1:**
- [ ] Both reviews completed
- [ ] Reports generated

---

### Step 2: APPROVAL GATE (Review Results)

**Execution Instructions:**

1. **Present combined review results to user:**
   ```
   ═══════════════════════════════════════════════════════════
   Comprehensive Review Complete
   ═══════════════════════════════════════════════════════════

   CODE QUALITY REVIEW
   ─────────────────────────────────────────────────────────
   Reviewer: Code Reviewer Agent
   Status: [APPROVED / APPROVED WITH RECOMMENDATIONS / CONDITIONAL / REJECTED]

   Issues Found:
     - Critical: [count]
     - High: [count]
     - Medium: [count]
     - Low: [count]

   ✓ Pattern Compliance
     - Clean Architecture: [Yes/No]
     - SOLID Principles: [Yes/No]
     - SOLUTION-PATTERNS.md: [Yes/No]

   ✓ Test Coverage
     - Unit: [percentage]%
     - Integration: [assessment]
     - E2E: [assessment]

   ✓ Acceptance Criteria
     - [count]/[total] met
     - Edge cases: [Handled/Needs work]

   SECURITY REVIEW
   ─────────────────────────────────────────────────────────
   Reviewer: Security Agent
   Status: [PASS / PASS WITH RECOMMENDATIONS / CONDITIONAL / FAIL]

   Vulnerabilities Found:
     - Critical: [count]
     - High: [count]
     - Medium: [count]
     - Low: [count]

   ✓ OWASP Top 10
     - [count]/10 checks passed
     - Failed checks: [list]

   ✓ Authorization
     - ABAC implementation: [Correct/Issues found]
     - Endpoint protection: [Complete/Incomplete]

   ✓ Audit & Compliance
     - Timeline events: [Yes/No]
     - Secrets management: [Secure/Issues found]

   ═══════════════════════════════════════════════════════════
   Detailed Reports:
   - Code Quality Review: [link/location]
   - Security Review: [link/location]
   ═══════════════════════════════════════════════════════════
   ```

2. **Compute gate state from combined findings:**
   ```
   total_critical = code_critical + security_critical
   total_high = code_high + security_high
   total_medium = code_medium + security_medium
   total_low = code_low + security_low

   IF required_runtime_evidence_missing:
     STATUS: ❌ BLOCKED
     OPTIONS: ["Generate Missing Evidence", "Reject"]
     APPROVE_ENABLED: false

   ELSE IF total_critical > 0:
     STATUS: ❌ BLOCKED
     OPTIONS: ["Fix Critical", "Reject"]
     APPROVE_ENABLED: false

   ELSE IF total_high > 0:
     STATUS: ⚠️ WARNING
     OPTIONS: ["Fix All High (Recommended)", "Approve with Justification", "Reject"]
     APPROVE_ENABLED: true (requires justification)

   ELSE:
     STATUS: ✓ ACCEPTABLE
     OPTIONS: ["Approve", "Fix Issues Anyway", "Reject"]
     APPROVE_ENABLED: true
   ```

3. **Present approval checklist:**
   ```
   Review Approval Checklist:
   - [ ] No critical code quality issues
   - [ ] No critical security vulnerabilities
   - [ ] High-severity issues fixed OR approved with mitigation justification
   - [ ] OWASP Top 10 compliance acceptable
   - [ ] SOLUTION-PATTERNS.md followed
   - [ ] Test/scan evidence from application runtime containers attached
   - [ ] Coverage/test evidence includes artifact paths and any layer exceptions are justified
   - [ ] Authorization correctly implemented
   - [ ] Audit logging complete
   ```

4. **Present gate options by state:**
   - **If BLOCKED (critical findings exist):**
     - Options: `"fix critical"`, `"reject"`
     - Do not present any approve option.
   - **If WARNING (no critical, one or more high):**
     - Options: `"fix all high"`, `"approve with justification"`, `"reject"`
   - **If ACCEPTABLE (no critical/high):**
     - Options: `"approve"`, `"fix issues anyway"`, `"reject"`

5. **Handle user response:**
   - **If "fix critical":**
     - Identify critical issues (code + security)
     - Developers fix critical issues
     - Return to Step 1 (re-run reviews)

   - **If "fix all high" or "fix issues anyway":**
     - Identify selected issues
     - Developers fix issues
     - Return to Step 1 (re-run reviews)

   - **If "approve with justification":**
     - Capture explicit mitigation justification for remaining high issues
     - Log decision and mitigation plan
     - Proceed to Step 3 (Review Complete)

   - **If "approve":**
     - Proceed to Step 3 (Review Complete)

   - **If "reject":**
     - Capture feedback
     - Return to implementation
     - Full rebuild required

   - **If user input is not in the current state's allowed options:**
     - Do not transition
     - Re-present current state and allowed options

5. **Machine-readable gate state:**

   Orchestrators must be able to programmatically determine gate state:

   ```json
   {
     "gate": "review",
     "status": "blocked" | "warning" | "acceptable",
     "findings": {
       "code_quality": {
         "critical": 0,
         "high": 1,
         "medium": 2,
         "low": 3
       },
       "security": {
         "critical": 0,
         "high": 0,
         "medium": 1,
         "low": 2
       }
     },
     "totals": {
       "critical": 0,
       "high": 1,
       "medium": 3,
       "low": 5
     },
     "can_approve": true,
     "requires_justification": true,
     "available_actions": ["fix_all_high", "approve_with_justification", "reject"],
     "blocking_issues": []
   }
   ```

**Gate Criteria:**
- [ ] Both reviews completed
- [ ] Combined critical issues = 0 before approval is enabled
- [ ] Any high-issue approval includes explicit mitigation justification
- [ ] User decision logged with rationale when required

---

### Step 3: Review Complete

**Execution Instructions:**

Present completion summary based on user decision:

**If Approved:**
```
═══════════════════════════════════════════════════════════
Review Complete - APPROVED ✓
═══════════════════════════════════════════════════════════

Code Quality: [Status]
  - Critical issues: [count] (all fixed)
  - Pattern compliance: ✓
  - Test coverage: [percentage]%

Security: [Status]
  - Critical vulnerabilities: [count] (all fixed)
  - OWASP Top 10: [passed count]/10
  - Authorization: ✓

User Decision: APPROVED

═══════════════════════════════════════════════════════════
Next Steps:
═══════════════════════════════════════════════════════════

Code is approved for:
1. Merge to main branch
2. Deployment to staging/production
3. Release to users

Optional:
- Address medium/low priority findings in future iterations
- Update documentation
- Run "document" action if needed

Review approved! ✓
═══════════════════════════════════════════════════════════
```

**If Fix Required:**
```
═══════════════════════════════════════════════════════════
Review Complete - FIX REQUIRED
═══════════════════════════════════════════════════════════

Issues to Fix:
  - Critical code issues: [count]
  - Critical security issues: [count]
  - High priority issues: [count]

User Decision: FIX [critical/all high] THEN RE-REVIEW

═══════════════════════════════════════════════════════════
Action Items:
═══════════════════════════════════════════════════════════

1. Fix identified issues (see reports for details)
2. Run review action again after fixes
3. Repeat until approval

Issues identified. Fix and re-review.
═══════════════════════════════════════════════════════════
```

---

## Validation Criteria

**Overall Review Action Success:**
- [ ] Code quality review completed
- [ ] Security review completed
- [ ] User reviewed findings
- [ ] User made explicit decision
- [ ] If approved: No critical issues remain
- [ ] If approved with high issues: Mitigation + justification recorded
- [ ] If fix required: Issues documented with remediation plan

---

## Prerequisites

Before running review action:
- [ ] Implementation completed (features or full codebase)
- [ ] Tests written and passing
- [ ] Code committed to version control
- [ ] SOLUTION-PATTERNS.md exists

---

## Review Severity Levels

### Code Review Severity
- **Critical:** Breaks architecture, causes bugs, violates core principles, prevents deployment
- **High:** Code smells, poor patterns, missing tests, maintainability issues
- **Medium:** Style issues, minor improvements, optimization opportunities
- **Low:** Suggestions, nice-to-haves, subjective improvements

### Security Review Severity
- **Critical:** Actively exploitable vulnerabilities (SQL injection, auth bypass, XSS, etc.)
- **High:** Potential vulnerabilities requiring specific conditions, significant security gaps
- **Medium:** Security weaknesses, defense-in-depth gaps, non-critical misconfigurations
- **Low:** Best practice recommendations, hardening opportunities

---

## Example Usage

### Scenario 1: Clean Review with Approval
```
User: "Run the review action on the customer feature"

[Step 1: Parallel reviews]
Code Reviewer:
  - No critical issues
  - 2 medium issues (naming conventions)
  - Test coverage: 87%
  - Recommendation: APPROVED WITH RECOMMENDATIONS

Security:
  - No vulnerabilities
  - OWASP Top 10: 10/10 passed
  - Authorization: Correct
  - Recommendation: PASS

[Step 2: Approval gate]
Agent Runtime: "Review complete.
  Code: APPROVED WITH RECOMMENDATIONS (2 medium issues)
  Security: PASS

  Do you want to take action? (approve/fix issues anyway/reject)"

User: "approve"

Agent Runtime: "Review approved! Code ready to merge."
```

### Scenario 2: Critical Security Issue
```
User: "Run the review action on order processing workflow"

[Step 1: Parallel reviews]
Code Reviewer:
  - 1 high issue (missing error handling)
  - Recommendation: APPROVED WITH HIGH-PRIORITY FIXES

Security:
  - 1 CRITICAL issue (SQL injection vulnerability in search)
  - 2 high issues (missing authorization checks)
  - Recommendation: FIX CRITICAL

[Step 2: Approval gate]
Agent Runtime: "Review complete.
  Code: APPROVED WITH RECOMMENDATIONS
  Security: FAIL (1 critical vulnerability)

  CRITICAL: SQL injection in customer search endpoint
  Location: CustomerController.cs:45
  Must fix before deployment!

  What action? (fix critical/reject)"

User: "fix critical"

Agent Runtime: "Fixing SQL injection vulnerability..."
[Backend Developer fixes using parameterized queries]

Agent Runtime: "Issue fixed. Running security review again..."
[Security re-reviews]

Agent Runtime: "Security review: WARNING. Critical issue resolved; 2 high issues remain.
  What action? (fix all high/approve with justification/reject)"

User: "approve with justification"

Agent Runtime: "Justification recorded. Review approved with mitigation plan."
```

---

## Related Actions

- **Before:** [build action](./build.md) or [feature action](./feature.md) - Implement first
- **After:** [document action](./document.md) - Document after approval
- **Part of:** [build action](./build.md) includes review as Phase 2

---

## Notes

- Review action can be run on any scope (feature, PR, full codebase)
- Both reviews run in parallel for efficiency
- Critical issues must be fixed before approval
- Review reports should be saved for tracking
- Reviews can be re-run after changes
- User has final decision on approval within gate constraints (agents recommend, user decides)
- Automated tools can supplement but not replace agent reviews

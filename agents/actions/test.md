# Action: Test

## User Intent

Develop comprehensive test suites and execute testing to ensure quality, coverage, and correctness of the implementation.

## Agent Flow

```
Quality Engineer
  ↓
[SELF-REVIEW GATE: Validate test quality and coverage]
  ↓
[QUALITY GATE: Coverage and pass-rate thresholds]
  ↓
Test Complete
```

**Flow Type:** Single agent with quality gate

---

## Runtime Execution Boundary

- The builder runtime orchestrates test planning and gate decisions; it remains stack-agnostic.
- All test execution (unit, integration, E2E, performance) must run in application runtime containers (or CI jobs built from those container definitions).
- Test coverage reports, pass/fail results, and performance baselines are produced by application runtime executions and cited as evidence in gates.
- Layer-by-layer evidence must include artifact paths when available; summary prose alone is not sufficient evidence for a passing gate.

---

## Execution Steps

### Step 1: Test Planning

**Execution Instructions:**

1. **Activate Quality Engineer agent** by reading `agents/quality-engineer/SKILL.md`

2. **Read context:**
   - User stories from `{PRODUCT_ROOT}/planning-mds/features/` (colocated in feature folders)
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 3 (acceptance criteria) and Section 4.4 (workflows)
   - `{PRODUCT_ROOT}/planning-mds/api/` (API contracts)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - Existing test code in the codebase

3. **Determine testing scope from user input:**
   - `unit` — unit tests only
   - `integration` — integration tests only
   - `e2e` — E2E tests only
   - `performance` — performance tests only
   - `feature:{slug}` — all test types for a specific feature
   - `all` — comprehensive test suite (default)

4. **Produce test plan:**
   ```markdown
   # Test Plan

   Scope: [scope from user input]
   Date: [Date]

   ## Story-to-Test Mapping
   | Story | Acceptance Criteria | Test Type | Test Case |
   |-------|-------------------|-----------|-----------|
   | F0001-S0001 | List shows paginated results | Integration | GET /api/customers returns paginated response |
   | F0001-S0001 | Empty state shows message | Component | CustomerList renders empty state |

   ## Test Types in Scope
   - [ ] Unit tests (business logic, services, validators)
   - [ ] Integration tests (API endpoints, database operations)
   - [ ] E2E tests (critical workflows, user journeys)
   - [ ] Performance tests (response times, throughput)

   ## Coverage Targets
   - Unit test coverage: ≥80% for business logic
   - Integration: All API endpoints covered
   - E2E: All critical workflows covered
   - Performance: Baselines established for key operations

   ## Evidence Artifacts
   - Coverage artifact path(s): [expected files]
   - Test execution report path(s): [expected files]
   - Layer exceptions / skips: [none or justification]

   ## Test Infrastructure
   - Test data fixtures needed: [list]
   - Mocks/stubs needed: [list]
   - Test environment requirements: [list]
   ```

**Completion Criteria for Step 1:**
- [ ] Test plan produced with story-to-test mapping
- [ ] Coverage targets defined
- [ ] Test infrastructure requirements identified

---

### Step 2: Test Implementation and Execution

**Execution Instructions:**

1. **Write test suites based on test plan:**

   **Unit Tests:**
   - Domain logic tests (entities, value objects, business rules)
   - Service layer tests (application services, validators)
   - Frontend component tests (render, interaction, state)
   - Frontend utility/hook tests
   - Each test follows arrange-act-assert structure
   - Each test has a descriptive name reflecting the scenario

   **Integration Tests:**
   - API endpoint tests (request → response validation)
   - Database integration tests (repository operations)
   - External service integration tests (with mocks for external systems)
   - Cover both happy paths and error scenarios per acceptance criteria

   **E2E Tests:**
   - Critical workflow tests (end-to-end user journeys)
   - Cross-tier tests (frontend → API → database → response)
   - Error path tests (validation failures, authorization denials)

   **Performance Tests (when in scope):**
   - API response time benchmarks
   - Database query performance benchmarks
   - Frontend render performance (Core Web Vitals when applicable)
   - Establish baseline metrics

2. **Execute all test suites in application runtime containers:**
   - Run unit tests
   - Run integration tests
   - Run E2E tests
   - Run performance benchmarks (when in scope)
   - Capture all output as evidence

3. **Generate coverage and quality reports:**
   - Code coverage report (line, branch, function)
   - Test pass/fail summary
   - Performance baseline report (when applicable)
   - Identify coverage gaps
   - Record artifact paths for each executed layer

**Completion Criteria for Step 2:**
- [ ] All planned test suites written
- [ ] Tests executed in application runtime containers
- [ ] Coverage reports generated
- [ ] Pass/fail results captured
- [ ] Artifact paths recorded for executed layers

---

### Step 3: SELF-REVIEW GATE (Test Quality)

**Execution Instructions:**

Quality Engineer validates test quality before presenting results:

- [ ] All acceptance criteria from stories have corresponding tests
- [ ] Tests are independent and isolated (no shared state between tests)
- [ ] Tests have clear arrange-act-assert structure
- [ ] Tests have descriptive names (not test1, test2)
- [ ] No flaky tests (deterministic results)
- [ ] Unit tests run fast (< 1s each)
- [ ] Integration tests run reasonably fast (< 5s each)
- [ ] E2E tests cover the complete flow (not partial)
- [ ] Test data fixtures are realistic
- [ ] Mocks/stubs accurately represent real behavior
- [ ] Edge cases tested (empty lists, max values, nulls, boundary conditions)
- [ ] Error scenarios tested (validation failures, not-found, unauthorized)
- [ ] Required evidence artifacts exist and are linked
- [ ] If a fast layer is skipped, the reason is explicit and defensible
- [ ] If UI/runtime behavior changed, slower-layer-only proof is justified rather than assumed acceptable

**If any check fails:**
- Fix test quality issues
- Re-run self-review
- Repeat until passing

**Gate Criteria:**
- [ ] All test quality checks pass
- [ ] No flaky tests identified
- [ ] Coverage targets met or gaps justified

---

### Step 4: QUALITY GATE (Test Results)

**Execution Instructions:**

1. **Present test results to user:**
   ```
   ═══════════════════════════════════════════════════════════
   Test Execution Complete
   ═══════════════════════════════════════════════════════════

   Scope: [test scope]

   Unit Tests:
     - Total: [count]
     - Passing: [count]
     - Failing: [count]
     - Coverage: [percentage]%

   Integration Tests:
     - Total: [count]
     - Passing: [count]
     - Failing: [count]
     - Endpoints covered: [count]/[total]

   E2E Tests:
     - Total: [count]
     - Passing: [count]
     - Failing: [count]
     - Workflows covered: [count]/[total]

   Performance (if in scope):
     - API p95 latency: [value]
     - Database query p95: [value]
     - Frontend LCP: [value]

   Acceptance Criteria:
     - Stories covered: [count]/[total]
     - ACs with tests: [count]/[total]

   ═══════════════════════════════════════════════════════════
   ```

2. **Compute quality gate state:**

   **Gate Decision Logic:**
   ```
   IF required_artifacts_missing:
     STATUS: ❌ BLOCKED
     MESSAGE: "Required test evidence artifacts are missing."
     OPTIONS: ["Generate Missing Evidence", "Cancel"]
     APPROVE_ENABLED: false

   ELSE IF missing_required_layer_evidence:
     STATUS: ❌ BLOCKED
     MESSAGE: "Required test layers are missing or unjustified."
     OPTIONS: ["Add Missing Tests", "Cancel"]
     APPROVE_ENABLED: false

   ELSE IF failing_tests > 0:
     STATUS: ❌ BLOCKED
     MESSAGE: "Failing tests must be fixed."
     OPTIONS: ["Fix Failing Tests", "Cancel"]
     APPROVE_ENABLED: false

   ELSE IF coverage < target_coverage:
     STATUS: ⚠️ WARNING
     MESSAGE: "Coverage below target ([actual]% vs [target]%)."
     OPTIONS: ["Add More Tests (Recommended)", "Accept Current Coverage", "Cancel"]
     APPROVE_ENABLED: true (requires acceptance)

   ELSE:
     STATUS: ✓ PASSING
     MESSAGE: "All tests passing. Coverage targets met."
     OPTIONS: ["Accept", "Add More Tests", "Cancel"]
     APPROVE_ENABLED: true
   ```

3. **Machine-readable gate state:**

   Orchestrators must be able to programmatically determine gate state:

   ```json
   {
     "gate": "test_quality",
     "status": "blocked" | "warning" | "passing",
     "results": {
       "unit": { "total": 45, "passing": 45, "failing": 0, "coverage_pct": 87.5 },
       "integration": { "total": 23, "passing": 23, "failing": 0 },
       "e2e": { "total": 8, "passing": 8, "failing": 0 },
       "performance": { "api_p95_ms": 142, "db_p95_ms": 35 }
     },
     "artifacts": {
       "coverage": ["coverage/lcov.info"],
       "reports": ["test-results/unit.xml", "test-results/e2e.xml"]
     },
     "missing_artifacts": [],
     "layer_exceptions": [],
     "coverage_target_pct": 80.0,
     "coverage_actual_pct": 87.5,
     "acceptance_criteria": { "covered": 15, "total": 15 },
     "can_accept": true,
     "requires_acknowledgment": false,
     "available_actions": ["accept", "add_more_tests", "cancel"]
   }
   ```

4. **Handle user response:**
   - **If "Fix Failing Tests":**
     - Identify and fix failing tests
     - Re-run test execution
     - Return to Step 4

   - **If "Add More Tests (Recommended)" or "Add More Tests":**
     - Identify coverage gaps
     - Write additional tests
     - Re-run test execution
     - Return to Step 4

   - **If "Accept Current Coverage" or "Accept":**
     - Log acceptance
     - Proceed to Step 5

   - **If "Cancel":**
     - End test action

   - **If user input is not in current state's allowed options:**
     - Do not transition
     - Re-present current state and allowed options

**Gate Criteria:**
- [ ] Required artifacts exist before approval is enabled
- [ ] Required layers are present or explicitly justified
- [ ] All tests passing (0 failures)
- [ ] Coverage meets target or user explicitly accepts lower coverage
- [ ] User decision logged

---

### Step 5: Test Complete

**Execution Instructions:**

Present completion summary:

```
═══════════════════════════════════════════════════════════
Test Action Complete! ✓
═══════════════════════════════════════════════════════════

Test Plan:
  ✓ [count] stories mapped to test cases
  ✓ Coverage targets defined

Test Suites:
  ✓ Unit Tests: [count] tests, [coverage]% coverage
  ✓ Integration Tests: [count] tests, [endpoint_count] endpoints
  ✓ E2E Tests: [count] tests, [workflow_count] workflows
  ✓ Performance: [baseline established / not in scope]

Quality:
  ✓ All tests passing
  ✓ Coverage target: [met / accepted at X%]
  ✓ All acceptance criteria covered
  ✓ No flaky tests

Evidence:
  ✓ Coverage artifacts: [path(s)]
  ✓ Test reports: [path(s)]
  ✓ Layer exceptions: [none / listed]

═══════════════════════════════════════════════════════════
Next Steps:
═══════════════════════════════════════════════════════════

1. Run "review" action for code and security review
2. Run "document" action to update test documentation
3. Integrate tests into CI/CD pipeline
4. Monitor test suite health over time

Test suite complete! ✓
═══════════════════════════════════════════════════════════
```

---

## Validation Criteria

**Overall Test Action Success:**
- [ ] Test plan produced with story-to-test mapping
- [ ] All test suites written and executed in application runtime containers
- [ ] Unit test coverage ≥80% for business logic (or user-accepted lower target)
- [ ] Integration tests cover all API endpoints
- [ ] E2E tests cover critical workflows
- [ ] All tests passing
- [ ] Self-review gate passed (test quality validated)
- [ ] Quality gate passed (user accepted results)
- [ ] Coverage reports saved as evidence
- [ ] Artifact paths saved as evidence for executed layers

---

## Prerequisites

Before running test action:
- [ ] Implementation code exists (backend and/or frontend)
- [ ] User stories with acceptance criteria available in `{PRODUCT_ROOT}/planning-mds/features/`
- [ ] Test framework and tools configured in the project
- [ ] Application runtime containers can build and run

---

## Test Pyramid

```
         /  E2E   \        Fewest (critical paths only)
        / ──────── \
       / Integration\      Moderate (API + DB operations)
      / ──────────── \
     /    Unit Tests   \    Most (business logic, components)
    / ──────────────── \
```

- **Unit** — Individual functions, methods, components. Fast (< 1s). Dependencies mocked.
- **Integration** — API endpoints, database operations, service integrations. Medium speed (< 5s). Real test database, mocked external services.
- **E2E** — Complete user workflows. Slow (10-30s). Full stack running in containers.
- **Performance** — API latency, DB queries, UI rendering. Variable speed. Production-like environment.

---

## Example Usage

### Scenario 1: Test Single Feature
```
User: "Write tests for the customer management feature"

Agent Runtime: [Reads test.md]
Agent Runtime: "I'll create a test plan for customer management
  and implement all test types..."

[Step 1: Test planning]
  - Maps 5 customer stories to 23 test cases
  - Identifies: 12 unit, 7 integration, 4 E2E

[Step 2: Implementation and execution]
  Unit Tests:
    - CustomerService.CreateCustomer (valid, invalid, duplicate)
    - CustomerService.SearchCustomers (empty, filtered, paginated)
    - CustomerValidator (required fields, email format, phone format)
  Integration Tests:
    - POST /api/customers (201, 400, 409)
    - GET /api/customers (200, paginated, filtered)
    - GET /api/customers/:id (200, 404)
    - PUT /api/customers/:id (200, 400, 404, 409)
  E2E Tests:
    - Create new customer flow
    - Search and filter customers flow
    - Update customer information flow
    - View customer activity timeline

[Step 3: Self-review — all quality checks pass]

[Step 4: Quality gate]
Agent Runtime: "Test execution complete.
  - 23 tests written, 23 passing
  - Unit coverage: 92%
  - All 5 stories covered
  ✓ All targets met.
  Options: accept / add more tests / cancel"

User: "accept"

Agent Runtime: "Test suite complete for customer management!"
```

### Scenario 2: Failing Tests
```
User: "Run comprehensive testing on the order processing feature"

[Steps 1-2 execute]

[Step 3: Self-review — pass]

[Step 4: Quality gate]
Agent Runtime: "Test execution complete.
  - 31 tests written
  - 29 passing, 2 FAILING
  - Failures:
    1. OrderService.SubmitOrder: Expected 201, got 500
       (null reference in discount calculation)
    2. E2E CreateOrder: Timeout waiting for confirmation page

  ❌ Failing tests must be fixed.
  Options: fix failing tests / cancel"

User: "fix failing tests"

Agent Runtime: "Fixing 2 failing tests..."
[Quality Engineer investigates and fixes root causes]

Agent Runtime: "Re-running tests... All 31 passing.
  Coverage: 88%. All targets met.
  Options: accept / add more tests / cancel"

User: "accept"

Agent Runtime: "Test suite complete!"
```

### Scenario 3: Low Coverage Warning
```
User: "Test the notification feature"

[Steps 1-3 execute]

[Step 4: Quality gate]
Agent Runtime: "Test execution complete.
  - 14 tests written, 14 passing
  - Unit coverage: 65% (target: 80%)
  - 2 service methods not covered

  ⚠️ Coverage below target (65% vs 80%).
  Options: add more tests (recommended) / accept current coverage / cancel"

User: "add more tests"

Agent Runtime: "Adding tests for uncovered methods..."
[Writes additional tests, re-runs]

Agent Runtime: "Coverage now 84%. All targets met.
  Options: accept / add more tests / cancel"

User: "accept"

Agent Runtime: "Test suite complete!"
```

---

## Related Actions

- **Part Of:** [build action](./build.md) — testing is part of parallel implementation
- **Part Of:** [feature action](./feature.md) — testing is part of feature slice
- **Before:** [review action](./review.md) — review validates test quality
- **After:** Implementation — always test after building

---

## Notes

- Test action can be run standalone or as part of build/feature actions
- Focus on quality over quantity (good tests > many tests)
- Prefer fast, focused tests over slow, broad tests
- Follow the test pyramid: many unit, fewer integration, fewest E2E
- Do not approve behavior changes on slow-layer evidence alone when faster-layer coverage is expected and missing
- Keep tests maintainable (avoid brittle selectors, magic values)
- All test execution runs in application runtime containers, not the builder runtime
- Test code should follow the same quality standards as production code
- Run tests in CI/CD for continuous validation

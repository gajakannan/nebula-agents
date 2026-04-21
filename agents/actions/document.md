# Action: Document

## User Intent

Generate comprehensive technical documentation including API documentation, README files, runbooks, and developer guides based on implemented code and architecture.

## Agent Flow

```
Technical Writer
  ↓
[SELF-REVIEW GATE: Validate documentation quality and accuracy]
  ↓
[APPROVAL GATE: User reviews documentation]
  ↓
Document Complete
```

**Flow Type:** Single agent with review gate

---

## Runtime Execution Boundary

- The builder runtime orchestrates documentation flow and gates; it remains stack-agnostic.
- Documentation that references runtime behavior (API examples, CLI commands, health checks) should be verified against application runtime containers when possible.
- The Technical Writer inspects code artifacts but does not compile or execute them — any execution validation runs in application runtime containers.

---

## Execution Steps

### Step 1: Documentation Planning

**Execution Instructions:**

1. **Activate Technical Writer agent** by reading `agents/technical-writer/SKILL.md`

2. **Read context:**
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` (project overview, architecture)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
   - `{PRODUCT_ROOT}/planning-mds/architecture/decisions/` (ADRs)
   - `{PRODUCT_ROOT}/planning-mds/api/` (OpenAPI/API contracts)
   - `{PRODUCT_ROOT}/planning-mds/features/` (feature folders with stories)
   - Existing documentation in the project
   - Codebase: API controllers, database schema, configuration, Docker setup

3. **Determine documentation scope from user input:**
   - `api` — API reference documentation
   - `readme` — README files (root and component)
   - `runbooks` — operational runbooks
   - `guides` — developer guides
   - `feature:{slug}` — documentation for a specific feature
   - `all` — comprehensive documentation (default)

4. **Produce documentation plan:**
   ```markdown
   # Documentation Plan

   Scope: [scope from user input]
   Target Audience: [developers / operators / end users]
   Date: [Date]

   ## Documents to Create/Update
   | Document | Type | Status | Location |
   |----------|------|--------|----------|
   | Root README.md | README | Create/Update | ./README.md |
   | API Reference | API Docs | Create | docs/api/ |
   | Deployment Runbook | Runbook | Create | docs/runbooks/deployment.md |

   ## Source Material
   - API contracts: [list files]
   - Architecture: [list files]
   - Code: [list key directories]
   ```

**Completion Criteria for Step 1:**
- [ ] Documentation plan produced
- [ ] Target audience identified
- [ ] Source material identified

---

### Step 2: Documentation Generation

**Execution Instructions:**

Generate documentation based on the plan. All documentation follows the target audience's needs.

1. **API Documentation (when in scope):**
   - Generate or update OpenAPI specification from code
   - Write endpoint descriptions with purpose and behavior
   - Add request/response examples with realistic data
   - Document authentication and authorization requirements
   - Document error responses (codes, ProblemDetails format)
   - Add pagination, filtering, and sorting documentation
   - Include usage examples (curl or SDK)

2. **README Files (when in scope):**
   - **Root README.md:**
     - Project overview and purpose
     - Tech stack with versions
     - Prerequisites
     - Quick start guide (clone → run in 5 minutes)
     - Project structure explanation
     - Development setup
     - Testing instructions
     - Deployment guide (or link to runbook)
     - Contributing guidelines (or link to CONTRIBUTING.md)

   - **Component READMEs (if multiple services):**
     - Component-specific setup
     - Architecture within the component
     - Key files and directories

3. **Runbooks (when in scope):**
   - Deployment runbook (step-by-step with verification after each action)
   - Operational runbook (monitoring, troubleshooting)
   - Database migration runbook
   - Backup and recovery runbook
   - Each runbook includes rollback procedures

4. **Developer Guides (when in scope):**
   - Architecture overview with diagrams
   - Code organization guide
   - Development workflow (branch → PR → review → merge)
   - Testing guide (how to run, write, and debug tests)
   - Common tasks guide (add endpoint, add entity, add page)

**Completion Criteria for Step 2:**
- [ ] All planned documents generated
- [ ] Content is accurate and complete
- [ ] Examples are realistic

---

### Step 3: SELF-REVIEW GATE (Documentation Quality)

**Execution Instructions:**

Technical Writer validates documentation quality:

**Accuracy:**
- [ ] All code references match actual codebase (file paths, class names, endpoints)
- [ ] API examples match actual request/response shapes
- [ ] Environment variables match actual configuration
- [ ] Prerequisites are correct and complete
- [ ] Version numbers are current

**Completeness:**
- [ ] All endpoints documented (for API docs)
- [ ] Quick start guide covers clone-to-running
- [ ] Runbooks include verification and rollback steps
- [ ] Error scenarios documented
- [ ] Authentication/authorization documented

**Clarity:**
- [ ] No jargon without explanation
- [ ] Steps are numbered and sequential
- [ ] Code examples are syntax-highlighted
- [ ] Links are valid (internal cross-references)
- [ ] No TODO or placeholder text remains

**Testability:**
- [ ] Commands in docs can be copy-pasted and executed
- [ ] Quick start guide works on a fresh clone
- [ ] API examples return expected responses

**If any check fails:**
- Fix documentation quality issues
- Re-run self-review
- Repeat until passing

**Gate Criteria:**
- [ ] All accuracy checks pass
- [ ] All completeness checks pass
- [ ] All clarity checks pass
- [ ] No placeholder content remains

---

### Step 4: APPROVAL GATE (Documentation Review)

**Execution Instructions:**

1. **Present documentation results to user:**
   ```
   ═══════════════════════════════════════════════════════════
   Documentation Generation Complete
   ═══════════════════════════════════════════════════════════

   Scope: [documentation scope]
   Target Audience: [audience]

   Documents Created/Updated:
     - [Document Name] → [file path]
     - [Document Name] → [file path]
     - [Document Name] → [file path]

   Content Summary:
     - API Endpoints Documented: [count]
     - README Sections: [count]
     - Runbook Steps: [count]
     - Guide Sections: [count]
     - Code Examples: [count]

   Quality Check:
     - Accuracy: ✓
     - Completeness: ✓
     - Clarity: ✓

   ═══════════════════════════════════════════════════════════
   Please review the generated documentation.
   ═══════════════════════════════════════════════════════════
   ```

2. **Present approval options:**
   ```
   Documentation Review:
   - "approve" — Documentation is accurate and complete
   - "request changes" — Specify what needs to change
   - "reject" — Major issues, needs rewrite
   ```

3. **Handle user response:**
   - **If "approve":**
     - Proceed to Step 5 (Document Complete)

   - **If "request changes":**
     - Ask: "What changes are needed?"
     - Capture feedback
     - Apply changes to documentation
     - Return to Step 3 (re-run self-review)

   - **If "reject":**
     - Ask: "What are the major issues?"
     - Capture feedback
     - Return to Step 2 (regenerate documentation with feedback)

**Gate Criteria:**
- [ ] User has reviewed documentation
- [ ] User has made explicit decision
- [ ] Any requested changes have been applied

---

### Step 5: Document Complete

**Execution Instructions:**

Present completion summary:

```
═══════════════════════════════════════════════════════════
Document Action Complete! ✓
═══════════════════════════════════════════════════════════

Documentation Delivered:
  ✓ [Document type]: [file path]
  ✓ [Document type]: [file path]
  ✓ [Document type]: [file path]

Quality:
  ✓ Accuracy verified
  ✓ Completeness checked
  ✓ Examples tested
  ✓ Links validated

User Decision: APPROVED

═══════════════════════════════════════════════════════════
Next Steps:
═══════════════════════════════════════════════════════════

1. Commit documentation with code changes
2. Publish to documentation site (if applicable)
3. Share with team for onboarding
4. Keep documentation updated as code evolves

Documentation complete! ✓
═══════════════════════════════════════════════════════════
```

---

## Validation Criteria

**Overall Document Action Success:**
- [ ] Documentation plan produced
- [ ] All planned documents generated
- [ ] Self-review gate passed (accuracy, completeness, clarity)
- [ ] User reviewed and approved documentation
- [ ] No TODO or placeholder content remains
- [ ] All examples are realistic and testable

---

## Prerequisites

Before running document action:
- [ ] Implementation code exists (backend and/or frontend)
- [ ] Architecture artifacts available in `{PRODUCT_ROOT}/planning-mds/`
- [ ] API endpoints are stable and tested
- [ ] Application is deployable (for runbook verification)

---

## Documentation Best Practices

### API Documentation
- ✅ Use OpenAPI/Swagger standard
- ✅ Include realistic examples with actual field values
- ✅ Document error scenarios with ProblemDetails responses
- ✅ Keep in sync with code (regenerate when endpoints change)
- ❌ Don't use generic descriptions ("Gets data")
- ❌ Don't skip error documentation

### README Files
- ✅ Start with quick start (clone-to-running)
- ✅ Use clear headings and numbered steps
- ✅ Include working, copy-pasteable commands
- ❌ Don't assume prior knowledge of the stack
- ❌ Don't skip prerequisites

### Runbooks
- ✅ Use numbered step-by-step format
- ✅ Include verification steps after each major action
- ✅ Add troubleshooting tips for common failures
- ✅ Document rollback procedures
- ❌ Don't use ambiguous language ("usually works")
- ❌ Don't skip edge cases

### Developer Guides
- ✅ Explain the "why" not just "how"
- ✅ Use diagrams for architecture
- ✅ Link to related docs (don't duplicate)
- ❌ Don't duplicate README content
- ❌ Don't overwhelm with implementation details

---

## Example Usage

### Scenario 1: API Documentation
```
User: "Document the customer management API"

Agent Runtime: [Reads document.md]
Agent Runtime: "I'll generate API documentation for customer management..."

[Step 1: Planning]
  - Scope: API docs for customer endpoints
  - Source: 5 API endpoints, OpenAPI contract, SOLUTION-PATTERNS.md

[Step 2: Generation]
  - POST /api/customers — documented with create example
  - GET /api/customers — documented with pagination/filter examples
  - GET /api/customers/:id — documented with response example
  - PUT /api/customers/:id — documented with update example
  - DELETE /api/customers/:id — documented with soft-delete behavior

[Step 3: Self-review — all quality checks pass]

[Step 4: Approval gate]
Agent Runtime: "API documentation complete.
  - 5 endpoints documented
  - 10 request/response examples
  - Error codes and ProblemDetails format documented
  - Authentication requirements documented

  Please review. Options: approve / request changes / reject"

User: "approve"

Agent Runtime: "API documentation complete! Saved to docs/api/customers.md"
```

### Scenario 2: Complete Documentation Suite
```
User: "Generate all documentation for the application"

[Step 1: Planning]
  - Scope: all (API, README, runbooks, guides)
  - 14 documents planned

[Step 2: Generation]
  - Root README.md (overview, quick start, structure)
  - {PRODUCT_ROOT}/engine/README.md (backend setup, architecture)
  - {PRODUCT_ROOT}/experience/README.md (frontend setup, components)
  - docs/api/ (all endpoints)
  - docs/runbooks/ (deployment, operations, migrations)
  - docs/guides/ (architecture, development, testing)

[Step 3: Self-review — pass]

[Step 4: Approval]
Agent Runtime: "14 documentation files generated. Review?"

User: "request changes — add troubleshooting section to deployment runbook"

Agent Runtime: "Adding troubleshooting section..."
[Updates runbook, re-runs self-review]

Agent Runtime: "Updated. Review again?"

User: "approve"

Agent Runtime: "Documentation suite complete!"
```

### Scenario 3: Feature-Scoped Documentation
```
User: "Document the task management feature"

[Step 1: Planning]
  - Scope: feature:task-management
  - Source: 8 stories, 6 API endpoints, feature STATUS.md

[Step 2: Generation]
  - Feature API reference (6 endpoints)
  - Feature user guide (task CRUD + assignment flow)
  - Updated root README with feature overview

[Step 3: Self-review — pass]

[Step 4: Approval]
Agent Runtime: "Feature documentation ready. Review?"

User: "approve"

Agent Runtime: "Task management documentation complete!"
```

---

## Related Actions

- **After:** [build action](./build.md) or [feature action](./feature.md) — document after building
- **With:** [blog action](./blog.md) — docs for reference, blogs for narrative
- **Continuous:** Update docs when code changes

---

## Notes

- Documentation should be versioned with code
- Keep docs close to code (co-located when possible)
- Automate API doc generation from code annotations when available
- Test all commands and examples in docs before finalizing
- Consider documentation as part of the Definition of Done
- Update docs in the same PR as code changes

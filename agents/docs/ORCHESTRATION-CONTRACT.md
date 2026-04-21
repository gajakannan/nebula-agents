# Orchestration Contract

This document defines the minimum execution contract for running this framework, whether the flow is executed by a human operator or an automated orchestrator.

The framework is orchestrator-agnostic and model-agnostic.
It can be used with any agent runtime that can read markdown contracts and follow file-based workflows.

## Operating Model

- **Framework session root:** `nebula-agents`. Orchestrators load role definitions, actions, and templates from `agents/` here. They do not copy `agents/` into the product repo.
- **Implementation target:** a sibling product repo resolved as `{PRODUCT_ROOT}` at session start (see `agents/docs/AGENT-USE.md` → Session Setup). All product-owned artifacts — `{PRODUCT_ROOT}/planning-mds/`, `{PRODUCT_ROOT}/engine/`, `{PRODUCT_ROOT}/experience/`, `{PRODUCT_ROOT}/neuron/`, and `{PRODUCT_ROOT}/scripts/kg/` — live under the product repo.
- **No build-time or runtime coupling** exists between `nebula-agents` and `{PRODUCT_ROOT}`. The connection is entirely process-level — the orchestrator knows to look left for framework guidance and right for product artifacts.
- **Tool-specific config files are optional.** Orchestrators must not depend on `.claude/settings.json`, `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, or any vendor-specific bootstrap file. The durable contract is the repository content itself.

## 0. Execution Modes

### 0.1 Manual Mode (Initial Public Preview)

- A human operator executes action files and role guides directly.
- The manual operator must still enforce all required gates and approval decisions.
- Evidence capture is required; follow `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`.

### 0.2 Automated Mode (Future)

- An automated orchestrator may run the same contracts.
- Automated execution must satisfy all requirements in this document.
- Replacing manual flow with automation must not weaken gate, approval, boundary, or audit requirements.

## 1. Action Discovery

- Discover available user-facing actions from `agents/actions/README.md`.
- Each action definition lives in `agents/actions/<action>.md`.

## 2. Role Activation

- When an action requires a role, load `agents/<role>/SKILL.md`.
- Use role scope/boundaries exactly as specified.
- Do not merge role responsibilities unless the action explicitly does so.

## 3. Intent Routing

- Map user intent to an action definition.
- If intent is ambiguous, request clarification before execution.
- Execute action steps in defined order, including sequential and parallel stages.

## 4. Inputs and Outputs

- Required planning inputs come from `{PRODUCT_ROOT}/planning-mds/`.
- Generic templates and references come from `agents/templates/` and `agents/**/references/`.
- Output artifacts must be written to the paths defined by each action.

## 5. Approval and Review Gates

- For each approval gate, present the gate summary and capture an explicit user decision.
- Route execution based on that decision (`approve`, `fix`, `reject`, etc.).
- Never skip required gates.

## 6. Boundary Enforcement

- Treat `agents/` as generic framework content.
- Treat `{PRODUCT_ROOT}/planning-mds/` as solution-specific content.
- Do not introduce solution-specific requirements into `agents/`.

## 7. Failure Handling

### 7.1 Failure Classification

Orchestrators must distinguish between failure types and apply appropriate handling strategies:

**Transient Failures (Retry Eligible):**
- Network timeouts communicating with agents
- Temporary resource unavailability (file locks, API rate limits)
- Agent process crashes without data corruption
- Recoverable validation failures (e.g., missing optional field)

**Permanent Failures (No Retry):**
- Invalid action specification (action file malformed)
- Missing required role definition (SKILL.md not found)
- Schema validation failures (required artifact fields missing)
- Authorization failures (agent lacks required permissions)
- User cancellation requests

**Partial Failures (Selective Retry):**
- Multi-agent parallel execution where subset fails
- Multi-step action where intermediate step fails
- Gate rejection requiring rework of specific artifacts

---

### 7.2 Agent Execution Failures

#### Timeout Handling

**Recommended Timeouts by Agent Type:**
- Product Manager: 10 minutes
- Architect: 15 minutes
- Backend/Frontend/AI Developer: 30 minutes (code generation is slow)
- Quality Engineer: 20 minutes (test execution)
- Code Reviewer: 10 minutes
- Security: 10 minutes
- DevOps: 15 minutes
- Technical Writer: 10 minutes

**On Timeout:**
1. Terminate agent execution gracefully
2. Log timeout event with agent ID, action, and duration
3. Preserve any partial artifacts created (do not delete)
4. Present user with options:
   - **Retry** - Run agent again with same inputs
   - **Extend timeout** - Retry with longer timeout (useful for complex tasks)
   - **Skip** - Continue without this agent's output (if optional)
   - **Cancel** - Abort entire action

---

#### Invalid Output Handling

**Validation Requirements:**
- All agent outputs must be validated against expected schema
- Validate artifact completeness (required sections, fields)
- Validate artifact format (valid markdown, JSON, YAML, code syntax)
- Validate cross-references (links to other artifacts are valid)

**On Invalid Output:**
1. Run validation checks on agent output
2. If validation fails:
   - Collect all validation errors with specific locations
   - Re-invoke agent with error feedback in prompt:
     ```
     Previous output was invalid. Errors found:
     - Missing required section: "3.2 Personas"
     - Invalid JSON in line 45: unexpected token
     - Broken reference: Link to non-existent story F0001-S0099

     Please correct these issues and regenerate output.
     ```
3. Retry up to **2 times** with error feedback
4. If still invalid after 2 retries:
   - Save invalid output to `.artifacts-failed/` directory
   - Escalate to user with validation report
   - User options:
     - **Manual Fix** - User edits artifact directly
     - **Retry with different agent** - Try different model/capability tier
     - **Skip validation** - Accept output as-is (not recommended)

---

#### Missing Required Artifacts

**On Missing Artifacts:**
- Agent completes but expected output files do not exist
- Check action's "Output Contract" for required artifacts

**Handling:**
1. Fail immediately (no retry for missing artifacts)
2. Report to user:
   ```
   Agent <role> completed but required artifacts missing:
   - Expected: {PRODUCT_ROOT}/planning-mds/architecture/data-model.md
   - Expected: {PRODUCT_ROOT}/planning-mds/api/customers.yaml

   This indicates an agent execution issue.
   ```
3. User options:
   - **Retry agent** - Run again from scratch
   - **Cancel** - Abort action

---

### 7.3 Partial Completion Failures

#### Parallel Agent Execution

**Scenario:** Multiple agents run in parallel (e.g., Backend + Frontend + AI Engineer in `build` action)

**On Partial Failure:**
- Some agents succeed, others fail

**Handling Strategy:**
1. **Preserve successful work** - Do not rollback or delete successful outputs
2. **Retry failed agents only** - Re-run only the agents that failed
3. **Do not proceed** - Block progression to next action step until ALL agents succeed
4. **Report status clearly:**
   ```
   Parallel execution results:
   ✅ Backend Developer - Success
   ❌ Frontend Developer - Failed (syntax error in generated code)
   ✅ Quality Engineer - Success

   Retrying Frontend Developer...
   ```

**Retry Limits:**
- Each failed agent gets **2 retry attempts**
- If agent fails after 2 retries:
  - Preserve other agents' work
  - Escalate to user for manual intervention

---

#### Sequential Step Failures

**Scenario:** Action has sequential steps (Step 1 → Step 2 → Step 3)

**On Step Failure:**
- Step N fails, but Steps 1 through N-1 succeeded

**Handling Strategy:**
1. **Stop execution** - Do not proceed to Step N+1
2. **Preserve completed work** - Keep outputs from Steps 1 through N-1
3. **Retry failed step** - Re-run Step N only (up to 2 times)
4. **Resume on success** - Continue from Step N+1 after successful retry
5. **Escalate on repeated failure** - After 2 retries, ask user:
   - **Retry again** - Manual override for more attempts
   - **Skip step** - Continue to next step (if step is optional)
   - **Cancel action** - Abort entire action

---

### 7.4 Gate Failure Handling

#### User Rejection at Approval Gate

**Scenario:** User reviews artifact and selects "Reject" or "Request Changes"

**Handling Flow:**
```
┌─────────────────────────────────┐
│ Agent produces artifact         │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│ Present to user at gate         │
│ Options: Approve / Changes / Reject │
└────────────┬────────────────────┘
             ↓
     ┌───────┴────────┐
     │                │
  Approve         Reject/Changes
     │                │
     ↓                ↓
  Continue    ┌──────────────────┐
              │ Capture feedback │
              └────────┬─────────┘
                       ↓
              ┌──────────────────┐
              │ Return to agent  │
              │ with feedback    │
              └────────┬─────────┘
                       ↓
              ┌──────────────────┐
              │ Agent revises    │
              └────────┬─────────┘
                       ↓
              ┌──────────────────┐
              │ Present again    │
              └──────────────────┘
```

**Implementation:**
1. **Capture user feedback** - Require user to provide reason for rejection:
   ```
   Why are you rejecting this artifact?
   [ User enters feedback: "Data model is missing Customer.Email field" ]
   ```

2. **Return to originating agent** - Re-invoke agent with rejection feedback:
   ```
   User rejected your output with feedback:
   "Data model is missing Customer.Email field"

   Please revise the artifact addressing this feedback.
   ```

3. **Iterate until approval** - Repeat revision → review loop
   - **No limit on iterations** - User controls when to approve
   - Each iteration logged with timestamp and feedback

4. **Allow user cancellation** - User can abandon action at any iteration

---

#### Quality Gate Failures

**Scenario:** Automated quality gate fails (e.g., test coverage < 80%, security scan finds critical issues)

**Handling by Gate Type:**

**Test Coverage Gate:**
```
Coverage: 65% (threshold: 80%)
❌ FAIL - Below threshold

Options:
1. Fix coverage - Return to developers to add tests
2. Lower threshold - Update quality requirements (requires justification)
3. Override - Proceed anyway (requires approval + reason)
```

**Security Gate:**
```
Security scan found 2 CRITICAL issues:
- SQL Injection vulnerability in CustomerController.cs:45
- Hardcoded secret in config/database.json:12

❌ BLOCK - Cannot proceed until resolved

Action: Returning to Backend Developer to fix issues.
```

**Handling:**
1. **Critical issues = Block** - Must be fixed, no override
2. **High issues = Warn** - User can approve only with explicit justification
3. **Medium/Low issues = Log** - Proceed but track for later

---

### 7.5 Retry Strategies

#### Exponential Backoff for Transient Failures

**For:** Network issues, rate limits, temporary unavailability

**Strategy:**
```python
def retry_with_backoff(agent_fn, max_retries=3):
    for attempt in range(max_retries):
        try:
            return agent_fn()
        except TransientError as e:
            if attempt == max_retries - 1:
                raise  # Final attempt failed

            wait_seconds = 2 ** attempt  # 1s, 2s, 4s
            log(f"Transient error: {e}. Retrying in {wait_seconds}s...")
            time.sleep(wait_seconds)
```

**Max Retries:** 3 attempts with backoff

---

#### Immediate Retry for Recoverable Errors

**For:** Validation failures with feedback, invalid output that can be corrected

**Strategy:**
- Retry immediately (no backoff) with error feedback
- Max 2 retries
- Each retry includes specific error messages to help agent correct

---

#### No Retry for Permanent Errors

**For:** Missing files, authorization failures, schema violations

**Strategy:**
- Fail immediately
- Report error to user
- Do not waste time retrying (will fail again)

---

### 7.6 Rollback Procedures

#### When to Rollback

**Rollback scenarios:**
- User explicitly requests rollback ("undo last action")
- Critical error detected that corrupts artifact state
- User cancels action mid-execution

**When NOT to rollback:**
- Partial failures in parallel execution (preserve successful work)
- Gate rejections (keep work for revision)
- Validation failures (keep for debugging)

---

#### Artifact Versioning for Rollback

**Implementation:**
1. **Before each action execution:**
   - Create snapshot of current `{PRODUCT_ROOT}/planning-mds/` state
   - Store in `.snapshots/<action>-<timestamp>/`
   - Include manifest of all files

2. **On rollback request:**
   - User selects snapshot to restore
   - Show diff: "This will revert 5 files, delete 3 new files"
   - Require confirmation
   - Restore from snapshot
   - Log rollback event

**Example snapshot structure:**
```
.snapshots/
├── build-2026-02-07-10-30-00/
│   ├── manifest.json            # List of files + checksums
│   ├── {PRODUCT_ROOT}/planning-mds/            # Full snapshot
│   ├── {PRODUCT_ROOT}/engine/                  # Generated code snapshot
│   └── {PRODUCT_ROOT}/experience/
└── plan-2026-02-07-09-15-00/
    └── ...
```

**Retention policy:**
- Keep last 10 snapshots per action
- Auto-delete snapshots older than 30 days
- User can manually delete to free space

---

### 7.7 Error Reporting Requirements

**On any failure, orchestrator must report:**

```
┌─────────────────────────────────────────────┐
│ EXECUTION FAILURE                           │
├─────────────────────────────────────────────┤
│ Action:       build                         │
│ Step:         3 (Frontend Developer)        │
│ Agent:        frontend-developer            │
│ Failed at:    2026-02-07 10:45:23 UTC      │
│ Duration:     12 minutes 34 seconds         │
├─────────────────────────────────────────────┤
│ Error Type:   ValidationError               │
│ Message:      Generated code has syntax errors │
├─────────────────────────────────────────────┤
│ Impacted Artifacts:                         │
│ - {PRODUCT_ROOT}/experience/src/components/CustomerList.tsx │
│   (syntax error at line 45)                │
├─────────────────────────────────────────────┤
│ Suggested Remediation:                      │
│ 1. Review error details above              │
│ 2. Retry with error feedback (recommended) │
│ 3. Edit file manually                      │
├─────────────────────────────────────────────┤
│ Options:                                    │
│ [Retry] [Manual Fix] [Skip] [Cancel]       │
└─────────────────────────────────────────────┘
```

**Log Requirements:**
- Write full error details to `logs/errors/<timestamp>.json`
- Include stack traces for debugging
- Include agent inputs/outputs (if not too large)
- Never log secrets or PII

---

### 7.8 Escalation to User

**Escalate to user when:**
- Retry limit exceeded (agent failed 3 times)
- Permanent error encountered (cannot be retried)
- Ambiguous situation (orchestrator doesn't know what to do)
- User input required for decision

**Escalation UI/UX:**
1. **Stop execution** - Pause action, do not proceed
2. **Present clear context:**
   - What failed?
   - Why did it fail?
   - What has been tried already?
3. **Provide actionable options:**
   - Always include: "Retry", "Cancel"
   - When applicable: "Manual Fix", "Skip", "Rollback"
4. **Explain consequences** of each option
5. **Wait for user decision** - Do not timeout or auto-proceed
6. **Log user decision** - Record choice and reason (if provided)

---

### 7.9 Failure Handling Compliance

**An orchestrator is compliant when:**
- ✅ It distinguishes transient vs permanent failures
- ✅ It retries transient failures with backoff (max 3 times)
- ✅ It retries invalid outputs with feedback (max 2 times)
- ✅ It preserves successful work in partial failures
- ✅ It implements gate rejection feedback loops
- ✅ It enforces quality gate blocking for critical issues
- ✅ It supports rollback with artifact snapshots
- ✅ It reports failures with impacted artifacts and remediation
- ✅ It escalates to user after retry exhaustion
- ✅ It logs all failures for debugging and auditing

**Non-compliant behaviors:**
- ❌ Silently swallowing errors without user notification
- ❌ Infinite retry loops without user intervention
- ❌ Rolling back successful work in partial failures
- ❌ Proceeding past critical quality gate failures
- ❌ Lacking rollback capability
- ❌ Generic error messages without actionable remediation

## 8. Auditability

- Keep execution traceable by referencing:
  - which action was run
  - which roles were activated
  - which artifacts were read/written
  - which approval decisions were made
- In manual mode, store evidence for each run using `agents/docs/MANUAL-ORCHESTRATION-RUNBOOK.md`.

## 9. Runtime Independence

This repository does not require a single vendor-specific orchestrator file to function.
Any orchestrator is compatible if it honors this contract and role/action definitions.

Examples of compatible execution models include Claude Code, OpenAI assistants,
custom in-house orchestrators, or manual human-driven execution of action files.

### 9.1 Container Execution Boundary

- Treat the builder runtime as orchestration-only and stack-agnostic.
- Execute stack-specific compile/test/lint/security steps in application runtime containers (or CI jobs built from those containers).
- Gate decisions must be based on recorded evidence from those stack-specific executions.

## 10. Action I/O Contract Matrix

The orchestrator must treat each action definition as executable contract source.
At minimum, it must satisfy the following action-level I/O requirements:

| Action | Contract Source | Required Inputs | Primary Outputs | Gate Handling |
|---|---|---|---|---|
| `init` | `agents/actions/init.md` | Project name, domain context, target users, initial entities | `{PRODUCT_ROOT}/planning-mds/` scaffold, `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`, `{PRODUCT_ROOT}/planning-mds/domain/glossary.md`, `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md` | No explicit approval gate; validate required artifacts exist |
| `plan` | `agents/actions/plan.md` | Existing `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`, domain/context inputs, user clarifications | Updated `BLUEPRINT.md`, planning artifacts (stories/personas/features/screens), architecture specs and contracts per action | Enforce all gates defined in action (including requirement and architecture approvals) |
| `build` | `agents/actions/build.md` | Approved planning + architecture artifacts, stories, API and pattern references | Production code, tests, deployment configs, build/review summaries | Enforce severity-based review/security gates (no critical override) and route on user decision |
| `feature` | `agents/actions/feature.md` | Feature-scoped stories + architecture/API context | Feature-scoped backend/frontend/AI changes and tests, feature review output | Enforce severity-based feature gate outcome (critical blocks approval) |
| `review` | `agents/actions/review.md` | Candidate implementation artifacts and applicable planning/architecture references | Code-quality and security review findings with remediation expectations | Enforce severity-based review gate outcome (critical blocks approval) |
| `validate` | `agents/actions/validate.md` | `{PRODUCT_ROOT}/planning-mds/` artifacts and consistency context | Validation report, gaps, and corrective actions | No skip of required validation checklist steps |
| `test` | `agents/actions/test.md` | Implemented code, story acceptance criteria, test strategy inputs | Test plan, executed results, defect reports, quality summary | Enforce stop/continue behavior specified by quality thresholds |
| `document` | `agents/actions/document.md` | Implemented features, API/contracts, operational context | Documentation artifacts (README/API/runbook/usage docs as scoped by action) | Apply review gate if defined by action; otherwise require completeness checks |
| `blog` | `agents/actions/blog.md` | Change context, release narrative inputs, evidence links | Dev log or technical blog artifacts | Apply quality checks defined in action before completion |

## 11. Contract Compliance Checklist

An orchestrator implementation is compliant when all are true:

- It maps user intent to the correct `agents/actions/<action>.md`.
- It loads required role guides from `agents/<role>/SKILL.md` at execution time.
- It requests missing required inputs instead of guessing.
- It writes outputs to action-specified artifact locations.
- It executes and records all gate decisions without silent bypass.
- It reports failures with impacted artifacts and next-step remediation.

## 12. Lifecycle Stages and Gate Activation

Lifecycle-stage declaration is split into:
- Policy contract in this document (human-readable)
- Machine-readable config in `lifecycle-stage.yaml` (execution source of truth)

### 12.1 Canonical Stage Source

- The current lifecycle stage must be declared in `lifecycle-stage.yaml` under `current_stage`.
- Stage names and required gate sets must be declared in `lifecycle-stage.yaml` under `stages`.
- Gate command definitions must be declared in `lifecycle-stage.yaml` under `gates`.
- CI and local validation execution must resolve required gates from this file.

### 12.2 Stage Intent

- `framework-bootstrap`:
  - Framework setup and boundary hardening.
  - Solution/application runtime remains placeholder.
- `planning`:
  - Planning artifacts are authored and reviewed.
  - Implementation/runtime gates remain non-strict where app runtime does not exist.
- `implementation`:
  - Application runtime artifacts exist.
  - Strict infra and strict security evidence gates are mandatory.
- `release-readiness`:
  - Public-release hardening and final gate evidence collection.
  - Strict infra/security gates remain mandatory.

### 12.3 Required Execution Model

- Execute required gates via `python3 agents/scripts/run-lifecycle-gates.py`.
- CI must run the same command and fail on any required gate failure.
- Changing lifecycle stage requires updating `lifecycle-stage.yaml` in version control.
- Gate evidence used for approval decisions must correspond to the currently declared stage.

## 13. Agent Context Loading

When activating an agent, load context in priority order. Each agent's `SKILL.md` defines its full input/output contract; this section provides the orchestrator with a compact routing table.

- **Tier 1 (Always):** Load before the agent starts. Mandatory regardless of scope.
- **Tier 2 (Feature-Scoped):** Load narrowed to the current feature or story. Skip artifacts for unrelated features.
- **Tier 3 (On Demand):** Load only when the agent's task specifically requires it (e.g., a reference guide for an unfamiliar pattern).

### 13.1 Context Manifest

| Agent | Tier 1 (Always) | Tier 2 (Feature-Scoped) | Tier 3 (On Demand) |
|-------|-----------------|-------------------------|-------------------|
| Product Manager | `BLUEPRINT.md` §0-2, `domain/` | — | `agents/product-manager/references/` |
| Architect | `BLUEPRINT.md` §0-3, `SOLUTION-PATTERNS.md` | Feature stories and acceptance criteria | `agents/architect/references/`, implementation agent SKILL.md files |
| Backend Developer | `SOLUTION-PATTERNS.md`, story file, `BLUEPRINT.md` §4 | Feature API endpoints, feature JSON schemas, feature ERD | `agents/backend-developer/references/` |
| Frontend Developer | `SOLUTION-PATTERNS.md`, story file, screen spec | Feature API endpoints, feature JSON schemas, UX audit ruleset | `agents/frontend-developer/references/` |
| AI Engineer | `SOLUTION-PATTERNS.md`, story file, `BLUEPRINT.md` §4 | Existing `{PRODUCT_ROOT}/neuron/` code for this feature | `agents/ai-engineer/references/` |
| Quality Engineer | Story file (acceptance criteria), `SOLUTION-PATTERNS.md` | Developer test code for this feature, runtime validation outputs | `agents/quality-engineer/references/` |
| DevOps | `SOLUTION-PATTERNS.md`, `BLUEPRINT.md` §4 (NFRs) | Existing Dockerfiles, compose files, deployment scripts | `agents/devops/references/` |
| Code Reviewer | Story file, `SOLUTION-PATTERNS.md`, code under review | Runtime validation outputs (build, test, lint, SAST), tracker docs (if planning changed) | `agents/code-reviewer/references/` |
| Security | `SOLUTION-PATTERNS.md`, `BLUEPRINT.md` §4.5, code under review | `{PRODUCT_ROOT}/planning-mds/security/` (threat model, policies), runtime scan outputs | `agents/security/references/` |
| Technical Writer | `BLUEPRINT.md`, `SOLUTION-PATTERNS.md` | Feature code and API contracts for docs scope | `agents/technical-writer/references/` |
| Blogger | Feature context (stories, STATUS.md, evidence) | Relevant code changes and review outputs | `agents/blogger/references/` |

All paths are relative to the repository root. `BLUEPRINT.md` refers to `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`; `SOLUTION-PATTERNS.md` refers to `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`. Section numbers (§) refer to BLUEPRINT.md top-level sections.

### 13.2 Feature-Scoped Narrowing

When an agent operates on a specific feature or story, apply these filters to avoid loading unrelated content:

- **BLUEPRINT.md:** Load only sections listed in the agent's tier-1 column, not the entire file.
- **API contracts (`{PRODUCT_ROOT}/planning-mds/api/`):** Load only endpoints touched by the current feature.
- **JSON schemas (`{PRODUCT_ROOT}/planning-mds/schemas/`):** Load only schemas for entities the current feature modifies.
- **ADRs (`{PRODUCT_ROOT}/planning-mds/architecture/decisions/`):** Load only ADRs referenced in the feature README or story files.
- **SOLUTION-PATTERNS.md:** Always load in full. This is institutional memory and must not be summarized or filtered.

### 13.3 Context Budget Guidance

When operating under context window constraints:

1. Tier 1 + tier 2 should fit within roughly 70% of available context, leaving 30% for agent output.
2. If tier 1 + tier 2 exceeds this budget, summarize BLUEPRINT.md sections (keep structure, compress detail). Never summarize SOLUTION-PATTERNS.md.
3. Prefer loading the story file verbatim over loading BLUEPRINT.md verbatim — acceptance criteria are the single source of truth for implementation agents.
4. When a feature references many ADRs, load the ADR title and decision (skip context/consequences sections) to conserve space.

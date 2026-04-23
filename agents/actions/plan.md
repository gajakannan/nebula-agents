# Action: Plan

## User Intent

Complete planning phase (Phase A + B) by defining product requirements,
technical architecture, and the feature's solution-ontology bindings with
mandatory approval and synchronization gates.

## Agent Flow

```
Product Manager (Phase A)
  ↓
[APPROVAL GATE: User reviews requirements]
  ↓
Architect (Phase B)
  ↓
[ONTOLOGY SYNC GATE: Feature mapping and canonical bindings aligned]
  ↓
[APPROVAL GATE: User reviews architecture]
  ↓
Ready for Build
```

**Flow Type:** Sequential with approval and synchronization gates

---

## Retrieval Contract

Retuned by `python3 {PRODUCT_ROOT}/scripts/kg/eval.py`; do not hand-edit without running eval.

```yaml
tier_defaults:
  plan:
    greenfield:      { start_tier: file-centric, max_auto_tier: 2 }
    refinement:      { start_tier: 2,            max_auto_tier: 3 }
    drift-reconcile: { start_tier: 3,            max_auto_tier: 4 }
```

- `python3 {PRODUCT_ROOT}/scripts/kg/lookup.py <feature-id>` is a first-pass scope resolver and retrieval aid, not an authoritative source of truth.
- Raw artifacts win on conflict: feature folder, ADRs, API contracts, schemas, and policy artifacts outrank KG output.
- Navigate instead of eager-loading: open linked raw artifacts on demand when the current gate needs detail or drift repair.

## Context Files

Load in this order when the work is feature-scoped:

1. `agents/ROUTER.md`
2. `agents/agent-map.yaml`
3. `agents/docs/AGENT-USE.md`
4. `agents/actions/plan.md`
5. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml`
6. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml`
7. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`
8. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/code-index.yaml`
9. `{PRODUCT_ROOT}/planning-mds/knowledge-graph/coverage-report.yaml`
10. `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/**` when the feature folder exists

## On-Demand Paths

- `{PRODUCT_ROOT}/planning-mds/api/<openapi-spec>.yaml`
- `{PRODUCT_ROOT}/planning-mds/security/authorization-matrix.md`
- `{PRODUCT_ROOT}/planning-mds/security/policies/policy.csv`
- `{PRODUCT_ROOT}/planning-mds/knowledge-graph/*.yaml` beyond what `lookup.py` already returned
- `agents/<role>/references/**` only after a matching `agents/ROUTER.md` row

## Deliverables Contract

- PM artifacts: `PRD.md`, stories, personas, trackers, feature folder scaffolding, and feature mapping stubs
- Architect artifacts: data model, workflow design, API contracts, ADRs, authorization deltas, and completed KG bindings
- KG artifacts: `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`, plus `canonical-nodes.yaml` or `solution-ontology.yaml` only when shared semantics or ontology vocabulary changed
- Tracker artifacts: `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md`, `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md`, `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`, and generated story index as needed
- `feature-assembly-plan.md` is not a plan deliverable; it belongs to `agents/actions/feature.md` Step 0

## Ownership Contract

- `product-manager` owns `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`, stories, PRD, personas, and planning trackers
- `architect` owns `{PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml`, `{PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml`, ADRs, API contracts, schemas, and authorization artifacts
- Other roles flag drift but do not silently redefine canonical shared semantics

## Forbidden

- Hand-enumerating schemas, ADRs, or contract files when `lookup.py` output is already available
- Loading `agents/<role>/references/**` without a `agents/ROUTER.md` row match
- Treating lookup/KG mappings as authoritative over raw artifacts
- Non-architect roles editing `{PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml` or `{PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml`
- Proceeding past any gate without an explicit approval token
- Widening scope outside the current feature or declared plan target
- Climbing past `max_auto_tier` without recording `workstate.py escalate`

## Gate Contract

- `G1 CLARIFICATION` — Step 1.5 Requirements Clarification
- `G2 TRACKER SYNC (A)` — Step 1.75 Mandatory tracker synchronization before Phase A approval
- `G3 PHASE A APPROVAL` — Step 2 Phase A Review
- `G4 ONTOLOGY SYNC (B)` — Step 3.5 Mandatory ontology synchronization before Phase B approval
- `G5 PHASE B APPROVAL` — Step 4 Phase B Review

## Stop Conditions

- `validate.py` exits non-zero and cannot be repaired within the declared scope
- A required approval gate lacks an explicit approval token
- Scope drifts outside the declared feature or planning target
- A non-architect attempts to edit architect-owned canonical semantics
- `INSUFFICIENT_CONTEXT`: `lookup.py` returns empty scope for a declared in-scope node, or only ambiguous / low-confidence (`inferred`, `confidence < 0.5`) matches on a node about to be edited, or the workflow needs to climb past `max_auto_tier`; halt the current gate, invoke `workstate.py escalate <reason> --nodes ... --opened-raw ...`, open the raw artifacts, and do not proceed with weak matches

## Exit Validation

Run in this order:

1. `python3 agents/product-manager/scripts/validate-stories.py {FEATURE_PATH}`
2. `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/`
3. `python3 agents/product-manager/scripts/validate-trackers.py`
4. `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report` when KG changed
5. `python3 {PRODUCT_ROOT}/scripts/kg/validate.py`
6. `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --check-drift`
7. `python3 agents/scripts/validate_templates.py`

---

## Execution Steps

### Step 1: Execute Product Manager (Phase A)

**Execution Instructions:**

1. **Activate Product Manager agent** by reading `agents/product-manager/SKILL.md`

2. **Read required context:**
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` (Sections 0-2 for baseline context)
   - `{PRODUCT_ROOT}/planning-mds/domain/` (domain glossary, if exists)
   - `{PRODUCT_ROOT}/planning-mds/knowledge-graph/` (shared ontology context, if present)

3. **Execute Product Manager responsibilities:**
   - Define vision and explicit non-goals
   - Create personas representing target users
   - Decompose vision into epics and features
   - Write user stories with clear acceptance criteria
   - Specify screen list and responsibilities
   - Map key workflows across screens
   - Produce ASCII screen layouts in the PRD `## Screen Layouts (ASCII)` section whenever the feature introduces or materially modifies a user-visible screen or multi-step flow (Desktop + one narrow variant minimum). Skip only when the feature has no UI surface; record the reason in the section.
   - Seed a minimal feature mapping stub in `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml` for any new or materially changed feature in scope

4. **Produce outputs:**
   - Update `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 3 (complete, no TODOs)
   - Create `{PRODUCT_ROOT}/planning-mds/examples/personas/*.md` (if detailed personas needed)
   - Create feature folders at `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/` with PRD.md, README.md, STATUS.md, GETTING-STARTED.md
   - Create stories colocated in feature folders as `F{NNNN}-S{NNNN}-{slug}.md`
   - Create or update a minimal feature mapping stub in `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`
   - Ensure `{PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md` exists (copy from `agents/templates/tracker-governance-template.md` if missing)
   - Update `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md` with new features
   - Update `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md` with sequence changes (`Now / Next / Later / Completed`)

5. **Validate Phase A outputs:**
   - [ ] Vision and non-goals documented
   - [ ] Personas defined
   - [ ] Features listed with MVP prioritization
   - [ ] User stories have acceptance criteria
   - [ ] Screen responsibilities specified
   - [ ] ASCII screen layouts present in `## Screen Layouts (ASCII)` for every UI-bearing feature (Desktop + narrow variant), or a written "No UI" justification if omitted
   - [ ] Minimal ontology stub exists for each touched feature (`id`, `path`, `status`, obvious dependencies/high-confidence affected nodes)
   - [ ] No invented business rules (all traced to user needs)
   - [ ] No TODOs remain in Section 3

**Phase A Outputs:**
- `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 3 (complete)
- `{PRODUCT_ROOT}/planning-mds/examples/personas/` (optional)
- `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/` (feature folders with PRD, README, STATUS, GETTING-STARTED, and story files)
- `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml` (minimal feature/story stub for touched scope)
- `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md` (feature index)
- `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md` (prioritization/sequence view)

---

### Step 1.5: CLARIFICATION GATE (Requirements Clarification)

**Execution Instructions:**

1. **Review Phase A outputs for underspecified areas:**

   Read through all Phase A deliverables and identify:
   - Vague acceptance criteria (no numbers, no specifics)
   - Ambiguous language ("should", "might", "probably", "easy", "fast", "secure")
   - Missing edge cases or error scenarios
   - Undefined dependencies
   - Unstated assumptions
   - Features without clear success criteria

2. **Identify specific issues:**

   Create a list of underspecified areas with specific questions:

   ```markdown
   ## Requirements Clarification Needed

   ### Vague Acceptance Criteria

   **Story:** "Customer search should be fast"
   **Issue:** "Fast" is not measurable
   **Questions:**
   - How fast is "fast"? (< 200ms? < 1s? < 5s?)
   - For how many results? (100? 1000? 10000?)
   - What's acceptable if it's slower?

   **Story:** "Users can upload documents"
   **Issues:** Missing specifications
   **Questions:**
   - What file types allowed? (PDF, images, Office docs, all?)
   - Max file size? (1MB? 10MB? 100MB?)
   - What happens if upload fails? (retry? error message?)
   - Where are files stored? (database? blob storage?)
   - Virus scanning required?

   ### Ambiguous Language

   **Story:** "Dashboard should be intuitive"
   **Issue:** "Intuitive" is subjective
   **Questions:**
   - What specific widgets/data on dashboard?
   - What actions can users take from dashboard?
   - What defines "success" for this dashboard?

   ### Missing Edge Cases

   **Feature:** "Customer list with pagination"
   **Questions:**
   - What happens with empty list (no customers)?
   - Default page size? (10? 20? 50?)
   - Max page size?
   - What happens on last page with < full page?

   ### Unstated Assumptions

   **Feature:** "Email notifications"
   **Questions:**
   - Who sends emails? (system? specific user?)
   - When are emails sent? (immediate? batched?)
   - What if email fails to send?
   - Unsubscribe option required?
   ```

3. **Ask user for clarifications:**

   Present the clarification questions to the user:

   ```
   ═══════════════════════════════════════════════════════════
   Requirements Clarification Needed
   ═══════════════════════════════════════════════════════════

   Phase A requirements have [count] underspecified areas that
   need clarification before proceeding to architecture design.

   [List questions by category]

   Please provide answers to these questions, or indicate if
   any should be deferred to architecture phase.
   ═══════════════════════════════════════════════════════════
   ```

4. **Update Phase A outputs with clarifications:**

   - Update user stories with specific, quantified acceptance criteria
   - Remove ambiguous language
   - Add edge cases and error scenarios
   - Document assumptions explicitly
   - Add dependencies to stories

5. **Validate clarifications are complete:**

   **Testability Check:**
   - [ ] All acceptance criteria are specific and measurable
   - [ ] No ambiguous words remain ("should" → "must", "fast" → "< 200ms")
   - [ ] All performance requirements quantified
   - [ ] Error scenarios specified for each story
   - [ ] Edge cases identified

   **Completeness Check:**
   - [ ] All dependencies documented
   - [ ] All assumptions explicit
   - [ ] File upload/download specs complete (types, sizes, errors)
   - [ ] Notification specs complete (when, who, how, failures)
   - [ ] Search/filter specs complete (fields, operators, performance)

**Anti-Patterns to Catch:**

Banned words that indicate vagueness:
- ❌ "should", "might", "probably", "usually", "generally"
- ❌ "easy", "simple", "intuitive", "user-friendly"
- ❌ "fast", "quick", "slow", "performant", "responsive"
- ❌ "secure", "safe", "protected" (without specifics)
- ❌ "scalable", "flexible", "robust" (without metrics)

Replace with:
- ✅ "must" (requirement), "may" (optional)
- ✅ Specific metrics ("< 200ms p95", "≥ 80% success rate")
- ✅ Explicit error handling ("show error: 'File too large'")
- ✅ Quantified criteria ("support 10,000 concurrent users")

**Gate Criteria:**
- [ ] All underspecified areas identified
- [ ] User provided clarifications
- [ ] Phase A outputs updated with specifics
- [ ] No ambiguous language remains
- [ ] All acceptance criteria testable
- [ ] Edge cases and errors documented

**If Clarifications Complete:**
- Proceed to Step 2 (Approval Gate)

**If User Defers Some Questions:**
- Document as "Architect to decide" with rationale
- Proceed to Step 2

---

### Step 1.75: TRACKER SYNC GATE (Mandatory)

**Execution Instructions:**

Before Phase A approval, synchronize and validate planning trackers:

1. Ensure tracker updates are complete:
   - `{PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md` exists and reflects required signoff governance
   - `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md` reflects feature inventory and paths
   - `{PRODUCT_ROOT}/planning-mds/features/ROADMAP.md` reflects current sequencing
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` feature/story status links resolve
   - `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml` contains a minimal stub for each touched feature

2. Regenerate generated tracker:
   - Run `python3 agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/`

3. Validate trackers and stories:
   - Run `python3 agents/product-manager/scripts/validate-stories.py {PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/` for each touched feature
   - Run `python3 agents/product-manager/scripts/validate-trackers.py`

4. If validation fails:
   - Fix tracker drift immediately
   - Re-run all validation commands until passing

**Gate Criteria:**
- [ ] Tracker governance contract exists
- [ ] Story index regenerated after story file changes
- [ ] Story validation passes
- [ ] Tracker validation passes
- [ ] Minimal feature mapping stub present for touched planning scope
- [ ] No stale links/paths/status mismatches across tracker docs

---

### Step 2: APPROVAL GATE (Phase A Review)

**Execution Instructions:**

1. **Present Phase A outputs to user:**
   ```
   ═══════════════════════════════════════════════════════════
   Phase A Complete - Requirements Definition
   ═══════════════════════════════════════════════════════════

   ✓ Vision & Non-goals
     - Vision: [1-2 sentence summary]
     - Non-goals: [count] explicit exclusions

   ✓ Personas
     - [count] personas created
     - Primary: [list primary personas]

   ✓ Features & Epics
     - [count] features defined
     - MVP scope: [list MVP features]
     - Future scope: [list deferred features]

   ✓ User Stories
     - [count] stories written
     - Acceptance criteria: All stories have testable criteria

   ✓ Screens
     - [count] screens specified
     - Key workflows: [list main workflows]

   ═══════════════════════════════════════════════════════════
   Review the following files:
   - {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md (Section 3)
   - {PRODUCT_ROOT}/planning-mds/examples/personas/ (if created)
   - {PRODUCT_ROOT}/planning-mds/features/REGISTRY.md (feature index)
   - {PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/ (feature folders with PRDs and stories)
   ═══════════════════════════════════════════════════════════
   ```

2. **Present approval checklist:**
   ```
   Phase A Approval Checklist:
   - [ ] Vision aligns with business goals
   - [ ] Non-goals are explicit and clear
   - [ ] Personas represent actual target users
   - [ ] Features are well-scoped (not too big or too small)
   - [ ] User stories have testable acceptance criteria
   - [ ] Screen responsibilities are clear
   - [ ] ASCII screen layouts present for UI-bearing features (Desktop + narrow variant) or "No UI" justified
   - [ ] No ambiguities or TODOs remain
   - [ ] Scope is realistic for MVP
   ```

3. **Ask user for approval:**
   ```
   Do you approve Phase A (Requirements)?

   Options:
   - "approve" - Proceed to Phase B (Architecture)
   - "reject" - Provide feedback and iterate on Phase A
   - "request changes" - Specify what needs to change
   ```

4. **Handle user response:**
   - **If "approve":**
     - Log approval with timestamp
     - Proceed to Step 3 (Execute Architect)

   - **If "reject" or "request changes":**
     - Ask: "What feedback do you have? What should be changed?"
     - Capture feedback
     - Return to Step 1 with feedback context
     - Product Manager iterates based on feedback
     - Return to Step 2 for re-approval

**Gate Criteria:**
- [ ] Vision and non-goals clear
- [ ] Personas validated with stakeholders
- [ ] Features align with business goals
- [ ] User stories have testable acceptance criteria
- [ ] No TODOs or ambiguities remain
- [ ] User explicitly approves

---

### Step 3: Execute Architect (Phase B)

**Execution Instructions:**

1. **Activate Architect agent** by reading `agents/architect/SKILL.md`

2. **Read required context:**
   - `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Sections 0-3 (especially Section 3 - approved requirements)
   - `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md` (project-specific patterns to follow)
   - `{PRODUCT_ROOT}/planning-mds/domain/` (domain knowledge)
   - `{PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml`, `canonical-nodes.yaml`, and `feature-mappings.yaml` (if present)
   - `agents/architect/references/` (generic architecture best practices)

3. **Execute Architect responsibilities:**
   - Validate Phase A deliverables for technical feasibility
   - Define service/module boundaries
   - Design data model (entities, relationships, key attributes)
   - Create API contracts (endpoints, request/response schemas)
   - Define authorization model (roles, resources, actions, policies)
   - Specify workflow state machines and business rules
   - Document architectural decisions (ADRs)
   - Define non-functional requirements (performance, security, scalability)
   - Complete the target feature's ontology mapping in `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`
   - Add or update canonical shared nodes in `{PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml` when Phase B introduces reusable solution semantics
   - Update `{PRODUCT_ROOT}/planning-mds/knowledge-graph/solution-ontology.yaml` only if the ontology vocabulary itself must change

4. **Validate against SOLUTION-PATTERNS.md:**
   - [ ] Authorization follows Casbin ABAC pattern
   - [ ] Audit fields included in all entities
   - [ ] API endpoints follow `/api/{resource}/{id}` pattern
   - [ ] Errors use ProblemDetails pattern
   - [ ] Clean architecture layers respected
   - [ ] Workflow transitions are append-only
   - [ ] All mutations create timeline events

5. **Produce outputs:**
   - Update `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 4 (complete, no TODOs)
   - Create `{PRODUCT_ROOT}/planning-mds/architecture/decisions/*.md` (ADRs for key decisions)
   - Create `{PRODUCT_ROOT}/planning-mds/architecture/data-model.md` (if detailed ERD needed)
   - Create `{PRODUCT_ROOT}/planning-mds/api/*.yaml` (OpenAPI contracts for implementation)
   - Complete ontology bindings in `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`
   - Add canonical shared nodes in `{PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml` when needed

6. **Validate Phase B outputs:**
   - [ ] Service boundaries clear
   - [ ] Data model complete with relationships
   - [ ] API contracts defined for all user stories
   - [ ] Authorization model comprehensive
   - [ ] Workflow rules specified
   - [ ] NFRs measurable
   - [ ] ADRs written for key decisions
   - [ ] Feature ontology mapping completed
   - [ ] New shared semantics captured in canonical nodes when applicable
   - [ ] Architecture satisfies all Phase A requirements
   - [ ] SOLUTION-PATTERNS.md followed
   - [ ] No TODOs remain in Section 4

**Phase B Outputs:**
- `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` Section 4 (complete)
- `{PRODUCT_ROOT}/planning-mds/architecture/decisions/*.md` (ADRs)
- `{PRODUCT_ROOT}/planning-mds/architecture/data-model.md` (optional)
- `{PRODUCT_ROOT}/planning-mds/api/*.yaml` (OpenAPI contracts)
- `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml` (completed feature/story bindings)
- `{PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml` (when new shared semantics were introduced)

---

### Step 3.5: ONTOLOGY SYNC GATE (Mandatory)

**Execution Instructions:**

Before Phase B approval, synchronize and validate the solution ontology for the
touched planning scope:

1. Ensure feature mapping completion:
   - The target feature exists in `{PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml`
   - Story mappings exist when architecture decisions materially depend on canonical workflow, schema, or ADR links
   - `status`, `path`, and dependency references align with the feature folder and trackers

2. Ensure canonical shared semantics are captured correctly:
   - If the feature only reuses existing shared semantics, reference existing canonical nodes
   - If the feature introduces a new reusable workflow, workflow state, entity, schema grouping, or capability, add it to `{PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml`
   - Do not add new canonical nodes for feature-local details that remain owned by the PRD alone

3. Validate source precedence and ownership boundaries:
   - Raw feature, ADR, API, schema, and data-model artifacts remain the authority
   - Product Manager Phase A stubs are not left as the final semantic mapping when Phase B clarified the design
   - Architect-owned canonical bindings are complete before plan closeout

4. Validate ontology integrity:
   - Touched YAML files parse successfully
   - Referenced IDs exist
   - Referenced paths exist
   - No stale or contradictory bindings remain for the touched feature
   - Refresh the coverage report: `python3 {PRODUCT_ROOT}/scripts/kg/validate.py --write-coverage-report`
   - Run `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` — it MUST exit 0 before the gate passes (stale `coverage-report.yaml`, missing paths, unknown refs, or uncovered feature dirs will fail the gate)

**Gate Criteria:**
- [ ] Target feature has a completed ontology mapping
- [ ] New shared semantics captured in canonical nodes when applicable
- [ ] Mapping references resolve to real IDs and paths
- [ ] Ontology does not contradict raw planning/architecture artifacts
- [ ] Architect has finished ontology updates before plan closeout
- [ ] `python3 {PRODUCT_ROOT}/scripts/kg/validate.py` exits 0 (coverage report fresh, no integrity errors)

---

### Step 4: APPROVAL GATE (Phase B Review)

**Execution Instructions:**

1. **Present Phase B outputs to user:**
   ```
   ═══════════════════════════════════════════════════════════
   Phase B Complete - Architecture Design
   ═══════════════════════════════════════════════════════════

   ✓ Service Boundaries
     - [list modules/services defined]

   ✓ Data Model
     - [count] entities designed
     - Key relationships: [list main relationships]

   ✓ API Contracts
     - [count] endpoints specified
     - Endpoints: [list key endpoints]

   ✓ Authorization Model
     - Model: [ABAC/RBAC type]
     - Roles: [list roles]
     - Resources: [list key resources]

   ✓ Workflows
     - [count] state machines defined
     - Workflows: [list workflows]

   ✓ Architectural Decisions
     - [count] ADRs documented
     - Key decisions: [list major ADRs]

   ✓ Ontology Sync
     - Feature mapping: complete
     - Canonical nodes updated: [yes/no]
     - Shared semantics captured: [list key nodes or "no new shared nodes"]

   ✓ Non-Functional Requirements
     - Performance: [summary]
     - Security: [summary]
     - Scalability: [summary]

   ✓ Pattern Compliance
     - SOLUTION-PATTERNS.md: All patterns followed

   ═══════════════════════════════════════════════════════════
   Review the following files:
   - {PRODUCT_ROOT}/planning-mds/BLUEPRINT.md (Section 4)
   - {PRODUCT_ROOT}/planning-mds/architecture/decisions/ (ADRs)
   - {PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md (patterns followed)
   - {PRODUCT_ROOT}/planning-mds/knowledge-graph/feature-mappings.yaml
   - {PRODUCT_ROOT}/planning-mds/knowledge-graph/canonical-nodes.yaml (if changed)
   ═══════════════════════════════════════════════════════════
   ```

2. **Present approval checklist:**
   ```
   Phase B Approval Checklist:
   - [ ] Architecture satisfies all Phase A requirements
   - [ ] Data model is complete and normalized
   - [ ] API contracts are clear and RESTful
   - [ ] Authorization model is comprehensive
   - [ ] Workflow state machines are well-defined
   - [ ] NFRs are measurable and achievable
   - [ ] ADRs explain key architectural decisions
   - [ ] Ontology mapping is complete and aligned with the architecture
   - [ ] SOLUTION-PATTERNS.md patterns are followed
   - [ ] No technical debt or shortcuts
   - [ ] Architecture is implementable
   ```

3. **Ask user for approval:**
   ```
   Do you approve Phase B (Architecture)?

   Options:
   - "approve" - Architecture approved, ready for build action
   - "reject" - Provide feedback and iterate on Phase B
   - "request changes" - Specify what needs to change
   ```

4. **Handle user response:**
   - **If "approve":**
     - Log approval with timestamp
     - Proceed to Step 5 (Plan Complete)

   - **If "reject" or "request changes":**
     - Ask: "What feedback do you have? What should be changed?"
     - Capture feedback
     - Return to Step 3 with feedback context
     - Architect iterates based on feedback
     - Return to Step 4 for re-approval

**Gate Criteria:**
- [ ] Architecture satisfies all requirements
- [ ] Data model complete
- [ ] API contracts clear
- [ ] Authorization model sound
- [ ] Ontology sync complete
- [ ] Follows SOLUTION-PATTERNS.md
- [ ] NFRs measurable
- [ ] User explicitly approves

---

### Step 5: Plan Complete

**Execution Instructions:**

Present completion summary:

```
═══════════════════════════════════════════════════════════
Plan Action Complete! ✓
═══════════════════════════════════════════════════════════

Phase A (Product Manager):
  ✓ Vision defined
  ✓ [count] personas created
  ✓ [count] features planned (MVP scope)
  ✓ [count] user stories written
  ✓ [count] screens specified
  Status: APPROVED

Phase B (Architect):
  ✓ Data model designed ([count] entities)
  ✓ API contracts specified ([count] endpoints)
  ✓ Authorization model defined
  ✓ [count] workflows specified
  ✓ [count] ADRs documented
  ✓ Ontology mapping synchronized
  ✓ SOLUTION-PATTERNS.md followed
  Status: APPROVED

═══════════════════════════════════════════════════════════
Next Steps:
═══════════════════════════════════════════════════════════

Ready for implementation! You can now:

1. Run the "build" action to implement all MVP features
2. Run the "feature" action to implement one feature at a time
3. Run the "validate" action to double-check alignment

Recommended: Start with "feature" action for incremental delivery

Example: "Run the feature action for [specific feature name]"
═══════════════════════════════════════════════════════════
```

---

## Validation Criteria

**Overall Plan Action Success:**
- [ ] Phase A completed and approved by user
- [ ] Phase B completed and approved by user
- [ ] All outputs exist in {PRODUCT_ROOT}/planning-mds/
- [ ] No TODOs remain in BLUEPRINT.md Sections 3-4
- [ ] SOLUTION-PATTERNS.md patterns documented and followed
- [ ] Ontology mapping synchronized for touched feature scope
- [ ] Ready to proceed to build action

---

## Prerequisites

Before running plan action:
- [ ] `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` exists with Sections 0-2 (baseline context)
- [ ] `{PRODUCT_ROOT}/planning-mds/features/TRACKER-GOVERNANCE.md` exists (or will be created from `agents/templates/tracker-governance-template.md` during this run)
- [ ] `{PRODUCT_ROOT}/planning-mds/knowledge-graph/` exists or can be created during this run
- [ ] Domain glossary exists or can be created
- [ ] User is available to provide approvals at gates
- [ ] User has clarified business requirements

---

## Example Usage

### Scenario 1: Plan New Feature
```
User: "Run the plan action for customer management"

Agent Runtime: [Reads plan.md]
Agent Runtime: "I'll execute Step 1: Product Manager for Phase A..."

[Product Manager executes - defines personas, stories, screens for customer management]

Agent Runtime: "Phase A complete. Outputs:
  - 2 personas (Distribution Manager, Customer Relationship Manager)
  - 5 features (Customer CRUD, Search, Activity Timeline)
  - 15 user stories with acceptance criteria
  - 4 screens (List, Detail, Create/Edit, Search)

Do you approve Phase A? (approve/reject/request changes)"

User: "approve"

Agent Runtime: "Proceeding to Step 3: Architect for Phase B..."

[Architect executes - designs data model, API, authorization, workflows]

Agent Runtime: "Phase B complete. Outputs:
  - Data model: Customer entity with relationships
  - API: 7 endpoints defined
  - Authorization: ABAC policies for customer operations
  - Patterns followed: All SOLUTION-PATTERNS.md patterns applied

Do you approve Phase B? (approve/reject/request changes)"

User: "approve"

Agent Runtime: "Plan action complete! Ready for build action."
```

### Scenario 2: Iteration on Phase A
```
User: "Run the plan action for order processing workflow"

[Phase A executes]

Agent Runtime: "Phase A complete. Do you approve?"

User: "reject - the personas don't match our actual users"

Agent Runtime: "What feedback do you have? What should be changed?"

User: "Add a persona for Enterprise Account Managers, they're a key user"

Agent Runtime: "Understood. Iterating on Phase A with your feedback..."

[Product Manager updates personas]

Agent Runtime: "Phase A updated. New outputs:
  - 3 personas (added Enterprise Account Manager)
  - Stories updated to reflect enterprise account needs

Do you approve Phase A now? (approve/reject/request changes)"

User: "approve"

[Continues to Phase B...]
```

---

## Related Actions

- **Before:** [init action](./init.md) - Bootstrap project structure
- **Next:** [build action](./build.md) - Implement the plan (all features)
- **Next:** [feature action](./feature.md) - Implement incrementally (one feature)
- **Alternative:** [validate action](./validate.md) - Validate architecture before building

---

## Notes

- Plan action can be run for the entire project or individual features
- Approval gates are mandatory - cannot skip to Phase B without Phase A approval
- Product Manager seeds the minimal ontology stub in Phase A; Architect completes ontology bindings in Phase B
- If requirements change mid-project, re-run plan action for affected features
- Both agents use templates from `agents/templates/` for consistency
- Architect must reference SOLUTION-PATTERNS.md to ensure pattern compliance

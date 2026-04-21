# Blueprint Requirements

What makes a complete Phase A (Product Manager Mode) specification.

## Purpose

This document defines the completion criteria for Phase A work. Use this as a checklist before handing off to the Architect Agent for Phase B.

---

## Phase A Deliverables

Phase A work is documented in `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` sections 3.1 through 3.5.

### Section 3.1: Vision & Non-Goals

**Required Elements:**

✅ **Vision Statement**
- Clear, concise statement of what your product achieves
- Focuses on business outcome, not technical capabilities
- 2-3 sentences maximum
- Example: "Our platform helps operations teams manage customers and orders in one place, replacing spreadsheets and email workflows with structured data and automated reminders."

✅ **Success Criteria**
- 3-5 measurable outcomes that define success
- Examples:
  - Reduce order processing time by 50%
  - Increase order completion rate from 70% to 90%
  - Eliminate lost orders (100% tracked in system)
  - Improve customer satisfaction score from 3.5 to 4.5/5

✅ **Explicit Non-Goals**
- List of 5-10 things explicitly excluded from scope
- Each with brief reason (deferred to Phase 1, not needed, etc.)
- Examples:
  - ❌ External customer self-service portal (Phase 1)
  - ❌ Document versioning (Phase 1)
  - ❌ Advanced analytics dashboards (Future)
  - ❌ Mobile app (Future)

---

### Section 3.2: Personas

**Required: Minimum 3 Personas**

For each persona, define:

✅ **Persona Header**
- Name (e.g., "Sarah - Sales Operations Manager")
- Role/Title
- Priority (Primary | Secondary | Future)

✅ **Demographics & Background**
- Experience level (years in role/industry)
- Daily responsibilities (3-5 bullet points)

✅ **Goals & Motivations**
- Primary goals (what they want to achieve)
- Success metrics (how they measure success)

✅ **Pain Points**
- Current pain points (3-5 specific frustrations)
- Impact and frequency of each pain point

✅ **Jobs-to-be-Done**
- 3-5 jobs in format: "When [situation], I want to [action], so I can [outcome]"

**Minimum Personas for Generic MVP:**
1. Sales Operations Manager (Primary)
2. Order Operations Specialist (Primary)
3. Customer Success Manager (Secondary)

**Optional Personas:**
4. Program Manager
5. Admin

---

### Section 3.3: Epics & Features

**Required: All Core Epics Defined**

Features use 4-digit IDs (F0001, F0002, ...) and live in self-contained folders under `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/`. Each feature folder contains a PRD, README, STATUS, GETTING-STARTED, and colocated story files.

For each epic:

✅ **Epic Header**
- Epic ID (E1, E2, etc.)
- Epic Name
- Priority

✅ **Epic Statement**
- As a [persona]
- I want [high-level capability]
- So that [business value]

✅ **Business Objective**
- Clear statement of business goal
- Success metrics (2-3 measurable outcomes)

✅ **Scope & Boundaries**
- In scope: High-level capabilities (3-5 bullet points)
- Out of scope: Explicit exclusions with reasons

**Minimum Epics for Generic MVP:**
1. E1: Customer Relationship Management
2. E2: Customer 360 & Activity Timeline
3. E3: Order Intake Workflow
4. E4: Order Follow-up Pipeline
5. E5: Task Center + Reminders (optional MVP)

---

### Section 3.4: MVP User Stories

**Required: One Complete Vertical Slice (Minimum)**

Stories are colocated inside their feature folder: `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/F{NNNN}-S{NNNN}-{slug}.md`. There is no separate top-level stories directory.

For MVP, define at least one complete vertical slice with all CRUD operations.

**Minimum Requirement: Customer Vertical Slice**
- F0001-S0001: Create customer with basic information ✅
- F0001-S0002: View customer list with search/filtering ✅
- F0001-S0003: View customer 360 detail screen ✅
- F0001-S0004: Update customer information ✅
- F0001-S0005: Delete customer (soft delete) ✅
- F0001-S0006: View customer timeline events ✅

**Each Story Must Include:**

✅ **Story Header**
- Story ID, Epic, Title, Priority, Phase

✅ **User Story**
- As a [specific persona]
- I want [capability]
- So that [business value]

✅ **Acceptance Criteria**
- Happy path (Given/When/Then format)
- Edge cases and error scenarios
- Permission checks
- Audit trail requirements (if mutation)

✅ **Data Requirements**
- Required fields
- Optional fields
- Validation rules

✅ **Out of Scope**
- Explicit exclusions for this story

✅ **Definition of Done**
- Testable completion criteria

**Quality Bar:**
- Stories follow INVEST criteria
- Acceptance criteria are testable and complete
- No invented business rules (all rules are validated)

---

### Section 3.5: Screen Specifications

**Required: Minimum Screens for MVP**

For each screen:

✅ **Screen Header**
- Screen ID, Name, Type, Route

✅ **Purpose & Context**
- What is this screen for?
- Which personas use it?

✅ **Data Fields**
- Fields displayed on screen
- Field formats and validation

✅ **User Actions**
- Primary and secondary actions
- Permission requirements for each action

✅ **Navigation & Flow**
- Entry points (how users get here)
- Exit points (where they go from here)

**Minimum Screens for Generic MVP:**
1. Navigation Shell (top nav, side nav) ✅
2. Customer List (searchable table) ✅
3. Customer 360 (detail view with timeline) ✅
4. Create/Edit Customer Form ✅
5. Dashboard (optional MVP)

---

## Phase A Completion Checklist

Before handing off to Architect (Phase B), verify:

### Documentation Completeness

- [ ] All sections 3.1-3.5 in BLUEPRINT.md are complete
- [ ] No TODO or TBD placeholders remain
- [ ] All personas have detailed profiles
- [ ] All epics have clear business objectives
- [ ] At least one vertical slice of stories is complete
- [ ] All MVP screens are specified

### Quality Standards

- [ ] Vision statement is clear and business-focused
- [ ] Non-goals are explicit (at least 5 items)
- [ ] Personas are based on real user needs (not fictional)
- [ ] Stories follow INVEST criteria
- [ ] Acceptance criteria are testable
- [ ] No invented business rules (all validated with stakeholder)
- [ ] Audit trail requirements are documented for mutations
- [ ] Permission requirements are specified for all actions

### Validation

- [ ] Product Owner has reviewed and approved
- [ ] Domain expert has validated business rules
- [ ] No open questions remain (all answered or explicitly marked)
- [ ] Stakeholders agree on MVP scope

### Handoff Preparation

- [ ] Architect has been notified that Phase A is complete
- [ ] Summary of deliverables has been provided
- [ ] Product Manager is available for clarification questions
- [ ] BLUEPRINT.md is committed to git repository

---

## Common Completion Pitfalls

### ❌ Incomplete Acceptance Criteria
**Problem:** Stories have acceptance criteria but miss edge cases, errors, or permissions
**Fix:** Use `agents/templates/acceptance-criteria-checklist.md` to validate

### ❌ Technical Solutions in Stories
**Problem:** Stories specify implementation details (APIs, database, tech stack)
**Fix:** Focus on user-observable behavior, defer technical decisions to Architect

### ❌ Invented Business Rules
**Problem:** PM assumed business rules without validation
**Fix:** Review all stories for assumptions, validate with stakeholders

### ❌ Vague Screen Specifications
**Problem:** Screens described in general terms without specific fields or actions
**Fix:** Use `agents/templates/screen-spec-template.md` for detailed specifications

### ❌ Missing Non-Goals
**Problem:** Only documented what's included, not what's excluded
**Fix:** Explicitly list 5-10 non-goals with reasons

---

## Phase A to Phase B Handoff

### Handoff Meeting Agenda

1. **Vision Review** (5 min)
   - Present vision statement and success criteria
   - Confirm alignment with business strategy

2. **Persona Walkthrough** (10 min)
   - Review each primary persona
   - Highlight key pain points and jobs-to-be-done

3. **Epic Overview** (10 min)
   - Present each epic with business objectives
   - Confirm MVP vs Phase 1 prioritization

4. **Story Deep Dive** (20 min)
   - Walk through the complete vertical slice (Customer CRUD)
   - Highlight audit trail and permission requirements
   - Clarify any complex acceptance criteria

5. **Screen Specifications** (10 min)
   - Review key screens (Customer List, Customer 360)
   - Discuss navigation and user workflows

6. **Q&A** (15 min)
   - Answer Architect's clarification questions
   - Document any open items for follow-up

### Handoff Artifacts

Provide Architect with:
- ✅ `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` (sections 3.1-3.5 complete)
- ✅ `{PRODUCT_ROOT}/planning-mds/features/REGISTRY.md` (feature index)
- ✅ Feature folders with PRDs and stories (`{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/`)
- ✅ Link to all templates used (story, persona, epic, screen)
- ✅ Domain glossary (`{PRODUCT_ROOT}/planning-mds/domain/<domain>-glossary.md`)
- ✅ Contact info for follow-up questions

---

## Measuring Phase A Quality

### Quality Metrics

**Coverage:**
- Number of personas defined: Target ≥ 3
- Number of epics defined: Target ≥ 5
- Number of MVP stories: Target ≥ 20
- Number of screens specified: Target ≥ 5

**Completeness:**
- Stories with complete acceptance criteria: Target 100%
- Stories with audit trail requirements (if applicable): Target 100%
- Stories with permission checks: Target 100%
- Screens with data fields specified: Target 100%

**Quality:**
- Stories passing INVEST criteria: Target ≥ 90%
- Stories with no invented business rules: Target 100%
- Stories with edge cases documented: Target ≥ 80%

### Quality Review

Run validation before handoff:
```bash
# Validate all stories across feature folders
python agents/product-manager/scripts/validate-stories.py {PRODUCT_ROOT}/planning-mds/features/

# Generate index
python agents/product-manager/scripts/generate-story-index.py {PRODUCT_ROOT}/planning-mds/features/
```

---

## Version History

**Version 1.0** - 2026-01-26 - Initial blueprint requirements

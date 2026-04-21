---
template: feature-prd
version: 2.0
applies_to: product-manager
---

# Product Requirements Document (PRD) Template

Use this template to define a feature as a comprehensive PRD. Each feature lives in its own folder at `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/PRD.md`.

## Feature Header

**Feature ID:** [F0001, F0002, ...]
**Feature Name:** [Short descriptive name]
**Priority:** [Critical | High | Medium | Low]
**Phase:** [MVP | Phase 1 | Phase 2 | Future]
**Status:** [Draft | In Progress | Complete | Archived]

## Feature Statement

**As a** [persona]
**I want** [capability]
**So that** [business value]

## Business Objective

- **Goal:** [Measurable outcome]
- **Metric:** [How success is measured]
- **Baseline:** [Current state]
- **Target:** [Desired improvement]

## Problem Statement

- **Current State:** [Pain today]
- **Desired State:** [Target outcome]
- **Impact:** [Cost/time/quality impact]

## Scope & Boundaries

**In Scope:**
- [Capability 1]
- [Capability 2]

**Out of Scope:**
- [Explicit non-goal 1]
- [Explicit non-goal 2]

## Acceptance Criteria Overview

High-level acceptance criteria for the feature as a whole. Individual stories refine these into testable scenarios.

- [ ] [Feature-level criterion 1]
- [ ] [Feature-level criterion 2]
- [ ] [Feature-level criterion 3]

## UX / Screens

List screens and key interactions this feature introduces or modifies.

| Screen | Purpose | Key Actions |
|--------|---------|-------------|
| [Screen name] | [What it does] | [Primary user actions] |

**Key Workflows:**
1. [Workflow name] — [Brief description of steps]

## Data Requirements

**Core Entities:**
- [Entity]: [Purpose and key fields]

**Validation Rules:**
- [Rule 1]
- [Rule 2]

**Data Relationships:**
- [Entity A] → [Entity B]: [Relationship type and meaning]

## Role-Based Access

| Role | Access Level | Notes |
|------|-------------|-------|
| [Role] | [Create / Read / Update / Delete] | [Constraints] |

## Success Criteria

- [Measurable outcome 1]
- [Measurable outcome 2]

## Risks & Assumptions

- [Risk]
- [Assumption]
- [Mitigation]

## Dependencies

- [Dependency 1]
- [Dependency 2]

## Related Stories

Stories are colocated in this feature folder as `F{NNNN}-S{NNNN}-{slug}.md`.

- [F0001-S0001] - [Story title]
- [F0001-S0002] - [Story title]

## Rollout & Enablement (Optional)

- Training or documentation needs
- Rollout plan or feature flag notes

---

## Example Library

See `{PRODUCT_ROOT}/planning-mds/examples/features/` for project-specific feature examples.

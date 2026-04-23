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

## Screen Layouts (ASCII)

**Required when** this feature introduces or materially modifies a screen, a new zone/section, or a multi-step flow. Omit only for back-office / API-only features with no user-visible surface (state the reason explicitly, e.g. "No UI — integration job only").

Provide one ASCII layout per screen introduced or changed. For multi-breakpoint screens (dashboard, list, detail), include at minimum a Desktop variant and one narrow variant (Mobile or iPad). For flows that span screens, add a simple step-to-step ASCII showing screen transitions.

Conventions:
- Use box-drawing characters (`┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼ ─ │`) or `+ - |` — be consistent within a diagram.
- Label zones/regions (e.g. `NUDGE ZONE`, `KPI BAND`, `TASK CARD`) so the architect and frontend engineer can map components.
- Show primary controls (buttons, filters, tabs) inline in the diagram with `[Label]`.
- Mark dynamic content with placeholders (e.g. `{count}`, `{status}`) rather than baking in fake data.
- Annotate non-obvious interactions with footnotes below the diagram.

### [Screen Name] — Desktop

```text
┌─────────────────────────────────────────────────────────────┐
│  [Header / nav]                                              │
├─────────────────────────────────────────────────────────────┤
│  [Zone / primary content]                                    │
│  ...                                                         │
└─────────────────────────────────────────────────────────────┘
```

### [Screen Name] — Mobile / iPad

```text
┌──────────────────────┐
│  [Stacked layout]    │
└──────────────────────┘
```

Cross-reference: detailed per-screen specs (components, states, validation, accessibility) live in `{PRODUCT_ROOT}/planning-mds/screens/S-*.md`.

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

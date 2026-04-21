---
template: workflow-spec
version: 1.1
applies_to: architect
---

# Workflow Specification Template

Use this template to define a workflow/state machine for any domain process. Project-specific workflows live in `{PRODUCT_ROOT}/planning-mds/workflows/`.

## 1) Workflow Overview

**Workflow Name:** [Short name]
**Entity/Process:** [Entity or process]
**Purpose:** [Why this workflow exists]
**Primary Roles:** [Role A, Role B, Role C]

## 2) State Definitions

| State | Description | Type (Initial/Active/Terminal) | Can Transition Out? |
|------|-------------|-------------------------------|---------------------|
| Draft | [Description] | Initial | Yes |
| InReview | [Description] | Active | Yes |
| Approved | [Description] | Terminal | No |
| Rejected | [Description] | Terminal | No |

## 3) Transition Matrix

| From State | To State | Trigger | Preconditions | Validation Rules | Error on Failure |
|-----------|----------|---------|---------------|------------------|-----------------|
| Draft | InReview | Submit | [Required fields complete] | [Rule list] | 409 Conflict |
| InReview | Approved | Approve | [Reviewer assigned] | [Rule list] | 409 Conflict |
| InReview | Rejected | Reject | [Rejection reason provided] | [Rule list] | 409 Conflict |

## 4) Required Fields by State

- **Draft:** [fieldA, fieldB]
- **InReview:** [fieldC, fieldD]
- **Approved:** [fieldE]
- **Rejected:** [fieldF]

## 5) Role Permissions

- **Role A:** [Allowed transitions]
- **Role B:** [Allowed transitions]
- **Role C:** [Allowed transitions]

## 6) Audit & Timeline Requirements

- [ ] Log transition events (state change, user, timestamp)
- [ ] Capture reason/context for transitions

## 7) Notifications (Optional)

- **On Submit:** [Notification or task]
- **On Approve:** [Notification or task]
- **On Reject:** [Notification or task]

## 8) SLAs & Metrics (Optional)

- [Target response time or review window]
- [Escalation conditions]

## 9) Edge Cases & Exceptions

- [Edge case] → [Expected handling]

## 10) Open Questions

- [ ] [Question requiring stakeholder input]

---

## Example Library

See `{PRODUCT_ROOT}/planning-mds/workflows/` for project-specific workflow definitions.

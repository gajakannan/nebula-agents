---
template: screen-spec
version: 1.1
applies_to: product-manager
---

# Screen Specification Template

Use this template to describe UI screens in a domain-neutral way. Project-specific screens live in `{PRODUCT_ROOT}/planning-mds/screens/`.

## Screen Header

**Screen ID:** [S-001]
**Name:** [Screen Name]
**Type:** [List | Detail | Form | Dashboard]
**Route/URL:** [Logical route, e.g., `/records/:id`]

## Purpose & Context

- **Primary Users:** [Persona(s)]
- **Goal:** [What user accomplishes here]

## Primary Data

- [Field 1]
- [Field 2]
- [Field 3]

## UI Elements

- [Element 1]
- [Element 2]
- [Element 3]

## User Actions

| Action | UI Element | Result | Permission |
|--------|------------|--------|------------|
| Create | “New” button | Opens create form | CreateEntity |
| Edit | “Edit” button | Opens edit form | UpdateEntity |
| Delete | “Delete” button | Shows confirmation | DeleteEntity |

## Navigation & Flow

**Entry Points:**
- [Where users come from]

**Exit Points:**
- [Where users go next]

## States & Empty Cases

- **Empty State:** [No data]
- **Error State:** [Permission or load errors]
- **Loading State:** [Skeleton/spinner]

## Validation & Errors

- [Inline validation rules]
- [Global errors and fallbacks]

## Accessibility Notes

- [Keyboard navigation]
- [Screen reader labels]

---

## Example Library

See `{PRODUCT_ROOT}/planning-mds/examples/screens/` for project-specific screen examples.

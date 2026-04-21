---
template: entity-model
version: 1.1
applies_to: architect
---

# Entity Model Template

Use this template to define entities in a domain-neutral way. Project-specific entities and examples should live in `{PRODUCT_ROOT}/planning-mds/examples/`.

## 1) Entity Overview

**Entity Name:** [EntityName]
**Purpose:** [What this entity represents]
**Primary Key:** [UUID/Sequence]

## 2) Fields

| Field | Type | Required | Description | Constraints |
|------|------|----------|-------------|-------------|
| id | UUID | Yes | Unique identifier | Primary key |
| name | string | Yes | Display name | Max length 255 |
| status | string | No | Lifecycle status | Enum or reference table |
| createdAt | datetime | Yes | Creation timestamp | UTC |
| updatedAt | datetime | Yes | Last update timestamp | UTC |

## 3) Relationships

- **One-to-Many:** EntityA → EntityB
- **Many-to-One:** EntityB → EntityA
- **Many-to-Many:** EntityA ↔ EntityC (join table)
- **Self-Referencing:** EntityA → EntityA (hierarchy)

## 4) Indexes

- `IX_Entity_Name` - Optimize lookups by name
- `IX_Entity_Status` - Filter by status

## 5) Constraints & Validation

- Required fields: [list]
- Unique fields: [list]
- Business rules: [list]

## 6) Audit & Timeline

- [ ] Append-only audit events for mutations
- [ ] Include actor, timestamp, change summary

## 7) Authorization Notes

- [ ] Define resource attributes for ABAC
- [ ] Map actions to roles/policies

## 8) Reference Data & Seeding

- [ ] Reference tables (if any)
- [ ] Deterministic seed data (if required)

## 9) Soft Delete (If Applicable)

- [ ] `deletedAt` field
- [ ] Filtering strategy for deleted records

## 10) Events (Optional)

- [ ] Domain events emitted on changes

---

## Example Library

See `{PRODUCT_ROOT}/planning-mds/examples/` for project-specific entity examples.

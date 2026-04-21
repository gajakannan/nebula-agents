# Boundary Policy: Generic Agents vs Solution-Specific Content

**Date:** 2026-02-01
**Status:** Active
**Owner:** Architecture Team

---

## Purpose

This policy defines the boundary between generic, reusable agent roles (`agents/`) and solution-specific content (`{PRODUCT_ROOT}/planning-mds/`).

---

## Policy Rules

### Rule 1: agents/ is Generic and Reusable

**Principle:** Everything in `agents/` must be applicable to **any** software project, regardless of domain.

**What belongs in agents/:**
- ✅ Agent role definitions (SKILL.md and supporting references/scripts/assets)
- ✅ Generic best practices (SOLID, DDD, INVEST, vertical slicing, etc.)
- ✅ Generic examples from multiple domains (B2B SaaS, e-commerce, healthcare, etc.)
- ✅ Generic templates (story, feature, persona, ADR, API contract, etc.)
- ✅ Generic scripts and tools (validation, linting, formatting)

**What does NOT belong in agents/:**
- ❌ Domain-specific terminology (insurance, underwriting, claims, etc.)
- ❌ Competitive analysis for specific markets
- ❌ Solution-specific examples (personas, features, stories referencing project entities)
- ❌ Solution-specific architecture patterns
- ❌ Project-specific business rules or workflows

---

### Rule 2: {PRODUCT_ROOT}/planning-mds/ is Solution-Specific

**Principle:** Everything in `{PRODUCT_ROOT}/planning-mds/` is specific to the current project and would be replaced for a new project.

**What belongs in {PRODUCT_ROOT}/planning-mds/:**
- ✅ Project master specification (BLUEPRINT.md)
- ✅ Domain knowledge (glossary, competitive analysis, domain-specific patterns)
- ✅ Project-specific examples (personas, features, stories, architecture)
- ✅ Actual project requirements (features/, stories/, architecture/)
- ✅ Project-specific ADRs and design decisions

**What does NOT belong in {PRODUCT_ROOT}/planning-mds/:**
- ❌ Generic best practices (those go in agents/)
- ❌ Generic examples from other domains
- ❌ Reusable templates (those go in agents/templates/)

---

### Rule 3: Agents Must Not Invent Requirements

**Principle:** Agent roles consume requirements from `{PRODUCT_ROOT}/planning-mds/`; they do not create or embed solution requirements.

**Implementation:**
- Agents read from `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` and `{PRODUCT_ROOT}/planning-mds/domain/` to understand project context
- Agents reference `{PRODUCT_ROOT}/planning-mds/examples/` to see how generic patterns apply to this project
- Agents generate deliverables based on templates in `agents/templates/` and requirements in `{PRODUCT_ROOT}/planning-mds/`
- Agents never hard-code project-specific business logic in their role definitions

---

### Rule 4: Starting a New Project

**Principle:** Reusing the framework for a new product should be as simple as placing the product repo next to `nebula-agents` and resolving `{PRODUCT_ROOT}` to that product repo. The framework is not copied into the product — the two repos operate as siblings.

**Process:**
1. Clone `nebula-agents` and the product repo as siblings under a shared workspace root
2. Resolve `{PRODUCT_ROOT}` via `NEBULA_PRODUCT_ROOT`, operator input at session start, or the default `../<product-repo>` relative to `nebula-agents`
3. From a session rooted in `nebula-agents`, run the `init` action to scaffold `{PRODUCT_ROOT}/planning-mds/` structure (or write it by hand)
4. Write domain knowledge in `{PRODUCT_ROOT}/planning-mds/domain/`
5. Create project-specific examples in `{PRODUCT_ROOT}/planning-mds/examples/`
6. Write `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` for the new project
7. Agents are immediately ready to use with new project context

---

### Rule 5: Script Placement Boundary

**Principle:** Framework-generic automation must live under `agents/`; repository-root `scripts/` is solution/runtime scoped.

**Placement rules:**
- ✅ Put reusable governance and validation scripts under `agents/**/scripts/` or `agents/scripts/`
- ✅ Keep role-specific generic validators with their role (`agents/<role>/scripts/`)
- ❌ Do not keep framework-generic scripts in root `scripts/`
- ✅ Use root `scripts/` only for solution deployment/runtime/project-specific automation

---

## Standard Example Entities

All reference files in `agents/` that include code or API examples must use the same set of example entities. This prevents two problems: inconsistency across files (one guide uses `User/Post`, another uses `Customer/Order`), and accidental re-introduction of solution-specific entities during edits.

### The Standard Set

| Entity | Role in examples | Replaces (in Nebula) |
|--------|-----------------|----------------------|
| `customers` | Primary entity — CRUD, search, filtering | `brokers` |
| `orders` | Child entity — nested resources, status workflows | `submissions` |

### Why These Two

- **Universal** — customers and orders exist in retail, SaaS, healthcare, insurance, manufacturing. They don't imply any single domain.
- **Structurally rich** — together they cover every pattern a reference file needs to demonstrate:
  - Basic CRUD and search (`customers`)
  - Nested/hierarchical resources (`/customers/{id}/orders`)
  - Status lifecycle and state transitions (`orders`: Pending → Processing → Shipped → Delivered → Cancelled)
  - Unique constraint violations (`OrderNumber` must be unique)
  - Numeric and date range filtering (`amount`, `orderDate`)
  - Permission names (`CreateOrder`, `ViewCustomer`)
- **Two entities, not ten** — keeps examples readable. If a pattern genuinely needs a third entity, use `products` as a line item within an order.

### Field Mapping

When rewriting examples, use this mapping for common field types:

| Field type | Use | Example |
|------------|-----|---------|
| Name / primary text | `name` | `"Acme Inc"` |
| Unique identifier (business key) | `orderNumber` | `"ORD-12345"` |
| Status (enumerated) | `status` | `Active`, `Pending`, `Shipped` |
| Email | `email` | `"contact@acme.example.com"` |
| Numeric (for range filters) | `amount` | `500.00` |
| Date (for range filters) | `orderDate` | `"2026-06-15"` |
| Region / category | `region` | `"West"` |
| Error codes | `DUPLICATE_ORDER_NUMBER` | — |

### Header Note

Every reference file that uses examples must include this note at the top, immediately after the `# Title`:

```markdown
> **Examples in this guide use `customers` and `orders` as illustrative entities.
> These are not prescriptive — substitute your own domain entities when applying
> these patterns. See `BOUNDARY-POLICY.md` → "Standard Example Entities" for
> the full convention and field mapping.
```

---

## Enforcement

### Pre-Commit Checks

Run validation before committing changes to `agents/`:

```bash
# Check for project-specific terms (customize for your project)
grep -r "YourProjectName\|YourDomainEntity" agents/ --include="*.md"
```

### Code Review Checklist

When reviewing PRs that modify `agents/`:
- [ ] No project-specific terminology in agent files
- [ ] Examples use the standard entity set (`customers` / `orders`) — see "Standard Example Entities" above
- [ ] No hard-coded business rules or domain logic
- [ ] All project-specific content belongs in `{PRODUCT_ROOT}/planning-mds/`

When reviewing PRs that modify `{PRODUCT_ROOT}/planning-mds/`:
- [ ] Content is specific to current project
- [ ] No generic best practices (those belong in `agents/`)
- [ ] References to `agents/` resources are correct

---

## Examples

### ✅ GOOD: Generic Example

**File:** `agents/product-manager/references/persona-examples.md`

```markdown
## Example: B2B SaaS - Sales Representative

**Name:** Alex Rivera
**Role:** Enterprise Sales Representative
**Goals:** Close enterprise deals, reduce sales cycle, improve lead qualification
```

**Why good:** Uses a generic domain (B2B SaaS), generic persona name (Alex Rivera), no project-specific terms.

---

### ❌ BAD: Project-Specific in agents/

**File:** `agents/product-manager/references/persona-examples.md` (WRONG)

```markdown
## Example: Subscription Billing — Plan Manager

**Name:** Priya Shah
**Role:** Plan Manager
**Goals:** Manage subscription plans, track billing cycles, reconcile payments
```

**Why bad:** References a specific product's domain (subscription billing), a specific persona (Priya Shah), and product-specific entities (plans, billing cycles, payments). This belongs in `{PRODUCT_ROOT}/planning-mds/examples/personas/`, not in the framework.

---

### ✅ GOOD: Solution-Specific in {PRODUCT_ROOT}/planning-mds/

**File:** `{PRODUCT_ROOT}/planning-mds/examples/personas/plan-manager.md`

```markdown
## Persona: Plan Manager

**Name:** Priya Shah
**Role:** Plan Manager at AcmeBilling
**Goals:** Manage subscription plans, track billing cycles, reconcile payments
```

**Why good:** Project-specific persona lives in the correct product-owned location (`{PRODUCT_ROOT}/planning-mds/`), not inside the framework.

---

## Version History

**Version 1.1** - 2026-02-03 - Added Standard Example Entities section (customers/orders convention, field mapping, header note template)
**Version 1.0** - 2026-02-01 - Initial boundary policy

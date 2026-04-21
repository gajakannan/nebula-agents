# Assets Directory

Generic visual asset templates and examples for the architect agent.

## Diagram Standards

See `agents/architect/SKILL.md` (Diagram Standards section) for the full format rules.

**Summary:**
- **Mermaid** — primary format for all stored diagrams. Renders in GitHub, GitLab, VS Code.
- **ASCII** — companion format for ADR inline content and quick sketches.

## What Goes Here vs. {PRODUCT_ROOT}/planning-mds/

| Content | Location |
|---------|----------|
| Generic diagram templates and examples | `agents/architect/assets/` |
| Solution-specific diagrams (C4, ERD, state machines) | `{PRODUCT_ROOT}/planning-mds/architecture/` |
| Feature-scoped diagrams | Embedded in the relevant feature README |

## Diagram Types

| Type | Mermaid Syntax | Stored In |
|------|---------------|-----------|
| C4 System Context (L1) | `C4Context` | `{PRODUCT_ROOT}/planning-mds/architecture/c4-context.md` |
| C4 Container (L2) | `C4Container` | `{PRODUCT_ROOT}/planning-mds/architecture/c4-container.md` |
| C4 Component (L3) | `C4Component` | Feature README or `{PRODUCT_ROOT}/planning-mds/architecture/c4-component-{feature}.md` |
| Entity Relationship | `erDiagram` | `{PRODUCT_ROOT}/planning-mds/architecture/data-model.md` (domain); feature README (feature-scoped) |
| Workflow State Machine | `stateDiagram-v2` | `{PRODUCT_ROOT}/planning-mds/workflows/` |
| Sequence / API Flow | `sequenceDiagram` | ADR or feature README |

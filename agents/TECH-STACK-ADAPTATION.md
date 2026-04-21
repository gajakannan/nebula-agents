# Adapting to Different Tech Stacks

This framework is reusable across stacks. The agent roles and templates stay the same; only stack-specific references and examples need adjustments.

## Quick Checklist

1) Identify the target stack (backend, frontend, database, infra/auth).
2) Replace or add stack-specific reference guides under `agents/**/references/`.
3) Update `agents/README.md` tech stack assumptions to match your stack.
4) Update any scripts that are stack-specific (test runners, scaffolds).
5) Keep templates and SKILL.md files unchanged.

## What Works Unchanged (Any Tech Stack)

- All 11 agent `SKILL.md` files
- All templates in `agents/templates/`
- Product Manager, Architect, QA, Security, Code Reviewer roles
- Generic references (clean architecture, testing best practices, UX, accessibility, etc.)

## What Needs Updating

### Example: FastAPI Backend

Replace or add:
- `agents/backend-developer/references/dotnet-best-practices.md` → `fastapi-best-practices.md`
- `agents/backend-developer/references/ef-core-patterns.md` → `sqlalchemy-patterns.md`

Keep unchanged:
- `clean-architecture-guide.md` (generic)
- `SKILL.md` (generic responsibilities)

### Example: Vue.js Frontend

Replace or add:
- `agents/frontend-developer/references/react-best-practices.md` → `vue-best-practices.md`
- Update component examples in `testing-guide.md` if they are React-specific

Keep unchanged:
- `typescript-patterns.md`
- `accessibility-guide.md`
- `ux-principles.md`

## Guidance

- Prefer adding new stack-specific reference files over renaming existing ones to avoid breaking links.
- If you need a new stack, add a small “stack pack” under each role’s `references/` folder.
- Keep solution-specific examples in `{PRODUCT_ROOT}/planning-mds/`, never in `agents/`.

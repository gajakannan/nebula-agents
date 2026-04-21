# Blueprint Setup (Meta)

This folder contains **process/meta** guidance for starting a new product on top of the framework. It is **not** part of solution-specific planning content.

The framework runs as a sibling repo. All product planning artifacts live under `{PRODUCT_ROOT}/planning-mds/`, where `{PRODUCT_ROOT}` is resolved at session start (see `agents/docs/AGENT-USE.md` → Session Setup).

## Bootstrap Steps (New Product)

Run these from a session rooted in `nebula-agents` after `{PRODUCT_ROOT}` is resolved. The `init` action automates most of the scaffolding; this list is the manual equivalent for reviewers.

1) Create `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md` with sections 0–2 (context, scope, constraints).
2) Create `{PRODUCT_ROOT}/planning-mds/domain/` and add your glossary + competitive analysis.
3) Create `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md` from `agents/templates/solution-patterns-template.md`.
4) Create `{PRODUCT_ROOT}/planning-mds/examples/` with at least one persona, feature, and story example.
5) Create `{PRODUCT_ROOT}/planning-mds/features/` (with `REGISTRY.md` and `F{NNNN}-{slug}/` folders) for actual requirements.
6) Create `{PRODUCT_ROOT}/planning-mds/screens/` and `{PRODUCT_ROOT}/planning-mds/workflows/` for UI and state specs.

## Minimal Folder Scaffold

Run from any shell with `PRODUCT_ROOT` exported:

```bash
mkdir -p "$PRODUCT_ROOT"/planning-mds/{domain,examples,features,screens,workflows,architecture,api,security,testing,operations}
mkdir -p "$PRODUCT_ROOT"/planning-mds/features/archive
mkdir -p "$PRODUCT_ROOT"/planning-mds/examples/{personas,features,stories,screens,architecture,architecture/adrs}
```

## BLUEPRINT.md Outline (Minimal)

```
0) How we will work (process + roles)
1) Product context (what we're building, users, core entities)
2) Platform/technology constraints (if any)
3) Product Manager spec (vision, personas, epics/features, stories, screens)
4) Architect spec (service boundaries, data model, workflows, auth, APIs, NFRs)
```

## Template Pointers

Use these generic templates from `agents/templates/` (in `nebula-agents`):
- `story-template.md`
- `feature-template.md`
- `persona-template.md`
- `screen-spec-template.md`
- `workflow-spec-template.md`
- `api-contract-template.yaml`
- `solution-patterns-template.md`

## Examples (Non-Insurance)

See `blueprint-setup/examples/` in `nebula-agents` for small, partial examples across different domains.

## First 4 Artifacts (Minimum)

1) `{PRODUCT_ROOT}/planning-mds/BLUEPRINT.md`
2) `{PRODUCT_ROOT}/planning-mds/domain/[project]-glossary.md`
3) `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md`
4) `{PRODUCT_ROOT}/planning-mds/examples/stories/[project]-story-example.md`

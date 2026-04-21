# React Best Practices

**Version:** 1.0  
**Last Updated:** 2026-02-27  
**Applies To:** Frontend Developer

---

## Scope

This guide defines practical React implementation defaults for `{PRODUCT_ROOT}/experience/`.

For UX release gates and accessibility enforcement, also apply:

- `agents/frontend-developer/references/ux-audit-ruleset.md`
- `agents/frontend-developer/references/accessibility-guide.md`

---

## Component Architecture

- Prefer feature-local components under `{PRODUCT_ROOT}/experience/src/features/<feature>/components`.
- Keep global `components/ui` for reusable primitives only.
- Keep components focused: one clear responsibility per component.
- Prefer composition over inheritance and deep prop drilling.

## State and Data Boundaries

- Server state: TanStack Query hooks.
- Form state: React Hook Form (+ AJV/JSON schema validation).
- Local UI state: React hooks (`useState`, `useReducer`).
- Avoid storing derived values; compute with memoization when needed.

## Hooks and Side Effects

- Keep hooks deterministic and side effects explicit.
- Co-locate feature-specific hooks in `features/<feature>/hooks`.
- Use dependency arrays correctly; avoid stale closures.
- Prefer callback/query invalidation patterns over ad-hoc event buses.

## Rendering and Performance

- Split route-level bundles with lazy loading where meaningful.
- Use `React.memo` and memoization selectively for measured hot paths.
- Keep list rendering stable with deterministic keys.
- Defer non-critical work and avoid blocking initial render.

## Forms and Validation

- Standardize on React Hook Form for manual forms.
- Keep validation messages specific and contextual.
- Disable form submit actions only when necessary and explain why.
- Surface async request states and failure recovery paths.

## UX and Accessibility in React Components

- Use semantic elements for interactions (`button`, `a/Link`).
- Preserve keyboard navigation and visible focus.
- Ensure dialogs/popovers/tabs use accessible primitives and patterns.
- Validate components in light and dark themes using semantic tokens.

## Testing Expectations

- Unit test component logic and conditionals.
- Integration test user flows and async states.
- Add accessibility assertions where interaction complexity is high.
- When styling/theme behavior changes, run visual theme checks.

## Required Command Set for PR Validation

```bash
pnpm --dir {PRODUCT_ROOT}/experience lint
pnpm --dir {PRODUCT_ROOT}/experience lint:theme
pnpm --dir {PRODUCT_ROOT}/experience build
pnpm --dir {PRODUCT_ROOT}/experience test
```

If styles/theme changed:

```bash
pnpm --dir {PRODUCT_ROOT}/experience test:visual:theme
```

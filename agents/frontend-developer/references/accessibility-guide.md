# Accessibility Guide

**Version:** 1.0  
**Last Updated:** 2026-02-27  
**Applies To:** Frontend Developer, Code Reviewer, Quality Engineer

---

## Baseline Standard

- Target **WCAG 2.1 AA** for all user-facing interfaces.
- Treat accessibility as a build quality gate, not post-implementation cleanup.

Primary enforcement document:

- `agents/frontend-developer/references/ux-audit-ruleset.md`

---

## Mandatory Rules (Must Pass)

### 1. Semantics and Structure

- Use semantic elements for intent (`button`, `nav`, `main`, `form`, `table`).
- Use heading hierarchy in order (no skipping levels for visual styling).
- Use `label` + `htmlFor` for form controls.

### 2. Keyboard and Focus

- Every interactive element must be keyboard reachable.
- Keep visible focus styles; do not remove focus without accessible replacement.
- Dialog-like surfaces must manage focus correctly (initial focus, trap, restore).

### 3. Accessible Names and Descriptions

- Icon-only actions require `aria-label`.
- Inputs must expose accessible names and error descriptions.
- Validation messages should be programmatically associated to inputs.

### 4. Color and Contrast

- Ensure readable foreground/background contrast in light and dark themes.
- Do not communicate state by color only; pair with text/icon/shape cues.
- Use semantic theme tokens/classes; avoid raw palette classes in app UI.

### 5. State and Feedback

- Async actions must expose loading states accessibly.
- Errors should be clear, specific, and actionable.
- Empty states should describe context and provide next action when possible.

---

## Component Pattern Notes

- **Dialog/Sheet:** trap focus, `Escape` handling, focus restoration.
- **Tabs:** proper tablist roles and arrow-key navigation.
- **Popover/Menu:** trigger semantics, keyboard navigation, close behavior.
- **Form controls:** `aria-invalid`, helper text, and inline error mapping.

---

## Verification Commands

```bash
pnpm --dir {PRODUCT_ROOT}/experience lint
pnpm --dir {PRODUCT_ROOT}/experience lint:theme
pnpm --dir {PRODUCT_ROOT}/experience test
pnpm --dir {PRODUCT_ROOT}/experience build
```

When theme or styling changes:

```bash
pnpm --dir {PRODUCT_ROOT}/experience test:visual:theme
```

---

## Review Checklist

- [ ] No clickable non-interactive wrappers.
- [ ] Keyboard-only navigation succeeds for touched flows.
- [ ] Focus state visible and logical.
- [ ] Form fields have labels and accessible errors.
- [ ] Light/dark readability and contrast verified.
- [ ] Evidence captured in handoff notes.

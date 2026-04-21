# UX Audit Rule Set (Frontend)

**Version:** 1.0  
**Last Updated:** 2026-02-27  
**Applies To:** Frontend Developer, Code Reviewer, Quality Engineer

---

## Purpose

This document defines non-negotiable UX implementation and audit rules for all frontend work in `{PRODUCT_ROOT}/experience/`.

- Treat **P0/P1 rules** as release gates.
- Treat **P2 rules** as improvement targets unless product scope says otherwise.

---

## Severity Model

- **P0 (Blocking):** Must pass before merge.
- **P1 (High):** Must be fixed in the same work item unless explicitly deferred with approval.
- **P2 (Advisory):** Improve when touching related code.

---

## Rule Families

### 1. Interaction Semantics

- **P0:** Clickable UI must use semantic interactive elements:
  - Use `<button>` for actions.
  - Use `<a>` or router `Link` for navigation.
  - Do not use clickable `<div>`/`<span>` wrappers.
- **P0:** Icon-only controls require an accessible name (`aria-label` or visible label).
- **P1:** Disabled state must be explicit and visually distinct.
- **P1:** Destructive actions require confirmation when impact is irreversible.

### 2. Keyboard, Focus, and ARIA Behavior

- **P0:** All interactive elements must be keyboard reachable.
- **P0:** Visible focus indicators must remain enabled.
- **P0:** Dialogs/sheets/popovers that capture input must:
  - Move focus into the surface when opened.
  - Trap focus while open.
  - Close on `Escape` where pattern requires.
  - Restore focus to trigger on close.
- **P0:** Tabs/menus/listboxes must support arrow key navigation per ARIA pattern.
- **P1:** Heading levels must be sequential and meaningful for screen readers.

### 3. Readability and Content Clarity

- **P0:** Body text and controls must remain readable in both light and dark themes.
- **P1:** Avoid vague UI copy (for example: "Error occurred"); provide actionable next steps.
- **P1:** Form errors must be specific at field level and clear at form level.
- **P2:** Keep primary actions concise and outcome-oriented ("Save Customer", not "Submit").

### 4. Color, Contrast, and Theming

- **P0:** Use semantic theme classes/tokens for text, surfaces, and borders.
- **P0:** Do not introduce raw Tailwind palette classes for app UI text/surface/border colors.
- **P0:** UI changes must be verified in both dark and light themes.
- **P1:** Do not rely on color alone to communicate status; pair with text/icon shape.

### 5. Layout and Responsive Behavior

- **P0:** Critical workflows must work on mobile and desktop breakpoints.
- **P1:** Touch targets should be at least 44x44 CSS pixels.
- **P1:** Prevent overflow clipping of key actions/content on small screens.
- **P2:** Preserve consistent spacing rhythm (Tailwind spacing scale).

### 6. Feedback and State Handling

- **P0:** Every async action must expose loading, success, and error feedback.
- **P0:** Empty states must explain "what happened" and include a next action when possible.
- **P1:** Long-running operations should show progressive feedback (skeleton, progress, or staged status).

### 7. Component Pattern Requirements

- **P0:** Prefer hardened primitives from `{PRODUCT_ROOT}/experience/src/components/ui/` for dialog, tabs, popover, menu.
- **P0:** If building custom composite widgets, implement ARIA roles + keyboard behavior explicitly.
- **P1:** Reuse established UI primitives before introducing new variants.

---

## Required Verification Commands

Run these commands for frontend PRs:

```bash
pnpm --dir {PRODUCT_ROOT}/experience lint
pnpm --dir {PRODUCT_ROOT}/experience lint:theme
pnpm --dir {PRODUCT_ROOT}/experience build
pnpm --dir {PRODUCT_ROOT}/experience test
```

Run this additional command when styling, theming, or visual behavior changes:

```bash
pnpm --dir {PRODUCT_ROOT}/experience test:visual:theme
```

If a command is unavailable, use the nearest project-equivalent and document it in the PR.

---

## Audit Evidence Required in Handoff

Attach:

- Command results for required verification.
- Light/dark screenshots for affected screens.
- Note of any deferred P1/P2 items with owner and due date.

Store audit evidence in:

- `{PRODUCT_ROOT}/planning-mds/operations/evidence/frontend-ux/ux-audit-YYYY-MM-DD.md`

CI validator:

- `agents/frontend-developer/scripts/validate-frontend-ux-evidence.py`

---

## Quick Audit Checklist

- [ ] No clickable non-interactive wrappers.
- [ ] Keyboard and focus behavior works for all new/changed interactions.
- [ ] Modal/popover/tabs ARIA and keyboard behavior validated.
- [ ] Readability and contrast acceptable in dark and light mode.
- [ ] Semantic theme classes used; `lint:theme` passes.
- [ ] Mobile + desktop checks complete for affected flows.
- [ ] Async, empty, and error states implemented.
- [ ] Verification evidence captured.

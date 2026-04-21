---
template: feature-readme
version: 1.1
applies_to: product-manager
---

# Feature README Template

Lightweight index for a feature folder. Place as `README.md` inside each feature folder.

---

# F{NNNN} — [Feature Name]

**Status:** [Draft | In Progress | Complete | Archived]
**Archived:** [YYYY-MM-DD — fill when status is Archived, omit otherwise]
**Priority:** [Critical | High | Medium | Low]
**Phase:** [MVP | Phase 1 | Phase 2 | Infrastructure | Future]

## Overview

[One-paragraph summary of what this feature does and why it matters.]

## Documents

| Document | Purpose |
|----------|---------|
| [PRD.md](./PRD.md) | Full product requirements (why + what + how) |
| [STATUS.md](./STATUS.md) | Completion checklist and progress tracking |
| [GETTING-STARTED.md](./GETTING-STARTED.md) | Developer/agent setup guide |

## Stories

| ID | Title | Status |
|----|-------|--------|
| [F{NNNN}-S0001](./F{NNNN}-S0001-{slug}.md) | [Story title] | [Not Started / In Progress / Done] |
| [F{NNNN}-S0002](./F{NNNN}-S0002-{slug}.md) | [Story title] | [Not Started / In Progress / Done] |

**Total Stories:** [count]
**Completed:** [count] / [total]

## Architecture Review (Optional — fill after Phase B)

**Phase B status:** [Complete / In Progress / N/A]
**Execution Plan:** [`feature-assembly-plan.md`](./feature-assembly-plan.md)

### Key Findings

[List any significant findings from the architecture review: requirement corrections, feasibility concerns, cross-feature dependencies, or deviations from expected patterns.]

### Architecture Artifacts

| Artifact | Status |
|----------|--------|
| Data model / ERD | [Updated / N/A — reason] |
| API contract (OpenAPI) | [Updated / N/A — reason] |
| Workflow state machine | [Updated / N/A — reason] |
| Casbin policy | [Updated / N/A — reason] |
| JSON schemas | [Updated / N/A — reason] |
| C4 diagrams | [Updated / N/A — reason] |
| ADRs | [ADR-NNN created / None required — reason] |
| Assembly plan | [`feature-assembly-plan.md`](./feature-assembly-plan.md) |

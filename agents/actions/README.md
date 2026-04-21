# Agent Action Flow

## Purpose

The **Action Flow** provides a user-friendly interface for composing agents to accomplish complete workflows. Each action defines how agents work together in sequence or parallel to achieve a specific goal.

Actions are **generic and reusable** - they define agent composition patterns that work across any project.

## What is an Action?

An action is a **composition recipe** that:
- Maps user intent to agent execution
- Defines which agents to invoke and in what order
- Specifies inputs, outputs, and validation criteria
- Can run agents sequentially, in parallel, or both

## Design Principles

1. **User Intent Over Implementation** - Actions express what the user wants ("plan the project") not implementation details
2. **Agent Composition** - Actions compose existing agents; they don't duplicate agent logic
3. **Phase Alignment** - Actions align with the three-phase workflow (A: Product, B: Architecture, C: Implementation)
4. **Boundary Respect** - Actions are generic; solution-specific usage lives in `{PRODUCT_ROOT}/planning-mds/`
5. **Flow Clarity** - Each action clearly shows the flow: sequential (→) or parallel (+)

## Action Index

### Bootstrap Actions
- **[init](./init.md)** - Bootstrap a new project structure and blueprint document

### Planning Actions
- **[plan](./plan.md)** - Complete planning flow (Phase A + B): requirements → architecture
- **[validate](./validate.md)** - Validate requirements, architecture, and implementation alignment

### Implementation Actions
- **[build](./build.md)** - Full implementation flow: app code + AI code (if needed) + tests + deployment
- **[feature](./feature.md)** - Single vertical slice end-to-end (including AI when in scope, with code + security reviews)

### Quality Actions
- **[review](./review.md)** - Comprehensive review: code quality + security + standards
- **[test](./test.md)** - Test suite development and execution

### Documentation Actions
- **[document](./document.md)** - Generate technical documentation and API docs
- **[blog](./blog.md)** - Write development logs and articles

## Action Flow Notation

We use simple notation to show how agents compose:

- **Sequential flow:** `Agent A → Agent B` (A completes, then B starts)
- **Parallel flow:** `Agent A + Agent B` (A and B run simultaneously)
- **Mixed flow:** `Agent A → (Agent B + Agent C)` (A completes, then B and C run in parallel)

## Action Structure

Each action file follows this template:

```markdown
# Action: <name>

## User Intent
What the user wants to accomplish

## Agent Flow
Which agents are invoked and in what sequence/parallel pattern

## Prerequisites
What must exist before running this action

## Inputs
What the action needs from the user or {PRODUCT_ROOT}/planning-mds/

## Outputs
What artifacts are created or updated

## Validation
How to verify the action succeeded

## Example Usage
Concrete examples of invoking this action
```

## How Actions Work

```
User → Invokes Action → Action composes Agents → Agents execute → Validation → Output
```

**Example: Plan Action**
```
User: "Run the plan action"
  ↓
Plan Action activates
  ↓
Product Manager agent (Phase A)
  ↓ (sequential)
Architect agent (Phase B)
  ↓
Validation checks Definition of Done
  ↓
Output: {PRODUCT_ROOT}/planning-mds/ populated with requirements + architecture
```

## Action vs Agent vs Phase

| Concept | Purpose | Location | Example |
|---------|---------|----------|---------|
| **Agent** | Role-based persona with specific responsibilities | `agents/<role>/` | Product Manager, Architect |
| **Action** | Composition of agents to accomplish a workflow | `agents/actions/` | plan, build, review |
| **Phase** | Stage in the development lifecycle | Process concept | Phase A, B, C |

## Relationship to Phases

```
Phase A (Product Manager Mode)
  └─ init action     → Product Manager
  └─ plan action     → Product Manager (Phase A portion)

Phase B (Architect/Tech Lead Mode)
  └─ plan action     → Architect (Phase B portion)
  └─ validate action → Architect

Phase C (Implementation Mode)
  └─ build action    → Architect (orchestration) → (Backend Developer + Frontend Developer + AI Engineer* + DevOps + Quality Engineer)
  └─ feature action  → Architect (orchestration) → (Backend Developer + Frontend Developer + AI Engineer* + Quality Engineer + DevOps)
  └─ review action   → Code Reviewer + Security
  └─ test action     → Quality Engineer
  └─ document action → Technical Writer
  └─ blog action     → Blogger
```

\* AI Engineer runs when stories include AI/LLM/MCP scope.

## Common Patterns

### Sequential Flow Pattern
When one agent's output is required input for the next:
```
Product Manager → Architect → Backend Developer
```

### Parallel Flow Pattern
When agents can work independently on different aspects:
```
Backend Developer + Frontend Developer + AI Engineer + Quality Engineer + DevOps
```

### Mixed Flow Pattern
Combination of sequential and parallel:
```
Architect → (Backend Developer + Frontend Developer) → Code Reviewer
```

## Extension Points

Actions can be extended by:
1. Adding new action definitions in this directory
2. Composing existing agents in new ways
3. Defining project-specific action shortcuts in `{PRODUCT_ROOT}/planning-mds/workflows/` (if needed)

## Getting Started

1. **Starting a new project?** → Run the [init action](./init.md)
2. **Planning a feature?** → Run the [plan action](./plan.md)
3. **Building an implementation?** → Run the [build action](./build.md)
4. **Need code review?** → Run the [review action](./review.md)

## Next Steps

- Review individual action definitions to understand agent compositions
- Map your workflows to actions
- Use actions as primary entry points instead of invoking agents directly
- For direct role prompts and fresh-session examples, see `agents/docs/AGENT-USE.md`
- Provide feedback on missing actions or better compositions

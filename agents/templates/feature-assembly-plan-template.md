# Feature Assembly Plan — F{NNNN}: {Feature Name}

**Created:** {date}
**Author:** Architect Agent
**Status:** Draft

> **Purpose:** This file is the implementation execution plan for the feature. It must contain enough detail — exact file paths, code signatures, logic flows, per-endpoint response tables — that a backend or frontend developer agent can implement the feature without cross-referencing architecture docs.
>
> **Depth expectation:** Placeholders like `{field count}` and `{summary}` must be replaced with actual values. "Existing Code" should state real field counts, method names, and precise change descriptions. "Step N" sections must include complete C# record/class definitions with all fields and types — not abbreviated signatures. If a developer agent would need to ask a clarifying question, the plan lacks sufficient detail.

**Placement:** `{PRODUCT_ROOT}/planning-mds/features/F{NNNN}-{slug}/feature-assembly-plan.md` — colocated with the feature folder so it archives together with PRD, stories, and STATUS. The umbrella cross-feature sequencing plan at `{PRODUCT_ROOT}/planning-mds/architecture/feature-assembly-plan.md` references this file.

Use this template for solution feature planning. If generic framework work under `agents/**` is also required, track it separately rather than mixing it into the solution feature plan.

**Note:** This template is oriented toward backend entity/service/endpoint features. For infrastructure-only features (DevOps scripts, CI workflows, tooling), adapt the structure: replace entity/DTO/endpoint sections with script modification specs, CLI argument definitions, and workflow step details. The depth expectation still applies — implementation-ready, not placeholder-level.

## Overview

{1–3 sentence summary of what the feature adds/changes and why the existing code must be restructured.}

## Build Order

| Step | Scope | Stories | Rationale |
|------|-------|---------|-----------|
| 1 | | | |
| 2 | | | |

## Existing Code (Must Be Modified)

> Resolve real paths from `{PRODUCT_ROOT}/planning-mds/knowledge-graph/code-index.yaml`
> and `canonical-nodes.yaml`. The rows below are shape-only — replace placeholders
> with the concrete paths returned by `{PRODUCT_ROOT}/scripts/kg/lookup.py <feature-id>`.

| File | Current State | F{NNNN} Change |
|------|---------------|----------------|
| `{domain-project}/Entities/{Entity}.cs` | {field count, nav props} | **Rewrite** — {summary} |
| `{application-project}/DTOs/{Dto}.cs` | {param count} | **Rewrite** — {summary} |
| `{application-project}/Services/{Service}.cs` | {methods} | **Expand** — {summary} |
| `{application-project}/Validators/{Validator}.cs` | {rules} | **Rewrite** — {summary} |
| `{application-project}/Interfaces/I{Repository}.cs` | {methods} | **Expand** — {summary} |
| `{infrastructure-project}/Repositories/{Repository}.cs` | {methods} | **Expand** — {summary} |
| `{infrastructure-project}/Persistence/Configurations/{Config}.cs` | {schema} | **Rewrite** — {summary} |
| `{api-project}/Endpoints/{Endpoints}.cs` | {route count} | **Rewrite** — {summary} |

## New Files

| File | Layer | Purpose |
|------|-------|---------|
| | | |

---

## Step N — {Title} ({Story ref})

### New Files

| File | Layer |
|------|-------|
| | |

### Modified Files

| File | Change |
|------|--------|
| | |

### Entity / DTO / Code

```csharp
// {File path}
// Full record/class definition with all fields
```

### Logic Flow

```
{Service method name}({params}) → returns {return type}
```

1. {Step with guard condition and error code}
2. {Step}
3. {Step — include timestamp, user identity, audit field handling}
4. Emit {EventType} timeline event (see Timeline section)
5. `unitOfWork.CommitAsync(ct)`
6. Return {mapped DTO}

### Casbin Enforcement

- Resource: `{resource}`, Action: `{action}`
- Hydrate attrs: `{ subjectId = user.UserId, ... }`
- Policy condition: `{condition from policy.csv}`
- Enforcement pattern: {describe — per-role loop, attribute match, etc.}

### Timeline Event

- EventType: `{EventType}`
- EntityType: `{Entity}`, EntityId: `{entity}.Id`
- EventDescription: `$"{template}"`
- ExternalDescription: `null` (InternalOnly) or `$"{external-safe template}"`
- EventPayloadJson: per `activity-event-payloads.schema.json` → `{definition name}`

### HTTP Responses

| Status | Body | Condition |
|--------|------|-----------|
| 201 Created | `{Dto}` | Success |
| 400 | ProblemDetails (`validation_error`) | Schema validation failure |
| 403 | ProblemDetails (`policy_denied`) | Casbin deny |
| 404 | ProblemDetails (`not_found`) | Entity not found |
| 409 | ProblemDetails (`{code}`) | {Business rule violation} |

---

{Repeat Step N for each endpoint / major service method}

---

## Scope Breakdown

| Layer | Required Work | Owner | Status |
|------|----------------|-------|--------|
| Backend (`{PRODUCT_ROOT}/engine/`) | | | |
| Frontend (`{PRODUCT_ROOT}/experience/`) | | | |
| AI (`{PRODUCT_ROOT}/neuron/`, if needed) | | | |
| Quality | | | |
| DevOps/Runtime | | | |

## Dependency Order

```
Step 0 (Architect):   architecture review + spec finalization
Step 1 (Backend):     {description}
Step 2 (Backend):     {description}
  ──── Backend checkpoint: {gate criteria} ────
Step N (Frontend):    {description}
  ──── Frontend checkpoint: {gate criteria} ────
Step N (QE):          {description}
```

## Integration Checkpoints

### After Step N ({Scope})

- [ ] {Specific, testable criterion}
- [ ] {Specific, testable criterion}

### Cross-Story Verification

- [ ] Full lifecycle: {describe end-to-end flow}
- [ ] All Casbin policies enforced ({role count} roles + ExternalUser denied)
- [ ] Timeline events for full lifecycle are correct and ordered
- [ ] ProblemDetails format consistent with existing endpoints (code + traceId)
- [ ] {Feature-specific verification}

## Integration Checklist

- [ ] API contract compatibility validated
- [ ] Frontend contract compatibility validated
- [ ] AI contract compatibility validated (if in scope)
- [ ] Test cases mapped to acceptance criteria
- [ ] Developer-owned fast-test responsibilities identified by layer
- [ ] Required runtime evidence artifacts identified (coverage/report/log paths as applicable)
- [ ] Framework vs solution boundary reviewed (no accidental `agents/**` drift in feature scope)
- [ ] Run/deploy instructions updated

## Risks and Blockers

| Item | Severity | Mitigation | Owner |
|------|----------|------------|-------|
| | | | |

## JSON Serialization Convention

{Document any non-obvious serialization rules — camelCase policy, date formats, uint-to-string, etc.}

## DI Registration Changes

{List any new services, repositories, or interface registrations needed in DependencyInjection.cs or Program.cs. State "None" if no changes needed.}

## Casbin Policy Sync

{Remind to copy updated policy.csv to the embedded resource location if Casbin policies were changed during architecture.}

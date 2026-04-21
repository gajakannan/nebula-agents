# SOLUTION-PATTERNS.md Template

> **Examples in this guide use `customers` and `orders` as illustrative entities.
> These are not prescriptive — substitute your own domain entities when applying
> these patterns. See `BOUNDARY-POLICY.md` -> "Standard Example Entities" for
> the full convention and field mapping.**

Use this template to create `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md` for a new project.
This file captures project-level implementation conventions all agents must follow.

## Metadata

- Project:
- Version:
- Last Updated:
- Owners:
- Scope:

## Pattern Categories

- `MUST` - mandatory convention for this solution
- `SHOULD` - recommended convention unless a documented exception exists
- `MAY` - optional convention based on feature needs

## Pattern Scope Labels

Use one scope label for each pattern to make portability explicit:

- `Universal` - technology-agnostic rule expected in any stack
- `Stack-Specific` - tied to a concrete framework/tool choice
- `Hybrid` - universal policy with stack-specific implementation details

---

## 1. Authorization Pattern

### Scope
- Label: `Universal` / `Stack-Specific` / `Hybrid`
- Stack context (required when label is not `Universal`):

### Decision
- Policy model:
- Enforcement point:

### Rationale
- Why this model is used:

### Applied In
- Backend:
- Frontend:
- AI layer:

### Enforcement Level
- `MUST` / `SHOULD` / `MAY`

### Example

```yaml
permissions:
  - customer:read
  - customer:update
  - order:create
```

---

## 2. Audit and Timeline Pattern

### Scope
- Label: `Universal` / `Stack-Specific` / `Hybrid`
- Stack context (required when label is not `Universal`):

### Decision
- What gets logged:
- Event immutability policy:

### Rationale
- Why this is needed:

### Applied In
- Data model:
- Workflow engine:

### Enforcement Level
- `MUST` / `SHOULD` / `MAY`

### Example

```json
{
  "entityType": "order",
  "entityId": "ord_123",
  "eventType": "OrderStatusChanged",
  "fromStatus": "Pending",
  "toStatus": "Processing",
  "changedBy": "user_42"
}
```

---

## 3. API Design Pattern

### Scope
- Label: `Universal` / `Stack-Specific` / `Hybrid`
- Stack context (required when label is not `Universal`):

### Decision
- API style (REST/GraphQL/etc):
- Error format:
- Pagination approach:

### Rationale
- Why this contract style is used:

### Applied In
- API contracts:
- Service endpoints:

### Enforcement Level
- `MUST` / `SHOULD` / `MAY`

### Example

```http
GET /api/customers?page=1&pageSize=20
```

---

## 4. Clean Architecture Pattern

### Scope
- Label: `Universal` / `Stack-Specific` / `Hybrid`
- Stack context (required when label is not `Universal`):

### Decision
- Layer boundaries:
- Dependency direction:

### Rationale
- Why this structure is used:

### Applied In
- `{PRODUCT_ROOT}/engine/`:
- `{PRODUCT_ROOT}/experience/`:

### Enforcement Level
- `MUST` / `SHOULD` / `MAY`

### Example

```text
Domain -> Application -> Infrastructure -> API
```

---

## 5. Frontend Pattern

### Scope
- Label: `Universal` / `Stack-Specific` / `Hybrid`
- Stack context (required when label is not `Universal`):

### Decision
- Form strategy:
- Data-fetching strategy:
- Validation strategy:

### Rationale
- Why this frontend stack and pattern set is used:

### Applied In
- `{PRODUCT_ROOT}/experience/` pages/components:

### Enforcement Level
- `MUST` / `SHOULD` / `MAY`

### Example

```text
React Hook Form + JSON Schema validation + query caching
```

---

## 6. Data Modeling Pattern

### Scope
- Label: `Universal` / `Stack-Specific` / `Hybrid`
- Stack context (required when label is not `Universal`):

### Decision
- Entity identity strategy:
- Soft delete policy:
- Temporal/audit fields:

### Rationale
- Why this model supports current requirements:

### Applied In
- Entity model docs:
- Migrations:

### Enforcement Level
- `MUST` / `SHOULD` / `MAY`

### Example

```sql
customers(id, name, email, created_at, updated_at, is_deleted)
orders(id, customer_id, order_number, amount, status, order_date)
```

---

## 7. Testing Pattern

### Scope
- Label: `Universal` / `Stack-Specific` / `Hybrid`
- Stack context (required when label is not `Universal`):

### Decision
- Unit/integration/e2e split:
- Coverage targets:
- Test data policy:

### Rationale
- Why this quality bar is used:

### Applied In
- Test plans:
- CI checks:

### Enforcement Level
- `MUST` / `SHOULD` / `MAY`

### Example

```text
Unit: business logic
Integration: endpoint and repository behavior
E2E: core customer/order workflow
```

---

## 8. Workflow Pattern

### Scope
- Label: `Universal` / `Stack-Specific` / `Hybrid`
- Stack context (required when label is not `Universal`):

### Decision
- State model:
- Transition constraints:
- Compensation/retry rules:

### Rationale
- Why these workflow guarantees are required:

### Applied In
- Workflow specs:
- Orchestration services:

### Enforcement Level
- `MUST` / `SHOULD` / `MAY`

### Example

```text
Order: Draft -> Pending -> Processing -> Shipped -> Delivered
```

---

## 9. Cross-Cutting Pattern

### Scope
- Label: `Universal` / `Stack-Specific` / `Hybrid`
- Stack context (required when label is not `Universal`):

### Decision
- Observability defaults:
- Error handling standard:
- Configuration strategy:

### Rationale
- Why cross-cutting rules are standardized:

### Applied In
- All services and runtimes:

### Enforcement Level
- `MUST` / `SHOULD` / `MAY`

### Example

```text
Structured logs + trace IDs + standardized problem details errors
```

---

## 10. DevOps Pattern

### Scope
- Label: `Universal` / `Stack-Specific` / `Hybrid`
- Stack context (required when label is not `Universal`):

### Decision
- Container strategy:
- Environment promotion model:
- Secrets handling:

### Rationale
- Why this deployment model is used:

### Applied In
- Dockerfiles:
- Compose/Kubernetes:

### Enforcement Level
- `MUST` / `SHOULD` / `MAY`

### Example

```text
Local compose, staged deployments, env-based configuration, no hardcoded secrets
```

---

## Pattern Update Process

1. Propose changes via ADR or architecture note.
2. Review impact across backend/frontend/AI/test/devops.
3. Update this file with rationale and enforcement level.
4. Communicate changes before implementation begins.

## Change Log

- YYYY-MM-DD: Initial project-specific pattern set created.

# JSON Schema Validation Architecture

**Cross-Tier Validation Strategy:**

JSON Schema serves as the **single source of truth** for validation rules, shared between frontend and backend to ensure consistency.

## Architecture Pattern

```
{PRODUCT_ROOT}/planning-mds/schemas/
├── customer.schema.json          # Shared validation schema
├── account.schema.json
└── order.schema.json
         ↓
    ┌────┴────────────┐
    ↓                 ↓
Frontend           Backend
(TypeScript)       (C# / .NET)
    ↓                 ↓
AJV Validator    NJsonSchema
or RJSF          Validator
```

## Design Decisions

**1. Schema Location:**
- Store all JSON Schemas in `{PRODUCT_ROOT}/planning-mds/schemas/`
- Frontend loads schemas from this location
- Backend loads schemas from this location
- Version control ensures frontend/backend stay in sync

**2. Validation Points:**

**Frontend:**
- **Manual forms:** React Hook Form + AJV resolver
- **Dynamic forms:** RJSF (auto-validates with JSON Schema)
- **Why validate frontend?** Immediate user feedback, reduce server load

**Backend:**
- **API endpoints:** Validate all incoming requests with NJsonSchema
- **Before domain logic:** Prevent invalid data from entering system
- **Why validate backend?** Security (never trust client), data integrity

**3. Integration with OpenAPI:**
- OpenAPI 3.x uses JSON Schema for request/response bodies
- Reuse JSON Schemas in OpenAPI `components/schemas` section
- Single schema definition serves both validation and documentation

## Example JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://your-app.com/schemas/customer.json",
  "title": "Customer",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 100,
      "errorMessage": "Name is required and must be at most 100 characters"
    },
    "email": {
      "type": "string",
      "format": "email",
      "errorMessage": "Invalid email address"
    },
    "phone": {
      "type": "string",
      "pattern": "^\\d{10}$",
      "errorMessage": "Phone must be 10 digits"
    },
    "status": {
      "type": "string",
      "enum": ["Active", "Inactive"]
    }
  },
  "required": ["name", "email", "status"],
  "additionalProperties": false
}
```

## Integration with OpenAPI

```yaml
# {PRODUCT_ROOT}/planning-mds/api/customers.yaml
openapi: 3.0.0
info:
  title: Customer API
  version: 1.0.0
paths:
  /api/customers:
    post:
      requestBody:
        content:
          application/json:
            schema:
              $ref: '../schemas/customer.schema.json'
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema:
                $ref: '../schemas/customer.schema.json'
        '400':
          description: Validation Error
          content:
            application/problem+json:
              schema:
                $ref: '#/components/schemas/ProblemDetails'
```

## Validation Library Choices

**Frontend:**
- **AJV** - Industry standard JSON Schema validator for JavaScript/TypeScript
- **RJSF** - React JSON Schema Form (includes validation + UI generation)
- **@hookform/resolvers/ajv** - Integrates AJV with React Hook Form

**Backend:**
- **NJsonSchema** - .NET library for JSON Schema validation and code generation
- Alternatives: Json.Schema.Net, Newtonsoft.Json.Schema

## Type Generation

**Frontend:**
```bash
# Generate TypeScript types from JSON Schema
npx json-schema-to-typescript schemas/customer.schema.json > types/customer.ts
```

**Backend:**
```csharp
// NJsonSchema can generate C# classes from schemas
var schema = await JsonSchema.FromFileAsync("schemas/customer.schema.json");
var generator = new CSharpGenerator(schema);
var code = generator.GenerateFile("Customer");
```

## Benefits

- **Single Source of Truth** - One schema definition, validated consistently across tiers
- **Type Safety** - Generate TypeScript and C# types from schemas
- **API Documentation** - OpenAPI specs include validation rules
- **Developer Experience** - Change schema once, frontend and backend update automatically
- **Consistency** - Same validation errors on frontend and backend
- **Maintainability** - Update validation rules in one place

## Architectural Decision Record (ADR)

Document this decision in `{PRODUCT_ROOT}/planning-mds/architecture/decisions/`:

**ADR: Use JSON Schema for Cross-Tier Validation**
- **Status:** Accepted
- **Context:** Need consistent validation between TypeScript frontend and C# backend
- **Decision:** Use JSON Schema as single source of truth for validation
- **Consequences:**
  - Consistency across tiers
  - Reduced duplication
  - TypeScript/C# type generation
  - Additional tooling required (AJV, NJsonSchema)
  - Learning curve for JSON Schema syntax

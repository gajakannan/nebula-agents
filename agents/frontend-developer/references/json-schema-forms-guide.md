# JSON Schema Forms Guide (AJV + RJSF)

**Version:** 1.0
**Last Updated:** 2026-01-30
**Applies To:** Frontend Developer

---

## Overview

This guide covers dynamic form handling using **JSON Schema** for schema definition, **AJV** for validation (frontend and backend), and **React JSON Schema Form (RJSF)** for rendering.

**Why This Approach:**
- **Backend/Frontend Parity**: Same JSON Schema validates on both .NET backend and React frontend
- **Dynamic Forms**: Forms driven by configuration/database, not hardcoded
- **Industry Standard**: JSON Schema is ISO standard (draft-07, draft-2020-12)
- **Complex Business Logic**: Region-specific rules, category variations, compliance requirements
- **Reusable Schemas**: Share schemas across services and teams

---

## Installation

```bash
npm install @rjsf/core @rjsf/utils @rjsf/validator-ajv8
npm install ajv ajv-formats ajv-errors
npm install @rjsf/mui  # Material-UI theme (optional, can use shadcn/ui custom theme)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Backend (.NET)                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ JSON Schema Definition (shared)                │ │
│  │ - customer-schema.json                         │ │
│  │ - order-schema.json                            │ │
│  │ - stored in database or config                 │ │
│  └────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────┐ │
│  │ JSON Schema Validator (.NET)                   │ │
│  │ - NJsonSchema or Json.NET Schema               │ │
│  │ - Validates API requests                       │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
                         │
                         │ API: GET /api/schemas/customer
                         ↓
┌─────────────────────────────────────────────────────┐
│                Frontend (React)                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ Fetch JSON Schema from backend                 │ │
│  └────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────┐ │
│  │ AJV Validator (validates user input)           │ │
│  └────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────┐ │
│  │ RJSF (renders form UI from schema)             │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## JSON Schema Basics

### Simple Customer Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/customer.json",
  "title": "Customer",
  "description": "Customer information",
  "type": "object",
  "required": ["name", "email", "region"],
  "properties": {
    "name": {
      "type": "string",
      "title": "Customer Name",
      "minLength": 1,
      "maxLength": 200,
      "description": "Legal name of the organization"
    },
    "email": {
      "type": "string",
      "format": "email",
      "title": "Email Address"
    },
    "region": {
      "type": "string",
      "title": "Region",
      "enum": ["US-West", "US-East", "EU-West", "APAC"],
      "description": "Customer region"
    },
    "phone": {
      "type": "string",
      "title": "Phone Number",
      "pattern": "^\\d{10}$",
      "description": "10-digit phone number"
    },
    "website": {
      "type": "string",
      "format": "uri",
      "title": "Website"
    }
  }
}
```

### Complex Order Schema with Conditional Logic

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/order.json",
  "title": "Order",
  "type": "object",
  "required": ["customerId", "category", "orderDate"],
  "properties": {
    "customerId": {
      "type": "string",
      "format": "uuid",
      "title": "Customer"
    },
    "category": {
      "type": "string",
      "title": "Category",
      "enum": ["standard", "express"],
      "default": "standard"
    },
    "orderDate": {
      "type": "string",
      "format": "date",
      "title": "Order Date"
    },
    "dueDate": {
      "type": "string",
      "format": "date",
      "title": "Due Date"
    },
    "amount": {
      "type": "number",
      "title": "Amount",
      "minimum": 0,
      "exclusiveMinimum": true
    },
    "items": {
      "type": "object",
      "title": "Order Items",
      "required": ["quantity", "unitPrice"],
      "properties": {
        "quantity": {
          "type": "number",
          "title": "Quantity",
          "minimum": 0
        },
        "unitPrice": {
          "type": "number",
          "title": "Unit Price",
          "minimum": 0
        }
      }
    },
    "expressPartner": {
      "type": "string",
      "title": "Express Partner",
      "minLength": 1
    }
  },
  "allOf": [
    {
      "if": {
        "properties": {
          "category": { "const": "express" }
        }
      },
      "then": {
        "required": ["expressPartner"]
      }
    }
  ]
}
```

---

## Backend Integration

### Storing Schemas in .NET

```csharp
// Domain/Schemas/FormSchemas.cs
public static class FormSchemas
{
    public static readonly string CustomerSchema = @"{
      ""$schema"": ""https://json-schema.org/draft/2020-12/schema"",
      ""type"": ""object"",
      ""required"": [""name"", ""email"", ""region""],
      ""properties"": {
        ""name"": {
          ""type"": ""string"",
          ""minLength"": 1,
          ""maxLength"": 200
        },
        ""email"": {
          ""type"": ""string"",
          ""format"": ""email""
        },
        ""region"": {
          ""type"": ""string"",
          ""enum"": [""US-West"", ""US-East"", ""EU-West"", ""APAC""]
        }
      }
    }";
}

// Minimal API endpoint to serve schema
app.MapGet("/api/schemas/{schemaName}", (string schemaName) =>
{
    return schemaName switch
    {
        "customer" => Results.Json(JsonSerializer.Deserialize<JsonElement>(FormSchemas.CustomerSchema)),
        "order" => Results.Json(JsonSerializer.Deserialize<JsonElement>(FormSchemas.OrderSchema)),
        _ => Results.NotFound()
    };
}).WithName("GetFormSchema").WithTags("Schemas");
```

### Validating with JSON Schema in .NET

```csharp
// Using NJsonSchema
using NJsonSchema;
using NJsonSchema.Validation;

public class SchemaValidator
{
    public async Task<(bool IsValid, ICollection<ValidationError> Errors)>
        ValidateAsync(string schemaJson, string dataJson)
    {
        var schema = await JsonSchema.FromJsonAsync(schemaJson);
        var data = JsonDocument.Parse(dataJson);
        var errors = schema.Validate(data.RootElement);

        return (errors.Count == 0, errors);
    }
}

// In Minimal API endpoint
app.MapPost("/api/customers", async (
    CreateCustomerRequest request,
    SchemaValidator validator) =>
{
    var requestJson = JsonSerializer.Serialize(request);
    var (isValid, errors) = await validator.ValidateAsync(
        FormSchemas.CustomerSchema,
        requestJson
    );

    if (!isValid)
    {
        return Results.ValidationProblem(
            errors.ToDictionary(
                e => e.Path,
                e => new[] { e.Kind.ToString() }
            )
        );
    }

    // Process valid request...
    return Results.Ok();
});
```

---

## Frontend Implementation with RJSF

### Basic Form with RJSF

```tsx
// components/forms/CustomerForm.tsx
import Form from '@rjsf/core';
import validator from '@rjsf/validator-ajv8';
import { RJSFSchema, UiSchema } from '@rjsf/utils';

interface CustomerFormProps {
  onSubmit: (data: any) => void;
  initialData?: any;
}

export function CustomerForm({ onSubmit, initialData }: CustomerFormProps) {
  // Schema would typically be fetched from backend
  const schema: RJSFSchema = {
    type: 'object',
    required: ['name', 'email', 'region'],
    properties: {
      name: {
        type: 'string',
        title: 'Customer Name',
        minLength: 1,
        maxLength: 200,
      },
      email: {
        type: 'string',
        format: 'email',
        title: 'Email',
      },
      region: {
        type: 'string',
        title: 'Region',
        enum: ['US-West', 'US-East', 'EU-West', 'APAC'],
      },
      phone: {
        type: 'string',
        title: 'Phone',
        pattern: '^\\d{10}$',
      },
    },
  };

  // UI Schema for custom rendering
  const uiSchema: UiSchema = {
    email: {
      'ui:widget': 'email',
    },
    phone: {
      'ui:help': '10 digits, no formatting',
      'ui:placeholder': '5551234567',
    },
  };

  return (
    <Form
      schema={schema}
      uiSchema={uiSchema}
      validator={validator}
      formData={initialData}
      onSubmit={({ formData }) => onSubmit(formData)}
    />
  );
}
```

### Fetching Schema from Backend

```tsx
// hooks/useFormSchema.ts
import { useQuery } from '@tanstack/react-query';
import { RJSFSchema } from '@rjsf/utils';

export function useFormSchema(schemaName: string) {
  return useQuery({
    queryKey: ['schemas', schemaName],
    queryFn: async () => {
      const response = await fetch(`/api/schemas/${schemaName}`);
      if (!response.ok) throw new Error('Failed to fetch schema');
      return response.json() as Promise<RJSFSchema>;
    },
    staleTime: 1000 * 60 * 30, // Schemas don't change often
  });
}

// Usage
function DynamicCustomerForm() {
  const { data: schema, isLoading } = useFormSchema('customer');

  if (isLoading) return <Skeleton />;

  return (
    <Form
      schema={schema}
      validator={validator}
      onSubmit={handleSubmit}
    />
  );
}
```

### Custom Widgets for shadcn/ui

```tsx
// components/forms/widgets/CustomTextWidget.tsx
import { WidgetProps } from '@rjsf/utils';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export function CustomTextWidget(props: WidgetProps) {
  const {
    id,
    value,
    required,
    disabled,
    readonly,
    onChange,
    onBlur,
    onFocus,
    label,
    schema,
    rawErrors = [],
  } = props;

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>
        {label || schema.title}
        {required && <span className="text-destructive ml-1">*</span>}
      </Label>
      <Input
        id={id}
        value={value || ''}
        disabled={disabled || readonly}
        onChange={(e) => onChange(e.target.value)}
        onBlur={() => onBlur && onBlur(id, value)}
        onFocus={() => onFocus && onFocus(id, value)}
        placeholder={schema.examples?.[0] as string}
        className={rawErrors.length > 0 ? 'border-destructive' : ''}
      />
      {schema.description && (
        <p className="text-sm text-muted-foreground">{schema.description}</p>
      )}
      {rawErrors.length > 0 && (
        <p className="text-sm text-destructive">{rawErrors[0]}</p>
      )}
    </div>
  );
}

// Custom select widget
export function CustomSelectWidget(props: WidgetProps) {
  const { id, value, onChange, options, schema, required, rawErrors } = props;

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>
        {schema.title}
        {required && <span className="text-destructive ml-1">*</span>}
      </Label>
      <Select
        value={value}
        onValueChange={(val) => onChange(val)}
      >
        <SelectTrigger className={rawErrors.length > 0 ? 'border-destructive' : ''}>
          <SelectValue placeholder={`Select ${schema.title}`} />
        </SelectTrigger>
        <SelectContent>
          {options.enumOptions?.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {rawErrors.length > 0 && (
        <p className="text-sm text-destructive">{rawErrors[0]}</p>
      )}
    </div>
  );
}
```

### Custom Theme for shadcn/ui

```tsx
// components/forms/ShadcnTheme.tsx
import { ThemeProps } from '@rjsf/core';
import { CustomTextWidget } from './widgets/CustomTextWidget';
import { CustomSelectWidget } from './widgets/CustomSelectWidget';

const ShadcnTheme: ThemeProps = {
  widgets: {
    TextWidget: CustomTextWidget,
    EmailWidget: CustomTextWidget,
    URLWidget: CustomTextWidget,
    SelectWidget: CustomSelectWidget,
  },
  templates: {
    // Override default templates
    ObjectFieldTemplate: CustomObjectFieldTemplate,
    ArrayFieldTemplate: CustomArrayFieldTemplate,
    FieldTemplate: CustomFieldTemplate,
  },
};

export default ShadcnTheme;

// Usage
import { withTheme } from '@rjsf/core';

const ThemedForm = withTheme(ShadcnTheme);

function CustomerForm() {
  return (
    <ThemedForm
      schema={schema}
      validator={validator}
      onSubmit={handleSubmit}
    />
  );
}
```

---

## AJV Configuration with Custom Formats

```typescript
// lib/ajv-config.ts
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import ajvErrors from 'ajv-errors';

export function createAjvInstance() {
  const ajv = new Ajv({
    allErrors: true,
    verbose: true,
    strict: false,
    $data: true, // Enable $data references
  });

  // Add standard formats (email, uri, date, etc.)
  addFormats(ajv);

  // Add custom error messages
  ajvErrors(ajv);

  // Add custom formats
  ajv.addFormat('phone', {
    type: 'string',
    validate: (value: string) => /^\d{10}$/.test(value),
  });

  ajv.addFormat('order-number', {
    type: 'string',
    validate: (value: string) => /^[A-Z0-9]{6,10}$/.test(value),
  });

  // Add custom keywords
  ajv.addKeyword({
    keyword: 'isNotEmpty',
    type: 'string',
    validate: function validate(schema: any, data: string) {
      return typeof data === 'string' && data.trim().length > 0;
    },
    errors: false,
  });

  return ajv;
}

// Create custom validator for RJSF
import { customizeValidator } from '@rjsf/validator-ajv8';

export const customValidator = customizeValidator({}, createAjvInstance());
```

---

## Conditional Logic / Dynamic Fields

### Show Field Based on Another Field

```json
{
  "type": "object",
  "properties": {
    "category": {
      "type": "string",
      "enum": ["standard", "express"],
      "default": "standard"
    },
    "expressPartner": {
      "type": "string"
    }
  },
  "dependencies": {
    "category": {
      "oneOf": [
        {
          "properties": {
            "category": { "const": "express" }
          },
          "required": ["expressPartner"]
        }
      ]
    }
  }
}
```

### Using `allOf` for Complex Conditions

```json
{
  "type": "object",
  "properties": {
    "region": {
      "type": "string",
      "enum": ["US-West", "US-East", "EU-West"]
    },
    "regionCode": {
      "type": "string"
    }
  },
  "allOf": [
    {
      "if": {
        "properties": {
          "region": { "const": "US-West" }
        }
      },
      "then": {
        "properties": {
          "regionCode": {
            "pattern": "^USW[0-9]{7}$"
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "region": { "const": "EU-West" }
        }
      },
      "then": {
        "properties": {
          "regionCode": {
            "pattern": "^EUW[0-9]{7}$"
          }
        }
      }
    }
  ]
}
```

---

## Custom Validation Rules

### Cross-Field Validation

```json
{
  "type": "object",
  "properties": {
    "orderDate": {
      "type": "string",
      "format": "date"
    },
    "dueDate": {
      "type": "string",
      "format": "date"
    }
  },
  "if": {
    "properties": {
      "orderDate": { "type": "string" },
      "dueDate": { "type": "string" }
    },
    "required": ["orderDate", "dueDate"]
  },
  "then": {
    "properties": {
      "dueDate": {
        "formatMinimum": { "$data": "1/orderDate" }
      }
    }
  }
}
```

### Custom Error Messages

```json
{
  "type": "object",
  "properties": {
    "amount": {
      "type": "number",
      "minimum": 0,
      "errorMessage": {
        "type": "Amount must be a number",
        "minimum": "Amount must be greater than zero"
      }
    }
  }
}
```

---

## Region-Specific Schema Examples

### US-West-Specific Order Schema

```typescript
// lib/schemas/region-schemas.ts
export const usWestOrderSchema = {
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  type: 'object',
  required: ['shippingMethod', 'regionalTax'],
  properties: {
    shippingMethod: {
      type: 'string',
      title: 'Shipping Method',
      enum: ['ground', 'express', 'overnight'],
      description: 'US-West shipping options',
    },
    regionalTax: {
      type: 'number',
      title: 'Regional Tax (%)',
      minimum: 0,
      maximum: 100,
      default: 7.25,
      description: 'Regional tax rate',
    },
  },
};

// Merge with base schema
export function getOrderSchema(region: string) {
  const baseSchema = { /* base order schema */ };
  const regionSchema = regionSchemas[region] || {};

  return {
    ...baseSchema,
    properties: {
      ...baseSchema.properties,
      ...regionSchema.properties,
    },
    required: [
      ...baseSchema.required,
      ...(regionSchema.required || []),
    ],
  };
}
```

---

## Testing JSON Schemas

### Unit Testing Schemas

```typescript
import Ajv from 'ajv';
import { customerSchema } from './schemas/customer';

describe('Customer Schema', () => {
  const ajv = new Ajv();
  const validate = ajv.compile(customerSchema);

  it('should accept valid customer data', () => {
    const validData = {
      name: 'Acme Corporation',
      email: 'contact@acme.com',
      region: 'US-West',
      phone: '5551234567',
    };

    const isValid = validate(validData);
    expect(isValid).toBe(true);
  });

  it('should reject invalid email', () => {
    const invalidData = {
      name: 'Acme Corp',
      email: 'invalid-email',
      region: 'US-West',
    };

    const isValid = validate(invalidData);
    expect(isValid).toBe(false);
    expect(validate.errors?.[0].keyword).toBe('format');
  });

  it('should require email', () => {
    const invalidData = {
      name: 'Acme Corp',
      region: 'US-West',
    };

    const isValid = validate(invalidData);
    expect(isValid).toBe(false);
    expect(validate.errors?.[0].keyword).toBe('required');
  });
});
```

---

## Best Practices

### 1. Version Your Schemas

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/customer/v1.0.0",
  "version": "1.0.0",
  "type": "object"
}
```

### 2. Use References for Reusability

```json
{
  "$defs": {
    "address": {
      "type": "object",
      "required": ["street", "city", "region", "postalCode"],
      "properties": {
        "street": { "type": "string" },
        "city": { "type": "string" },
        "region": { "type": "string" },
        "postalCode": { "type": "string" }
      }
    }
  },
  "type": "object",
  "properties": {
    "mailingAddress": { "$ref": "#/$defs/address" },
    "billingAddress": { "$ref": "#/$defs/address" }
  }
}
```

### 3. Provide Good Error Messages

```json
{
  "properties": {
    "amount": {
      "type": "number",
      "minimum": 0,
      "errorMessage": "Amount must be a positive number"
    }
  }
}
```

### 4. Use UI Schema for Customization

```typescript
const uiSchema = {
  amount: {
    'ui:widget': 'updown',
    'ui:help': 'Enter amount in USD',
    'ui:options': {
      prefix: '$',
    },
  },
  orderDate: {
    'ui:widget': 'date',
    'ui:options': {
      yearsRange: [2024, 2030],
    },
  },
};
```

---

## Comparison: Shared JSON Schema vs Per-Layer Validation

| Feature | JSON Schema + AJV (Shared) | Per-Layer Validation (Separate Rules) |
|---------|-----------------------------|----------------------------------------|
| **Validation Source** | Single schema shared by frontend + backend | Separate frontend and backend rules |
| **Drift Risk** | Low | High |
| **Backend Sharing** | Works in .NET/Node/Python | Reimplementation required per stack |
| **Dynamic Forms** | Designed for schema-driven rendering | Usually custom-coded |
| **Tooling** | Validators, generators, OpenAPI alignment | Fragmented by language/library |
| **Compliance/Auditability** | Strong (explicit schema artifacts) | Weaker (scattered rule definitions) |
| **Performance** | Very fast (compiled validators) | Varies by implementation |

**Recommendation:**
Use **JSON Schema + AJV + RJSF** when:
- Forms are dynamic and region-specific
- Need backend/frontend validation parity (.NET + React)
- Schemas can be stored in database and updated without code deploy
- Industry standard for compliance and auditing

---

## Migration Path

If you currently validate only at one layer (frontend or backend), migrate in this order:

1. Define canonical JSON Schemas under `{PRODUCT_ROOT}/planning-mds/schemas/` or `{PRODUCT_ROOT}/experience/src/schemas/`
2. Wire frontend forms to `ajvResolver` (manual forms) or RJSF validator (dynamic forms)
3. Wire backend request validation to the same schemas
4. Remove duplicated per-layer validation rules once parity tests pass

---

## References

- [JSON Schema Specification](https://json-schema.org)
- [AJV Documentation](https://ajv.js.org)
- [React JSON Schema Form](https://rjsf-team.github.io/react-jsonschema-form/)
- [NJsonSchema (.NET)](https://github.com/RicoSuter/NJsonSchema)
- [Understanding JSON Schema](https://json-schema.org/understanding-json-schema/)

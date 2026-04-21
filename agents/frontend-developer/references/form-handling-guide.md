# Form Handling Guide (JSON Schema + AJV)

**Version:** 3.0
**Last Updated:** 2026-02-07
**Applies To:** Frontend Developer

---

## Overview

This guide standardizes form validation on **React Hook Form + AJV + JSON Schema**.

Goals:
- Single validation source shared across frontend and backend
- Predictable error behavior
- Schema-driven form evolution without duplicated rules

---

## Standard Approach

### Manual Forms
Use **React Hook Form + AJV** for custom UX and fixed layouts.

### Dynamic Forms
Use **RJSF + AJV validator** when form fields are schema-driven or configurable.

---

## Installation

```bash
npm install react-hook-form ajv ajv-errors @hookform/resolvers
```

---

## Manual Form Example (React Hook Form + AJV)

```tsx
import { useForm } from 'react-hook-form';
import { ajvResolver } from '@hookform/resolvers/ajv';
import Ajv from 'ajv';
import addErrors from 'ajv-errors';

const schema = {
  type: 'object',
  required: ['name', 'email'],
  properties: {
    name: { type: 'string', minLength: 1, maxLength: 200 },
    email: { type: 'string', format: 'email' },
  },
  additionalProperties: false,
  errorMessage: {
    required: {
      name: 'Name is required',
      email: 'Email is required',
    },
  },
} as const;

const ajv = new Ajv({ allErrors: true, strict: false });
addErrors(ajv);

export function CustomerForm() {
  const form = useForm({
    resolver: ajvResolver(schema, undefined, { ajv }),
    defaultValues: { name: '', email: '' },
  });

  return (
    <form onSubmit={form.handleSubmit(console.log)}>
      <input {...form.register('name')} />
      <p>{form.formState.errors.name?.message as string}</p>

      <input {...form.register('email')} />
      <p>{form.formState.errors.email?.message as string}</p>

      <button type="submit">Save</button>
    </form>
  );
}
```

---

## Dynamic Form Example (RJSF)

```tsx
import Form from '@rjsf/core';
import validator from '@rjsf/validator-ajv8';

const schema = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['Active', 'Inactive'] },
  },
} as const;

export function DynamicSettingsForm() {
  return <Form schema={schema} validator={validator} onSubmit={console.log} />;
}
```

---

## Implementation Rules

- Keep schemas versioned and committed.
- Reuse the same schema in frontend and backend validation.
- Always set `additionalProperties: false` unless intentionally extensible.
- Provide human-readable `errorMessage` entries for required fields and key constraints.
- Add tests for both valid and invalid payloads.

---

## References

- [JSON Schema Specification](https://json-schema.org)
- [AJV Documentation](https://ajv.js.org)
- [React Hook Form](https://react-hook-form.com)
- [RJSF](https://rjsf-team.github.io/react-jsonschema-form/)

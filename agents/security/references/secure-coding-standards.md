# Secure Coding Standards

## Rules
- Validate all inputs server-side
- Use parameterized queries only
- Avoid logging sensitive data
- Enforce least privilege
- Use standard error responses

## Required Server Controls
- Apply authorization in server handlers/services, never only in UI.
- Perform resource-level ownership checks for read/update/delete operations.
- Use allow-lists for enum-like inputs and strict parsing for IDs/dates/numbers.
- Reject unknown/extra fields for security-sensitive operations.
- Enforce request size and pagination limits to reduce abuse risk.

## Secrets and Cryptography
- Do not hardcode credentials, API keys, or tokens in code/tests/docs.
- Fetch secrets from environment/secret stores with scoped access.
- Use approved crypto libraries and modern algorithms; avoid custom crypto.
- Rotate keys/secrets on schedule and after incident exposure.

## Logging and Errors
- Log security-relevant events with actor, action, resource, and decision outcome.
- Redact or hash sensitive fields before logging.
- Return generic external error messages; keep internal diagnostics in protected logs.

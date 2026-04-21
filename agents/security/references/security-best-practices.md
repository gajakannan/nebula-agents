# Security Best Practices

Guidance for Security agent work. Use OWASP and internal standards.

## Core Practices
- Authenticate all endpoints (except health)
- Authorize all mutations with least privilege
- Validate all inputs server-side
- Encrypt sensitive data at rest and in transit
- Log security-relevant events without leaking sensitive data

## Minimum Review Evidence
- Record review scope (feature/full/system), assumptions, and target environment.
- List trust boundaries (browser, API, DB, queue, third-party providers).
- Capture at least one threat scenario per STRIDE category in scope.
- Link scan evidence (SAST, dependency, secret, DAST where applicable) with timestamps.
- Document residual risk and release disposition.

## Control Verification Checklist
- Injection resistance: server-side validation, canonicalization, parameterized queries.
- AuthN/AuthZ: strong identity verification, server-side authorization, deny-by-default policy.
- Session/token: expiry, revocation strategy, secure transport, storage constraints.
- Data protection: field-level sensitivity mapping, encryption at rest/in transit, log redaction.
- Misconfiguration: CORS, cookie flags, security headers, environment segregation.
- Component risk: vulnerable package triage and remediation owner/date.
- Logging/monitoring: audit events for auth, authorization denies, and sensitive mutations.
- Abuse resistance: rate limits, lockout, replay defense, idempotency controls.
- Failure safety: generic user errors, no stack leakage, safe fallback behavior.

## Reviews
- Threat modeling for new features
- Token storage ADR for auth changes
- OWASP Top 10 coverage per release

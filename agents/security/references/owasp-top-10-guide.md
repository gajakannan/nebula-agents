# OWASP Top 10 Guide

Short checklist for core categories:
- A01 Broken Access Control
- A02 Cryptographic Failures
- A03 Injection
- A04 Insecure Design
- A05 Security Misconfiguration
- A06 Vulnerable Components
- A07 Auth Failures
- A08 Integrity Failures
- A09 Logging/Monitoring Failures
- A10 SSRF

## Category-to-Check Mapping
- A01: Server-side authorization per endpoint and per resource ownership.
- A02: TLS enforced, strong crypto usage, and protected secret/key material.
- A03: Parameterized queries, safe command usage, and strict input validation.
- A04: Threat model exists for new flows with abuse and trust-boundary analysis.
- A05: Hardened defaults for CORS, headers, cookies, and environment settings.
- A06: Dependency scans run and vulnerable packages triaged with owner/date.
- A07: Robust identity verification, token/session controls, lockout/rate limits.
- A08: Integrity checks for packages, artifacts, and untrusted deserialization paths.
- A09: Security events logged, monitored, and usable for incident response.
- A10: Outbound request allow-listing and metadata/internal network protections.

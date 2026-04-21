# Threat Modeling Guide

## Approach
- Identify assets and trust boundaries
- Enumerate threats using STRIDE
- Rank by likelihood and impact
- Document mitigations

## Minimum Threat Model Content
- System context and reviewed deployment environment.
- Asset inventory with sensitivity (public/internal/confidential/restricted).
- Actor list (user roles, admins, service accounts, external integrations).
- Entry points (API endpoints, webhooks, file upload, scheduled jobs).
- Data flow notes crossing trust boundaries.
- Existing controls and identified control gaps.

## STRIDE Prompt Set
- Spoofing: how can identity be forged and what verifies it?
- Tampering: what data/instructions can be modified in transit/at rest?
- Repudiation: what actions are non-repudiable via audit evidence?
- Information disclosure: what sensitive data can leak via API/log/errors?
- Denial of service: what is expensive and how is abuse throttled?
- Elevation of privilege: can roles bypass ownership or policy checks?

## Output Quality Bar
- Every high/critical threat includes exploit path, impact, and mitigation owner.
- Mitigations map to concrete backlog items or implemented controls.
- Residual risk is explicit for accepted or deferred items.

## Output
- One threat model per major feature
- Stored in {PRODUCT_ROOT}/planning-mds/security/

---
template: feature-getting-started
version: 1.1
applies_to: product-manager
---

# Feature GETTING-STARTED Template

Practical setup guide for developers and agents implementing this feature. The PM creates a skeleton; implementing agents fill in details as they build.

Place as `GETTING-STARTED.md` inside each feature folder.

---

# F{NNNN} — [Feature Name] — Getting Started

## Prerequisites

- [ ] [Required service or dependency]
- [ ] [Database migration applied]
- [ ] [Seed data loaded]

## Services to Run

```bash
# List the services needed to work on this feature
# Example:
# docker compose up -d postgres
# dotnet run --project {PRODUCT_ROOT}/engine/src/MyApp.Api
# pnpm --dir {PRODUCT_ROOT}/experience dev
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| [VAR_NAME] | [What it controls] | [Default value] |

## Seed Data

Describe any seed data required for this feature to function:
- [Entity]: [What is seeded and why]

## How to Verify

Steps to confirm the feature works end-to-end:

1. [Step 1 — e.g., navigate to a specific URL]
2. [Step 2 — e.g., perform an action]
3. [Step 3 — e.g., verify expected result]

## Key Files

| Layer | Path | Purpose |
|-------|------|---------|
| Backend | `{PRODUCT_ROOT}/engine/src/...` | [What this file does] |
| Frontend | `{PRODUCT_ROOT}/experience/src/...` | [What this file does] |

## Dev User Credentials (If feature introduces or depends on auth flows)

Document any credentials, tokens, or auth configuration developers need to test this feature:

| Username | Role | Credential / Token Key |
|----------|------|----------------------|
| [username] | [Role] | [token or password] |

Manual token acquisition example (if applicable):
```bash
# Example ROPC token acquisition
curl -X POST http://localhost:9000/application/o/token/ \
  -d "grant_type=password&client_id=example&username=user&password=token-key&scope=openid"
```

## Notes

- [Any gotchas, workarounds, or context that helps implementers]

**Rich gotchas encouraged.** Document specific failure modes and their solutions, not just "things to know." Examples of valuable gotchas:
- Auth-specific behaviors (e.g., "password grant requires app-password tokens, not login passwords")
- Health endpoint URLs that differ across services
- Exit code conventions for scripts
- Timing-sensitive operations (e.g., "blueprint needs 5s after worker starts")

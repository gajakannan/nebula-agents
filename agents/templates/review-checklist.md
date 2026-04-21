---
template: review-checklist
version: 1.1
applies_to: code-reviewer
---

# Code Review Checklist

## Must Check

- [ ] Tests added/updated and passing
- [ ] Clean Architecture boundaries respected (Domain → Application → Infrastructure → API)
- [ ] AuthN/AuthZ enforced on all mutations and sensitive reads
- [ ] Error handling consistent (ProblemDetails / RFC 7807 where applicable)
- [ ] No secrets or credentials in code

## Common Defect Categories

Watch for these categories that frequently surface in reviews. When a defect is found, tag it (e.g., DEF-01) in the review notes for traceability.

| Category | What to Look For |
|----------|-----------------|
| **Authorization scope** | Casbin/ABAC check missing or checking the wrong resource/action. Endpoint allows broader access than policy intends. |
| **IDOR (Insecure Direct Object Reference)** | Endpoint accepts an entity ID without verifying the caller owns or has access to that entity. |
| **Data resolution** | DTO maps wrong field, navigation property not included, null reference on optional relationship. |
| **Filter logic** | Query filter is wrong or missing — returns too many or too few results. Pagination off-by-one. Soft-deleted records leaking into results. |
| **Concurrent updates** | Missing optimistic concurrency check (xmin/RowVersion). Two users can overwrite each other's changes. |
| **Timeline/audit gap** | Mutation does not produce the expected ActivityTimelineEvent or produces it with wrong EventType/payload. |
| **State machine violation** | Workflow transition bypasses guard conditions or allows an invalid state change. |
| **Validation gap** | Input accepted without validation, or validation rules don't match the JSON Schema / OpenAPI contract. |

## Should Check

- [ ] Readability and naming
- [ ] Duplicated logic
- [ ] Performance foot-guns (N+1 queries, unbounded lists, missing indexes)
- [ ] Docs updated if needed
- [ ] Tracker/STATUS.md updated if story state changed

## Review Evidence

When recording review provenance in `STATUS.md`, include:
- Defect IDs found and their resolution status (fixed / deferred / wontfix)
- File paths reviewed
- Review date

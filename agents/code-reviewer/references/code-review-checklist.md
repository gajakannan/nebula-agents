# Code Review Checklist

Detailed walkthrough checklist for use during a code review. For the quick Must-Check / Should-Check summary, see `agents/templates/review-checklist.md`.

Work through these sections in order. The earlier sections provide context that makes the later ones faster.

---

## 1. Before You Read Code

- [ ] Have I read the user story and its acceptance criteria?
- [ ] Have I read `{PRODUCT_ROOT}/planning-mds/architecture/SOLUTION-PATTERNS.md` to know the conventions?
- [ ] Do I know which layers the changes touch (Domain, Application, Infrastructure, API, UI)?
- [ ] Have I noted the scope? Is this a small feature, a refactor, a hotfix?

*If you can't answer these, stop and gather context before reviewing code.*

---

## 2. Acceptance Criteria Mapping

Walk each AC item. For each one, find the code that delivers it. If you can't trace an AC to code, that is a **critical** finding.

- [ ] Every AC item has corresponding implementation code
- [ ] Every AC item has corresponding test coverage
- [ ] Edge cases called out in the story are handled
- [ ] Error scenarios called out in the story are handled
- [ ] Role-based visibility / access control is enforced where the story specifies it

---

## 3. Architecture & Boundaries

- [ ] No layer leaks — Domain does not import Application or Infrastructure
- [ ] Controllers depend only on the Application layer (use cases / services), not on repositories or DbContext directly
- [ ] DTOs are used at layer boundaries — no domain entities serialised directly to the API response
- [ ] Repositories contain only persistence logic — no business rules or query-building that belongs in a use case
- [ ] New files are placed in directories that match the project's existing structure

---

## 4. Logic & Correctness

- [ ] Boundary conditions are handled (null, empty, zero, max values, negative numbers)
- [ ] Control flow is correct (conditionals, loops, off-by-one risks)
- [ ] Async operations are awaited / handled — no fire-and-forget where a result matters
- [ ] Concurrency risks are addressed if shared state is involved
- [ ] No unreachable code paths

---

## 5. Error Handling

- [ ] Errors are caught at the right boundary — not swallowed silently (no empty `catch` or `catch` that only logs)
- [ ] API endpoints return a consistent error shape
- [ ] The UI surfaces errors to the user (toast, inline message, etc.) — not just to the console
- [ ] Retryable errors (network, rate-limit) are distinguished from fatal errors (validation, not-found)

---

## 6. Tests

- [ ] Tests exist for every acceptance criterion
- [ ] Edge cases and error paths are tested
- [ ] Tests assert behaviour (what the user sees / what the system does), not implementation details (internal state, private methods)
- [ ] Tests are deterministic — no `sleep`, no random data, no shared mutable state across tests
- [ ] Test names describe the scenario, not the method being called

---

## 7. Performance

- [ ] No N+1 query patterns (loop that issues one DB query per iteration)
- [ ] Large result sets are bounded (TAKE / LIMIT / pagination)
- [ ] No synchronous `.Wait()` or `.Result` on async calls
- [ ] No obviously expensive operations in hot paths (loops, request handlers) without justification

---

## 8. Security Handoff

*Security agent owns the deep vulnerability scan. Your job here is to flag anything obvious so it does not slip through the cracks during parallel review.*

- [ ] No hardcoded credentials, API keys, or connection strings
- [ ] User-facing endpoints check authorisation (not just authentication)
- [ ] Input from outside the system boundary is not passed directly into queries, shell commands, or HTML without sanitisation

*If you spot a real vulnerability, note it in your report and flag it for the Security agent — do not attempt a full security analysis yourself.*

---

## 9. Readability & Naming

- [ ] Names say what the thing *is*, not how it's *implemented*
- [ ] No magic numbers or unexplained string literals — extracted to named constants
- [ ] Functions are short enough to understand at a glance
- [ ] Nesting depth is reasonable (≤ 3 levels)
- [ ] Code follows the conventions already present in the file / module

---

## 10. Over- and Under-Engineering

- [ ] No abstractions (interfaces, base classes, factories) with exactly one implementation and no clear reason to expect a second
- [ ] No generic frameworks built for a single use case
- [ ] Conversely: is any logic duplicated 3+ times that should be extracted?
- [ ] Are there unused imports, dead code paths, or commented-out code?

---

## 11. Final Check

- [ ] Does the change do what was asked — no more, no less?
- [ ] Would a developer unfamiliar with this feature understand the code without an explanation?
- [ ] Are there any open questions or assumptions that should be called out before merge?

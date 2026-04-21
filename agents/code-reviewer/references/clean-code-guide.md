# Clean Code Guide

Quick-reference reminders on naming, structure, and readability. These apply across languages and layers — use them when a finding in a review is about code clarity rather than logic or architecture.

---

## Naming

- **Variables and parameters** — nouns or noun phrases. Name the *thing*, not how it got there. `user` not `fetchedUser`. `total` not `calculatedTotal`.
- **Functions and methods** — verbs or verb phrases. Name the *action*. `calculateDiscount`, `sendNotification`, `validateInput`.
- **Booleans** — prefix with `is`, `has`, `can`, or `should`. `isActive`, `hasPermission`. Avoid negated names (`isNotActive`); invert the logic instead.
- **Classes** — singular nouns. One class, one noun. `OrderProcessor` not `OrderProcessors`.
- **Constants** — SCREAMING_SNAKE_CASE (most languages) or PascalCase where the language convention requires it. Always named, never inline magic numbers or strings.
- **Avoid abbreviations** — `customer` not `cust`. `index` not `idx`. The one exception: well-known domain abbreviations everyone on the team already uses.
- **Avoid generic names** — `data`, `info`, `stuff`, `temp`, `obj`. If you can't think of a name, you probably don't understand the value yet — step back and clarify what it represents.

## Function & Method Shape

- **One job per function.** If you have to use "and" to describe what it does, split it.
- **Guard clauses first.** Validate preconditions at the top and return/throw early. This keeps the happy path un-nested and readable.
- **Target < 20 lines of body.** This is a guideline, not a hard rule. If a function is long, ask: can the logic be broken into well-named helpers?
- **Limit parameters to 3–4.** More than that usually means the function is doing too much, or the parameters belong in an object.
- **No flag parameters.** A `boolean` argument that changes the function's behaviour is a sign it should be two functions.

```
// ❌ Flag parameter — what does "true" mean at the call site?
formatName(name, true);

// ✓ Two clear functions
formatNameWithTitle(name);
formatNamePlain(name);
```

## Structure & Organisation

- **Constants and configuration at the top** of the file or class. Magic numbers buried in logic make diffs and comprehension harder.
- **Public interface before private helpers.** A reader should see *what* the class does before *how*.
- **Related logic stays together.** Validation next to validation. Formatting next to formatting. Don't scatter related concerns across a file.
- **Limit nesting to 2–3 levels.** Deep nesting (`if` inside `if` inside `for`) is almost always a sign that a helper function or early return is needed.

## Comments

- **Comments explain *why*, not *what*.** If the code is clear enough to need no explanation, don't add one. If the *reason* behind a decision isn't obvious, that's worth a comment.
- **Never comment out dead code.** Delete it. Version control is the history.
- **TODOs are fine if they have a ticket or owner.** Bare `TODO` with no context is noise.

## Consistency

- Follow the conventions already in the file. If the codebase uses `camelCase` for variables, don't introduce `snake_case` in your PR.
- If you disagree with a convention, raise it as a team decision — don't unilaterally change it in a feature PR.

# Code Smells Guide

A catalogue of common code smells, why each one matters, and how to address it. Use this during reviews when something *feels* off but you need to articulate why.

These are indicators, not rules. A single occurrence of any smell is often fine. A pattern — the same smell repeated across a module — is the signal to act.

---

## Long Method

**What it looks like:** A function or method that runs for 30+ lines and handles multiple responsibilities.

**Why it matters:** Hard to test in isolation. Hard to read top-to-bottom without losing context. Changes to one responsibility risk breaking another.

**How to fix:** Extract well-named helper functions. Each helper should do one thing. Use guard clauses to flatten nesting.

---

## Large Class

**What it looks like:** A class with dozens of methods and fields, responsible for multiple unrelated behaviours.

**Why it matters:** Violates Single Responsibility. Changes to any one feature carried by the class require touching the same file. High merge-conflict risk.

**How to fix:** Split into focused classes. Move groups of related methods into their own class. Extract the shared state into a collaborator.

---

## Feature Envy

**What it looks like:** A method that spends most of its time accessing data from *another* class rather than its own.

**Why it matters:** The method belongs in the other class. Keeping it where it is creates an unnecessary coupling.

**How to fix:** Move the method to the class whose data it actually needs. If it pulls from two classes, extract the shared logic into a third.

```
// ❌ OrderSummary lives on Customer but only touches Order fields
class Customer {
    string GetOrderSummary(Order order) {
        return $"{order.Id}: {order.Items.Count} items, ${order.Total}";
    }
}

// ✓ Moved to Order where it belongs
class Order {
    string Summary() { ... }
}
```

---

## Data Clumps

**What it looks like:** The same group of 3+ variables appearing together repeatedly — as parameters, as local variables, as fields.

**Why it matters:** They are a concept that hasn't been named yet. Passing them around as loose variables means every call site has to know the internal structure.

**How to fix:** Extract the group into a class or record. Give it a meaningful name.

```
// ❌ Street, city, postalCode always travel together
void Ship(string street, string city, string postalCode) { ... }

// ✓ Named concept
void Ship(Address destination) { ... }
```

---

## Primitive Obsession

**What it looks like:** Using raw primitives (`string`, `int`, `bool`) to represent domain concepts that have meaning and rules.

**Why it matters:** No validation, no self-documentation. A `string` could be an email, a phone number, or a product code — the type tells you nothing.

**How to fix:** Introduce small value objects or types. `Email`, `PhoneNumber`, `ProductCode`. They carry their own validation.

---

## Speculative Generality

**What it looks like:** An abstraction (interface, base class, generic parameter) that was added "just in case" a second implementation might be needed, but only one exists.

**Why it matters:** Adds indirection with no current payoff. Makes the code harder to follow. YAGNI — You Aren't Gonna Need It.

**How to fix:** Delete the abstraction. Use the concrete type directly. If a second implementation actually materialises later, introduce the abstraction then.

---

## Dead Code

**What it looks like:** Unreachable code paths, unused variables, commented-out blocks, methods that are never called.

**Why it matters:** Confuses readers. Creates maintenance burden. Makes diffs noisier.

**How to fix:** Delete it. Version control preserves the history if it is ever needed again.

---

## God Object / God Class

**What it looks like:** One class that knows about and orchestrates nearly everything in the system.

**Why it matters:** Everything depends on it. Changes to any part of the system risk touching it. Impossible to test in isolation.

**How to fix:** Distribute responsibilities to smaller, focused classes. The God Object should shrink to a thin orchestrator at most.

---

## Divergent Change

**What it looks like:** One class is modified in many different PRs for many different reasons.

**Why it matters:** It is carrying multiple responsibilities. Each change risks breaking the others.

**How to fix:** Same as Large Class — split by responsibility.

---

## Shotgun Surgery

**What it looks like:** One logical change requires touching many different classes/files.

**Why it matters:** The responsibility for that concept is scattered. Every change is expensive and error-prone.

**How to fix:** Consolidate the scattered responsibility into one place. The change should be local.

---

## Comments That Smell

**What it looks like:** A comment that is necessary *only* because the code itself is unclear.

**Why it matters:** The comment is a band-aid. If the code needs explaining, the code should be clearer.

**How to fix:** Rename the method or variable so the comment becomes unnecessary. If the *why* genuinely can't be expressed in code, a short comment is fine — but the *what* should be self-evident.

---

## Severity guidance

| Smell | Typical severity in review |
|-------|---------------------------|
| Long Method, Large Class, God Object | High — maintainability risk |
| Feature Envy, Shotgun Surgery, Divergent Change | High — structural coupling |
| Data Clumps, Primitive Obsession | Medium — clarity and safety |
| Speculative Generality, Dead Code | Medium — over-engineering or noise |
| Comments That Smell | Low — style, but worth flagging |

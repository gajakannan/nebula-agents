# Product Manager Best Practices

Comprehensive guide for writing high-quality product requirements.

## Table of Contents

1. [User Story Best Practices](#user-story-best-practices)
2. [INVEST Criteria](#invest-criteria)
3. [Vertical Slicing](#vertical-slicing)
4. [Acceptance Criteria Patterns](#acceptance-criteria-patterns)
5. [Epic Decomposition](#epic-decomposition)
6. [Persona Development](#persona-development)
7. [Requirements Elicitation](#requirements-elicitation)
8. [Scope Management](#scope-management)

---

## User Story Best Practices

### The Three C's: Card, Conversation, Confirmation

**Card:** The written story (As a...I want...So that...)
**Conversation:** Discussion with stakeholders to understand context
**Confirmation:** Acceptance criteria that define done

### Writing Effective User Stories

#### DO:
- **Focus on user value:** Every story must deliver measurable value to a specific persona
- **Keep stories small:** Should fit in one iteration (1-2 weeks)
- **Write from user perspective:** Not "The system should..." but "As a user, I want..."
- **Include the "So that":** The business value or benefit must be explicit
- **Be specific about the persona:** Not just "user" but "Sales Operations Manager" or "Order Operations Specialist"

#### DON'T:
- **Write technical solutions:** Focus on what, not how
- **Create dependencies:** Stories should be independent when possible
- **Use vague language:** "Improve", "enhance", "optimize" without specifics
- **Skip acceptance criteria:** Every story needs testable criteria
- **Invent business rules:** Ask questions when requirements are unclear

### Story Sizing

**Too Small (Tasks, not stories):**
- "Add a column to customer table"
- "Change button color to blue"
- These lack user value and should be combined into meaningful stories

**Right Size (Vertical slices):**
- "Create new customer with basic information"
- "Search customers by name and email"
- Delivers end-to-end value, testable, fits in one iteration

**Too Large (Epics, not stories):**
- "Implement customer management system"
- "Build order workflow"
- These need to be broken down into 5-10 smaller stories

---

## INVEST Criteria

Every user story should be INVEST:

### **I - Independent**
- Story can be developed without dependencies on other incomplete stories
- Can be prioritized and delivered in any order
- Minimizes coordination overhead

**Example:**
✅ Good: "Create customer" and "Update customer" are independent
❌ Bad: "Create customer part 1" and "Create customer part 2" are dependent

### **N - Negotiable**
- Story describes what, not how
- Details can be discussed during implementation
- Leaves room for developer creativity

**Example:**
✅ Good: "Search customers by name and email"
❌ Bad: "Implement ElasticSearch for customer search with fuzzy matching algorithm"

### **V - Valuable**
- Delivers measurable value to users or business
- Has a clear "So that" statement
- Not just technical work

**Example:**
✅ Good: "Search customers so I can quickly find the right contact"
❌ Bad: "Add database indexes" (no user value)

### **E - Estimable**
- Development team can estimate the effort
- Requirements are clear enough to assess size
- Unknowns have been discussed

**Example:**
✅ Good: Clear acceptance criteria, well-understood domain
❌ Bad: "Integrate with external system" (unknown API, unclear scope)

### **S - Small**
- Can be completed in one iteration (1-2 weeks)
- Small enough to plan and track progress
- Reduces risk and enables faster feedback

**Example:**
✅ Good: "Create customer with basic fields"
❌ Bad: "Implement complete customer lifecycle management" (too large)

### **T - Testable**
- Has clear acceptance criteria
- QA can write test cases directly from criteria
- Pass/fail is unambiguous

**Example:**
✅ Good: "When I enter duplicate email, I see error 'Email already exists'"
❌ Bad: "Error handling should work properly" (not testable)

---

## Vertical Slicing

See `vertical-slicing-guide.md` for comprehensive guide on breaking features into thin vertical slices.

### Quick Reference

**Vertical Slice:** Delivers end-to-end value across all layers (UI → API → Database)

**Horizontal Slice (Anti-pattern):** Completes one layer at a time (all UI, then all API, then all DB)

**Why Vertical Slicing:**
- Delivers user value incrementally
- Enables early testing and feedback
- Reduces integration risk
- Allows parallel development

**Example: Customer Management**

**❌ Horizontal (Don't do this):**
1. Build all customer UI screens
2. Build all customer APIs
3. Build customer database schema

**✅ Vertical (Do this):**
1. Slice 1: Create customer (form → API → DB → list view)
2. Slice 2: View customer 360 (detail screen → API → DB)
3. Slice 3: Update customer (edit form → API → DB → timeline)
4. Slice 4: Delete customer (confirmation → API → DB → timeline)

---

## Acceptance Criteria Patterns

### Given/When/Then (Preferred for Scenarios)

**Format:**
```
Given [precondition/context]
When [action or event]
Then [expected outcome]
And [additional outcome]
```

**When to use:** User interactions, workflows, conditional logic

**Example:**
```
Given I'm on the Customer List screen
When I click "Add New Customer"
Then I'm navigated to the Create Customer form
And the form is empty except for default values
```

### Checklist Format (Preferred for Simple Criteria)

**Format:**
```
- [ ] Criterion 1: Specific, testable condition
- [ ] Criterion 2: Specific, testable condition
```

**When to use:** Simple feature requirements, configuration, data display

**Example:**
```
- [ ] Customer name is displayed as page title
- [ ] Status badge shows customer status (Active/Inactive/Suspended)
- [ ] Edit and Delete buttons are visible to authorized users
```

### Scenario Outline (for Multiple Similar Cases)

**Format:**
```
Scenario: [Description]
Given [context]
When [action with <parameter>]
Then [outcome with <parameter>]

Examples:
| parameter1 | parameter2 | expected_result |
| value1     | value2     | result1         |
```

**When to use:** Testing multiple variations of the same scenario

**Example:**
```
Scenario: Email validation
Given I'm creating a new customer
When I enter email <email>
Then I see <result>

Examples:
| email        | result                    |
| j.smith@example.com | Accepted            |
| (blank)        | "Email is required"     |
| invalid-format | "Invalid email format"  |
```

---

## Epic Decomposition

### How to Break Epics into Stories

1. **Start with User Workflows**
   - Map the end-to-end user journey
   - Identify key touchpoints and actions

2. **Apply CRUD Pattern**
   - Create, Read, Update, Delete
   - Each CRUD operation is usually one story

3. **Consider Workflow States**
   - Each state transition can be a story
   - Include state-specific validations

4. **Separate Read and Write**
   - List/search screens separate from detail views
   - Create/edit forms separate from read-only views

5. **Defer Nice-to-Haves**
   - MVP: Essential features only
   - Phase 1: Important but not critical
   - Future: Nice-to-have enhancements

### Example: Customer Management Epic → Stories

**Epic E1: Customer Relationship Management**

**MVP Stories:**
- F0001-S0001: Create customer with basic information
- F0001-S0002: View customer list with search and filtering
- F0001-S0003: View customer 360 detail screen
- F0001-S0004: Update customer information
- F0001-S0005: Delete customer (soft delete)
- F0001-S0006: View customer timeline events

**Phase 1 Stories:**
- F0001-S0007: Manage customer hierarchy (parent/sub-customer)
- F0001-S0008: Manage customer addresses
- F0001-S0009: Bulk import customers from CSV
- F0001-S0010: Export customer data

**Future Stories:**
- F0001-S0011: Customer performance analytics
- F0001-S0012: Automated customer health scoring

---

## Persona Development

### Jobs-to-be-Done Framework

Instead of asking "What features do users want?", ask:
- **When** [situation] arises
- **I want to** [motivation/task]
- **So I can** [outcome/benefit]

**Example:**
- **When** I receive a new order email
- **I want to** quickly create an order record and assign it to an order operations specialist
- **So I can** ensure fast turnaround and not lose track of opportunities

### Creating Effective Personas

1. **Base on Real Users**
   - Interview actual users or stakeholders
   - Don't create fictional personas without validation

2. **Focus on Goals and Pain Points**
   - What are they trying to accomplish?
   - What frustrates them about current process?

3. **Include Behavioral Patterns**
   - How do they make decisions?
   - How tech-savvy are they?
   - What's their work style?

4. **Make Them Actionable**
   - Persona should inform design decisions
   - If it doesn't change how you build, it's not useful

5. **Keep Them Updated**
   - Personas evolve as you learn more
   - Revisit quarterly or when strategy changes

---

## Requirements Elicitation

### Asking Good Questions

**Open-Ended Questions (Discover):**
- "Tell me about your typical day..."
- "Walk me through how you currently handle [process]..."
- "What are the biggest challenges you face with [task]?"

**Closed-Ended Questions (Validate):**
- "Can a customer have multiple addresses?"
- "Is email unique per customer?"
- "What happens when an order is cancelled?"

**Prioritization Questions:**
- "If you could only have three features, which would they be?"
- "What would make the biggest impact on your workflow?"
- "What's the minimum you need to replace your current tool?"

### Validating Requirements

Use the "Five Whys" technique:
1. **Requirement:** "We need a customer dashboard"
2. **Why?** "To see customer activity at a glance"
3. **Why do you need that?** "To identify which customers need follow-up"
4. **Why identify that?** "To increase order completion rate"
5. **Why increase that?** "To grow revenue and hit retention targets"

**Root need:** Increase revenue growth by improving customer relationships

**Better requirement:** "Customer relationship health score with recommended actions"

### Handling Scope Creep

**When stakeholders say "Can we also...":**

1. **Acknowledge:** "That's a great idea"
2. **Document:** Add to backlog with "Phase 1" or "Future" tag
3. **Re-focus:** "Let's make sure we nail the MVP first"
4. **Prioritize:** "If we add that, what would you be willing to cut?"

**Key phrase:** "Let's capture that for Phase 1, but for MVP we're focusing on..."

---

## Scope Management

### Defining MVP (Minimum Viable Product)

**MVP is NOT:**
- Half-baked features
- Buggy software
- Everything stakeholders want

**MVP IS:**
- Smallest feature set that delivers core value
- High quality, fully functional features
- Foundation for future enhancements

### MVP vs Phase 1 vs Future

**MVP (Must Have):**
- Core workflows that solve the primary problem
- Features without which the product is not usable
- Target: 3-5 key user stories per epic

**Phase 1 (Should Have):**
- Important features that significantly improve usability
- Can be delayed 1-2 months without major impact
- Target: 2-3 additional stories per epic

**Future (Nice to Have):**
- Enhancements and optimizations
- Features that don't solve immediate pain
- Target: Captured in backlog, no commitment

### Writing Non-Goals

**Why Non-Goals Matter:**
- Sets expectations with stakeholders
- Prevents scope creep during development
- Documents why certain features were excluded

**Example Non-Goals for Generic Phase 0:**
```
### Non-Goals (Phase 0 MVP)

**Out of Scope:**
- External customer self-service portal access
- Document upload and versioning
- Advanced analytics and dashboards
- Bulk operations (import/export)
- Email integration
- Mobile app

**Why Excluded:**
- Focus on core internal workflows first
- Validate core value before expanding
- These can be added in Phase 1 without architectural changes
```

---

## Common Pitfalls & How to Avoid Them

### Pitfall 1: Technical Requirements Disguised as User Stories

**❌ Bad:**
> As a developer, I want to use PostgreSQL, so that I can store data

**✅ Good:**
> As a Sales Operations Manager, I want to search customers by name, so I can quickly find contact information

**Fix:** Focus on user needs, not technical solutions

---

### Pitfall 2: Vague Acceptance Criteria

**❌ Bad:**
> The form should work properly and validate inputs

**✅ Good:**
> When I submit the form with blank Email, I see error "Email is required"

**Fix:** Be specific, testable, and include examples

---

### Pitfall 3: Gold-Plating (Over-Specifying)

**❌ Bad:**
> The customer name field should be exactly 24px from the top, use Inter font at 18px, with #2C3E50 color...

**✅ Good:**
> The customer name field should be prominently displayed near the top of the form

**Fix:** Specify what matters to users, defer styling details to designers

---

### Pitfall 4: Invented Business Rules

**❌ Bad:**
> (Assuming) A customer can only have 5 addresses maximum

**✅ Good:**
> [Question raised] Is there a limit to how many addresses a customer can have?

**Fix:** Ask questions when business rules are unclear

---

### Pitfall 5: Stories That Are Too Large

**❌ Bad:**
> As a Sales Operations Manager, I want to manage customers, so I can track relationships

**✅ Good:**
> - F0001-S0001: Create new customer
> - F0001-S0002: View customer list
> - F0001-S0003: View customer 360
> - F0001-S0004: Update customer
> - F0001-S0005: Delete customer

**Fix:** Break large stories into thin vertical slices

---

## Templates & Tools

**Available Templates:**
- `agents/templates/story-template.md`
- `agents/templates/persona-template.md`
- `agents/templates/epic-template.md`
- `agents/templates/screen-spec-template.md`
- `agents/templates/acceptance-criteria-checklist.md`

**Validation Tools:**
- `agents/product-manager/scripts/validate-stories.py` - Check story completeness
- `agents/product-manager/scripts/generate-story-index.py` - Generate story index

---

## Further Reading

- Mike Cohn: "User Stories Applied" (definitive guide)
- Jeff Patton: "User Story Mapping" (visual story planning)
- Roman Pichler: "Strategize" (product strategy and roadmapping)
- Gojko Adzic: "Specification by Example" (acceptance criteria patterns)

---

## Version History

**Version 1.0** - 2026-01-26 - Initial best practices guide

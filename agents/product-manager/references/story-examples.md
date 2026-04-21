# Story Examples

This document provides generic user story examples across different domains. Use these as templates when writing stories for your specific solution.

---

## Example 1: Task Management - Create Task

**Story ID:** F0001-S0001
**Feature:** F0001 - Task Organization
**Domain:** Productivity SaaS

**User Story:**
As a project manager,
I want to create a task with title, description, assignee, and due date,
So that my team knows what to work on and when it's due.

**Context & Background:**
Project managers currently track tasks in spreadsheets, leading to version control issues and lack of visibility. This story enables centralized task creation with all essential metadata.

**Acceptance Criteria:**

**Given** I am on the Tasks page
**When** I click "Create Task"
**Then** I see a form with fields: Title (required), Description (optional), Assignee (dropdown), Due Date (date picker), Priority (dropdown)

**Given** I fill in Title = "Design landing page" and Assignee = "John Doe"
**When** I click "Save"
**Then** The task is created and appears in the task list
**And** John Doe receives an email notification

**Given** I try to save a task without a Title
**When** I click "Save"
**Then** I see an error message "Title is required"
**And** The task is not created

**Checklist:**
- [ ] Title is required (max 255 characters)
- [ ] Description is optional (max 2000 characters)
- [ ] Assignee dropdown shows all active team members
- [ ] Due date defaults to 7 days from now
- [ ] Priority defaults to "Medium"
- [ ] Task appears in assignee's task list immediately
- [ ] Email notification sent to assignee

**Edge Cases & Error Scenarios:**
- User tries to assign task to inactive team member → Show error "Cannot assign to inactive user"
- User selects due date in the past → Show warning "Due date is in the past, are you sure?"
- Network error during save → Show error "Failed to create task, please retry"

**Audit & Timeline Requirements:**
- Log TaskCreated event with timestamp, created by user, task details
- Capture in activity timeline: "[User] created task '[Title]'"

**Data Requirements:**
- Task entity: Id (GUID), Title (string), Description (string), AssigneeId (GUID), DueDate (DateTime), Priority (enum), Status (enum), CreatedAt, CreatedBy, UpdatedAt, UpdatedBy

**Dependencies:**
- Requires User entity (for assignee dropdown)
- Requires Email service (for notifications)

**Out of Scope:**
- Recurring tasks (deferred to Phase 2)
- Task templates (deferred to Phase 2)
- Bulk task creation (deferred to Phase 2)

**Definition of Done:**
- [ ] Code complete and peer reviewed
- [ ] Unit tests written (>80% coverage)
- [ ] Integration tests written
- [ ] Manual QA completed
- [ ] Accessible (WCAG 2.1 AA compliant)
- [ ] Documentation updated
- [ ] Deployed to staging and verified

---

## Example 2: E-commerce - Add to Cart

**Story ID:** F0002-S0001
**Feature:** F0002 - Shopping Cart
**Domain:** E-commerce

**User Story:**
As a customer,
I want to add a product to my cart,
So that I can purchase it later.

**Context & Background:**
Customers browse products and want to save items for purchase. Cart persists across sessions so customers can return later.

**Acceptance Criteria:**

**Given** I am viewing a product detail page
**When** I click "Add to Cart"
**Then** The product is added to my cart
**And** I see a confirmation message "Product added to cart"
**And** The cart icon badge updates to show cart count

**Given** I add a product that's already in my cart
**When** I click "Add to Cart"
**Then** The quantity increments by 1
**And** I see "Cart updated: 2x [Product Name]"

**Given** I add a product that's out of stock
**When** I click "Add to Cart"
**Then** I see an error "Product is out of stock"
**And** The product is not added to cart

**Checklist:**
- [ ] Product added with quantity = 1 (if new)
- [ ] Quantity incremented (if already in cart)
- [ ] Cart persists across browser sessions (cookie or local storage)
- [ ] Cart syncs to server for logged-in users
- [ ] Out of stock products cannot be added
- [ ] Cart icon badge shows total item count
- [ ] Confirmation message displays for 3 seconds

**Edge Cases & Error Scenarios:**
- Product becomes out of stock between view and add → Show error, refresh inventory
- User's cart reaches max items (100) → Show error "Cart is full"
- Network error during add → Retry 3 times, then show error

**Audit & Timeline Requirements:**
- Log ProductAddedToCart event (productId, quantity, userId, timestamp)
- Used for abandoned cart analysis

**Data Requirements:**
- Cart entity: UserId (GUID or session ID), ProductId (GUID), Quantity (int), AddedAt (DateTime)
- Product entity: Id, Name, Price, StockQuantity

**Dependencies:**
- Product catalog (must exist)
- Session management (for anonymous users)

**Out of Scope:**
- Cart recommendations (deferred to Phase 2)
- Save for later (deferred to Phase 2)

**Definition of Done:**
- [ ] Code complete and peer reviewed
- [ ] Unit tests written
- [ ] E2E tests written (Playwright)
- [ ] Performance tested (add to cart < 200ms)
- [ ] Analytics tracking verified
- [ ] Deployed to production

---

## How to Use These Examples

1. **Follow the template structure** exactly (User Story, Context, Acceptance Criteria, etc.)
2. **Use Given/When/Then** format for acceptance criteria (Gherkin syntax)
3. **Include checklists** for implementation details
4. **Document edge cases** explicitly (don't leave to developer imagination)
5. **Define DoD** - what "done" means for your team

---

## For Project-Specific Stories

See your project's `{PRODUCT_ROOT}/planning-mds/examples/stories/` directory for user story examples specific to your solution.

---

## Version History

**Version 2.0** - 2026-02-01 - Generic examples (separated from solution-specific content)
**Version 1.0** - Initial version

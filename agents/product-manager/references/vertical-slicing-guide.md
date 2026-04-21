# Vertical Slicing Guide

Comprehensive guide to breaking features into thin vertical slices that deliver end-to-end value.

## What is Vertical Slicing?

**Vertical Slice:** A feature increment that cuts through all architectural layers (UI → API → Business Logic → Database) and delivers complete user value.

**Horizontal Slice (Anti-pattern):** Building one layer at a time (all UI, then all backend, then all database).

---

## Why Vertical Slicing?

### Benefits

1. **Delivers Value Incrementally**
   - Each slice is a shippable, testable unit
   - Users get value sooner
   - Enables early feedback

2. **Reduces Integration Risk**
   - Integration happens continuously, not at the end
   - Problems discovered early when they're cheaper to fix
   - No "big bang" integration phase

3. **Enables Parallel Development**
   - Teams can work on different slices simultaneously
   - Clear boundaries reduce conflicts
   - Better utilization of team capacity

4. **Improves Estimation Accuracy**
   - Slices are small and concrete
   - Less uncertainty than large features
   - Velocity becomes more predictable

5. **Facilitates Testing**
   - Each slice is independently testable
   - QA can start testing slice 1 while slice 2 is being built
   - Faster feedback loops

---

## Vertical vs Horizontal Slicing

### Example: Customer Management Feature

#### ❌ Horizontal Slicing (DON'T DO THIS)

**Sprint 1: All UI**
- Build customer list screen
- Build customer detail screen
- Build customer create form
- Build customer edit form
- **Problem:** Nothing works without backend!

**Sprint 2: All APIs**
- Build GET /customers
- Build GET /customers/:id
- Build POST /customers
- Build PUT /customers/:id
- Build DELETE /customers/:id
- **Problem:** Still can't test end-to-end!

**Sprint 3: All Database**
- Create customer table
- Create indexes
- Create migrations
- **Problem:** Integration hell begins!

**Sprint 4: Integration**
- Connect UI to API
- Debug issues
- Fix mismatches
- **Problem:** Surprises everywhere!

**Result:** 4 sprints, no working feature until the end

---

#### ✅ Vertical Slicing (DO THIS)

**Sprint 1, Slice 1: View Customer List (Read-Only)**
- UI: Customer list screen (table, pagination)
- API: GET /customers with filtering
- DB: Customer table + sample data
- **Value:** Users can see customers!
- **Testable:** End-to-end integration test

**Sprint 1, Slice 2: Create Customer**
- UI: Create customer form (name, email, region)
- API: POST /customers with validation
- DB: Insert customer record
- Timeline: Log "Customer Created" event
- **Value:** Users can add new customers!
- **Testable:** Full create flow works

**Sprint 2, Slice 3: View Customer 360**
- UI: Customer detail screen
- API: GET /customers/:id
- DB: Join with related entities
- Timeline: Display timeline events
- **Value:** Users can see customer details!
- **Testable:** Navigation from list to detail works

**Sprint 2, Slice 4: Update Customer**
- UI: Edit customer form (pre-filled)
- API: PUT /customers/:id
- DB: Update customer record
- Timeline: Log "Customer Updated" event with changes
- **Value:** Users can fix incorrect data!
- **Testable:** Full update flow works

**Sprint 3, Slice 5: Delete Customer (Soft Delete)**
- UI: Delete button with confirmation
- API: DELETE /customers/:id (soft delete)
- DB: Update deleted_at timestamp
- Timeline: Log "Customer Deleted" event
- **Value:** Users can remove invalid customers!
- **Testable:** Delete flow works, data preserved

**Result:** Working features delivered incrementally every sprint

---

## How to Slice Features

### Strategy 1: CRUD Operations

Most entities can be sliced by CRUD operations:

1. **Read (List):** View list of entities
2. **Create:** Add new entity
3. **Read (Detail):** View single entity details
4. **Update:** Modify existing entity
5. **Delete:** Remove entity

**Example: Account Management**
- Slice 1: View account list
- Slice 2: Create new account
- Slice 3: View account 360
- Slice 4: Update account information
- Slice 5: Delete account

---

### Strategy 2: Workflow States

For workflows, slice by state transitions:

**Example: Order Workflow**

States: Received → Validating → ReadyForProcessing → Processing → Completed

**Slices:**
- Slice 1: Receive order (Received state)
- Slice 2: Validate order (Received → Validating → ReadyForProcessing)
- Slice 3: Process order (ReadyForProcessing → Processing)
- Slice 4: Complete order (Processing → Completed)
- Slice 5: Archive completed order (Completed → Archived)
- Slice 6: Handle cancellation (any state → Cancelled)
- Slice 7: Handle hold (any state → OnHold)

---

### Strategy 3: Complexity Layers

Start simple, add complexity incrementally:

**Example: Customer Search**

- **Slice 1 (Simple):** Search by exact customer name
- **Slice 2 (Better):** Search by partial name (contains)
- **Slice 3 (Advanced):** Add email search
- **Slice 4 (Filters):** Add region filter
- **Slice 5 (Polish):** Add status filter, sorting

---

### Strategy 4: Persona-Based

Slice by user role or persona:

**Example: Customer 360 Screen**

- **Slice 1:** Sales operations view (basic customer info + timeline)
- **Slice 2:** Order operations view (add order history)
- **Slice 3:** Relationship Manager view (add performance metrics)
- **Slice 4:** Admin view (add audit log, delete capability)

---

### Strategy 5: Happy Path First

Build happy path, then error cases:

**Example: Create Customer**

- **Slice 1:** Create customer with valid data (happy path)
- **Slice 2:** Validation errors (required fields, format checks)
- **Slice 3:** Business rule errors (duplicate email)
- **Slice 4:** Permission errors (unauthorized user)
- **Slice 5:** System errors (database unavailable)

---

## Slicing Patterns

### Pattern 1: Walking Skeleton

**Definition:** Thinnest possible slice that connects all architectural layers

**Purpose:** Prove integration works before building full features

**Example: Customer Management Walking Skeleton**
- UI: Display "Hello, Customers" text
- API: GET /customers returns `{"message": "Hello"}`
- DB: Simple health check query

**Value:** Confirms deployment pipeline, authentication, authorization all work

---

### Pattern 2: Defer Complexity

**Start Simple:**
- Hardcode values
- Skip optional features
- Use stub implementations

**Add Complexity Later:**
- Make it configurable
- Add optional features
- Implement full logic

**Example: Customer Status**
- Slice 1: All customers are "Active" (hardcoded)
- Slice 2: Add "Inactive" status with toggle
- Slice 3: Add "Suspended" status with reason field
- Slice 4: Add automated status changes based on rules

---

### Pattern 3: Tracer Bullet

**Definition:** Build one specific use case end-to-end

**Purpose:** Prove the approach works for a concrete scenario

**Example: Order Workflow**
- Tracer Bullet: One specific order (Starter Subscription for Small Business)
- Build full flow for this case
- Then generalize to other order types

---

## Common Slicing Mistakes

### Mistake 1: Slicing by Technology Layer

❌ **Bad:**
- Story 1: Build React components
- Story 2: Build REST APIs
- Story 3: Build database schema

✅ **Good:**
- Story 1: View customer list (UI + API + DB)
- Story 2: Create customer (UI + API + DB)

---

### Mistake 2: Making Slices Too Large

❌ **Bad:**
- Story 1: Complete customer management system

✅ **Good:**
- Story 1: View customer list
- Story 2: Create customer
- Story 3: View customer details
- Story 4: Update customer
- Story 5: Delete customer

**Rule of Thumb:** If a story takes more than 1-2 weeks, it's too large

---

### Mistake 3: Slicing by Component

❌ **Bad:**
- Story 1: Customer header component
- Story 2: Customer form component
- Story 3: Customer table component

✅ **Good:**
- Story 1: View customer list (includes table component)
- Story 2: Create customer (includes form component)
- Story 3: View customer 360 (includes header component)

---

### Mistake 4: UI-Only or API-Only Stories

❌ **Bad:**
- Story 1: Implement customer API endpoints
- Story 2: Build customer UI screens

✅ **Good:**
- Story 1: View customer list (UI + API + DB)
- Story 2: Create customer (UI + API + DB)

**Exception:** Infrastructure or refactoring stories may be horizontal, but feature stories should always be vertical

---

## Slicing Workshop Exercise

### Original Requirement

> "As a Sales Operations Manager, I want to manage customer relationships including addresses, hierarchy, orders, and performance metrics, so that I can optimize our customer network."

### Step 1: Identify Core Entities
- Customer
- Address
- Hierarchy
- Order
- Performance Metrics

### Step 2: Apply CRUD Pattern

**Customer:**
- F0001-S0001: View customer list
- F0001-S0002: Create customer
- F0001-S0003: View customer 360
- F0001-S0004: Update customer
- F0001-S0005: Delete customer

**Addresses (Separate Epic):**
- F0002-S0001: View addresses for customer
- F0002-S0002: Add address to customer
- F0002-S0003: Update address
- F0002-S0004: Remove address

**Hierarchy (Separate Epic):**
- F0003-S0001: View customer hierarchy
- F0003-S0002: Assign parent customer
- F0003-S0003: View sub-customers

**Orders (Separate Epic):**
- F0004-S0001: View orders for customer
- F0004-S0002: Link order to customer

**Performance Metrics (Future Phase):**
- Deferred - not MVP

### Step 3: Prioritize for MVP

**MVP (Must Have):**
- F0001-S0001: View customer list ✓
- F0001-S0002: Create customer ✓
- F0001-S0003: View customer 360 ✓
- F0001-S0004: Update customer ✓

**Phase 1 (Should Have):**
- F0001-S0005: Delete customer
- F0002-S0001: View addresses
- F0002-S0002: Add address
- F0003-S0001: View hierarchy

**Future (Nice to Have):**
- F0003-S0002 through F0004-S0002: Advanced features
- Performance metrics

---

## Real-World Example: Customer CRUD

### Slice 1: View Customer List (Read)

**What's Included:**
- UI: Customer list screen with table
- API: GET /customers endpoint
- DB: Customer table with sample data
- Features: Pagination, sorting by name
- Test: Integration test for list retrieval

**What's Excluded (Defer):**
- Search/filtering (Slice 2)
- Bulk actions (Phase 1)
- Export (Phase 1)

**Acceptance Criteria:**
```
Given I navigate to /customers
When the page loads
Then I see a table with columns: Name, Email, Region, Status
And I see 20 customers per page
And I can navigate to next/previous pages
And I can sort by clicking column headers
```

**Estimate:** 3-5 days

---

### Slice 2: Create Customer (Create)

**What's Included:**
- UI: Create customer form (Name, Email, Region)
- API: POST /customers with validation
- DB: Insert customer record
- Timeline: Log "Customer Created" event
- Test: Create flow end-to-end

**What's Excluded (Defer):**
- Address management (Slice 6)
- Hierarchy assignment (Slice 10)
- Bulk import (Phase 1)

**Acceptance Criteria:**
```
Given I'm on the customer list
When I click "Add New Customer"
Then I see a create form with fields: Name, Email, Region
When I fill valid data and click Save
Then the customer is created
And I see success message "Customer created successfully"
And I'm redirected to Customer 360 view
And a timeline event "Customer Created" is logged
```

**Estimate:** 3-5 days

---

### Slice 3: View Customer 360 (Read Detail)

**What's Included:**
- UI: Customer detail screen with tabs
- API: GET /customers/:id
- DB: Fetch customer with related data
- Timeline: Display recent timeline events
- Test: Navigation from list to detail

**What's Excluded (Defer):**
- Addresses tab (Slice 6)
- Orders tab (Epic 3)
- Performance metrics (Future)

**Acceptance Criteria:**
```
Given I'm on the customer list
When I click on a customer name
Then I see the Customer 360 screen showing:
  - Customer name as page title
  - Basic info: Email, Region, Status
  - Activity timeline with recent events
  - Edit and Delete action buttons
```

**Estimate:** 3-5 days

---

### Slice 4: Update Customer (Update)

**What's Included:**
- UI: Edit customer form (pre-populated)
- API: PUT /customers/:id
- DB: Update customer record
- Timeline: Log "Customer Updated" event with field changes
- Test: Update flow end-to-end

**What's Excluded (Defer):**
- Concurrent update handling (Phase 1)
- Version history (Future)
- Approval workflow (Future)

**Acceptance Criteria:**
```
Given I'm on Customer 360 screen
When I click Edit button
Then I see the edit form pre-filled with current values
When I change Name from "Acme" to "Acme Retail"
And I click Save
Then the customer is updated
And I see success message "Customer updated successfully"
And I'm redirected to Customer 360 view
And a timeline event "Customer Updated" is logged showing:
  - Field: Name
  - Old Value: "Acme"
  - New Value: "Acme Retail"
```

**Estimate:** 3-5 days

---

### Slice 5: Delete Customer (Delete)

**What's Included:**
- UI: Delete button with confirmation modal
- API: DELETE /customers/:id (soft delete)
- DB: Set deleted_at timestamp
- Timeline: Log "Customer Deleted" event
- Test: Delete flow end-to-end

**What's Excluded (Defer):**
- Hard delete (Admin only, Phase 1)
- Restore deleted customer (Phase 1)
- Cascade delete prevention (Phase 1)

**Acceptance Criteria:**
```
Given I'm on Customer 360 screen
When I click Delete button
Then I see confirmation modal "Are you sure you want to delete this customer?"
When I click Confirm
Then the customer is soft deleted (deleted_at timestamp set)
And I see success message "Customer deleted successfully"
And I'm redirected to customer list
And the deleted customer no longer appears in the list
And a timeline event "Customer Deleted" is logged
```

**Estimate:** 2-3 days

---

## Checklist: Is This a Good Vertical Slice?

Use this checklist to validate your slices:

- [ ] **End-to-End:** Touches UI, API, and Database layers
- [ ] **User Value:** Delivers something a user can see and use
- [ ] **Independently Testable:** Can write integration tests for this slice alone
- [ ] **Small Enough:** Can be completed in 1-2 weeks
- [ ] **No Hidden Dependencies:** Doesn't require other incomplete work
- [ ] **Clear Scope:** Acceptance criteria are specific and testable
- [ ] **Deferrable Complexity:** Nice-to-haves are explicitly excluded
- [ ] **Shippable:** Could be deployed to production (if needed)

---

## Summary

**Key Principles:**
1. Each slice cuts through all layers (UI → API → DB)
2. Each slice delivers complete user value
3. Start simple, add complexity incrementally
4. Happy path first, error cases later
5. MVP essentials first, nice-to-haves later

**Benefits:**
- Faster feedback
- Reduced risk
- Better parallelization
- Clearer progress tracking
- Higher quality through continuous integration

**Remember:** A vertical slice should be **thin** (small scope) and **tall** (full stack), not **thick** (large scope) and **flat** (one layer).

---

## Version History

**Version 1.0** - 2026-01-26 - Initial vertical slicing guide

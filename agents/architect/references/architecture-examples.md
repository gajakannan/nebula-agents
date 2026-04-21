# Architecture Examples

Real-world architecture examples across different domains. Use these as templates when designing your specific solution.

---

## Example 1: E-commerce Order Management System

### Order Entity Specification

**Table Name:** `Orders`

**Description:** Represents a customer order with line items.

#### Fields

| Field | Type | Constraints | Default | Description |
|-------|------|-------------|---------|-------------|
| Id | Guid | PK, NOT NULL | NewGuid() | Unique identifier |
| OrderNumber | string(50) | NOT NULL, UNIQUE | - | Human-readable order number (ORD-2026-001234) |
| CustomerId | Guid | FK → Customers, NOT NULL | - | Customer who placed order |
| Status | string(20) | NOT NULL | 'Pending' | Pending, Processing, Shipped, Delivered, Cancelled |
| OrderDate | DateTime | NOT NULL | UtcNow | When order was placed |
| TotalAmount | decimal(18,2) | NOT NULL | - | Order total (sum of line items) |
| ShippingAddress | string(500) | NOT NULL | - | Delivery address |
| PaymentMethod | string(50) | NOT NULL | - | CreditCard, PayPal, BankTransfer |
| PaymentStatus | string(20) | NOT NULL | 'Pending' | Pending, Paid, Refunded |
| CreatedAt | DateTime | NOT NULL | UtcNow | UTC timestamp |
| CreatedBy | Guid | NOT NULL | - | System or user who created |
| UpdatedAt | DateTime | NOT NULL | UtcNow | UTC timestamp |
| UpdatedBy | Guid | NOT NULL | - | User who last updated |

#### Relationships

- **One-to-Many:** Order → OrderItems (cascade delete)
- **Many-to-One:** Order → Customer (restrict delete if orders exist)

#### Indexes

- `IX_Orders_OrderNumber` (UNIQUE)
- `IX_Orders_CustomerId`
- `IX_Orders_Status`
- `IX_Orders_OrderDate`

#### Audit Requirements

- All mutations create `ActivityTimelineEvent`
- Events: OrderCreated, OrderStatusChanged, OrderCancelled
- Timeline includes before/after state for updates

### Order Workflow State Machine

**States:**
- Pending (initial) → Processing → Shipped → Delivered (terminal)
- Pending → Cancelled (terminal)

**Allowed Transitions:**

| From | To | Prerequisites | Authorization |
|------|----|---------------|---------------|
| Pending | Processing | Payment confirmed | System, Admin |
| Processing | Shipped | Items picked, label generated | WarehouseStaff, Admin |
| Shipped | Delivered | Carrier confirms delivery | System |
| Pending | Cancelled | No payment or customer request | Customer, Admin |
| Processing | Cancelled | Customer request before shipment | Admin only |

**Validation Rules:**

**Processing → Shipped:**
- All order items must be picked
- Shipping label must be generated
- Carrier tracking number must exist

**Error Responses:**

```json
{
  "code": "INVALID_TRANSITION",
  "message": "Cannot ship order. Items not yet picked.",
  "details": {
    "currentStatus": "Processing",
    "attemptedStatus": "Shipped",
    "missingRequirements": ["Items not picked"]
  }
}
```

### Order API Contract

```yaml
openapi: 3.0.0
paths:
  /api/orders:
    post:
      summary: Create a new order
      operationId: createOrder
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [customerId, items, shippingAddress]
              properties:
                customerId:
                  type: string
                  format: uuid
                items:
                  type: array
                  items:
                    type: object
                    properties:
                      productId:
                        type: string
                        format: uuid
                      quantity:
                        type: integer
                        minimum: 1
                      price:
                        type: number
                        format: decimal
                shippingAddress:
                  type: string
                paymentMethod:
                  type: string
                  enum: [CreditCard, PayPal, BankTransfer]
      responses:
        '201':
          description: Order created successfully
        '400':
          description: Validation error
        '402':
          description: Payment required
        '409':
          description: Inventory conflict (out of stock)

  /api/orders/{id}/status:
    put:
      summary: Update order status
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [status]
              properties:
                status:
                  type: string
                  enum: [Processing, Shipped, Delivered, Cancelled]
                trackingNumber:
                  type: string
                  description: Required when transitioning to Shipped
      responses:
        '200':
          description: Status updated successfully
        '409':
          description: Invalid status transition
```

### Authorization Policies

**Casbin Policies:**

```
# Customers can create orders and view their own orders
p, Customer, Order, Create, allow
p, Customer, Order, Read, allow, sub.userId == res.customerId

# WarehouseStaff can update order status (Processing → Shipped)
p, WarehouseStaff, Order, Update, allow, res.status in ["Processing", "Shipped"]

# Admins can do everything
p, Admin, Order, *, allow
```

---

## Example 2: Content Management System - Article Workflow

### Article Entity Specification

**Table Name:** `Articles`

**Fields:**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| Id | Guid | PK | Unique identifier |
| Title | string(255) | NOT NULL | Article title |
| Slug | string(255) | UNIQUE, NOT NULL | URL-friendly slug |
| Content | text | NULL | Article body (markdown) |
| AuthorId | Guid | FK → Users | Author |
| Status | string(20) | NOT NULL | Draft, InReview, Published, Archived |
| PublishedAt | DateTime | NULL | When published |
| CreatedAt | DateTime | NOT NULL | Creation timestamp |
| UpdatedAt | DateTime | NOT NULL | Last update timestamp |

### Article Workflow

**States:**
- Draft (initial) → InReview → Published (terminal)
- Draft → Archived (terminal)

**Allowed Transitions:**

| From | To | Prerequisites |
|------|----|---------------|
| Draft | InReview | Title and content populated |
| InReview | Draft | Editor requests changes |
| InReview | Published | Editor approval |
| Published | Archived | Author or editor archives |

---

## Example 3: SaaS Subscription Management

### Subscription Entity

**Table Name:** `Subscriptions`

**Fields:**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| Id | Guid | PK | Subscription ID |
| CustomerId | Guid | FK → Customers | Customer |
| PlanId | Guid | FK → Plans | Subscription plan (Starter, Pro, Enterprise) |
| Status | string(20) | NOT NULL | Active, Suspended, Cancelled, Expired |
| BillingCycle | string(20) | NOT NULL | Monthly, Yearly |
| StartDate | DateTime | NOT NULL | Subscription start |
| EndDate | DateTime | NULL | Subscription end (null = ongoing) |
| NextBillingDate | DateTime | NOT NULL | Next charge date |
| MRR | decimal(18,2) | NOT NULL | Monthly Recurring Revenue |

### Subscription Workflow

**States:**
- Active → Suspended (payment failed) → Active (payment recovered)
- Active → Cancelled → Expired (terminal)

**Business Rules:**
- Cannot cancel if in trial period (trial cancels automatically)
- Cannot downgrade mid-cycle (takes effect next billing date)
- Suspend after 3 failed payment attempts
- Expire 30 days after cancellation (grace period)

---

## How to Use These Examples

1. Select a domain relevant to your solution (or create your own)
2. Follow the structure (Entity → Workflow → API → Authorization)
3. Adapt field names and relationships to your domain
4. Keep patterns consistent across all entities in your system
5. Reference these examples when designing new modules

---

## For Project-Specific Architecture

See your project's `{PRODUCT_ROOT}/planning-mds/examples/architecture/` directory for architecture examples specific to your solution.

---

## Version History

**Version 2.0** - 2026-02-01 - Generic examples (separated from solution-specific content)
**Version 1.0** - Initial version

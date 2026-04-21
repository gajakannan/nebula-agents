# Workflow Design Guide

Comprehensive guide for designing workflows and state machines. This guide covers workflow fundamentals, Temporal integration, order workflow patterns, subscription expiration workflows, and event sourcing.

---

## 1. Workflow Fundamentals

### 1.1 State Machine Components

**State Machine** is a model of computation with defined states and transitions.

**Components:**
- **States**: Discrete stages in a workflow (Received, Pending, InReview, Approved, Completed)
- **Transitions**: Allowed state changes (Pending → ReadyForReview)
- **Events**: Triggers for transitions (user action, time-based, external system)
- **Guards**: Conditions that must be true for transition to occur (required fields populated)
- **Actions**: Side effects executed on transition (send email, log event)

---

### 1.2 State Types

**Initial State:**
- Entry point of workflow (e.g., Received for orders)
- Created automatically when entity created

**Active States:**
- Work-in-progress states (Pending, InReview, Approved)
- Can transition to other states

**Terminal States:**
- End states, no further transitions allowed (Completed, Rejected, Cancelled)
- Workflow complete

**Example:**
```
Received (initial)
    ↓
Pending (active)
    ↓
ReadyForReview (active)
    ↓
InReview (active)
    ↓
Approved (active)
    ↓
Completed (terminal)
```

---

### 1.3 Transition Rules

**Allowed Transitions:** Define valid state changes

**Blocked Transitions:** Invalid state changes (return 409 Conflict)

**Example:**
```csharp
private static readonly Dictionary<string, List<string>> AllowedTransitions = new()
{
    ["Pending"] = new() { "NeedsInfo", "ReadyForReview", "Rejected", "Cancelled" },
    ["ReadyForReview"] = new() { "InReview", "NeedsInfo", "Rejected", "Cancelled" },
    ["InReview"] = new() { "Approved", "NeedsInfo", "Rejected", "Cancelled" },
    ["Approved"] = new() { "PaymentPending", "Rejected", "Cancelled" },
    ["PaymentPending"] = new() { "Completed", "Rejected" },
    ["Completed"] = new(), // Terminal, no transitions
    ["Rejected"] = new(), // Terminal
    ["Cancelled"] = new() // Terminal
};

public static bool IsValidTransition(string fromStatus, string toStatus)
{
    return AllowedTransitions.TryGetValue(fromStatus, out var allowed) && allowed.Contains(toStatus);
}
```

---

### 1.4 Workflow Events (Triggers)

**User-Initiated Events:**
- User clicks "Submit for Review" button → transition to ReadyForReview
- Manager clicks "Approve" → transition to Approved

**Time-Based Events:**
- 120 days before subscription expiration → trigger expiration reminder
- 30 days before expiration → escalate to manager

**System Events:**
- Payment confirmed → transition to Completed
- External pricing API returns quote → transition to Approved

---

### 1.5 Compensation (Rollback)

**Compensation** is the process of undoing a workflow step when a later step fails.

**Example: Payment Request Fails**
- Transition to PaymentPending
- Call payment API → fails
- Compensate: Transition back to Approved
- Log compensation event

**Saga Pattern:** Sequence of local transactions with compensating transactions for rollback.

---

### 1.6 Idempotency

**Idempotent Workflows** can be safely retried without side effects.

**Design Principle:**
- Store workflow state (current status)
- If transition request received for current state → no-op (already transitioned)
- If transition request for different state → validate and execute

**Example:**
```csharp
public async Task TransitionAsync(Guid orderId, string toStatus)
{
    var order = await _context.Orders.FindAsync(orderId);

    // Idempotency check
    if (order.Status == toStatus)
        return; // Already in target state, no-op

    // Validate and execute transition
    if (!IsValidTransition(order.Status, toStatus))
        throw new InvalidTransitionException();

    order.Status = toStatus;
    await _context.SaveChangesAsync();
}
```

---

## 2. Temporal Integration

### 2.1 What is Temporal?

**Temporal** is a durable workflow orchestration engine.

**Use Cases:**
- Long-running workflows (expiration reminders spanning months)
- Scheduled tasks (send reminder 120 days before expiration)
- Reliable retries (retry failed external API calls)
- Workflow versioning (change workflow logic without breaking in-flight workflows)

---

### 2.2 Temporal Workflow Definitions (C# SDK)

**Workflow Definition:**

```csharp
using Temporalio.Workflows;

[Workflow]
public class ExpirationReminderWorkflow
{
    [WorkflowRun]
    public async Task RunAsync(ExpirationWorkflowInput input)
    {
        var subscription = input.Subscription;

        // Schedule reminder 120 days before expiration
        var delay120 = subscription.ExpirationDate.AddDays(-120) - DateTime.UtcNow;
        if (delay120 > TimeSpan.Zero)
        {
            await Workflow.DelayAsync(delay120);
            await Workflow.ExecuteActivityAsync<SendExpirationReminderActivity>(
                new ReminderActivityInput { SubscriptionId = subscription.Id, DaysOut = 120 });
        }

        // Schedule reminder 90 days before expiration
        await Workflow.DelayAsync(TimeSpan.FromDays(30));
        await Workflow.ExecuteActivityAsync<SendExpirationReminderActivity>(
            new ReminderActivityInput { SubscriptionId = subscription.Id, DaysOut = 90 });

        // Schedule reminder 60 days before expiration
        await Workflow.DelayAsync(TimeSpan.FromDays(30));
        await Workflow.ExecuteActivityAsync<SendExpirationReminderActivity>(
            new ReminderActivityInput { SubscriptionId = subscription.Id, DaysOut = 60 });

        // Check if follow-up order created
        var followUpOrderCreated = await Workflow.ExecuteActivityAsync<CheckFollowUpOrderActivity>(
            subscription.Id);

        if (!followUpOrderCreated)
        {
            // Escalate to manager if no follow-up order 30 days before expiration
            await Workflow.DelayAsync(TimeSpan.FromDays(30));
            await Workflow.ExecuteActivityAsync<EscalateFollowUpActivity>(subscription.Id);
        }
    }
}

// Workflow input
public record ExpirationWorkflowInput(Guid SubscriptionId, Subscription Subscription);
```

---

### 2.3 Temporal Activities (Side Effects)

**Activities** perform side effects (send email, call API, write to database).

**Activity Definition:**

```csharp
using Temporalio.Activities;

[Activity]
public class SendExpirationReminderActivity
{
    private readonly IEmailService _emailService;

    [ActivityMethod]
    public async Task ExecuteAsync(ReminderActivityInput input)
    {
        var subscription = await _subscriptionRepository.GetByIdAsync(input.SubscriptionId);

        await _emailService.SendExpirationReminderAsync(
            to: subscription.CustomerEmail,
            subject: $"Expiration Reminder - {input.DaysOut} Days",
            body: $"Your subscription {subscription.SubscriptionNumber} expires in {input.DaysOut} days.");
    }
}
```

**Activities are:**
- Retryable (automatic retry on failure)
- Timeout-enforced (fail if activity takes too long)
- Logged (execution history tracked)

---

### 2.4 Temporal Signals (External Events)

**Signals** send events to running workflows from external systems.

**Example: Follow-up Order Submitted Signal**

```csharp
[Workflow]
public class ExpirationReminderWorkflow
{
    private bool _followUpOrderSubmitted = false;

    [WorkflowRun]
    public async Task RunAsync(ExpirationWorkflowInput input)
    {
        // ... schedule reminders

        // Wait for follow-up order or expiration date
        await Workflow.WaitConditionAsync(() => _followUpOrderSubmitted || DateTime.UtcNow >= input.Subscription.ExpirationDate);

        if (_followUpOrderSubmitted)
        {
            // Success, workflow complete
            return;
        }
        else
        {
            // Expiration reached, escalate
            await Workflow.ExecuteActivityAsync<EscalateFollowUpActivity>(input.SubscriptionId);
        }
    }

    [WorkflowSignal]
    public async Task FollowUpOrderSubmittedAsync()
    {
        _followUpOrderSubmitted = true;
    }
}

// External system signals workflow
await _temporalClient.SignalWorkflowAsync<ExpirationReminderWorkflow>(
    workflowId: $"expiration-{subscriptionId}",
    signal: wf => wf.FollowUpOrderSubmittedAsync());
```

---

### 2.5 Temporal Queries (Workflow Status)

**Queries** read workflow state without mutating it.

```csharp
[Workflow]
public class ExpirationReminderWorkflow
{
    private int _remindersSent = 0;

    [WorkflowQuery]
    public int GetRemindersSent() => _remindersSent;

    [WorkflowRun]
    public async Task RunAsync(ExpirationWorkflowInput input)
    {
        await Workflow.ExecuteActivityAsync<SendExpirationReminderActivity>(...);
        _remindersSent++;
    }
}

// Query workflow
var remindersSent = await _temporalClient.QueryWorkflowAsync<ExpirationReminderWorkflow, int>(
    workflowId: $"expiration-{subscriptionId}",
    query: wf => wf.GetRemindersSent());
```

---

### 2.6 Temporal Best Practices

**Determinism:**
- Workflow code must be deterministic (same input → same output)
- No random numbers, no DateTime.Now (use Workflow.UtcNow)
- No direct I/O (use activities for I/O)

**Versioning:**
- Use workflow versioning to change logic without breaking in-flight workflows

```csharp
[Workflow]
public class ExpirationReminderWorkflow
{
    [WorkflowRun]
    public async Task RunAsync(ExpirationWorkflowInput input)
    {
        var version = Workflow.GetVersion("add-60-day-reminder", Workflow.DefaultVersion, 2);

        if (version >= 2)
        {
            // New logic: Send 60-day reminder
            await Workflow.DelayAsync(TimeSpan.FromDays(60));
            await Workflow.ExecuteActivityAsync<SendExpirationReminderActivity>(...);
        }
    }
}
```

**Child Workflows:**
- Break complex workflows into smaller child workflows
- Each child workflow can be retried independently

---

## 3. Order Workflow Deep Dive

### 3.1 Complete State Machine

**States:**
1. Received (initial)
2. Pending
3. NeedsInfo
4. ReadyForReview
5. InReview
6. Approved
7. PaymentPending
8. Completed (terminal)
9. Rejected (terminal)
10. Cancelled (terminal)

**Transition Matrix:**

| From | To | Prerequisites | Authorization | Side Effects |
|------|----|--------------|--------------|--------------|
| Received | Pending | None | System | Log timeline event |
| Pending | NeedsInfo | Missing info documented | User, Admin | Email customer, log event |
| Pending | ReadyForReview | All required fields | User, Admin | Email reviewers, log event |
| Pending | Rejected | Rejection reason | User, Admin | Email customer, log event |
| NeedsInfo | ReadyForReview | Missing info received | User, Admin | Email reviewers, log event |
| ReadyForReview | InReview | Reviewer assigned | Manager, Admin | Log event |
| InReview | Approved | Approval granted | Manager, Admin | Email customer, log event |
| Approved | PaymentPending | Customer acceptance | User, Admin | Call payment API, log event |
| PaymentPending | Completed | Payment confirmed | Manager, Admin | Generate invoice, email customer, log event |

---

### 3.2 Validation Rules Per Transition

**Pending → ReadyForReview:**

```csharp
public async Task ValidateReadyForReview(Order order)
{
    var errors = new List<string>();

    if (string.IsNullOrEmpty(order.CustomerName))
        errors.Add("Customer name is required");

    if (order.Category == null)
        errors.Add("Category is required");

    if (order.CustomerId == null)
        errors.Add("Customer must be assigned");

    if (order.OrderDate == default)
        errors.Add("Order date is required");

    if (order.DueDate == default)
        errors.Add("Due date is required");

    if (order.OrderDate >= order.DueDate)
        errors.Add("Due date must be after order date");

    if (errors.Any())
        throw new ValidationException("Cannot transition to ReadyForReview", errors);
}
```

---

### 3.3 Side Effects (Email Notifications, Timeline Events)

**On Transition:**

```csharp
public async Task OnTransitionedToReadyForReview(Order order)
{
    // 1. Create workflow transition event (immutable)
    await _context.WorkflowTransitions.AddAsync(new WorkflowTransition
    {
        OrderId = order.Id,
        FromStatus = "Pending",
        ToStatus = "ReadyForReview",
        TransitionedAt = DateTime.UtcNow,
        TransitionedBy = _currentUser.UserId
    });

    // 2. Create timeline event
    await _context.ActivityTimelineEvents.AddAsync(new ActivityTimelineEvent
    {
        EntityType = "Order",
        EntityId = order.Id,
        EventType = "OrderReadyForReview",
        UserId = _currentUser.UserId,
        Timestamp = DateTime.UtcNow,
        Payload = new { orderNumber = order.OrderNumber }
    });

    // 3. Send email notification to review team
    await _emailService.SendOrderReadyForReviewEmailAsync(order);

    await _context.SaveChangesAsync();
}
```

---

### 3.4 Error Handling (Invalid Transitions, Missing Data)

**Invalid Transition (409 Conflict):**

```json
{
  "code": "INVALID_TRANSITION",
  "message": "Cannot transition from Completed to Pending",
  "details": {
    "currentStatus": "Completed",
    "attemptedStatus": "Pending",
    "allowedStatuses": []
  }
}
```

**Missing Required Fields (400 Bad Request):**

```json
{
  "code": "MISSING_REQUIRED_FIELDS",
  "message": "Cannot transition to ReadyForReview. Missing required fields.",
  "details": [
    { "field": "customerName", "message": "Customer name is required" },
    { "field": "category", "message": "Category is required" }
  ]
}
```

---

### 3.5 Compensation (Rollback if Payment Fails)

**Scenario:** Transition to PaymentPending → Payment API fails → Rollback to Approved

```csharp
public async Task TransitionToPaymentPendingAsync(Guid orderId)
{
    var order = await _context.Orders.FindAsync(orderId);

    // Transition to PaymentPending
    order.Status = "PaymentPending";
    await _context.SaveChangesAsync();

    try
    {
        // Call payment API
        var paymentResult = await _paymentService.ProcessPaymentAsync(order);

        if (!paymentResult.Success)
            throw new PaymentFailedException(paymentResult.Error);
    }
    catch (Exception ex)
    {
        // Compensate: Rollback to Approved
        order.Status = "Approved";

        await _context.WorkflowTransitions.AddAsync(new WorkflowTransition
        {
            OrderId = orderId,
            FromStatus = "PaymentPending",
            ToStatus = "Approved",
            TransitionedAt = DateTime.UtcNow,
            TransitionedBy = _currentUser.UserId,
            Reason = $"Payment failed: {ex.Message}"
        });

        await _context.SaveChangesAsync();

        throw; // Rethrow to return error to client
    }
}
```

---

## 4. Subscription Expiration Workflow

### 4.1 Scheduled Reminders

**Temporal Workflow for expiration reminders:**

```csharp
[Workflow]
public class ExpirationReminderWorkflow
{
    [WorkflowRun]
    public async Task RunAsync(ExpirationWorkflowInput input)
    {
        var subscription = input.Subscription;

        // Reminder 1: 120 days before expiration
        var delay120 = subscription.ExpirationDate.AddDays(-120) - Workflow.UtcNow;
        if (delay120 > TimeSpan.Zero)
        {
            await Workflow.DelayAsync(delay120);
            await Workflow.ExecuteActivityAsync<SendExpirationReminderActivity>(
                new ReminderActivityInput { SubscriptionId = subscription.Id, DaysOut = 120 },
                new ActivityOptions { StartToCloseTimeout = TimeSpan.FromMinutes(5) });
        }

        // Reminder 2: 90 days before expiration
        await Workflow.DelayAsync(TimeSpan.FromDays(30));
        await Workflow.ExecuteActivityAsync<SendExpirationReminderActivity>(
            new ReminderActivityInput { SubscriptionId = subscription.Id, DaysOut = 90 });

        // Reminder 3: 60 days before expiration
        await Workflow.DelayAsync(TimeSpan.FromDays(30));
        await Workflow.ExecuteActivityAsync<SendExpirationReminderActivity>(
            new ReminderActivityInput { SubscriptionId = subscription.Id, DaysOut = 60 });

        // Final check: 30 days before expiration
        await Workflow.DelayAsync(TimeSpan.FromDays(30));

        var followUpOrderCreated = await Workflow.ExecuteActivityAsync<CheckFollowUpOrderActivity>(
            subscription.Id);

        if (!followUpOrderCreated)
        {
            // Escalate to manager
            await Workflow.ExecuteActivityAsync<EscalateFollowUpActivity>(
                new EscalationActivityInput
                {
                    SubscriptionId = subscription.Id,
                    Reason = "No follow-up order created 30 days before expiration"
                });
        }
    }
}
```

---

### 4.2 Expiration Status Tracking

**Follow-up Tracking Entity:**

```csharp
public class SubscriptionFollowUp : BaseEntity
{
    public Guid SubscriptionId { get; set; }
    public Subscription Subscription { get; set; }

    public Guid? FollowUpOrderId { get; set; }
    public Order? FollowUpOrder { get; set; }

    public string Status { get; set; } // Pending, Approved, Completed, NotCompleted, Rejected

    public DateTime ExpirationDate { get; set; }
    public DateTime? ApprovedAt { get; set; }
    public DateTime? CompletedAt { get; set; }
}
```

---

### 4.3 Escalation Rules

**Escalation Triggers:**
- No follow-up order created 30 days before expiration → escalate to manager
- Follow-up pending 60 days before expiration → escalate to director

**Escalation Activity:**

```csharp
[Activity]
public class EscalateFollowUpActivity
{
    [ActivityMethod]
    public async Task ExecuteAsync(EscalationActivityInput input)
    {
        var subscription = await _subscriptionRepository.GetByIdAsync(input.SubscriptionId);

        // Send email to manager
        await _emailService.SendEscalationEmailAsync(
            to: "manager@example.com",
            subject: $"Escalation: Follow-up Pending for Subscription {subscription.SubscriptionNumber}",
            body: $"Subscription {subscription.SubscriptionNumber} expires in 30 days. No follow-up order created. Reason: {input.Reason}");

        // Log escalation event
        await _context.ActivityTimelineEvents.AddAsync(new ActivityTimelineEvent
        {
            EntityType = "SubscriptionFollowUp",
            EntityId = subscription.Id,
            EventType = "FollowUpEscalated",
            UserId = Guid.Empty, // System user
            Timestamp = DateTime.UtcNow,
            Payload = new { subscriptionId = subscription.Id, reason = input.Reason }
        });

        await _context.SaveChangesAsync();
    }
}
```

---

## 5. Event Sourcing for Workflows

### 5.1 WorkflowTransition Events (Immutable)

**Store all state transitions as immutable events:**

```csharp
public class WorkflowTransition : BaseEntity
{
    public Guid OrderId { get; set; } // Or other entity with workflow
    public string FromStatus { get; set; }
    public string ToStatus { get; set; }
    public DateTime TransitionedAt { get; set; }
    public Guid TransitionedBy { get; set; }
    public string? Reason { get; set; } // Required for Rejected/Cancelled
}
```

**Benefits:**
- Complete audit trail of all state changes
- Can rebuild current state from events
- Can analyze workflow patterns (average time in each state, common paths)

---

### 5.2 Rebuilding Workflow State from Events

**Rebuild current state by replaying events:**

```csharp
public async Task<Order> RebuildOrderFromEventsAsync(Guid orderId)
{
    var transitions = await _context.WorkflowTransitions
        .Where(t => t.OrderId == orderId)
        .OrderBy(t => t.TransitionedAt)
        .ToListAsync();

    var order = new Order { Id = orderId, Status = "Received" };

    foreach (var transition in transitions)
    {
        order.Status = transition.ToStatus;
    }

    return order;
}
```

**Use Cases:**
- Debugging (what was the state at time X?)
- Analytics (how long do orders spend in InReview?)
- Compliance (prove state was X at time Y)

---

### 5.3 Event Versioning

**Handle schema changes over time:**

**Event Payload with Version:**

```csharp
public class WorkflowTransition : BaseEntity
{
    public string EventType { get; set; } // "OrderTransitioned"
    public int EventVersion { get; set; } // 1, 2, 3...
    public string Payload { get; set; } // JSON

    // Deserialize based on version
    public T GetPayload<T>() where T : class
    {
        return EventVersion switch
        {
            1 => JsonSerializer.Deserialize<T>(Payload),
            2 => JsonSerializer.Deserialize<T>(Payload), // V2 schema
            _ => throw new NotSupportedException($"Event version {EventVersion} not supported")
        };
    }
}
```

---

## Version History

**Version 2.0** - 2026-01-31 - Comprehensive workflow design guide with Temporal integration (350 lines)
**Version 1.0** - 2026-01-26 - Initial workflow design guide (52 lines)

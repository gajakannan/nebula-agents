# Quality Engineer - Code Patterns Reference

Detailed code examples and patterns for test implementation across all tiers.

## Testing by Layer

### Frontend Testing ({PRODUCT_ROOT}/experience/)

**Test Structure:**
```
{PRODUCT_ROOT}/experience/
├── src/
│   ├── components/
│   │   └── CustomerCard.tsx
│   └── pages/
│       └── CustomerList.tsx
└── tests/
    ├── unit/
    │   └── CustomerCard.test.tsx
    ├── integration/
    │   └── CustomerList.test.tsx
    └── e2e/
        └── customer-flows.spec.ts
```

**Coverage Target:** ≥80% for business logic components

**Example Unit Test:**
```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CustomerCard } from './CustomerCard';

describe('CustomerCard', () => {
  it('displays customer name and status', () => {
    const customer = { id: '1', name: 'Test Customer', status: 'Active' };
    render(<CustomerCard customer={customer} />);

    expect(screen.getByText('Test Customer')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('shows inactive badge for inactive customers', () => {
    const customer = { id: '1', name: 'Test', status: 'Inactive' };
    render(<CustomerCard customer={customer} />);

    expect(screen.getByText('Inactive')).toHaveClass('badge-inactive');
  });
});
```

**Example E2E Test:**
```typescript
import { test, expect } from '@playwright/test';

test('create customer flow', async ({ page }) => {
  await page.goto('/customers');

  // Click Create button
  await page.getByRole('button', { name: 'Create Customer' }).click();

  // Fill form
  await page.getByLabel('Customer Name').fill('E2E Test Customer');
  await page.getByLabel('Email').fill('e2e@example.com');
  await page.getByLabel('Phone').fill('1234567890');

  // Submit
  await page.getByRole('button', { name: 'Save' }).click();

  // Verify
  await expect(page.getByText('Customer created successfully')).toBeVisible();
  await expect(page.getByText('E2E Test Customer')).toBeVisible();
});
```

**Example Accessibility Test:**
```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('customer form has no accessibility violations', async ({ page }) => {
  await page.goto('/customers/new');

  const results = await new AxeBuilder({ page }).analyze();

  expect(results.violations).toEqual([]);
});
```

### Backend Testing ({PRODUCT_ROOT}/engine/)

**Test Structure:**
```
{PRODUCT_ROOT}/engine/
├── src/
│   └── MyApp.Domain/
│       └── Entities/
│           └── Customer.cs
├── tests/
    ├── MyApp.Domain.Tests/
    │   └── CustomerTests.cs
    ├── MyApp.Application.Tests/
    │   └── CustomerServiceTests.cs
    └── MyApp.Api.Tests/
        └── CustomerEndpointTests.cs
```

**Coverage Target:** ≥80% for domain and application logic

**Example Unit Test:**
```csharp
using Xunit;
using Shouldly;

public class CustomerTests
{
    [Fact]
    public void Activate_ShouldSetStatusToActive()
    {
        // Arrange
        var customer = new Customer { Status = CustomerStatus.Inactive };

        // Act
        customer.Activate();

        // Assert
        customer.Status.ShouldBe(CustomerStatus.Active);
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void SetName_WithEmptyName_ShouldThrowException(string name)
    {
        // Arrange
        var customer = new Customer();

        // Act
        var act = () => customer.SetName(name);

        // Assert
        var exception = Should.Throw<ArgumentException>(act);
        exception.Message.ShouldBe("Name cannot be empty");
    }
}
```

**Example Integration Test (with Testcontainers):**
```csharp
using Testcontainers.PostgreSql;
using Microsoft.EntityFrameworkCore;
using Xunit;

public class CustomerRepositoryTests : IAsyncLifetime
{
    private PostgreSqlContainer _postgres;
    private AppDbContext _context;
    private CustomerRepository _repository;

    public async Task InitializeAsync()
    {
        // Start real PostgreSQL container
        _postgres = new PostgreSqlBuilder()
            .WithImage("postgres:15")
            .Build();
        await _postgres.StartAsync();

        // Create DbContext
        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseNpgsql(_postgres.GetConnectionString())
            .Options;
        _context = new AppDbContext(options);
        await _context.Database.MigrateAsync();

        _repository = new CustomerRepository(_context);
    }

    [Fact]
    public async Task AddAsync_ShouldPersistCustomer()
    {
        // Arrange
        var customer = new Customer
        {
            Id = Guid.NewGuid(),
            Name = "Test Customer",
            Email = "test@example.com"
        };

        // Act
        await _repository.AddAsync(customer);

        // Assert
        var saved = await _repository.GetByIdAsync(customer.Id);
        saved.ShouldNotBeNull();
        saved!.Name.ShouldBe("Test Customer");
    }

    public async Task DisposeAsync()
    {
        await _context.DisposeAsync();
        await _postgres.DisposeAsync();
    }
}
```

**Example Load Test (k6):**
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 50 },   // Ramp up to 50 users
    { duration: '3m', target: 50 },   // Stay at 50 users
    { duration: '1m', target: 100 },  // Spike to 100 users
    { duration: '1m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests < 500ms
    http_req_failed: ['rate<0.01'],   // Error rate < 1%
  },
};

export default function () {
  const res = http.get('http://localhost:5000/api/customers');

  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });

  sleep(1);
}
```

### AI/Neuron Testing ({PRODUCT_ROOT}/neuron/)

**Test Structure:**
```
{PRODUCT_ROOT}/neuron/
├── domain_agents/
│   └── processor.py
└── tests/
    ├── test_processor_unit.py
    ├── test_processor_integration.py
    └── test_processor_evaluation.py
```

**Coverage Target:** ≥80% for agent logic

**Example Unit Test (Mocked LLM):**
```python
from unittest.mock import Mock, patch
import pytest

@patch('neuron.models.claude.ClaudeClient.generate')
def test_processor_classifies_record(mock_generate):
    # Mock LLM response
    mock_generate.return_value = {
        "content": "Priority: Medium\nScore: 75\nReasoning: Standard criteria met"
    }

    # Test agent
    agent = ProcessorAgent()
    result = agent.analyze_record({
        "category": "Standard",
        "value": 50000
    })

    assert result["priority"] == "Medium"
    assert result["score"] == 75
    mock_generate.assert_called_once()
```

**Example Evaluation Test:**
```python
import pytest

@pytest.fixture
def golden_dataset():
    return [
        {
            "input": {"category": "Standard", "value": 50000},
            "expected_priority": "Medium",
            "expected_score_range": (60, 80)
        },
        {
            "input": {"category": "Priority", "value": 100000},
            "expected_priority": "High",
            "expected_score_range": (80, 100)
        },
    ]

def test_processor_accuracy(golden_dataset):
    agent = ProcessorAgent(use_mock=True)
    correct = 0

    for case in golden_dataset:
        result = agent.analyze_record(case["input"])

        if result["priority"] == case["expected_priority"]:
            correct += 1

        score_in_range = (
            case["expected_score_range"][0]
            <= result["score"]
            <= case["expected_score_range"][1]
        )
        assert score_in_range, f"Score {result['score']} out of range"

    accuracy = correct / len(golden_dataset)
    assert accuracy >= 0.85, f"Accuracy {accuracy} below threshold"
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npm run test:unit
      - run: npm run test:e2e
      - run: npm run test:a11y
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-dotnet@v3
      - run: dotnet test --collect:"XPlat Code Coverage"
      - run: dotnet test --filter Category=Integration
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  ai-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements.txt
      - run: pytest {PRODUCT_ROOT}/neuron/tests/ --cov={PRODUCT_ROOT}/neuron --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'

  quality-gate:
    needs: [frontend-tests, backend-tests, ai-tests]
    runs-on: ubuntu-latest
    steps:
      - name: Check coverage
        run: |
          if [ "$COVERAGE" -lt 80 ]; then
            echo "Coverage below 80%"
            exit 1
          fi
```

## Common Patterns

### Testing Error Scenarios
```typescript
it('shows error message when API fails', async () => {
  // Mock API error
  server.use(
    http.get('/api/customers', () => {
      return new HttpResponse(null, { status: 500 });
    })
  );

  render(<CustomerList />);

  await waitFor(() => {
    expect(screen.getByText('Failed to load customers')).toBeInTheDocument();
  });
});
```

### Testing Async Operations
```csharp
[Fact]
public async Task GetCustomerAsync_ShouldReturnCustomer()
{
    // Arrange
    var customer = new Customer { Id = Guid.NewGuid() };
    await _repository.AddAsync(customer);

    // Act
    var result = await _repository.GetByIdAsync(customer.Id);

    // Assert
    result.ShouldNotBeNull();
    result!.Id.ShouldBe(customer.Id);
}
```

### Parametrized Tests
```csharp
[Theory]
[InlineData("test@example.com", true)]
[InlineData("invalid-email", false)]
[InlineData("", false)]
[InlineData(null, false)]
public void ValidateEmail_ShouldReturnExpectedResult(string email, bool expected)
{
    var isValid = EmailValidator.Validate(email);
    isValid.ShouldBe(expected);
}
```

## Best Practices

### Test Pyramid
```
      /\
     /  \  10% E2E (Slow, expensive)
    /----\
   /      \  20% Integration (Medium)
  /--------\
 /__________\  70% Unit (Fast, cheap)
```

**Why:**
- Unit tests are fast (< 1s), give immediate feedback
- Integration tests verify contracts (< 10s)
- E2E tests verify full flows but are slow (< 1min)

### Test Naming Convention
```typescript
// Good: Descriptive test names
describe('CustomerService', () => {
  it('creates customer with valid data', () => {});
  it('throws error when email is invalid', () => {});
  it('activates inactive customer', () => {});
});

// Bad: Non-descriptive names
describe('CustomerService', () => {
  it('test1', () => {});
  it('works', () => {});
});
```

### Arrange-Act-Assert Pattern
```csharp
[Fact]
public void TestMethod()
{
    // Arrange - Set up test data and dependencies
    var customer = new Customer { Name = "Test" };
    var service = new CustomerService();

    // Act - Execute the method under test
    var result = service.Activate(customer);

    // Assert - Verify the outcome
    result.ShouldBeTrue();
    customer.Status.ShouldBe(CustomerStatus.Active);
}
```

### Test Isolation
```typescript
// Good: Each test is independent
describe('CustomerList', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    // Fresh setup for each test
    queryClient = new QueryClient();
  });

  it('test 1', () => {
    // Uses fresh queryClient
  });

  it('test 2', () => {
    // Uses fresh queryClient, independent of test 1
  });
});
```

### Mock External Dependencies
```typescript
// Mock API calls in frontend tests
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

const server = setupServer(
  http.get('/api/customers', () => {
    return HttpResponse.json([{ id: '1', name: 'Mock Customer' }]);
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### Test Data Builders
```csharp
// Good: Test data builder for reusable fixtures
public class CustomerBuilder
{
    private string _name = "Default Customer";
    private string _email = "default@example.com";
    private CustomerStatus _status = CustomerStatus.Active;

    public CustomerBuilder WithName(string name)
    {
        _name = name;
        return this;
    }

    public CustomerBuilder WithEmail(string email)
    {
        _email = email;
        return this;
    }

    public Customer Build() => new Customer
    {
        Id = Guid.NewGuid(),
        Name = _name,
        Email = _email,
        Status = _status
    };
}

// Usage
var customer = new CustomerBuilder()
    .WithName("Test Customer")
    .WithEmail("test@example.com")
    .Build();
```

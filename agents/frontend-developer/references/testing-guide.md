# Testing Guide (React Testing Library)

**Version:** 1.0
**Last Updated:** 2026-01-29
**Applies To:** Frontend Developer

---

## Overview

This guide covers frontend testing using **React Testing Library** and **Vitest**. We follow the principle: **"Test behavior, not implementation."**

**Philosophy:** Write tests that interact with components the same way users do - through the rendered UI, not internal implementation details.

---

## Installation

```bash
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event @vitejs/plugin-react
```

### Vitest Configuration

```ts
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/mockData',
      ],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
```

### Test Setup File

```ts
// src/test/setup.ts
import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
```

---

## Basic Component Testing

### Simple Component Test

```tsx
// CustomerCard.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CustomerCard } from './CustomerCard';

describe('CustomerCard', () => {
  const mockCustomer = {
    id: '123',
    name: 'Acme Corporation',
    email: 'contact@acme.com',
    region: 'US-West',
  };

  it('should render customer name', () => {
    render(<CustomerCard customer={mockCustomer} />);

    expect(screen.getByText('Acme Corporation')).toBeInTheDocument();
  });

  it('should render email', () => {
    render(<CustomerCard customer={mockCustomer} />);

    expect(screen.getByText(/contact@acme.com/)).toBeInTheDocument();
  });

  it('should render email as a link', () => {
    render(<CustomerCard customer={mockCustomer} />);

    const emailLink = screen.getByRole('link', { name: /contact@acme.com/i });
    expect(emailLink).toHaveAttribute('href', 'mailto:contact@acme.com');
  });
});
```

---

## Querying Elements

### Query Priority (Use in this order)

1. **Accessible Queries (Preferred)**
```tsx
// By role (best for accessibility)
screen.getByRole('button', { name: /submit/i });
screen.getByRole('heading', { name: /customer details/i });
screen.getByRole('textbox', { name: /email/i });
screen.getByRole('link', { name: /view details/i });

// By label text (forms)
screen.getByLabelText(/customer name/i);

// By placeholder
screen.getByPlaceholderText(/search customers/i);

// By text content
screen.getByText(/no customers found/i);
```

2. **Semantic Queries**
```tsx
// By display value (inputs with values)
screen.getByDisplayValue(/acme corporation/i);

// By alt text (images)
screen.getByAltText(/customer logo/i);

// By title
screen.getByTitle(/close dialog/i);
```

3. **Test IDs (Last resort)**
```tsx
screen.getByTestId('customer-card');
```

### Query Variants

```tsx
// getBy* - Throws error if not found (use for elements that should exist)
screen.getByRole('button');

// queryBy* - Returns null if not found (use for elements that shouldn't exist)
expect(screen.queryByRole('button')).not.toBeInTheDocument();

// findBy* - Returns promise, waits for element (use for async)
await screen.findByRole('button');

// *AllBy* - Returns array of elements
const buttons = screen.getAllByRole('button');
```

---

## User Interactions

### Using userEvent (Recommended)

```tsx
import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

describe('CreateCustomerForm', () => {
  it('should submit form with valid data', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<CreateCustomerForm onSubmit={onSubmit} />);

    // Type into inputs
    await user.type(screen.getByLabelText(/customer name/i), 'Acme Corporation');
    await user.type(screen.getByLabelText(/email/i), 'test@acme.com');
    await user.type(screen.getByLabelText(/phone/i), '5551234567');

    // Click button
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Assert
    expect(onSubmit).toHaveBeenCalledWith({
      name: 'Acme Corporation',
      email: 'test@acme.com',
      phone: '5551234567',
    });
  });
});
```

### Common User Interactions

```tsx
const user = userEvent.setup();

// Typing
await user.type(input, 'text to type');
await user.clear(input);

// Clicking
await user.click(button);
await user.dblClick(button);

// Selecting
await user.selectOptions(select, 'option-value');
await user.deselectOptions(select, 'option-value');

// Checkboxes/Radio
await user.click(checkbox); // Toggle

// Keyboard
await user.keyboard('{Enter}');
await user.keyboard('{Escape}');
await user.tab(); // Focus next element

// Hover
await user.hover(element);
await user.unhover(element);

// Upload files
await user.upload(fileInput, file);
```

---

## Testing Forms

### Form Validation

```tsx
describe('CustomerForm validation', () => {
  it('should show error for invalid email', async () => {
    const user = userEvent.setup();
    render(<CustomerForm />);

    const emailInput = screen.getByLabelText(/email/i);
    await user.type(emailInput, 'invalid-email');
    await user.tab(); // Blur field

    expect(await screen.findByText(/invalid email address/i)).toBeInTheDocument();
  });

  it('should show error for required field', async () => {
    const user = userEvent.setup();
    render(<CustomerForm />);

    const submitButton = screen.getByRole('button', { name: /submit/i });
    await user.click(submitButton);

    expect(await screen.findByText(/customer name is required/i)).toBeInTheDocument();
  });

  it('should clear errors when valid input is entered', async () => {
    const user = userEvent.setup();
    render(<CustomerForm />);

    const emailInput = screen.getByLabelText(/email/i);

    // Enter invalid email
    await user.type(emailInput, 'invalid');
    await user.tab();
    expect(await screen.findByText(/invalid email/i)).toBeInTheDocument();

    // Fix email
    await user.clear(emailInput);
    await user.type(emailInput, 'valid@example.com');
    await user.tab();

    expect(screen.queryByText(/invalid email/i)).not.toBeInTheDocument();
  });
});
```

### Form Submission

```tsx
it('should submit form and show success message', async () => {
  const user = userEvent.setup();
  const mockCreateCustomer = vi.fn().mockResolvedValue({ id: '123' });

  render(<CreateCustomerForm createCustomer={mockCreateCustomer} />);

  // Fill form
  await user.type(screen.getByLabelText(/customer name/i), 'Acme Corporation');
  await user.type(screen.getByLabelText(/email/i), 'test@acme.com');
  await user.type(screen.getByLabelText(/phone/i), '5551234567');

  // Submit
  await user.click(screen.getByRole('button', { name: /submit/i }));

  // Assert API was called
  expect(mockCreateCustomer).toHaveBeenCalledWith({
    name: 'Acme Corporation',
    email: 'test@acme.com',
    phone: '5551234567',
  });

  // Assert success message
  expect(await screen.findByText(/customer created successfully/i)).toBeInTheDocument();
});
```

---

## Testing Async Operations

### Waiting for Elements

```tsx
import { waitFor } from '@testing-library/react';

it('should load and display customers', async () => {
  const mockCustomers = [
    { id: '1', name: 'Acme Corporation' },
    { id: '2', name: 'Beta Corp' },
  ];

  render(<CustomerList />);

  // Wait for customers to load
  expect(await screen.findByText('Acme Corporation')).toBeInTheDocument();
  expect(await screen.findByText('Beta Corp')).toBeInTheDocument();
});

// Or use waitFor for custom conditions
it('should update status after transition', async () => {
  render(<OrderCard />);

  const button = screen.getByRole('button', { name: /approve/i });
  await userEvent.click(button);

  await waitFor(() => {
    expect(screen.getByText(/approved/i)).toBeInTheDocument();
  });
});
```

### Mocking API Calls (with MSW)

```tsx
// src/test/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/customers', () => {
    return HttpResponse.json([
      { id: '1', name: 'Acme Corporation', email: 'contact@acme.com' },
      { id: '2', name: 'Beta Corp', email: 'info@beta.com' },
    ]);
  }),

  http.post('/api/customers', async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json(
      { id: '123', ...body },
      { status: 201 }
    );
  }),

  http.delete('/api/customers/:id', () => {
    return HttpResponse.json(null, { status: 204 });
  }),
];

// src/test/mocks/server.ts
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);

// src/test/setup.ts
import { server } from './mocks/server';
import { beforeAll, afterEach, afterAll } from 'vitest';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### Using MSW in Tests

```tsx
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';

describe('CustomerList', () => {
  it('should handle API error', async () => {
    // Override default handler for this test
    server.use(
      http.get('/api/customers', () => {
        return HttpResponse.json(
          { message: 'Internal Server Error' },
          { status: 500 }
        );
      })
    );

    render(<CustomerList />);

    expect(await screen.findByText(/failed to load customers/i)).toBeInTheDocument();
  });

  it('should show empty state when no customers', async () => {
    server.use(
      http.get('/api/customers', () => {
        return HttpResponse.json([]);
      })
    );

    render(<CustomerList />);

    expect(await screen.findByText(/no customers found/i)).toBeInTheDocument();
  });
});
```

---

## Testing with TanStack Query

### Wrapper Setup

```tsx
// src/test/utils.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // Don't retry in tests
        gcTime: Infinity, // Don't garbage collect
      },
    },
  });
}

export function renderWithQueryClient(ui: ReactNode) {
  const testQueryClient = createTestQueryClient();

  return render(
    <QueryClientProvider client={testQueryClient}>
      {ui}
    </QueryClientProvider>
  );
}
```

### Testing Queries

```tsx
import { renderWithQueryClient } from '@/test/utils';

describe('CustomerDetails', () => {
  it('should load and display customer', async () => {
    renderWithQueryClient(<CustomerDetails customerId="123" />);

    // Loading state
    expect(screen.getByText(/loading/i)).toBeInTheDocument();

    // Data loaded
    expect(await screen.findByText('Acme Corporation')).toBeInTheDocument();
    expect(screen.getByText('contact@acme.com')).toBeInTheDocument();
  });

  it('should show error when customer not found', async () => {
    server.use(
      http.get('/api/customers/:id', () => {
        return HttpResponse.json(
          { message: 'Not found' },
          { status: 404 }
        );
      })
    );

    renderWithQueryClient(<CustomerDetails customerId="999" />);

    expect(await screen.findByText(/customer not found/i)).toBeInTheDocument();
  });
});
```

### Testing Mutations

```tsx
it('should create customer and refetch list', async () => {
  const user = userEvent.setup();
  const testQueryClient = createTestQueryClient();

  render(
    <QueryClientProvider client={testQueryClient}>
      <CustomerList />
      <CreateCustomerDialog />
    </QueryClientProvider>
  );

  // Initially 2 customers
  expect(await screen.findAllByRole('article')).toHaveLength(2);

  // Open dialog and create customer
  await user.click(screen.getByRole('button', { name: /create customer/i }));
  await user.type(screen.getByLabelText(/customer name/i), 'New Customer');
  await user.type(screen.getByLabelText(/email/i), 'new@example.com');
  await user.click(screen.getByRole('button', { name: /submit/i }));

  // List should refetch and show 3 customers
  await waitFor(() => {
    expect(screen.getAllByRole('article')).toHaveLength(3);
  });
});
```

---

## Testing Accessibility

### ARIA Roles and Labels

```tsx
it('should have accessible button', () => {
  render(<DeleteCustomerButton />);

  const button = screen.getByRole('button', { name: /delete customer/i });
  expect(button).toBeInTheDocument();
});

it('should have accessible form fields', () => {
  render(<CustomerForm />);

  // Labels should be associated with inputs
  const nameInput = screen.getByLabelText(/customer name/i);
  expect(nameInput).toHaveAccessibleName('Customer Name');
});

it('should have accessible error messages', async () => {
  const user = userEvent.setup();
  render(<CustomerForm />);

  await user.click(screen.getByRole('button', { name: /submit/i }));

  const errorMessage = await screen.findByText(/customer name is required/i);
  expect(errorMessage).toHaveAccessibleDescription();
});
```

### Keyboard Navigation

```tsx
it('should be keyboard navigable', async () => {
  const user = userEvent.setup();
  render(<CustomerForm />);

  const nameInput = screen.getByLabelText(/customer name/i);
  const emailInput = screen.getByLabelText(/email/i);
  const submitButton = screen.getByRole('button', { name: /submit/i });

  // Tab through form
  await user.tab();
  expect(nameInput).toHaveFocus();

  await user.tab();
  expect(emailInput).toHaveFocus();

  await user.tab();
  expect(submitButton).toHaveFocus();

  // Submit with Enter
  await user.keyboard('{Enter}');
  // Assert form submission
});

it('should close dialog with Escape', async () => {
  const user = userEvent.setup();
  const onClose = vi.fn();

  render(<Dialog open onClose={onClose} />);

  await user.keyboard('{Escape}');
  expect(onClose).toHaveBeenCalled();
});
```

---

## Testing Hooks

### Custom Hook Testing

```tsx
import { renderHook, waitFor } from '@testing-library/react';

describe('useCustomer', () => {
  it('should fetch customer data', async () => {
    const { result } = renderHook(() => useCustomer('123'), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={createTestQueryClient()}>
          {children}
        </QueryClientProvider>
      ),
    });

    // Initially loading
    expect(result.current.isLoading).toBe(true);

    // Wait for data
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual({
      id: '123',
      name: 'Acme Corporation',
    });
  });
});
```

---

## Snapshot Testing

### When to Use Snapshots

Use snapshots for:
- Static components (headers, footers)
- Error messages
- Icons and small UI elements

**Don't use for:**
- Complex components with lots of logic
- Components with dynamic data

```tsx
it('should match snapshot', () => {
  const { container } = render(<ErrorMessage message="Something went wrong" />);
  expect(container).toMatchSnapshot();
});

// Update snapshots with:
// npm test -- -u
```

---

## Best Practices

### 1. Test User Behavior, Not Implementation

✅ **GOOD:**
```tsx
it('should show error message on failed login', async () => {
  const user = userEvent.setup();
  render(<LoginForm />);

  await user.type(screen.getByLabelText(/email/i), 'wrong@example.com');
  await user.type(screen.getByLabelText(/password/i), 'wrongpass');
  await user.click(screen.getByRole('button', { name: /login/i }));

  expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument();
});
```

❌ **BAD:**
```tsx
it('should call loginFailed action', () => {
  const { result } = renderHook(() => useLogin());
  result.current.loginFailed();
  expect(result.current.error).toBe('Invalid credentials');
});
```

### 2. Use Accessible Queries

✅ **GOOD:**
```tsx
screen.getByRole('button', { name: /submit/i });
screen.getByLabelText(/email/i);
```

❌ **BAD:**
```tsx
screen.getByTestId('submit-button');
screen.getByClassName('email-input');
```

### 3. Don't Test Third-Party Libraries

✅ **GOOD:**
```tsx
it('should submit form when valid', async () => {
  const onSubmit = vi.fn();
  render(<Form onSubmit={onSubmit} />);

  // Fill and submit
  await user.click(submitButton);

  expect(onSubmit).toHaveBeenCalled();
});
```

❌ **BAD:**
```tsx
it('should unit test AJV internals', () => {
  const validate = ajv.compile(schema);
  expect(validate({ name: 'ab' })).toBe(false);
});
```

### 4. Keep Tests Focused

✅ **GOOD:**
```tsx
it('should display customer name', () => {
  render(<CustomerCard customer={mockCustomer} />);
  expect(screen.getByText('Acme Corporation')).toBeInTheDocument();
});

it('should display email', () => {
  render(<CustomerCard customer={mockCustomer} />);
  expect(screen.getByText('contact@acme.com')).toBeInTheDocument();
});
```

❌ **BAD:**
```tsx
it('should render customer card correctly', () => {
  // Tests 10 different things
});
```

### 5. Use Descriptive Test Names

✅ **GOOD:**
```tsx
it('should show validation error when email is invalid', () => {});
it('should disable submit button while form is submitting', () => {});
```

❌ **BAD:**
```tsx
it('works', () => {});
it('test form', () => {});
```

---

## Coverage Goals

Target coverage levels:
- **Statements:** > 80%
- **Branches:** > 75%
- **Functions:** > 80%
- **Lines:** > 80%

Run coverage report:
```bash
npm test -- --coverage
```

---

## Common Testing Patterns

### Loading States

```tsx
it('should show skeleton while loading', () => {
  render(<CustomerList />);
  expect(screen.getByTestId('skeleton')).toBeInTheDocument();
});

it('should show content after loading', async () => {
  render(<CustomerList />);
  expect(await screen.findByText('Acme Corporation')).toBeInTheDocument();
  expect(screen.queryByTestId('skeleton')).not.toBeInTheDocument();
});
```

### Empty States

```tsx
it('should show empty state when no data', async () => {
  server.use(
    http.get('/api/customers', () => HttpResponse.json([]))
  );

  render(<CustomerList />);

  expect(await screen.findByText(/no customers found/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /create customer/i })).toBeInTheDocument();
});
```

### Conditional Rendering

```tsx
it('should show edit button for admin users', () => {
  render(<CustomerCard customer={mockCustomer} userRole="admin" />);
  expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
});

it('should not show edit button for regular users', () => {
  render(<CustomerCard customer={mockCustomer} userRole="user" />);
  expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument();
});
```

---

## Theme and Visual Regression Checks

### Light/Dark Theme Verification (Required for Styling Changes)

- Verify affected screens/components in both dark and light mode whenever UI styling changes.
- Confirm semantic theme token classes are used for app UI text/surfaces/borders instead of raw palette utility classes.
- Treat low-contrast regressions as failures for labels, content text, and interactive controls.

### Playwright Theme Smoke Tests (Recommended Pattern)

- Capture screenshots for a small set of critical pages in both themes (for example dashboard, list page, create/edit form).
- Mock auth/API responses for deterministic rendering.
- Disable animations/transitions for screenshot stability.
- Add at least one targeted readability/contrast assertion for high-risk UI areas (KPIs, forms, badges, overlays).

### CI Integration

- Run visual/theme smoke tests on frontend changes.
- Upload Playwright artifacts (`playwright-report`, `test-results`) for failure diagnosis.
- Pair browser tests with a fast static policy check (for example `lint:theme`) that blocks raw palette classes.

---

## References

- [React Testing Library Docs](https://testing-library.com/react)
- [Vitest Documentation](https://vitest.dev)
- [Common Testing Mistakes](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
- [Testing Library Guiding Principles](https://testing-library.com/docs/guiding-principles/)
- [MSW (Mock Service Worker)](https://mswjs.io)
- [Playwright Visual Comparisons](https://playwright.dev/docs/test-snapshots)

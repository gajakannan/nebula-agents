# Frontend Developer Code Patterns

Reference patterns extracted from the main SKILL.md for detailed implementation guidance.

## Best Practices

### Coverage Map
- Component structure and TypeScript patterns
- Form validation with AJV + React Hook Form
- Dynamic forms with RJSF and custom shadcn/ui widgets
- RJSF vs React Hook Form decision guide
- API integration with TanStack Query
- Error handling and protected routes
- Custom hooks (useAuth, permissions)
- List with search/filters, optimistic updates, infinite scroll
- Security (XSS, CSRF, token storage, CSP)
- Performance optimization (code splitting, memoization, images, bundle size)
- Testing (unit, integration, accessibility)

### Component Structure
```tsx
// Good: Well-structured component with TypeScript
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { customerApi } from '@/lib/api/customers';
import type { Customer } from '@/types/customer';

interface CustomerFormProps {
  customerId?: string;
  onSuccess?: (customer: Customer) => void;
}

export function CustomerForm({ customerId, onSuccess }: CustomerFormProps) {
  // Implementation
}
```

### Form Validation with AJV + React Hook Form
```tsx
import { useForm } from 'react-hook-form';
import { ajvResolver } from '@hookform/resolvers/ajv';
import Ajv from 'ajv';
import addErrors from 'ajv-errors';
import type { JSONSchemaType } from 'ajv';

// Define JSON Schema (can be shared with backend)
interface CustomerFormData {
  name: string;
  email: string;
  phone: string;
  status: 'Active' | 'Inactive';
}

const customerSchema: JSONSchemaType<CustomerFormData> = {
  type: 'object',
  properties: {
    name: {
      type: 'string',
      minLength: 1,
      maxLength: 100,
      errorMessage: {
        minLength: 'Name is required',
        maxLength: 'Name must be at most 100 characters',
      },
    },
    email: {
      type: 'string',
      format: 'email',
      errorMessage: 'Invalid email address',
    },
    phone: {
      type: 'string',
      pattern: '^\\d{10}$',
      errorMessage: 'Phone must be 10 digits',
    },
    status: {
      type: 'string',
      enum: ['Active', 'Inactive'],
    },
  },
  required: ['name', 'email', 'phone', 'status'],
  additionalProperties: false,
};

// Set up AJV with error messages
const ajv = new Ajv({ allErrors: true });
addErrors(ajv);

function CustomerForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CustomerFormData>({
    resolver: ajvResolver(customerSchema, {
      formats: { email: true }, // Enable format validation
    }),
  });

  const onSubmit = async (data: CustomerFormData) => {
    await createCustomer(data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <div>
        <label htmlFor="name">Customer Name</label>
        <input {...register('name')} id="name" />
        {errors.name && <p className="text-red-500">{errors.name.message}</p>}
      </div>
      <div>
        <label htmlFor="email">Email</label>
        <input {...register('email')} id="email" type="email" />
        {errors.email && <p className="text-red-500">{errors.email.message}</p>}
      </div>
      <div>
        <label htmlFor="phone">Phone</label>
        <input {...register('phone')} id="phone" />
        {errors.phone && <p className="text-red-500">{errors.phone.message}</p>}
      </div>
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Saving...' : 'Save Customer'}
      </Button>
    </form>
  );
}
```

**Alternative: Load schema from shared location**
```tsx
// schemas/customer.schema.json (shared with backend)
import customerSchema from '@/schemas/customer.schema.json';
import { ajvResolver } from '@hookform/resolvers/ajv';

function CustomerForm() {
  const { register, handleSubmit, formState: { errors } } = useForm({
    resolver: ajvResolver(customerSchema),
  });
  // ... rest of implementation
}
```

### Dynamic Forms with RJSF
```tsx
import Form from '@rjsf/core';
import validator from '@rjsf/validator-ajv8';
import { RJSFSchema, UiSchema } from '@rjsf/utils';

// JSON Schema (can be loaded from shared file)
const schema: RJSFSchema = {
  type: 'object',
  properties: {
    name: { type: 'string', title: 'Customer Name' },
    email: { type: 'string', format: 'email', title: 'Email' },
    phone: { type: 'string', pattern: '^\\d{10}$', title: 'Phone' },
    status: {
      type: 'string',
      enum: ['Active', 'Inactive'],
      title: 'Status'
    },
  },
  required: ['name', 'email', 'status'],
};

// UI Schema for customization (optional)
const uiSchema: UiSchema = {
  email: { 'ui:widget': 'email' },
  phone: { 'ui:placeholder': '1234567890' },
  status: { 'ui:widget': 'radio' },
};

function DynamicCustomerForm() {
  const handleSubmit = ({ formData }: any) => {
    // formData is already validated against schema
    createCustomer(formData);
  };

  return (
    <Form
      schema={schema}
      uiSchema={uiSchema}
      validator={validator}
      onSubmit={handleSubmit}
    />
  );
}
```

**Custom Widgets with shadcn/ui:**
```tsx
import Form from '@rjsf/core';
import validator from '@rjsf/validator-ajv8';
import { RegistryWidgetsType } from '@rjsf/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

// Custom text input widget using shadcn/ui
const CustomTextWidget = (props: any) => {
  return (
    <Input
      id={props.id}
      value={props.value}
      onChange={(e) => props.onChange(e.target.value)}
      placeholder={props.placeholder}
      className={props.rawErrors?.length > 0 ? 'border-red-500' : ''}
    />
  );
};

const widgets: RegistryWidgetsType = {
  TextWidget: CustomTextWidget,
  // Add more custom widgets for Select, Checkbox, etc.
};

function CustomerFormWithCustomWidgets() {
  return (
    <Form
      schema={schema}
      validator={validator}
      widgets={widgets}
      onSubmit={handleSubmit}
    >
      <Button type="submit">Save Customer</Button>
    </Form>
  );
}
```

**When to use RJSF vs React Hook Form:**

| Use Case | RJSF | React Hook Form |
|----------|------|-----------------|
| Admin forms with changing schemas | Yes | No |
| Configurable/dynamic forms | Yes | No |
| Rapid prototyping | Yes | No |
| Schema-driven forms | Yes | No |
| Standard CRUD forms | Yes | Yes |
| Custom layouts/designs | No | Yes |
| Complex multi-step wizards | No | Yes |
| Pixel-perfect branded UI | No | Yes |
| Forms with complex interactions | No | Yes |

### API Integration with TanStack Query
```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { customerApi } from '@/lib/api/customers';

function CustomerList() {
  const queryClient = useQueryClient();

  // Fetch customers
  const { data: customers, isLoading, error } = useQuery({
    queryKey: ['customers'],
    queryFn: customerApi.getAll,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Create customer mutation
  const createMutation = useMutation({
    mutationFn: customerApi.create,
    onSuccess: () => {
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: ['customers'] });
    },
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      {customers?.map(customer => (
        <div key={customer.id}>{customer.name}</div>
      ))}
    </div>
  );
}
```

### Error Handling
```tsx
import { useRouteError } from 'react-router-dom';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

// Error Boundary Component
export function ErrorBoundary() {
  const error = useRouteError();

  return (
    <Alert variant="destructive">
      <AlertTitle>Something went wrong</AlertTitle>
      <AlertDescription>
        {error instanceof Error ? error.message : 'An unexpected error occurred'}
      </AlertDescription>
    </Alert>
  );
}

// API Error Handling
async function handleApiError(error: unknown): Promise<string> {
  // Parse ProblemDetails from backend
  if (error instanceof Response) {
    const problemDetails = await error.json();
    return problemDetails.detail || 'An error occurred';
  }

  if (error instanceof Error) {
    return error.message;
  }

  return 'An unexpected error occurred';
}
```

### Protected Routes
```tsx
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

// Usage in router
const router = createBrowserRouter([
  {
    element: <ProtectedRoute />,
    children: [
      { path: '/customers', element: <CustomerList /> },
      { path: '/accounts', element: <AccountList /> },
    ],
  },
  { path: '/login', element: <Login /> },
]);
```

### Custom Hooks
```tsx
// useAuth hook for authentication state
import { useQuery } from '@tanstack/react-query';
import { authApi } from '@/lib/api/auth';

export function useAuth() {
  const { data: user, isLoading } = useQuery({
    queryKey: ['auth', 'user'],
    queryFn: authApi.getCurrentUser,
    retry: false,
    staleTime: Infinity, // User rarely changes
  });

  return {
    user,
    isAuthenticated: !!user,
    isLoading,
    hasPermission: (resource: string, action: string) => {
      // Check permissions from JWT claims
      return user?.permissions?.includes(`${resource}:${action}`);
    },
  };
}

// Usage
function CustomerActions({ customerId }: { customerId: string }) {
  const { hasPermission } = useAuth();

  return (
    <div>
      {hasPermission('customer', 'update') && (
        <Button onClick={() => editCustomer(customerId)}>Edit</Button>
      )}
      {hasPermission('customer', 'delete') && (
        <Button variant="destructive" onClick={() => deleteCustomer(customerId)}>
          Delete
        </Button>
      )}
    </div>
  );
}
```

## Common Patterns

### List with Search and Filters
```tsx
function CustomerList() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('all');

  const { data, isLoading } = useQuery({
    queryKey: ['customers', { search, status }],
    queryFn: () => customerApi.getAll({ search, status }),
  });

  return (
    <div>
      <input
        type="search"
        placeholder="Search customers..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <select value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="all">All</option>
        <option value="active">Active</option>
        <option value="inactive">Inactive</option>
      </select>
      {isLoading ? <Spinner /> : <CustomerTable customers={data} />}
    </div>
  );
}
```

### Optimistic Updates
```tsx
const deleteMutation = useMutation({
  mutationFn: customerApi.delete,
  onMutate: async (customerId) => {
    // Cancel outgoing refetches
    await queryClient.cancelQueries({ queryKey: ['customers'] });

    // Snapshot previous value
    const previousCustomers = queryClient.getQueryData(['customers']);

    // Optimistically remove customer
    queryClient.setQueryData(['customers'], (old: Customer[]) =>
      old.filter(b => b.id !== customerId)
    );

    return { previousCustomers };
  },
  onError: (err, customerId, context) => {
    // Rollback on error
    queryClient.setQueryData(['customers'], context?.previousCustomers);
  },
  onSettled: () => {
    // Refetch after success or error
    queryClient.invalidateQueries({ queryKey: ['customers'] });
  },
});
```

### Infinite Scroll / Pagination
```tsx
import { useInfiniteQuery } from '@tanstack/react-query';

function CustomerInfiniteList() {
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['customers', 'infinite'],
    queryFn: ({ pageParam = 1 }) => customerApi.getPage(pageParam),
    getNextPageParam: (lastPage) => lastPage.nextPage,
  });

  return (
    <div>
      {data?.pages.map((page) =>
        page.items.map((customer) => <CustomerCard key={customer.id} customer={customer} />)
      )}
      {hasNextPage && (
        <Button onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
          {isFetchingNextPage ? 'Loading...' : 'Load More'}
        </Button>
      )}
    </div>
  );
}
```

## Security Considerations

### XSS Prevention
- **Never use `dangerouslySetInnerHTML`** unless absolutely necessary and sanitized
- **Escape user input** - React does this by default for JSX content
- **Validate all inputs** - Use JSON Schema + AJV validation
- **Sanitize HTML** - Use DOMPurify if rendering user HTML

```tsx
// BAD - XSS vulnerable
<div dangerouslySetInnerHTML={{ __html: userInput }} />

// GOOD - React escapes by default
<div>{userInput}</div>

// GOOD - If you must render HTML, sanitize it
import DOMPurify from 'dompurify';
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(userInput) }} />
```

### CSRF Protection
- **Use httpOnly cookies** for tokens (backend sets these)
- **Include CSRF tokens** if using cookie-based auth
- **Validate origin** on backend (backend responsibility)

### Authentication Token Security
```tsx
// GOOD - Store in httpOnly cookie (backend sets)
// Frontend just reads from cookie automatically

// ACCEPTABLE - SessionStorage (not localStorage - XSS risk)
sessionStorage.setItem('token', token);

// BAD - localStorage (persists across sessions, XSS risk)
// Don't do this: localStorage.setItem('token', token);

// Include token in requests
const token = sessionStorage.getItem('token');
fetch('/api/customers', {
  headers: {
    'Authorization': `Bearer ${token}`,
  },
});
```

### Authorization
- **Never trust client-side checks** - UI hides/shows elements, backend enforces
- **Read permissions from JWT claims** - Don't hardcode roles
- **Hide UI elements** based on permissions for UX, but backend must validate

```tsx
// GOOD - Hide UI but backend still validates
{hasPermission('customer', 'delete') && (
  <Button onClick={handleDelete}>Delete</Button>
)}

// Backend MUST check permission even if button is hidden
```

### Content Security Policy (CSP)
- Configure CSP headers (DevOps/Backend responsibility)
- Avoid inline scripts and styles
- Use nonce or hash for necessary inline content

## Performance Optimization

### Code Splitting
```tsx
import { lazy, Suspense } from 'react';

// Lazy load heavy components
const CustomerDetails = lazy(() => import('@/features/customers/CustomerDetails'));

function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <CustomerDetails customerId="123" />
    </Suspense>
  );
}
```

### Memoization
```tsx
import { useMemo, useCallback } from 'react';

function CustomerList({ customers }: { customers: Customer[] }) {
  // Memoize expensive computation
  const sortedCustomers = useMemo(
    () => customers.sort((a, b) => a.name.localeCompare(b.name)),
    [customers]
  );

  // Memoize callback to prevent child re-renders
  const handleCustomerClick = useCallback((id: string) => {
    navigate(`/customers/${id}`);
  }, [navigate]);

  return (
    <div>
      {sortedCustomers.map(customer => (
        <CustomerCard key={customer.id} customer={customer} onClick={handleCustomerClick} />
      ))}
    </div>
  );
}

// Memoize component to prevent re-renders
const CustomerCard = React.memo(({ customer, onClick }: CustomerCardProps) => {
  // Component implementation
});
```

### Image Optimization
```tsx
// Lazy load images
<img src={customer.logoUrl} alt={customer.name} loading="lazy" />

// Responsive images
<img
  src={customer.logo.url}
  srcSet={`${customer.logo.small} 400w, ${customer.logo.large} 800w`}
  sizes="(max-width: 600px) 400px, 800px"
  alt={customer.name}
/>
```

### Bundle Size Monitoring
```bash
# Build and analyze bundle
npm run build
npm run analyze

# Check for large dependencies
npx vite-bundle-visualizer
```

## Testing Strategy

### Component Unit Tests
```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CustomerCard } from './CustomerCard';

describe('CustomerCard', () => {
  it('renders customer name', () => {
    const customer = { id: '1', name: 'Test Customer', status: 'Active' };
    render(<CustomerCard customer={customer} />);
    expect(screen.getByText('Test Customer')).toBeInTheDocument();
  });

  it('shows active status badge', () => {
    const customer = { id: '1', name: 'Test Customer', status: 'Active' };
    render(<CustomerCard customer={customer} />);
    expect(screen.getByText('Active')).toHaveClass('badge-success');
  });
});
```

### Integration Tests
```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CustomerForm } from './CustomerForm';
import { server } from '@/mocks/server'; // MSW mock server

describe('CustomerForm', () => {
  it('creates customer on submit', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <CustomerForm />
      </QueryClientProvider>
    );

    await user.type(screen.getByLabelText('Customer Name'), 'Test Customer');
    await user.type(screen.getByLabelText('Email'), 'test@example.com');
    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText('Customer created successfully')).toBeInTheDocument();
    });
  });
});
```

### Accessibility Tests
```tsx
import { axe, toHaveNoViolations } from 'jest-axe';
expect.extend(toHaveNoViolations);

describe('CustomerForm accessibility', () => {
  it('has no accessibility violations', async () => {
    const { container } = render(<CustomerForm />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
```

### Semantic Theme Token Styling (Required for App UI)

- Prefer semantic theme classes mapped from the app theme (for example `text-text-primary`, `text-text-secondary`, `text-text-muted`, `bg-surface-card`, `border-surface-border`).
- Do not use raw palette utility classes for app UI text/surfaces/borders (`text-zinc-*`, `bg-zinc-*`, `border-zinc-*`, and similar `slate/gray/neutral/stone`) unless a visual-effect exception is explicitly documented.
- Apply color/styling fixes in shared primitives (`components/ui/*`) first when the pattern is reused across screens.
- Route color semantics through theme tokens or CSS variables so dark/light mode behavior stays consistent.

**Avoid (theme-bypassing):**
```tsx
<p className="text-zinc-400">Status</p>
<input className="border-zinc-700 bg-zinc-950 text-zinc-200" />
```

**Prefer (theme-aware):**
```tsx
<p className="text-text-secondary">Status</p>
<input className="border-surface-border bg-surface-card text-text-primary" />
```

### Feature-First Vertical Slice Organization (Preferred in `{PRODUCT_ROOT}/experience/src`)

- Co-locate feature-specific UI behavior to reduce cognitive drift and ownership ambiguity.
- Default placement for new feature work:
  - `features/<feature>/components`
  - `features/<feature>/hooks`
  - `features/<feature>/api`
  - `features/<feature>/types`
  - `features/<feature>/lib`
  - `features/<feature>/tests`
- Keep only cross-feature code in shared/global folders:
  - UI primitives (`components/ui`)
  - app shell/layout/routing/providers
  - generic infrastructure utilities (auth, API client base, formatting, theme tokens)

**Avoid (feature code spilled into globals):**
```ts
// Global hook for one orders widget only
src/hooks/useOrderFlow.ts

// Global type used only by one feature
src/types/orders.ts

// Global component tied to one domain screen
src/components/OrderChart.tsx
```

**Prefer (co-located feature slice):**
```text
src/features/orders/
  api/order-flow.ts
  hooks/useOrderFlow.ts
  types/order-flow.ts
  components/OrderChart.tsx
  components/OrderPopover.tsx
```

**Refactor rule of thumb**
- If code is used by exactly one feature, move it into that feature slice when touched.
- If a second feature starts depending on it, promote it to shared/global with a clear name and ownership reason.

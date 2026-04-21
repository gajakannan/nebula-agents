# TanStack Query Guide

**Version:** 1.0
**Last Updated:** 2026-01-29
**Applies To:** Frontend Developer

---

## Overview

TanStack Query (formerly React Query) is our solution for managing server state. It handles data fetching, caching, synchronization, and updates with minimal boilerplate.

**Core Philosophy:** Server state is fundamentally different from client state. TanStack Query treats it as a cache that can become stale and needs revalidation.

---

## Installation & Setup

```bash
npm install @tanstack/react-query @tanstack/react-query-devtools
```

### Query Client Setup

```tsx
// src/lib/queryClient.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 30, // 30 minutes (formerly cacheTime)
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});
```

### Provider Setup

```tsx
// src/App.tsx
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { queryClient } from './lib/queryClient';

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

---

## Queries (Fetching Data)

### Basic Query

```tsx
import { useQuery } from '@tanstack/react-query';
import { getCustomers } from '@/api/customers';

function CustomerList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['customers'],
    queryFn: getCustomers,
  });

  if (isLoading) return <Skeleton />;
  if (error) return <ErrorAlert error={error} />;

  return (
    <div>
      {data.map(customer => (
        <CustomerCard key={customer.id} customer={customer} />
      ))}
    </div>
  );
}
```

### Query with Parameters

```tsx
function CustomerDetails({ customerId }: { customerId: string }) {
  const { data: customer, isLoading } = useQuery({
    queryKey: ['customers', customerId], // Include params in key
    queryFn: () => getCustomer(customerId),
    enabled: !!customerId, // Only run if customerId exists
  });

  // ...
}
```

### Query Key Patterns

```tsx
// ✅ GOOD - Hierarchical, specific keys
const queryKeys = {
  // All customers queries
  all: ['customers'] as const,

  // Customer lists (with filters)
  lists: () => [...queryKeys.all, 'list'] as const,
  list: (filters: CustomerFilters) => [...queryKeys.lists(), filters] as const,

  // Individual customers
  details: () => [...queryKeys.all, 'detail'] as const,
  detail: (id: string) => [...queryKeys.details(), id] as const,

  // Customer orders
  orders: (customerId: string) => [...queryKeys.detail(customerId), 'orders'] as const,
};

// Usage
useQuery({
  queryKey: queryKeys.detail(customerId),
  queryFn: () => getCustomer(customerId),
});

// ❌ BAD - Inconsistent, hard to invalidate
useQuery({ queryKey: ['customer', customerId], ... });
useQuery({ queryKey: [customerId, 'customer'], ... }); // Different order!
```

### Dependent Queries

```tsx
function OrderDetails({ orderId }: { orderId: string }) {
  // First query: Get order
  const { data: order } = useQuery({
    queryKey: ['orders', orderId],
    queryFn: () => getOrder(orderId),
  });

  // Second query: Get customer (depends on first query)
  const { data: customer } = useQuery({
    queryKey: ['customers', order?.customerId],
    queryFn: () => getCustomer(order!.customerId),
    enabled: !!order?.customerId, // Only run after order loads
  });

  // ...
}
```

### Parallel Queries

```tsx
function Dashboard() {
  const customers = useQuery({
    queryKey: ['customers'],
    queryFn: getCustomers,
  });

  const orders = useQuery({
    queryKey: ['orders'],
    queryFn: getOrders,
  });

  const subscriptions = useQuery({
    queryKey: ['subscriptions'],
    queryFn: getSubscriptions,
  });

  // All three queries run in parallel
  if (customers.isLoading || orders.isLoading || subscriptions.isLoading) {
    return <DashboardSkeleton />;
  }

  return (
    <div>
      <CustomersWidget data={customers.data} />
      <OrdersWidget data={orders.data} />
      <SubscriptionsWidget data={subscriptions.data} />
    </div>
  );
}
```

### Paginated Queries

```tsx
function CustomerList() {
  const [page, setPage] = useState(1);

  const { data, isLoading, isPlaceholderData } = useQuery({
    queryKey: ['customers', { page }],
    queryFn: () => getCustomers({ page, pageSize: 20 }),
    placeholderData: (previousData) => previousData, // Keep old data while loading new
  });

  return (
    <div>
      {data?.items.map(customer => <CustomerCard key={customer.id} customer={customer} />)}

      <Pagination
        currentPage={page}
        totalPages={data?.totalPages}
        onPageChange={setPage}
        isLoading={isPlaceholderData}
      />
    </div>
  );
}
```

### Infinite Queries

```tsx
function OrderFeed() {
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['orders', 'feed'],
    queryFn: ({ pageParam = 1 }) => getOrders({ page: pageParam }),
    getNextPageParam: (lastPage) => lastPage.nextPage ?? undefined,
    initialPageParam: 1,
  });

  return (
    <div>
      {data?.pages.map((page) =>
        page.items.map((order) => (
          <OrderCard key={order.id} order={order} />
        ))
      )}

      {hasNextPage && (
        <Button
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
        >
          {isFetchingNextPage ? 'Loading...' : 'Load More'}
        </Button>
      )}
    </div>
  );
}
```

---

## Mutations (Modifying Data)

### Basic Mutation

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createCustomer } from '@/api/customers';

function CreateCustomerDialog() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: createCustomer,
    onSuccess: () => {
      // Invalidate and refetch customer list
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      toast.success('Customer created successfully');
    },
    onError: (error) => {
      toast.error(error.message);
    },
  });

  const handleSubmit = (data: CreateCustomerRequest) => {
    mutation.mutate(data);
  };

  return (
    <Dialog>
      <CustomerForm
        onSubmit={handleSubmit}
        isSubmitting={mutation.isPending}
      />
    </Dialog>
  );
}
```

### Optimistic Updates

```tsx
function UpdateCustomerName({ customerId }: { customerId: string }) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (newName: string) => updateCustomer(customerId, { name: newName }),

    // Optimistic update: update UI immediately
    onMutate: async (newName) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['customers', customerId] });

      // Snapshot previous value
      const previousCustomer = queryClient.getQueryData(['customers', customerId]);

      // Optimistically update
      queryClient.setQueryData(['customers', customerId], (old: Customer) => ({
        ...old,
        name: newName,
      }));

      // Return context with snapshot
      return { previousCustomer };
    },

    // Rollback on error
    onError: (err, newName, context) => {
      queryClient.setQueryData(
        ['customers', customerId],
        context?.previousCustomer
      );
      toast.error('Failed to update customer name');
    },

    // Always refetch after success or error
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['customers', customerId] });
    },
  });

  return (
    <Input
      defaultValue={customer.name}
      onBlur={(e) => mutation.mutate(e.target.value)}
    />
  );
}
```

### Mutation with Cache Updates

```tsx
function DeleteCustomer({ customerId }: { customerId: string }) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => deleteCustomer(customerId),
    onSuccess: () => {
      // Option 1: Invalidate (refetch from server)
      queryClient.invalidateQueries({ queryKey: ['customers'] });

      // Option 2: Update cache directly (faster, no refetch)
      queryClient.setQueryData(['customers'], (old: Customer[]) =>
        old.filter(c => c.id !== customerId)
      );

      // Remove individual customer from cache
      queryClient.removeQueries({ queryKey: ['customers', customerId] });
    },
  });

  return (
    <AlertDialog>
      <AlertDialogAction onClick={() => mutation.mutate()}>
        Delete
      </AlertDialogAction>
    </AlertDialog>
  );
}
```

---

## Error Handling

### Global Error Boundary

```tsx
import { QueryErrorResetBoundary } from '@tanstack/react-query';
import { ErrorBoundary } from 'react-error-boundary';

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <QueryErrorResetBoundary>
        {({ reset }) => (
          <ErrorBoundary
            onReset={reset}
            fallbackRender={({ error, resetErrorBoundary }) => (
              <div>
                <h1>Something went wrong</h1>
                <p>{error.message}</p>
                <Button onClick={resetErrorBoundary}>Try again</Button>
              </div>
            )}
          >
            <Router />
          </ErrorBoundary>
        )}
      </QueryErrorResetBoundary>
    </QueryClientProvider>
  );
}
```

### Query-Level Error Handling

```tsx
function CustomerDetails({ customerId }: { customerId: string }) {
  const { data, error, isError, refetch } = useQuery({
    queryKey: ['customers', customerId],
    queryFn: () => getCustomer(customerId),
    retry: (failureCount, error) => {
      // Don't retry on 404
      if (error.response?.status === 404) return false;
      // Retry up to 3 times for other errors
      return failureCount < 3;
    },
  });

  if (isError) {
    if (error.response?.status === 404) {
      return <NotFoundAlert message="Customer not found" />;
    }
    return (
      <ErrorAlert
        error={error}
        onRetry={refetch}
      />
    );
  }

  // ...
}
```

---

## Cache Invalidation Strategies

### After Mutations

```tsx
// Invalidate specific query
queryClient.invalidateQueries({ queryKey: ['customers', customerId] });

// Invalidate all customer queries
queryClient.invalidateQueries({ queryKey: ['customers'] });

// Invalidate queries starting with 'customers'
queryClient.invalidateQueries({ queryKey: ['customers'], exact: false });
```

### Time-Based Invalidation

```tsx
useQuery({
  queryKey: ['customers'],
  queryFn: getCustomers,
  staleTime: 1000 * 60 * 5, // Data is fresh for 5 minutes
  gcTime: 1000 * 60 * 30, // Cache for 30 minutes
});
```

### On Focus/Reconnect

```tsx
useQuery({
  queryKey: ['orders'],
  queryFn: getOrders,
  refetchOnWindowFocus: true, // Refetch when window regains focus
  refetchOnReconnect: true, // Refetch when network reconnects
});
```

---

## Loading States

### Skeleton Screens

```tsx
function CustomerList() {
  const { data, isLoading } = useQuery({
    queryKey: ['customers'],
    queryFn: getCustomers,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {data.map(customer => <CustomerCard key={customer.id} customer={customer} />)}
    </div>
  );
}
```

### Suspense (Experimental)

```tsx
import { useSuspenseQuery } from '@tanstack/react-query';

function CustomerDetails({ customerId }: { customerId: string }) {
  // No isLoading check needed - Suspense handles it
  const { data: customer } = useSuspenseQuery({
    queryKey: ['customers', customerId],
    queryFn: () => getCustomer(customerId),
  });

  return <CustomerCard customer={customer} />;
}

// Wrap with Suspense
function CustomerPage({ customerId }: { customerId: string }) {
  return (
    <Suspense fallback={<CustomerDetailsSkeleton />}>
      <CustomerDetails customerId={customerId} />
    </Suspense>
  );
}
```

---

## Prefetching

### On Hover

```tsx
function CustomerListItem({ customer }: { customer: Customer }) {
  const queryClient = useQueryClient();

  const handleMouseEnter = () => {
    queryClient.prefetchQuery({
      queryKey: ['customers', customer.id],
      queryFn: () => getCustomer(customer.id),
    });
  };

  return (
    <Link
      to={`/customers/${customer.id}`}
      onMouseEnter={handleMouseEnter}
    >
      {customer.name}
    </Link>
  );
}
```

### On Route Load

```tsx
import { queryClient } from '@/lib/queryClient';
import { getCustomer } from '@/api/customers';

// In router loader
export const customerLoader = async ({ params }: LoaderParams) => {
  await queryClient.ensureQueryData({
    queryKey: ['customers', params.customerId],
    queryFn: () => getCustomer(params.customerId!),
  });
  return null;
};
```

---

## TypeScript Integration

### Typed Query Hooks

```tsx
import { useQuery, UseQueryResult } from '@tanstack/react-query';

interface Customer {
  id: string;
  name: string;
  email: string;
}

function useCustomer(customerId: string): UseQueryResult<Customer, Error> {
  return useQuery({
    queryKey: ['customers', customerId],
    queryFn: () => getCustomer(customerId),
  });
}

// Usage
function CustomerDetails({ customerId }: { customerId: string }) {
  const { data } = useCustomer(customerId); // data is typed as Customer | undefined
  // ...
}
```

### Query Key Factory with Types

```tsx
// src/lib/queryKeys.ts
export const customerKeys = {
  all: ['customers'] as const,
  lists: () => [...customerKeys.all, 'list'] as const,
  list: (filters: CustomerFilters) => [...customerKeys.lists(), filters] as const,
  details: () => [...customerKeys.all, 'detail'] as const,
  detail: (id: string) => [...customerKeys.details(), id] as const,
};

// TypeScript infers correct types
const key = customerKeys.detail('123'); // readonly ['customers', 'detail', '123']
```

---

## Best Practices

### 1. Use Query Keys Factories

✅ **GOOD:**
```tsx
const customerKeys = {
  all: ['customers'] as const,
  detail: (id: string) => [...customerKeys.all, id] as const,
};

useQuery({ queryKey: customerKeys.detail(customerId), ... });
```

❌ **BAD:**
```tsx
useQuery({ queryKey: ['customers', customerId], ... });
```

### 2. Handle Loading and Error States

✅ **GOOD:**
```tsx
const { data, isLoading, error } = useQuery(...);

if (isLoading) return <Skeleton />;
if (error) return <ErrorAlert error={error} />;
return <CustomerCard customer={data} />;
```

❌ **BAD:**
```tsx
const { data } = useQuery(...);
return <CustomerCard customer={data} />; // data could be undefined!
```

### 3. Invalidate After Mutations

✅ **GOOD:**
```tsx
useMutation({
  mutationFn: createCustomer,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['customers'] });
  },
});
```

❌ **BAD:**
```tsx
useMutation({
  mutationFn: createCustomer,
  // No invalidation - UI won't update!
});
```

### 4. Use Optimistic Updates for Instant Feedback

✅ **GOOD:**
```tsx
onMutate: async (newData) => {
  await queryClient.cancelQueries({ queryKey: ['item', id] });
  const previous = queryClient.getQueryData(['item', id]);
  queryClient.setQueryData(['item', id], newData);
  return { previous };
},
```

### 5. Set Appropriate Stale Times

✅ **GOOD:**
```tsx
// Static data: long stale time
useQuery({
  queryKey: ['regions'],
  queryFn: getRegions,
  staleTime: Infinity, // Never becomes stale
});

// Real-time data: short stale time
useQuery({
  queryKey: ['orders'],
  queryFn: getOrders,
  staleTime: 1000 * 10, // Stale after 10 seconds
});
```

### 6. Use Enabled Option for Conditional Queries

✅ **GOOD:**
```tsx
useQuery({
  queryKey: ['customer', customerId],
  queryFn: () => getCustomer(customerId),
  enabled: !!customerId, // Only run when customerId exists
});
```

---

## Common Patterns

### Customer 360 View

```tsx
function Customer360({ customerId }: { customerId: string }) {
  const customer = useQuery({
    queryKey: customerKeys.detail(customerId),
    queryFn: () => getCustomer(customerId),
  });

  const orders = useQuery({
    queryKey: ['orders', { customerId }],
    queryFn: () => getOrders({ customerId }),
    enabled: customer.isSuccess, // Wait for customer to load
  });

  const addresses = useQuery({
    queryKey: ['addresses', { customerId }],
    queryFn: () => getAddresses({ customerId }),
    enabled: customer.isSuccess,
  });

  if (customer.isLoading) return <Skeleton />;
  if (customer.error) return <ErrorAlert error={customer.error} />;

  return (
    <div>
      <CustomerHeader customer={customer.data} />

      <Tabs>
        <TabsContent value="orders">
          {orders.isLoading ? (
            <Skeleton />
          ) : (
            <OrdersTable data={orders.data} />
          )}
        </TabsContent>

        <TabsContent value="addresses">
          {addresses.isLoading ? (
            <Skeleton />
          ) : (
            <AddressesList data={addresses.data} />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

### Workflow State Transitions

```tsx
function useOrderTransition(orderId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (toState: OrderState) =>
      transitionOrder(orderId, toState),
    onMutate: async (toState) => {
      // Optimistic update
      await queryClient.cancelQueries({ queryKey: ['orders', orderId] });
      const previous = queryClient.getQueryData(['orders', orderId]);

      queryClient.setQueryData(['orders', orderId], (old: Order) => ({
        ...old,
        state: toState,
      }));

      return { previous };
    },
    onError: (err, toState, context) => {
      // Rollback
      queryClient.setQueryData(['orders', orderId], context?.previous);
      toast.error(`Failed to transition to ${toState}`);
    },
    onSuccess: () => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      queryClient.invalidateQueries({ queryKey: ['timeline', orderId] });
      toast.success('Order updated');
    },
  });
}
```

---

## Debugging

### DevTools

```tsx
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

<QueryClientProvider client={queryClient}>
  <App />
  <ReactQueryDevtools initialIsOpen={false} position="bottom-right" />
</QueryClientProvider>
```

### Logging

```tsx
const queryClient = new QueryClient({
  logger: {
    log: console.log,
    warn: console.warn,
    error: console.error,
  },
});
```

---

## References

- [TanStack Query Docs](https://tanstack.com/query/latest)
- [React Query Best Practices](https://tkdodo.eu/blog/practical-react-query)
- [Query Key Factories](https://tkdodo.eu/blog/effective-react-query-keys)

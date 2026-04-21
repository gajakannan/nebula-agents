# UX Principles and Best Practices

**Version:** 1.1
**Last Updated:** 2026-02-27
**Applies To:** Frontend Developer

---

## Overview

This document compiles user experience (UX) principles and best practices to guide the design and implementation of the application's frontend. These principles ensure the application is intuitive, efficient, and delightful to use.

## Enforcement in This Project

This guide is conceptual. For release-gating implementation rules, use:

- `agents/frontend-developer/references/ux-audit-ruleset.md` (mandatory checklist and pass/fail rules)
- `agents/frontend-developer/SKILL.md` (Definition of Done and workflow commands)

Project-specific rule:

- Use semantic theme tokens/classes for app UI (`text-text-*`, `bg-surface-*`, `border-surface-*`) rather than raw palette classes.

---

## Primary UX Resource: Laws of UX

**Source:** [lawsofux.com](https://lawsofux.com)

Laws of UX is a collection of psychology-based design principles that inform better user experiences.

### Key Laws to Apply

#### 1. Fitts's Law
**Principle:** The time to acquire a target is a function of the distance to and size of the target.

**Application:**
- Make primary action buttons larger and closer to expected user position
- Place "Save" buttons near form fields
- Size CTAs proportional to their importance
- Keep frequently-used actions within easy reach

**Example:**
```tsx
// ✅ GOOD - Large, easy-to-click primary action
<Button size="lg" className="w-full md:w-auto">
  Create Order
</Button>

// ❌ BAD - Small, hard-to-click action
<Button size="xs" className="float-right">
  Create Order
</Button>
```

#### 2. Hick's Law
**Principle:** The time it takes to make a decision increases with the number and complexity of choices.

**Application:**
- Limit navigation menu items (5-7 main items)
- Use progressive disclosure for complex forms
- Break multi-step processes into wizards
- Hide advanced options behind "Show more" controls

**Example:**
```tsx
// ✅ GOOD - Progressive disclosure
<FormSection title="Basic Information">
  <Input name="name" />
  <Input name="email" />
</FormSection>
<Collapsible>
  <CollapsibleTrigger>Advanced Options</CollapsibleTrigger>
  <CollapsibleContent>
    <Input name="customField1" />
    <Input name="customField2" />
  </CollapsibleContent>
</Collapsible>

// ❌ BAD - Overwhelming number of fields at once
<Form>
  {/* 20+ fields all visible at once */}
</Form>
```

#### 3. Miller's Law
**Principle:** The average person can only keep 7 (±2) items in their working memory.

**Application:**
- Limit tables to 5-7 columns by default
- Group related items together (chunking)
- Use pagination or infinite scroll for long lists
- Break long forms into logical sections

**Example:**
```tsx
// ✅ GOOD - Chunked information
<CustomerCard>
  <Section title="Contact Info">
    {/* 3-4 fields */}
  </Section>
  <Section title="Address Info">
    {/* 3-4 fields */}
  </Section>
</CustomerCard>

// ❌ BAD - 15 fields in flat list
<div>
  <Field1 />
  <Field2 />
  {/* ... */}
  <Field15 />
</div>
```

#### 4. Jakob's Law
**Principle:** Users spend most of their time on other sites, so they prefer your site to work the same way.

**Application:**
- Use standard navigation patterns (top nav, sidebar)
- Place search in top-right corner
- Use familiar icons (hamburger menu, magnifying glass)
- Follow platform conventions (Windows/Mac guidelines)
- Use standard form patterns (label above field)

**Example:**
```tsx
// ✅ GOOD - Familiar search placement
<Header>
  <Logo />
  <Nav />
  <Search className="ml-auto" /> {/* Top-right */}
  <UserMenu />
</Header>

// ❌ BAD - Non-standard placement
<Footer>
  <Search /> {/* Search in footer? */}
</Footer>
```

#### 5. Law of Proximity
**Principle:** Objects that are near, or proximate to each other, tend to be grouped together.

**Application:**
- Group related form fields together
- Use whitespace to separate unrelated content
- Place labels close to their inputs
- Group action buttons together

**Example:**
```tsx
// ✅ GOOD - Related fields grouped with spacing
<div className="space-y-6">
  <div className="space-y-4"> {/* Customer Info */}
    <Input label="Customer Name" />
    <Input label="Email" />
  </div>

  <div className="space-y-4"> {/* Address Info */}
    <Input label="Street" />
    <Input label="City" />
  </div>
</div>

// ❌ BAD - All fields equally spaced (no grouping)
<div className="space-y-4">
  <Input label="Customer Name" />
  <Input label="Street" />
  <Input label="Email" />
  <Input label="City" />
</div>
```

#### 6. Law of Common Region
**Principle:** Elements tend to be perceived into groups if they are sharing an area with a clearly defined boundary.

**Application:**
- Use cards/panels to group related information
- Use borders or background colors to define sections
- Separate primary and secondary actions visually

**Example:**
```tsx
// ✅ GOOD - Visual grouping with cards
<div className="grid grid-cols-2 gap-4">
  <Card>
    <CardHeader>Customer Information</CardHeader>
    <CardContent>{/* Customer fields */}</CardContent>
  </Card>
  <Card>
    <CardHeader>Activity Timeline</CardHeader>
    <CardContent>{/* Timeline */}</CardContent>
  </Card>
</div>

// ❌ BAD - No visual boundaries
<div>
  <h3>Customer Information</h3>
  {/* Fields */}
  <h3>Activity Timeline</h3>
  {/* Timeline */}
</div>
```

#### 7. Serial Position Effect
**Principle:** Users tend to remember the first and last items in a series best.

**Application:**
- Place most important actions at beginning or end
- Put critical information in hero sections or summaries
- Use the primacy effect: start with important info
- Use the recency effect: end with strong CTA

**Example:**
```tsx
// ✅ GOOD - Important actions at start and end
<Form>
  <PrimaryButton>Save Draft</PrimaryButton> {/* Primary action first */}

  <FormFields />

  <div className="flex gap-2">
    <Button variant="outline">Cancel</Button>
    <Button>Submit for Review</Button> {/* Primary action last */}
  </div>
</Form>
```

#### 8. Aesthetic-Usability Effect
**Principle:** Users often perceive aesthetically pleasing design as more usable.

**Application:**
- Use consistent spacing, typography, and colors
- Polish micro-interactions (hover states, transitions)
- Add subtle animations for delight
- Use high-quality icons and imagery
- Maintain visual hierarchy

**Example:**
```tsx
// ✅ GOOD - Polished with transitions
<Button className="transition-all hover:scale-105 hover:shadow-lg">
  Create Order
</Button>

// ❌ BAD - No polish, abrupt changes
<button>Create Order</button>
```

#### 9. Doherty Threshold
**Principle:** Productivity soars when a computer and its users interact at a pace (<400ms) that ensures neither has to wait on the other.

**Application:**
- Show loading states immediately (<100ms)
- Use skeleton screens for content loading
- Implement optimistic updates for instant feedback
- Prefetch data for common actions
- Debounce search inputs (300-500ms)

**Example:**
```tsx
// ✅ GOOD - Immediate feedback
const { mutate, isPending } = useMutation({
  mutationFn: createCustomer,
  onMutate: async (newCustomer) => {
    // Optimistic update
    queryClient.setQueryData(['customers'], (old) => [...old, newCustomer]);
  },
});

<Button disabled={isPending}>
  {isPending ? <Spinner /> : 'Create Customer'}
</Button>

// ❌ BAD - No loading state
<Button onClick={createCustomer}>Create Customer</Button>
```

#### 10. Goal-Gradient Effect
**Principle:** The tendency to approach a goal increases with proximity to the goal.

**Application:**
- Show progress indicators for multi-step forms
- Display completion percentages
- Show "You're almost done!" messages
- Highlight completed steps in wizards

**Example:**
```tsx
// ✅ GOOD - Progress indication
<WizardProgress currentStep={3} totalSteps={5}>
  <ProgressBar value={60} />
  <p className="text-sm text-muted">Step 3 of 5 - Almost there!</p>
</WizardProgress>

// ❌ BAD - No progress indication
<Form>
  {/* User has no idea how many steps remain */}
</Form>
```

---

## Additional UX Resources

### Nielsen Norman Group (nngroup.com)

Industry-leading UX research organization. Key concepts:

#### 10 Usability Heuristics
1. **Visibility of system status** - Keep users informed (loading states, confirmations)
2. **Match between system and real world** - Use familiar language, not jargon
3. **User control and freedom** - Provide undo/redo, cancel options
4. **Consistency and standards** - Follow platform conventions
5. **Error prevention** - Prevent errors before they occur
6. **Recognition rather than recall** - Minimize memory load
7. **Flexibility and efficiency** - Support both novice and expert users
8. **Aesthetic and minimalist design** - Remove unnecessary elements
9. **Help users recognize, diagnose, and recover from errors** - Clear error messages
10. **Help and documentation** - Provide contextual help

**Application Examples:**

```tsx
// ✅ Visibility of system status
<OrderCard>
  <StatusBadge status="in_review" />
  <p className="text-sm text-muted">
    Updated 2 minutes ago by John Doe
  </p>
</OrderCard>

// ✅ User control and freedom
<Dialog>
  <DialogContent>
    <p>Are you sure you want to delete this customer?</p>
    <div className="flex gap-2">
      <Button variant="outline" onClick={onCancel}>Cancel</Button>
      <Button variant="destructive" onClick={onConfirm}>Delete</Button>
    </div>
  </DialogContent>
</Dialog>

// ✅ Error prevention
<Input
  type="email"
  pattern="[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$"
  onBlur={validateEmail}
  error={errors.email?.message}
/>

// ✅ Recognition over recall (autocomplete)
<Combobox>
  <ComboboxTrigger>
    <ComboboxValue placeholder="Select customer..." />
  </ComboboxTrigger>
  <ComboboxContent>
    {customers.map(customer => (
      <ComboboxItem key={customer.id} value={customer.id}>
        {customer.name} - {customer.email}
      </ComboboxItem>
    ))}
  </ComboboxContent>
</Combobox>
```

### Refactoring UI (refactoringui.com)

Practical design tips by Tailwind CSS creators. Key takeaways:

#### Hierarchy and Emphasis
- **Start with gray** - Use color sparingly for emphasis
- **Use font weight for hierarchy** - Bold for important, regular for normal
- **Don't rely on font size alone** - Combine size, weight, and color
- **Limit color choices** - 3-4 shades per color is plenty

```tsx
// ✅ GOOD - Clear hierarchy with semantic theme tokens
<div>
  <h1 className="text-2xl font-bold text-text-primary">Customer Details</h1>
  <p className="text-sm font-medium text-text-secondary">Contact Information</p>
  <p className="text-sm text-text-muted">Additional details below</p>
</div>

// ❌ BAD - No hierarchy
<div>
  <h1 className="text-lg">Customer Details</h1>
  <p className="text-lg">Contact Information</p>
  <p className="text-lg">Additional details below</p>
</div>
```

#### Layout and Spacing
- **Start with too much white space** - Then remove
- **Use consistent spacing scale** - 4px, 8px, 16px, 24px, 32px, 48px
- **Don't fill the whole screen** - Max width 1280px for readability
- **Grids are overrated** - Use asymmetry for visual interest

```tsx
// ✅ GOOD - Consistent spacing scale (Tailwind's spacing)
<div className="space-y-6"> {/* 24px */}
  <Section className="space-y-4"> {/* 16px */}
    <Label className="mb-2" /> {/* 8px */}
    <Input />
  </Section>
</div>

// ✅ GOOD - Max width for readability
<div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
  <Content />
</div>
```

#### Color and Contrast
- **Colored backgrounds vs colored borders** - Backgrounds are more prominent
- **Overlap elements to create depth** - Cards, shadows
- **Use fewer borders** - Shadows, spacing, and backgrounds often work better

```tsx
// ✅ GOOD - Depth with shadow instead of border
<Card className="shadow-md border-0">
  <CardContent />
</Card>

// ❌ BAD - Flat with border
<div className="border border-gray-300">
  <Content />
</div>
```

### Inclusive Components (inclusive-components.design)

Accessible component patterns by Heydon Pickering.

#### Key Principles
- **Progressive enhancement** - Work without JavaScript
- **Semantic HTML** - Use proper elements
- **ARIA when needed** - Not as a replacement for semantics
- **Keyboard navigation** - Everything should be keyboard accessible

```tsx
// ✅ GOOD - Semantic disclosure widget
<details className="group">
  <summary className="cursor-pointer list-none">
    <ChevronDown className="group-open:rotate-180 transition" />
    Advanced Options
  </summary>
  <div className="mt-2">
    {/* Content */}
  </div>
</details>

// ✅ GOOD - Proper heading hierarchy
<article>
  <h1>Customer 360</h1>
  <section>
    <h2>Contact Information</h2>
    <h3>Primary Address</h3>
  </section>
  <section>
    <h2>Order History</h2>
  </section>
</article>
```

---

## Application-Specific UX Patterns

### Data-Heavy Interfaces
- Use **tables with fixed headers** for long lists
- Implement **column sorting and filtering**
- Show **key metrics in cards** above tables
- Use **expandable rows** for details

### Workflow Status
- Use **color-coded status badges** (but not color alone)
- Show **progress bars** for multi-step workflows
- Display **timeline/activity feed** for audit trail
- Use **icons + text** for status clarity

### Forms and Data Entry
- **Autosave drafts** every 30 seconds
- Show **validation inline** as user types (debounced)
- Use **smart defaults** from previous orders
- **Prefill data** from related entities (e.g., customer info)

### Search and Filters
- **Search across all fields** by default
- Show **recent searches** and **saved filters**
- Display **result count** before user applies filter
- Allow **filter combinations** (AND/OR logic)

---

## Performance UX

### Perceived Performance
- **Skeleton screens** > spinners > blank screens
- **Optimistic updates** for instant feedback
- **Prefetch** on hover for common actions
- **Lazy load** images and heavy components
- **Pagination** for lists > 50 items

### Loading States
```tsx
// ✅ GOOD - Skeleton screen
{isLoading ? (
  <div className="space-y-4">
    <Skeleton className="h-12 w-full" />
    <Skeleton className="h-12 w-full" />
    <Skeleton className="h-12 w-full" />
  </div>
) : (
  <CustomerList customers={data} />
)}

// ❌ BAD - Blank screen while loading
{!isLoading && <CustomerList customers={data} />}
```

---

## Mobile and Responsive UX

### Touch Targets
- Minimum **44x44px** for touch targets
- Add **padding** around clickable elements
- Use **larger buttons** on mobile

### Mobile Navigation
- **Hamburger menu** for mobile
- **Bottom navigation** for frequent actions
- **Swipe gestures** for common actions (optional)

### Responsive Patterns
```tsx
// ✅ GOOD - Responsive table → cards
<div className="hidden md:block">
  <Table /> {/* Desktop: table */}
</div>
<div className="md:hidden space-y-4">
  {items.map(item => <Card key={item.id} {...item} />)} {/* Mobile: cards */}
</div>
```

---

## Error Handling UX

### Error Messages
- **Be specific** - "Email is required" not "Invalid input"
- **Be helpful** - Suggest solutions
- **Be polite** - No blame or technical jargon
- **Show errors inline** near the problem

```tsx
// ✅ GOOD - Helpful error message
<Input
  error="Email is required. Please enter a valid email address like user@example.com"
/>

// ❌ BAD - Vague error
<Input error="Invalid" />
```

### Empty States
- **Explain why it's empty** - "No orders yet"
- **Provide next action** - "Create your first order"
- **Add illustration or icon** - Visual interest

```tsx
// ✅ GOOD - Helpful empty state
<EmptyState>
  <EmptyStateIcon icon={FileText} />
  <EmptyStateTitle>No orders yet</EmptyStateTitle>
  <EmptyStateDescription>
    Create your first order to get started
  </EmptyStateDescription>
  <Button onClick={openCreateDialog}>Create Order</Button>
</EmptyState>
```

---

## Accessibility and UX Overlap

Good UX is accessible by default:

- **Keyboard navigation** - Benefits power users
- **Clear focus indicators** - Shows current position
- **Color + icon/text** - Not color alone
- **Alt text for images** - Context for all users
- **Proper heading hierarchy** - Better scanability
- **High contrast** - Easier for everyone to read

---

## References

- [Laws of UX](https://lawsofux.com)
- [Nielsen Norman Group](https://www.nngroup.com)
- [Refactoring UI](https://www.refactoringui.com)
- [Inclusive Components](https://inclusive-components.design)
- [Material Design](https://m3.material.io)
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines)
- [The A11y Project](https://www.a11yproject.com)
- [Baymard Institute](https://baymard.com/blog)

---

## Usage in Development

1. **Before implementing a screen** - Review relevant UX laws
2. **During implementation** - Apply patterns from this guide
3. **Code review** - Check for UX anti-patterns
4. **User testing** - Validate assumptions with real users
5. **Iterate** - Refine based on feedback

Remember: **Good UX is invisible.** When users accomplish their goals effortlessly, you've succeeded.

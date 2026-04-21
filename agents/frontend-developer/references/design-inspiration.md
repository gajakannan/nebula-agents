# Design Inspiration and Visual References

**Version:** 1.0
**Last Updated:** 2026-01-29
**Applies To:** Frontend Developer

---

## Overview

This document curates modern design systems, applications, and websites that exemplify excellence in UI/UX design. Use these as inspiration for the application's visual design, interaction patterns, and overall aesthetic.

The focus is on **developer tools, SaaS platforms, and B2B applications** with clean, professional, and functional design.

---

## Primary Inspiration: Turborepo

**Website:** [turbo.build](https://turbo.build)

**Why it's great:**
- Clean, minimal developer-focused design
- Excellent use of whitespace and typography
- Strong visual hierarchy with clear CTAs
- Subtle animations that enhance (not distract)
- Great code examples with syntax highlighting
- Professional color palette (blue, purple, dark themes)
- Responsive design that scales beautifully

**Key Takeaways:**
- Large hero sections with clear value propositions
- Gradient accents used sparingly for emphasis
- Code blocks are first-class UI elements
- Navigation is simple and intuitive
- Dark mode done exceptionally well

**Design Elements to Adopt:**
```tsx
// Hero section with gradient accent
<section className="relative overflow-hidden bg-gradient-to-b from-white to-gray-50">
  <div className="mx-auto max-w-7xl px-6 py-24">
    <h1 className="text-6xl font-bold tracking-tight">
      The high-performance
      <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
        {" "}business platform
      </span>
    </h1>
  </div>
</section>

// Card with subtle hover effect
<Card className="transition-all hover:shadow-lg hover:border-blue-200">
  <CardContent />
</Card>
```

---

## Category: Developer Tools & Platforms

### 1. Vercel (vercel.com)

**Why it's great:**
- Minimal, clean aesthetic
- Exceptional typography (using Vercel's Geist font)
- Strategic use of black and white
- Subtle animations on scroll
- Clear information architecture

**Elements to Adopt:**
- Monospace fonts for technical data (order numbers, IDs)
- Generous line spacing for readability
- Black buttons for primary actions
- Grid layouts with consistent spacing

```tsx
// Vercel-style monospace for technical data
<div className="space-y-1">
  <Label className="text-xs text-gray-500">Order Number</Label>
  <div className="font-mono text-sm">{customer.orderNumber}</div>
</div>

// Clean black button
<Button className="bg-black hover:bg-gray-800 text-white">
  Create Order
</Button>
```

### 2. Linear (linear.app)

**Why it's great:**
- **Best-in-class animations** and micro-interactions
- Keyboard shortcuts everywhere (power user friendly)
- Beautiful gradient backgrounds
- Excellent command palette (Cmd+K)
- Smooth, native-feeling interactions

**Elements to Adopt:**
- Command palette for quick actions (Cmd+K)
- Smooth transitions between views
- Gradient accents on cards and backgrounds
- Keyboard shortcuts with visual indicators
- Loading states that feel instant

```tsx
// Linear-style command palette
<CommandDialog open={open} onOpenChange={setOpen}>
  <CommandInput placeholder="Type a command or search..." />
  <CommandList>
    <CommandGroup heading="Quick Actions">
      <CommandItem onSelect={() => navigate('/orders/new')}>
        <Plus className="mr-2 h-4 w-4" />
        Create Order
      </CommandItem>
      <CommandItem onSelect={() => navigate('/customers/new')}>
        <UserPlus className="mr-2 h-4 w-4" />
        Add Customer
      </CommandItem>
    </CommandGroup>
  </CommandList>
</CommandDialog>

// Keyboard shortcut hint
<Button className="relative">
  Create Order
  <kbd className="absolute -top-2 -right-2 rounded bg-gray-800 px-1.5 py-0.5 text-xs text-white">
    ⌘N
  </kbd>
</Button>
```

### 3. Stripe (stripe.com)

**Why it's great:**
- Professional, trustworthy design
- Excellent documentation design
- Clear data tables and API references
- Consistent component library
- Great use of color to indicate status

**Elements to Adopt:**
- Status badges with color + icon
- Clean table designs with zebra striping
- Code syntax highlighting in docs
- Inline validation with helpful hints
- Card-based layouts for sections

```tsx
// Stripe-style status badge
<Badge
  variant={status === 'active' ? 'success' : 'secondary'}
  className="gap-1"
>
  <div className={cn(
    "h-2 w-2 rounded-full",
    status === 'active' ? "bg-green-500" : "bg-gray-400"
  )} />
  {status}
</Badge>

// Clean data table
<Table>
  <TableHeader>
    <TableRow>
      <TableHead>Customer</TableHead>
      <TableHead>Email</TableHead>
      <TableHead>Status</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    {customers.map((customer, i) => (
      <TableRow
        key={customer.id}
        className={i % 2 === 0 ? 'bg-gray-50' : 'bg-white'}
      >
        <TableCell>{customer.name}</TableCell>
        <TableCell className="font-mono text-sm">{customer.email}</TableCell>
        <TableCell><StatusBadge status={customer.status} /></TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>
```

### 4. Supabase (supabase.com)

**Why it's great:**
- Dark mode with neon green accent
- Great use of code examples
- Clear product sections
- Excellent grid layouts
- Open-source friendly aesthetic

**Elements to Adopt:**
- Dark theme with vibrant accent colors
- Grid layouts for feature showcases
- Icon + title + description pattern
- Animated code examples

```tsx
// Supabase-style feature grid
<div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
  {features.map(feature => (
    <Card key={feature.title} className="border-gray-700 bg-gray-900">
      <CardHeader>
        <feature.icon className="h-10 w-10 text-green-400" />
        <CardTitle className="text-white">{feature.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-gray-400">{feature.description}</p>
      </CardContent>
    </Card>
  ))}
</div>
```

### 5. Resend (resend.com)

**Why it's great:**
- Beautiful gradient backgrounds
- Clean product screenshots
- Great copywriting paired with design
- Smooth scroll animations
- Developer-first but visually appealing

**Elements to Adopt:**
- Gradient backgrounds for hero sections
- Product screenshots with shadows and rounded corners
- Scroll-triggered animations
- Clean code snippets

```tsx
// Resend-style gradient background
<div className="relative overflow-hidden bg-gradient-to-br from-purple-500 via-pink-500 to-orange-500">
  <div className="absolute inset-0 bg-grid-white/[0.05] bg-[size:20px_20px]" />
  <div className="relative">
    <HeroContent />
  </div>
</div>

// Screenshot with shadow
<div className="rounded-lg border bg-white p-2 shadow-2xl">
  <img
    src="/dashboard-screenshot.png"
    alt="App Dashboard"
    className="rounded"
  />
</div>
```

---

## Category: Component Libraries & Design Systems

### 6. Radix UI (radix-ui.com)

**Why it's great:**
- Unstyled, accessible primitives
- Excellent documentation
- Clean, minimal design
- Focus on functionality over aesthetics
- Great component demos

**Elements to Adopt:**
- Accessible component patterns
- Compound component APIs
- Controlled vs uncontrolled patterns
- Keyboard navigation built-in

### 7. shadcn/ui (ui.shadcn.com)

**Why it's great:** (Already in our stack!)
- Copy-paste components, not npm packages
- Built on Radix UI primitives
- Fully customizable with Tailwind
- Excellent theming support
- Great dark mode

**Elements to Adopt:**
- Component composition patterns
- Consistent API design
- Theming with CSS variables
- Variant-based styling

```tsx
// shadcn/ui Button variants
<div className="flex gap-2">
  <Button variant="default">Primary</Button>
  <Button variant="secondary">Secondary</Button>
  <Button variant="outline">Outline</Button>
  <Button variant="ghost">Ghost</Button>
  <Button variant="destructive">Delete</Button>
</div>

// Theme switcher
<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <Button variant="ghost" size="icon">
      <Sun className="h-5 w-5 rotate-0 scale-100 dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute h-5 w-5 rotate-90 scale-0 dark:rotate-0 dark:scale-100" />
    </Button>
  </DropdownMenuTrigger>
  <DropdownMenuContent>
    <DropdownMenuItem onClick={() => setTheme('light')}>Light</DropdownMenuItem>
    <DropdownMenuItem onClick={() => setTheme('dark')}>Dark</DropdownMenuItem>
    <DropdownMenuItem onClick={() => setTheme('system')}>System</DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>
```

---

## Category: Modern SaaS Applications

### 8. Cal.com (cal.com)

**Why it's great:**
- Clean booking interface
- Open-source transparency
- Great use of color (purple brand)
- Simple, intuitive flows
- Mobile-first design

**Elements to Adopt:**
- Calendar/timeline interfaces
- Availability selection patterns
- Time slot pickers
- Booking confirmation flows

### 9. Raycast (raycast.com)

**Why it's great:**
- Gorgeous product design
- Beautiful marketing site
- Great use of animation
- Dark theme with colorful accents
- Native-feeling web experience

**Elements to Adopt:**
- Spotlight-style search
- Keyboard-first interactions
- Smooth animations
- Dark UI with pops of color

### 10. Clerk (clerk.com)

**Why it's great:**
- Excellent onboarding flows
- Beautiful authentication UI
- Great error states
- Smooth transitions
- Developer-friendly docs

**Elements to Adopt:**
- Multi-step onboarding wizards
- Authentication form patterns
- Error message design
- Loading states during auth

---

## Category: Design Systems & Guidelines

### 11. Material Design 3 (m3.material.io)

**Why it's great:**
- Comprehensive component library
- Motion guidelines
- Color system
- Accessibility built-in
- Responsive design patterns

**Key Concepts:**
- Material You (dynamic color)
- Elevation and shadows
- Motion and transitions
- Typography scale

### 12. Apple Human Interface Guidelines

**Why it's great:**
- Platform-specific guidance
- Excellent accessibility standards
- Typography and layout principles
- Icon design guidelines

**Key Concepts:**
- Clarity, deference, depth
- Consistent navigation
- Direct manipulation
- Feedback and communication

---

## Design Patterns

### Navigation Patterns

**Sidebar Navigation (Recommended)**

```tsx
<div className="flex h-screen">
  {/* Sidebar */}
  <aside className="w-64 border-r bg-gray-50">
    <div className="p-4">
      <Logo />
    </div>
    <nav className="space-y-1 px-2">
      <NavItem icon={Home} href="/" label="Dashboard" />
      <NavItem icon={Users} href="/customers" label="Customers" />
      <NavItem icon={FileText} href="/orders" label="Orders" />
      <NavItem icon={RefreshCw} href="/subscriptions" label="Subscriptions" />
      <NavItem icon={Calendar} href="/tasks" label="Tasks" />
    </nav>
  </aside>

  {/* Main content */}
  <main className="flex-1 overflow-y-auto">
    <Outlet />
  </main>
</div>
```

**Inspired by:** Linear, Stripe Dashboard

### Data Display Patterns

**360 View (Customer Detail)**

```tsx
<div className="space-y-6">
  {/* Header with primary actions */}
  <div className="flex items-center justify-between">
    <div>
      <h1 className="text-3xl font-bold">{customer.name}</h1>
      <p className="text-sm text-gray-500">Email: {customer.email}</p>
    </div>
    <div className="flex gap-2">
      <Button variant="outline">Edit</Button>
      <Button>New Order</Button>
    </div>
  </div>

  {/* Stats cards */}
  <div className="grid gap-4 md:grid-cols-4">
    <StatCard label="Active Orders" value={12} />
    <StatCard label="Completed YTD" value="$2.4M" />
    <StatCard label="Approval Rate" value="68%" />
    <StatCard label="Avg Days to Complete" value={14} />
  </div>

  {/* Tabbed content */}
  <Tabs defaultValue="orders">
    <TabsList>
      <TabsTrigger value="orders">Orders</TabsTrigger>
      <TabsTrigger value="addresses">Addresses</TabsTrigger>
      <TabsTrigger value="documents">Documents</TabsTrigger>
      <TabsTrigger value="activity">Activity</TabsTrigger>
    </TabsList>
    <TabsContent value="orders">
      <OrdersTable customerId={customer.id} />
    </TabsContent>
    {/* Other tabs */}
  </Tabs>
</div>
```

**Inspired by:** Stripe Dashboard, Linear Issues

### Form Patterns

**Multi-Step Form (Order Creation)**

```tsx
<Form>
  {/* Progress indicator */}
  <div className="mb-8">
    <ol className="flex items-center gap-2">
      <Step number={1} label="Basic Info" active />
      <Separator />
      <Step number={2} label="Details" />
      <Separator />
      <Step number={3} label="Documents" />
      <Separator />
      <Step number={4} label="Review" />
    </ol>
  </div>

  {/* Current step content */}
  <div className="space-y-6">
    <FormFields />
  </div>

  {/* Navigation */}
  <div className="mt-8 flex justify-between">
    <Button variant="outline" onClick={goBack}>
      Back
    </Button>
    <Button onClick={goNext}>
      Continue
    </Button>
  </div>
</Form>
```

**Inspired by:** Stripe Onboarding, Cal.com Booking

### Empty States

```tsx
<div className="flex min-h-[400px] flex-col items-center justify-center p-8 text-center">
  <div className="rounded-full bg-gray-100 p-6">
    <FileText className="h-12 w-12 text-gray-400" />
  </div>
  <h3 className="mt-4 text-lg font-semibold">No orders yet</h3>
  <p className="mt-2 text-sm text-gray-500">
    Get started by creating your first order
  </p>
  <Button className="mt-6" onClick={openCreateDialog}>
    <Plus className="mr-2 h-4 w-4" />
    Create Order
  </Button>
</div>
```

**Inspired by:** Linear, Vercel

---

## Color Palettes

### Professional B2B Palette (Recommended)

Based on Stripe, Linear, Vercel

```tsx
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        // Primary: Blue (trust, professionalism)
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          900: '#1e3a8a',
        },
        // Accent: Purple (modern, creative)
        accent: {
          500: '#8b5cf6',
          600: '#7c3aed',
        },
        // Success: Green
        success: {
          500: '#10b981',
          600: '#059669',
        },
        // Warning: Amber
        warning: {
          500: '#f59e0b',
          600: '#d97706',
        },
        // Danger: Red
        danger: {
          500: '#ef4444',
          600: '#dc2626',
        },
        // Grays: Neutral
        gray: {
          50: '#f9fafb',
          100: '#f3f4f6',
          500: '#6b7280',
          700: '#374151',
          900: '#111827',
        },
      },
    },
  },
};
```

### Status Colors (Workflow States)

```tsx
const statusColors = {
  draft: 'bg-gray-100 text-gray-700',
  pending: 'bg-yellow-100 text-yellow-700',
  in_review: 'bg-blue-100 text-blue-700',
  approved: 'bg-purple-100 text-purple-700',
  completed: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
};
```

---

## Typography

### Font Pairings (Recommended)

**Option 1: Inter (Headings + Body)**
- Clean, modern, excellent readability
- Used by: Vercel, Linear, Stripe

**Option 2: Geist (Vercel's font)**
- Modern, geometric
- Excellent for UI

**Option 3: System Font Stack**
- Fast loading, native feel
- Used by: GitHub, Apple

```tsx
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
};
```

### Type Scale

```tsx
// Headings
<h1 className="text-4xl font-bold">Customer 360</h1>
<h2 className="text-2xl font-semibold">Recent Activity</h2>
<h3 className="text-lg font-medium">Contact Information</h3>

// Body
<p className="text-base">Default body text</p>
<p className="text-sm text-gray-600">Secondary text</p>
<p className="text-xs text-gray-500">Meta information</p>

// Technical (monospace)
<code className="font-mono text-sm">Order: ORD-123456</code>
```

---

## Animation and Motion

### Principles

1. **Purposeful** - Animations should communicate, not just decorate
2. **Fast** - Keep under 300ms for most interactions
3. **Natural** - Use easing functions (ease-out for entrances, ease-in for exits)
4. **Subtle** - Don't distract from content

### Common Animations

```tsx
// Hover states (Turborepo-style)
<Card className="transition-all duration-200 hover:shadow-lg hover:-translate-y-1">
  <CardContent />
</Card>

// Loading skeleton (Vercel-style)
<div className="animate-pulse space-y-4">
  <div className="h-4 rounded bg-gray-200" />
  <div className="h-4 w-2/3 rounded bg-gray-200" />
</div>

// Fade in (Linear-style)
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.3 }}
>
  <Content />
</motion.div>

// Slide in sidebar
<motion.aside
  initial={{ x: -300 }}
  animate={{ x: 0 }}
  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
>
  <Sidebar />
</motion.aside>
```

---

## Responsive Design

### Breakpoints (Tailwind defaults)

```tsx
sm: '640px'   // Small tablets
md: '768px'   // Tablets
lg: '1024px'  // Laptops
xl: '1280px'  // Desktops
2xl: '1536px' // Large desktops
```

### Mobile-First Pattern

```tsx
// Stack on mobile, grid on desktop
<div className="flex flex-col gap-4 md:grid md:grid-cols-2 lg:grid-cols-3">
  <Card />
  <Card />
  <Card />
</div>

// Hide sidebar on mobile, show on desktop
<aside className="hidden lg:block">
  <Sidebar />
</aside>
```

---

## Reference Checklist for Designers/Developers

When implementing a new feature, ask:

- [ ] Does this follow Laws of UX principles?
- [ ] Is it accessible (keyboard, screen reader, WCAG AA)?
- [ ] Is it responsive (mobile, tablet, desktop)?
- [ ] Are loading states and errors handled?
- [ ] Does it match our design system (colors, spacing, typography)?
- [ ] Are animations purposeful and performant?
- [ ] Is it consistent with existing patterns?
- [ ] Can I find inspiration from our reference sites?

---

## Design Resources to Bookmark

### Inspiration
- [Turborepo](https://turbo.build)
- [Linear](https://linear.app)
- [Vercel](https://vercel.com)
- [Stripe](https://stripe.com)
- [Resend](https://resend.com)
- [Supabase](https://supabase.com)
- [Raycast](https://raycast.com)

### Component Libraries
- [shadcn/ui](https://ui.shadcn.com)
- [Radix UI](https://radix-ui.com)
- [Headless UI](https://headlessui.com)

### Design Systems
- [Material Design 3](https://m3.material.io)
- [Apple HIG](https://developer.apple.com/design)
- [Atlassian Design System](https://atlassian.design)

### Tools
- [Coolors](https://coolors.co) - Color palette generator
- [Type Scale](https://typescale.com) - Typography scale calculator
- [Hero Icons](https://heroicons.com) - Icon set
- [Lucide Icons](https://lucide.dev) - Icon set (used by shadcn/ui)

---

## Conclusion

Use these references as a **north star** for visual design decisions. When in doubt:

1. Look at how Linear/Stripe/Vercel solved similar problems
2. Apply Laws of UX principles
3. Use shadcn/ui components as a base
4. Keep it simple, professional, and accessible

**Good design is invisible.** Users should focus on their work, not on navigating the interface.

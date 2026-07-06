---
name: uhomes-design
description: Design system skill for uhomes. Activate when building UI components, pages, or any visual elements. Provides exact color tokens, typography scale, spacing grid, component patterns, and craft rules. Read references/DESIGN.md before writing any CSS or JSX. Includes ultra-mode visual journey: read references/ANIMATIONS.md, references/LAYOUT.md, references/COMPONENTS.md, and references/INTERACTIONS.md for full motion and layout details.
---

# uhomes Design System

You are building UI for **uhomes**. Light-themed, neutral palette, sans-serif typography (cfont), standard density on a 5px grid, expressive motion.

## Visual Reference

**IMPORTANT**: Study ALL screenshots below before writing any UI. Match colors, typography, spacing, layout, and motion exactly as shown.

### Homepage

![uhomes Homepage](screenshots/homepage.png)

### Scroll Journey (Cinematic Visual States)

> These screenshots capture the website at different scroll depths. The design changes dramatically as you scroll — each frame shows a different cinematic state. Replicate these exact visual transitions.

#### 0% — Hero / Above the fold

![Scroll 0%](screens/scroll/scroll-000.png)

#### 17% — Mid-page at 17% scroll

![Scroll 17%](screens/scroll/scroll-017.png)

#### 33% — Mid-page at 33% scroll

![Scroll 33%](screens/scroll/scroll-033.png)

#### 50% — Mid-page at 50% scroll

![Scroll 50%](screens/scroll/scroll-050.png)

#### 67% — Mid-page at 67% scroll

![Scroll 67%](screens/scroll/scroll-067.png)

#### 83% — Mid-page at 83% scroll

![Scroll 83%](screens/scroll/scroll-083.png)

#### 100% — Footer / End of page

![Scroll 100%](screens/scroll/scroll-100.png)

> Read `references/DESIGN.md` for full token details. Read `references/ANIMATIONS.md` for motion specs. Read `references/LAYOUT.md` for layout structure. Read `references/COMPONENTS.md` for component patterns.

## Ultra Reference Files

This package includes extended documentation. **Read these files before implementing:**

| File | Contents |
|------|----------|
| `references/DESIGN.md` | Full design system tokens, colors, typography, spacing |
| `references/VISUAL_GUIDE.md` | **START HERE** — Master visual guide with all screenshots embedded |
| `references/ANIMATIONS.md` | CSS keyframes, scroll triggers, motion library stack, video specs |
| `references/LAYOUT.md` | Flex/grid containers, page structure, spacing relationships |
| `references/COMPONENTS.md` | DOM component patterns, HTML structure, class fingerprints |
| `references/INTERACTIONS.md` | Hover/focus states with before/after style diffs |
| `screens/scroll/` | 7 scroll journey screenshots showing cinematic states |

## Design Philosophy

- **Layered depth** — use shadow tokens to create a sense of physical layering. Each elevation level has a specific shadow.
- **Gradient accents** — gradients are used thoughtfully for emphasis, not decoration.
- **Type pairing** — cfont for body/UI text, Poppins for headings/display. Never introduce a third typeface.
- **standard density** — 5px base grid. Every dimension is a multiple of 5.
- **neutral palette** — the color temperature runs neutral, matching the sans-serif typography.
- **Expressive motion** — animations are an integral part of the experience. Use spring physics and layout animations.

## Color System

### Core Palette

| Role | Token | Hex | Use |
|------|-------|-----|-----|
| Background | `--background` | `#ffffff` | Page/app background |
| Surface | `--surface` | `#fef0f0` | Cards, panels, modals |
| Text Primary | `--text-primary` | `#222222` | Headings, body text |
| Text Muted | `--text-muted` | `#555555` | Captions, placeholders |
| Border | `--border` | `#303133` | Dividers, card borders |

### Status Colors

| Status | Hex | Use |
|--------|-----|-----|
| Success | `#67c23a` | Confirmations, positive trends |
| Warning | `#faecd8` | Caution states, pending items |
| Danger | `#ff5a5f` | Errors, destructive actions |

### Extended Palette

- **el-color-primary-light-9:** `#e7f2f5` — Light surface or highlight color
- **el-text-color-regular:** `#666666`
- `#0c7094`
- **el-color-info:** `#999999`
- **el-color-info-light-5:** `#cccccc`
- **el-color-black:** `#000000` — Deep background layer or shadow color
- **el-color-info-light-7:** `#dedfe0`
- **el-color-danger:** `#f56c6c` — Destructive actions, error states

### CSS Variable Tokens

```css
--v-theme-background: 255,255,255;
--v-theme-background-overlay-multiplier: 1;
--v-theme-primary: 24,103,192;
--v-theme-primary-overlay-multiplier: 2;
--v-theme-primary-darken-1: 31,85,146;
--v-theme-primary-darken-1-overlay-multiplier: 2;
--v-theme-secondary: 72,169,166;
--v-theme-secondary-overlay-multiplier: 1;
--v-theme-secondary-darken-1: 1,135,134;
--v-theme-secondary-darken-1-overlay-multiplier: 1;
--v-theme-on-background: 0,0,0;
--v-theme-on-primary: 255,255,255;
--v-theme-on-primary-darken-1: 255,255,255;
--v-theme-on-secondary: 255,255,255;
--v-theme-on-secondary-darken-1: 255,255,255;
--v-border-color: 0,0,0;
--v-border-opacity: .12;
--v-field-border-width: 1px;
--v-field-border-opacity: .38;
--v-field-border-opacity: var(--v-high-emphasis-opacity);
```

## Typography

### Font Stack

- **cfont** — Heading 1, Heading 2, Heading 3
- **Poppins** — Body, Caption

### Font Sources

```css
@font-face {
  font-family: "Poppins";
  src: url("fonts/Poppins-Regular.woff2") format("woff2");
  font-weight: 400;
}
@font-face {
  font-family: "cfont";
  src: url("fonts/cfont-Regular.woff2") format("woff2");
  font-weight: 400;
}
@font-face {
  font-family: "iconfont";
  src: url("fonts/iconfont-Regular.woff2") format("woff2");
  font-weight: 400;
}
@font-face {
  font-family: "ufont";
  src: url("fonts/ufont-Regular.woff") format("woff");
  font-weight: 400;
}
@font-face {
  font-family: "element-icons";
  src: url("fonts/element-icons-Regular.woff") format("woff");
  font-weight: 400;
}
@font-face {
  font-family: "swiper-icons";
  src: url("data:application/font-woff;charset=utf-8;base64,\ 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");
  font-weight: 400;
}
```

### Type Scale

| Role | Family | Size | Weight |
|------|--------|------|--------|
| Heading 1 | cfont | 160px | 700 |
| Heading 2 | cfont | 150px | 700 |
| Heading 3 | cfont | 146px | 700 |
| Body | Poppins | 12px | 400 |
| Caption | Poppins | 14px | 400 |

### Typography Rules

- Body/UI: **cfont**, Headings: **Poppins** — these are the only display fonts
- Max 3-4 font sizes per screen
- Headings: weight 600-700, body: weight 400
- Use color and opacity for text hierarchy, not additional font sizes
- Line height: 1.5 for body, 1.2 for headings

## Spacing & Layout

### Base Grid: 5px

Every dimension (margin, padding, gap, width, height) must be a multiple of **5px**.

### Spacing Scale

`5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60` px

### Spacing as Meaning

| Spacing | Use |
|---------|-----|
| 2.5-5px | Tight: related items within a group |
| 10px | Medium: between groups |
| 15-20px | Wide: between sections |
| 30px+ | Vast: major section breaks |

### Border Radius

Scale: `.08rem, 1px, 2px, 3px, 3px 0px 0px 3px, 4px, 5px, 6px, 7px, 8px, 9px, 10px, 11px, 16px, inherit, 12px, 14px, 15px, 18px, 19px, 20px, 22px, 23px, 24px, 25px, 30px, 32px, 40px, 45px, 50px, 60px, 100%, 100px, 500px, unset`
Default: `15px`

### Container

Max-width: `960px`, centered with auto margins.

### Breakpoints

| Name | Value |
|------|-------|
| xs | 428px |
| xs | 480px |
| sm | 639px |
| md | 750px |
| md | 767px |
| md | 768px |
| lg | 769px |
| lg | 850px |
| lg | 892px |
| lg | 920px |
| lg | 960px |
| lg | 964px |
| lg | 992px |
| lg | 1023px |
| lg | 1024px |
| xl | 1100px |
| xl | 1179px |
| xl | 1180px |
| xl | 1200px |
| xl | 1280px |
| 2xl | 1299px |
| 2xl | 1300px |
| 2xl | 1340px |
| 2xl | 1350px |
| 2xl | 1400px |
| 2xl | 1401px |
| 2xl | 1920px |

Mobile-first: design for small screens, layer on responsive overrides.

## Component Patterns

### Card

```css
.card {
  background: #fef0f0;
  border: 1px solid #303133;
  border-radius: 15px;
  padding: 20px;
  box-shadow: 0 0 5px #0003;
}
```

```html
<div class="card">
  <h3>Card Title</h3>
  <p>Card content goes here.</p>
</div>
```

### Button

```css
/* Primary */
.btn-primary {
  background: #cccccc;
  color: #222222;
  border-radius: 15px;
  padding: 10px 20px;
  font-weight: 500;
  transition: opacity 150ms ease;
}
.btn-primary:hover { opacity: 0.9; }

/* Ghost */
.btn-ghost {
  background: transparent;
  border: 1px solid #303133;
  color: #222222;
  border-radius: 15px;
  padding: 10px 20px;
}
```

```html
<button class="btn-primary">Get Started</button>
<button class="btn-ghost">Learn More</button>
```

### Input

```css
.input {
  background: #ffffff;
  border: 1px solid #303133;
  border-radius: 15px;
  padding: 10px 15px;
  color: #222222;
  font-size: 14px;
}
.input:focus { border-color: var(--accent); outline: none; }
```

```html
<input class="input" type="text" placeholder="Search..." />
```

### Badge / Chip

```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
  background: #fef0f0;
  color: #555555;
}
```

```html
<span class="badge">New</span>
<span class="badge">Beta</span>
```

### Modal / Dialog

```css
.modal-backdrop { background: rgba(0, 0, 0, 0.6); }
.modal {
  background: #fef0f0;
  border: 1px solid #303133;
  border-radius: unset;
  padding: 30px;
  max-width: 480px;
  width: 90vw;
  box-shadow: 0 0 10px #0003;
}
```

```html
<div class="modal-backdrop">
  <div class="modal">
    <h2>Dialog Title</h2>
    <p>Dialog content.</p>
    <button class="btn-primary">Confirm</button>
    <button class="btn-ghost">Cancel</button>
  </div>
</div>
```

### Table

```css
.table { width: 100%; border-collapse: collapse; }
.table th {
  text-align: left;
  padding: 10px 15px;
  font-weight: 500;
  font-size: 12px;
  color: #555555;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid #303133;
}
.table td {
  padding: 15px;
  border-bottom: 1px solid #303133;
}
```

```html
<table class="table">
  <thead><tr><th>Name</th><th>Status</th><th>Date</th></tr></thead>
  <tbody>
    <tr><td>Item One</td><td>Active</td><td>Jan 1</td></tr>
    <tr><td>Item Two</td><td>Pending</td><td>Jan 2</td></tr>
  </tbody>
</table>
```

### Navigation

```css
.nav {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px 20px;
  border-bottom: 1px solid #303133;
}
.nav-link {
  color: #555555;
  padding: 10px 15px;
  border-radius: 15px;
  transition: color 150ms;
}
.nav-link:hover { color: #222222; }
```

```html
<nav class="nav">
  <a href="/" class="nav-link active">Home</a>
  <a href="/about" class="nav-link">About</a>
  <a href="/pricing" class="nav-link">Pricing</a>
  <button class="btn-primary" style="margin-left: auto">Get Started</button>
</nav>
```

### Extracted Components

These components were found in the codebase:

**Button** (`html`)
- Variants: `global`, `-disabled`, `-icon`, `-density-default`, `-variant-text`

**Card** (`html`)
- Variants: `badge`, `image`, `image-1`, `image-2`, `image-3`

**Navigation** (`html`)

**List** (`html`)

## Page Structure

The following page sections were detected:

- **Hero** — Hero/banner section with headline and CTAs
- **Features** — Feature/benefit cards grid (52 items)
- **Faq** — FAQ/accordion section
- **Testimonials** — Testimonials/reviews section
- **Navigation** — Top navigation bar

When building pages, follow this section order and structure.

## Animation & Motion

This project uses **expressive motion**. Animations are part of the design language.

### CSS Animations

- `dialog-fade-in-bb3332ab`
- `dialog-fade-out-bb3332ab`
- `indeterminate-ltr`
- `indeterminate-rtl`
- `indeterminate-short-ltr`

### Motion Tokens

- **Duration scale:** `0ms`, `.15s`, `.28s`, `.4s`, `.7s`, `2.2s`, `50ms`, `75ms`, `86ms`, `100ms`, `120ms`, `150ms`, `200ms`, `250ms`, `300ms`, `340ms`, `400ms`, `500ms`, `600ms`, `800ms`, `1000ms`
- **Easing functions:** `ease`, `cubic-bezier(.4,0,.2,1)`, `cubic-bezier(0,0,.2,1)`, `ease-in-out`, `linear`, `cubic-bezier(.55,0,.1,1)`, `cubic-bezier(.23,1,.32,1)`, `ease-out`, `cubic-bezier(.71,-.46,.29,1.46)`, `ease-in`, `cubic-bezier(.25,.8,.5,1)`, `cubic-bezier(.4,0,1,1)`, `cubic-bezier(.8,0,1,1)`, `cubic-bezier(.645,.045,.355,1)`

### Motion Guidelines

- **Duration:** Use values from the duration scale above. Short (0ms) for micro-interactions, long (1000ms) for page transitions
- **Easing:** Use `ease` as the default easing curve
- **Direction:** Elements enter from bottom/right, exit to top/left
- **Reduced motion:** Always respect `prefers-reduced-motion` — disable animations when set

## Depth & Elevation

### Shadow Tokens

- Subtle: `0 0 0 1px var(--el-input-border-color,var(--el-border-color)) inset`
- Subtle: `0 0 0 1px var(--el-input-hover-border-color) inset`
- Subtle: `0 0 0 1px var(--el-input-focus-border-color) inset`
- Subtle: `0 0 0 1px var(--el-disabled-border-color) inset`
- Subtle: `0 0 0 1px var(--el-color-danger) inset`
- Subtle: `inset 0 0 0 1px`

### Z-Index Scale

`0, 1, 2, 3, 4, 5, 6, 9, 10, 11, 13, 33, 50, 99, 100, 101, 997, 999, 1000, 1001, 1007, 1900, 2000, 9999, 10000, 10010, 10011, 10091, 10100, 10101, 10191, 99999, 999999, 1000000, 1000001, 999999999999`

Use these exact values — never invent z-index values.

## Anti-Patterns (Never Do)

- **No blur effects** — no backdrop-blur, no filter: blur()
- **No zebra striping** — tables and lists use borders for separation
- **No invented colors** — every hex value must come from the palette above
- **No arbitrary spacing** — every dimension is a multiple of 5px
- **No extra fonts** — only cfont and Poppins are allowed
- **No arbitrary border-radius** — use the scale: .08rem, 1px, 2px, 3px, 4px, 5px, 6px, 7px, 8px, 9px
- **No opacity for disabled states** — use muted colors instead

## Workflow

1. **Read** `references/DESIGN.md` before writing any UI code
2. **Pick colors** from the Color System section — never invent new ones
3. **Set typography** — cfont, Poppins only, using the type scale
4. **Build layout** on the 5px grid — check every margin, padding, gap
5. **Match components** to patterns above before creating new ones
6. **Apply elevation** — use shadow tokens
7. **Validate** — every value traces back to a design token. No magic numbers.

## Brand Spec

- **Favicon:** `/favicon.ico`
- **Site URL:** `https://uhomes.com`
- **Brand typeface:** cfont

## Quick Reference

```
Background:     #ffffff
Surface:        #fef0f0
Text:           #222222 / #555555
Accent:         (not extracted)
Border:         #303133
Font:           cfont
Spacing:        5px grid
Radius:         15px
Components:     9 detected
```

## When to Trigger

Activate this skill when:
- Creating new components, pages, or visual elements for uhomes
- Writing CSS, Tailwind classes, styled-components, or inline styles
- Building page layouts, templates, or responsive designs
- Reviewing UI code for design consistency
- The user mentions "uhomes" design, style, UI, or theme
- Generating mockups, wireframes, or visual prototypes

---

# Full Reference Files

> Every output file is embedded below. Claude has full design system context from /skills alone.

## Design System Tokens (DESIGN.md)

# uhomes DESIGN.md

> Auto-generated design system — reverse-engineered via static analysis by skillui.
> Frameworks: None detected
> Colors: 20 · Fonts: 2 · Components: 9
> Icon library: not detected · State: not detected
> Primary theme: light · Dark mode toggle: no · Motion: expressive

## Visual Reference

**Match this design exactly** — study colors, fonts, spacing, and component shapes before writing any UI code.

![uhomes Homepage](../screenshots/homepage.png)

---

## 1. Visual Theme & Atmosphere

This is a **light-themed** interface with a neutral, approachable feel. The light background emphasizes content clarity. Typography pairs **Poppins** for display/headings with **cfont** for body text, creating clear visual hierarchy through type contrast. Spacing follows a **5px base grid** (standard density), with scale: 5, 10, 15, 20, 25, 30, 35, 40px. Motion is expressive — spring physics, layout animations, and staggered reveals are part of the visual language.

---

## 2. Color Palette & Roles

| Token | Hex | Role | Use |
|---|---|---|---|
| el-color-white | `#ffffff` | background | Page background, darkest surface |
| el-color-danger-light-9 | `#fef0f0` | surface | Card and panel backgrounds |
| text-primary | `#222222` | text-primary | Headings and body text |
| text-muted | `#555555` | text-muted | Captions, placeholders, secondary info |
| el-text-color-primary | `#303133` | border | Dividers, card borders, outlines |
| danger | `#ff5a5f` | danger | Error states, destructive actions |
| el-color-success | `#67c23a` | success | Success states, positive indicators |
| el-color-warning-light-8 | `#faecd8` | warning | Warning states, caution indicators |
| el-color-primary-light-9 | `#e7f2f5` | info | Informational highlights |
| el-text-color-regular | `#666666` | unknown | Palette color |
| unknown | `#0c7094` | unknown | Palette color |
| el-color-info | `#999999` | unknown | Palette color |
| el-color-info-light-5 | `#cccccc` | unknown | Palette color |
| el-color-black | `#000000` | unknown | Palette color |
| el-color-info-light-7 | `#dedfe0` | unknown | Palette color |
| el-color-danger | `#f56c6c` | unknown | Palette color |
| unknown | `#fad7b7` | unknown | Palette color |
| el-color-warning | `#e6a23c` | unknown | Palette color |
| el-color-success-light-9 | `#f0f9eb` | unknown | Palette color |
| unknown | `#963434` | unknown | Palette color |

### CSS Variable Tokens

```css
--v-theme-background: 255,255,255;
--v-theme-background-overlay-multiplier: 1;
--v-theme-primary: 24,103,192;
--v-theme-primary-overlay-multiplier: 2;
--v-theme-primary-darken-1: 31,85,146;
--v-theme-primary-darken-1-overlay-multiplier: 2;
--v-theme-secondary: 72,169,166;
--v-theme-secondary-overlay-multiplier: 1;
--v-theme-secondary-darken-1: 1,135,134;
--v-theme-secondary-darken-1-overlay-multiplier: 1;
--v-theme-on-background: 0,0,0;
--v-theme-on-primary: 255,255,255;
--v-theme-on-primary-darken-1: 255,255,255;
--v-theme-on-secondary: 255,255,255;
--v-theme-on-secondary-darken-1: 255,255,255;
--v-border-color: 0,0,0;
--v-border-opacity: .12;
--v-field-border-width: 1px;
--v-field-border-opacity: .38;
--v-field-border-opacity: var(--v-high-emphasis-opacity);
```


---

## 3. Typography Rules

**Font Stack:**
- **cfont** — Heading 1, Heading 2, Heading 3
- **Poppins** — Body, Caption

**Font Sources:**

```css
@font-face {
  font-family: "Poppins";
  src: url("fonts/Poppins-Regular.woff2") format("woff2");
  font-weight: 400;
}
@font-face {
  font-family: "cfont";
  src: url("fonts/cfont-Regular.woff2") format("woff2");
  font-weight: 400;
}
@font-face {
  font-family: "iconfont";
  src: url("fonts/iconfont-Regular.woff2") format("woff2");
  font-weight: 400;
}
@font-face {
  font-family: "ufont";
  src: url("fonts/ufont-Regular.woff") format("woff");
  font-weight: 400;
}
@font-face {
  font-family: "element-icons";
  src: url("fonts/element-icons-Regular.woff") format("woff");
  font-weight: 400;
}
@font-face {
  font-family: "swiper-icons";
  src: url("data:application/font-woff;charset=utf-8;base64,\ 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");
  font-weight: 400;
}
```

| Role | Font | Size | Weight |
|---|---|---|---|
| Heading 1 | cfont | 160px | 700 |
| Heading 2 | cfont | 150px | 700 |
| Heading 3 | cfont | 146px | 700 |
| Body | Poppins | 12px | 400 |
| Caption | Poppins | 14px | 400 |

**Typographic Rules:**
- Limit to 2 font families max per screen
- Use **cfont** for body/UI text, **Poppins** for display/headings
- Maintain consistent hierarchy: no more than 3-4 font sizes per screen
- Headings use bold (600-700), body uses regular (400)
- Line height: 1.5 for body text, 1.2 for headings
- Use color and opacity for secondary hierarchy, not additional font sizes


---

## 4. Component Stylings

### Navigation (1)

**Navigation** — `html`

### Data Display (3)

**Card** — `html`
- Variants: `badge`, `image`, `image-1`, `image-2`, `image-3`

**Badge** — `html`

**List** — `html`

### Data Input (2)

**Button** — `html`
- Variants: `global`, `-disabled`, `-icon`, `-density-default`, `-variant-text`
- Animation: 

**Input** — `html`
- State: :focus, :placeholder

### Overlay (1)

**Modal** — `html`

### Media (2)

**Image** — `html`

**Icon** — `html`



---

## 5. Layout Principles

- **Base spacing unit:** 5px
- **Spacing scale:** 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60
- **Border radius:** .08rem, 1px, 2px, 3px, 3px 0px 0px 3px, 4px, 5px, 6px, 7px, 8px, 9px, 10px, 11px, 16px, inherit, 12px, 14px, 15px, 18px, 19px, 20px, 22px, 23px, 24px, 25px, 30px, 32px, 40px, 45px, 50px, 60px, 100%, 100px, 500px, unset
- **Max content width:** 960px

**Spacing as Meaning:**
| Spacing | Use |
|---|---|
| 2.5-5px | Tight: related items within a group |
| 10px | Medium: between groups |
| 15-20px | Wide: between sections |
| 30px+ | Vast: major section breaks |


---

## 6. Depth & Elevation

### Flat — subtle depth hints

- `0 0 0 1px var(--el-input-border-color,var(--el-border-color)) inset`
- `0 0 0 1px var(--el-input-hover-border-color) inset`
- `0 0 0 1px var(--el-input-focus-border-color) inset`

### Raised — cards, buttons, interactive elements

- `0 0 5px #0003`
- `0 0 8px #3333331a`
- `0 2px 1px -1px #0003,0 1px 1px #00000024,0 1px 3px #0000001f`

### Floating — dropdowns, popovers, modals

- `0 0 10px #0003`
- `0 2px 4px -1px #0003,0 4px 5px #00000024,0 1px 10px #0000001f`
- `0 2px 4px -1px var(--v-shadow-key-umbra-opacity,rgba(0,0,0,.2)),0 4px 5px 0 var(--v-shadow-key-penumbra-opacity,rgba(0,0,0,.14)),0 1px 10px 0 var(--v-shadow-key-ambient-opacity,rgba(0,0,0,.12))`

### Overlay — full-screen overlays, top-level dialogs

- `0 10px 24px #b6a6ef33`
- `0 10px 30px #00000026`
- `0 8px 10px -5px rgba(0,0,0,.2),0 16px 24px 2px rgba(0,0,0,.14),0 6px 30px 5px rgba(0,0,0,.12)`

### Z-Index Scale

`0, 1, 2, 3, 4, 5, 6, 9, 10, 11, 13, 33, 50, 99, 100, 101, 997, 999, 1000, 1001, 1007, 1900, 2000, 9999, 10000, 10010, 10011, 10091, 10100, 10101, 10191, 99999, 999999, 1000000, 1000001, 999999999999`



---

## 7. Animation & Motion

This project uses **expressive motion**. Animations are an integral part of the experience.

### CSS Animations

- `@keyframes dialog-fade-in-bb3332ab`
- `@keyframes dialog-fade-out-bb3332ab`
- `@keyframes indeterminate-ltr`
- `@keyframes indeterminate-rtl`
- `@keyframes indeterminate-short-ltr`
- `@keyframes indeterminate-short-rtl`
- `@keyframes stream`
- `@keyframes progress-linear-stripes`

### Animated Components

- **Button**: 

### Motion Guidelines

- Duration: 150-300ms for micro-interactions, 300-500ms for page transitions
- Easing: `ease-out` for enters, `ease-in` for exits
- Always respect `prefers-reduced-motion`


---

## 8. Do's and Don'ts

### Do's

- Use `#ffffff` as the primary page background
- Pair **cfont** (body) with **Poppins** (display) — these are the only allowed fonts
- Follow the **5px** spacing grid for all margins, padding, and gaps
- Use the defined shadow tokens for elevation — see Section 6
- Use border-radius from the scale: .08rem, 1px, 2px, 3px, 3px 0px 0px 3px
- Reuse existing components from Section 4 before creating new ones

### Don'ts

- Don't introduce colors outside this palette — extend the design tokens first
- Don't introduce additional font families beyond cfont and Poppins
- Don't use arbitrary spacing values — stick to multiples of 5px
- Don't create custom box-shadow values outside the system tokens
- Don't use arbitrary border-radius values — pick from the defined scale
- Don't duplicate component patterns — check Section 4 first
- Don't use backdrop-blur or blur effects

### Anti-Patterns (detected from codebase)

- No blur or backdrop-blur effects
- No zebra striping on tables/lists


---

## 9. Responsive Behavior

| Name | Value | Source |
|---|---|---|
| xs | 428px | css |
| xs | 480px | css |
| sm | 639px | css |
| md | 750px | css |
| md | 767px | css |
| md | 768px | css |
| lg | 769px | css |
| lg | 850px | css |
| lg | 892px | css |
| lg | 920px | css |
| lg | 960px | css |
| lg | 964px | css |
| lg | 992px | css |
| lg | 1023px | css |
| lg | 1024px | css |
| xl | 1100px | css |
| xl | 1179px | css |
| xl | 1180px | css |
| xl | 1200px | css |
| xl | 1280px | css |
| 2xl | 1299px | css |
| 2xl | 1300px | css |
| 2xl | 1340px | css |
| 2xl | 1350px | css |
| 2xl | 1400px | css |
| 2xl | 1401px | css |
| 2xl | 1920px | css |

**Approach:** Use `@media (min-width: ...)` queries matching the breakpoints above.


---

## 10. Agent Prompt Guide

Use these as starting points when building new UI:

### Build a Card

```
Background: #fef0f0
Border: 1px solid #303133
Radius: 15px
Padding: 20px
Font: cfont
Use shadow tokens from Section 6.
```

### Build a Button

```
Primary: bg var(--accent), text white
Ghost: bg transparent, border #303133
Padding: 10px 20px
Radius: 15px
Hover: opacity 0.9 or lighter shade
Focus: ring with var(--accent)
```

### Build a Page Layout

```
Background: #ffffff
Max-width: 960px, centered
Grid: 5px base
Responsive: mobile-first, breakpoints from Section 9
```

### Build a Stats Card

```
Surface: #fef0f0
Label: #555555 (muted, 12px, uppercase)
Value: #222222 (primary, 24-32px, bold)
Status: use success/warning/danger from Section 2
```

### Build a Form

```
Input bg: #ffffff
Input border: 1px solid #303133
Focus: border-color var(--accent)
Label: #555555 12px
Spacing: 20px between fields
Radius: 15px
```

### General Component

```
1. Read DESIGN.md Sections 2-6 for tokens
2. Colors: only from palette
3. Font: cfont, type scale from Section 3
4. Spacing: 5px grid
5. Components: match patterns from Section 4
6. Elevation: shadow tokens
```

## Visual Guide — Screenshots (VISUAL_GUIDE.md)

# uhomes — Visual Guide

> Master visual reference. Study every screenshot carefully before implementing any UI.
> Match colors, layout, typography, spacing, and motion states exactly.

## Scroll Journey

The page has cinematic scroll animations. Each screenshot below shows the exact visual state at that scroll depth.
**Replicate these transitions precisely** — the design changes dramatically as you scroll.

### Hero — Above the fold

*Scroll position: 0px of 7948px total*

![Hero — Above the fold](../screens/scroll/scroll-000.png)

### 17% scroll depth

*Scroll position: 1198px of 7948px total*

![17% scroll depth](../screens/scroll/scroll-017.png)

### 33% scroll depth

*Scroll position: 2326px of 7948px total*

![33% scroll depth](../screens/scroll/scroll-033.png)

### 50% scroll depth

*Scroll position: 3524px of 7948px total*

![50% scroll depth](../screens/scroll/scroll-050.png)

### 67% scroll depth

*Scroll position: 4722px of 7948px total*

![67% scroll depth](../screens/scroll/scroll-067.png)

### 83% scroll depth

*Scroll position: 5850px of 7948px total*

![83% scroll depth](../screens/scroll/scroll-083.png)

### Footer — End of page

*Scroll position: 7048px of 7948px total*

![Footer — End of page](../screens/scroll/scroll-100.png)

## Full Page Screenshots

### uhomes.com | Student Accommodation, Housing, Flats, Apartments for Rent

*URL: `https://uhomes.com`*

![uhomes.com | Student Accommodation, Housing, Flats, Apartments for Rent](../screens/pages/home.png)

## Section Screenshots

Clipped sections showing individual components in context.

### Section 1 — `[class*="section"]`

*1440×702px*

![Section 1](../screens/sections/home-section-1.png)

## Animations & Motion (ANIMATIONS.md)

# Animation Reference

> Cinematic motion design extracted from live DOM. Follow these specs exactly to recreate the experience.

## Motion Technology Stack

Pure CSS animations — no external animation libraries detected.

## Scroll Journey

The page is **7,948px** tall. Each frame below shows what the user sees at that scroll depth.

> **Use these screenshots to understand WHAT animates, WHEN it animates, and HOW it moves.**

### 0% — Top / Hero
Scroll position: 0px

![Scroll 0%](../screens/scroll/scroll-000.png)

### 17% — Opening Section
Scroll position: 1,198px

![Scroll 17%](../screens/scroll/scroll-017.png)

### 33% — First Feature Section
Scroll position: 2,326px

![Scroll 33%](../screens/scroll/scroll-033.png)

### 50% — Mid-Page
Scroll position: 3,524px

![Scroll 50%](../screens/scroll/scroll-050.png)

### 67% — Lower Content
Scroll position: 4,722px

![Scroll 67%](../screens/scroll/scroll-067.png)

### 83% — Near Footer
Scroll position: 5,850px

![Scroll 83%](../screens/scroll/scroll-083.png)

### 100% — Bottom / Footer
Scroll position: 7,048px

![Scroll 100%](../screens/scroll/scroll-100.png)

## Motion Tokens (CSS Variables)

### Duration Tokens

```css
--el-transition-duration: .3s;
--el-transition-duration-fast: .2s;
```

### Easing Tokens

```css
--el-transition-function-ease-in-out-bezier: cubic-bezier(.645,.045,.355,1);
--el-transition-function-fast-bezier: cubic-bezier(.23,1,.32,1);
```

### Other Tokens

```css
--el-transition-md-fade: transform .3s cubic-bezier(.23,1,.32,1),opacity .3s cubic-bezier(.23,1,.32,1);
--el-transition-fade: opacity .3s cubic-bezier(.23,1,.32,1);
--el-transition-box-shadow: box-shadow .2s cubic-bezier(.645,.045,.355,1);
--el-transition-border: border-color .2s cubic-bezier(.645,.045,.355,1);
--el-transition-fade-linear: opacity .2s linear;
--el-transition-color: color .2s cubic-bezier(.645,.045,.355,1);
--el-transition-all: all .3s cubic-bezier(.645,.045,.355,1);
```

## How to Recreate This Motion Design

### Step 2 — Scroll-Reveal Pattern

Elements that animate into view follow this pattern:

```css
/* Initial hidden state */
.reveal {
  opacity: 0;
  transform: translateY(40px);
  transition: opacity .3s cubic-bezier(.645,.045,.355,1),
              transform .3s cubic-bezier(.645,.045,.355,1);
}
.reveal.visible {
  opacity: 1;
  transform: translateY(0);
}
```

### Step 3 — Key Motion Principles

- **Duration scale:** `.3s` · `.2s` — use these values, never invent new durations
- **Always add** `@media (prefers-reduced-motion: reduce) { * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }`

### Step 4 — Scroll Journey Reference

Match what happens at each scroll position:

- **0%** (`0px`) → `screens/scroll/scroll-000.png`
- **17%** (`1198px`) → `screens/scroll/scroll-017.png`
- **33%** (`2326px`) → `screens/scroll/scroll-033.png`
- **50%** (`3524px`) → `screens/scroll/scroll-050.png`
- **67%** (`4722px`) → `screens/scroll/scroll-067.png`
- **83%** (`5850px`) → `screens/scroll/scroll-083.png`
- **100%** (`7048px`) → `screens/scroll/scroll-100.png`

## Layout & Grid (LAYOUT.md)

# Layout Reference

> Auto-extracted from live DOM. Use this to understand how the site is structured spatially.

## Spacing System

**Base grid:** 5px

**Scale:** `5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80` px

| Spacing | Semantic Use |
|---------|-------------|
| 5px | Tight — within a component |
| 10px | Medium — between sibling items |
| 20px | Wide — between sections |
| 40px | Vast — major section breaks |

## Flex Layouts

| Element | Direction | Justify | Align | Gap | Children |
|---------|-----------|---------|-------|-----|----------|
| `div.isMaxWidth1300.header-container` | row | space-between | center | — | 4 |
| `div.copyright-container.homepage-copyright-pd` | row | space-between | center | — | 3 |
| `div.r-container.newui-r-container` | row | — | center | — | 5 |
| `div.list-container` | row | space-between | — | — | 5 |
| `div.book-step-container.flex-c` | row | center | center | — | 1 |
| `div.get-in-touch-container` | row | space-between | center | 80px | 2 |
| `div.students-say-container` | row | space-between | center | 60px | 2 |
| `div.features-grid` | column | — | — | 20px | 2 |
| `div.steps-wrapper` | row | center | stretch | — | 3 |
| `div.features-row` | row | center | — | 20px | 2 |
| `div.features-row` | row | center | — | 20px | 2 |
| `div.collapse-header` | row | space-between | center | — | 2 |
| `div.collapse-header` | row | space-between | center | — | 2 |
| `div.collapse-header` | row | space-between | center | — | 2 |
| `div.collapse-header` | row | space-between | center | — | 2 |

## Grid Layouts

| Element | Template Columns | Gap | Children |
|---------|-----------------|-----|----------|
| `div.cities-grid` | `200px 200px 200px 200px 200px 200px` | 20px | 12 |
| `div.property-grid` | `310px 310px 310px 310px` | 20px | 8 |

## Structural Containers

### `<header>` (`header.header-container-box.header-absolute-container-box`)

```
display:          block
children:         1
```

## Layout Rules

- **Container max-width:** `1400px` — always center with `margin: auto`
- Primary layout system: **Flexbox**
- Secondary layout system: **CSS Grid** (used for card grids and multi-column layouts)
- Every spacing value must be a multiple of **5px**
- Never use arbitrary margin/padding values outside the spacing scale

## Component Patterns (COMPONENTS.md)

# Component Reference

> Repeated DOM patterns detected by structural analysis. Each component appeared 3+ times.

## Detected Components

| Component | Category | Instances | Key Classes |
|-----------|----------|-----------|-------------|
| **City Tab** | nav-item | 22× | `.city-tab` |
| **Cv House Card** | card | 16× | `.cv-house-card`, `.home-item`, `.must-stay-mode` |
| **Home Item Wrap** | card | 16× | `.home-item-wrap` |
| **Home Item Inner** | card | 16× | `.home-item-inner` |
| **Aspect Ratio 291 160** | unknown | 16× | `.aspect-ratio-291-160`, `.img-box` |
| **City Item** | card | 12× | `.city-item` |
| **City Link** | unknown | 12× | `.city-link` |
| **City Image Wrapper** | unknown | 12× | `.city-image-wrapper` |
| **City Image** | unknown | 12× | `.city-image` |
| **City Overlay** | unknown | 12× | `.city-overlay` |
| **City Name** | unknown | 12× | `.city-name` |
| **Small Img** | unknown | 7× | `.small-img` |
| **Desc** | unknown | 3× | `.desc` |
| **House Info Item** | card | 3× | `.house-info-item` |
| **Icon** | unknown | 3× | `.icon` |
| **Svg Icon** | unknown | 3× | `.svg-icon` |
| **Div** | unknown | 3× |  |
| **House Info Item Header** | card | 3× | `.house-info-item-header` |
| **House Info Item Header Title** | card | 3× | `.house-info-item-header-title` |
| **House Info Item Desc** | card | 3× | `.house-info-item-desc` |

## Cards

### Cv House Card

**Instances found:** 16

**CSS classes:** `.cv-house-card` `.home-item` `.must-stay-mode`

**HTML structure:**

```html
<a class="home-item cv-house-card must-stay-mode" href="/uk/london/detail-apartments-1502973" data-house-id="1502973" data-module="home-must-stay" data-v-17c149b3="" data-v-6ca743f6=""><div class="home-item-wrap" data-v-6ca743f6=""><div class="home-item-inner" data-v-6ca743f6=""><div class="img-box aspect-ratio-291-160" data-v-6ca743f6=""><img alt="Vita Student Lewisham Exchange" width="291" height="160" data-v-6ca743f6=""></div><div class="info-box" data-v-6ca743f6=""><p class="ellipsis title" data-v-6ca743f6="">Vita Student Lewisham Exchange</p><p class="address word-text" data-v-6ca743f6=""
```

**Base styles (from design tokens):**

```css
.cv-house-card {
  background: #fef0f0;
  border: 1px solid #303133;
  border-radius: 15px;
  padding: 10px;
}```

### Home Item Wrap

**Instances found:** 16

**CSS classes:** `.home-item-wrap`

**HTML structure:**

```html
<div class="home-item-wrap" data-v-6ca743f6=""><div class="home-item-inner" data-v-6ca743f6=""><div class="img-box aspect-ratio-291-160" data-v-6ca743f6=""><img alt="Vita Student Lewisham Exchange" width="291" height="160" data-v-6ca743f6=""></div><div class="info-box" data-v-6ca743f6=""><p class="ellipsis title" data-v-6ca743f6="">Vita Student Lewisham Exchange</p><p class="address word-text" data-v-6ca743f6="">Exchange Point, Loampit Vale, London SE1…</p><p class="options word-text" data-v-6ca743f6=""></p><div class="house-distance" data-v-6ca743f6="" data-v-53ec8903=""><p class="name" data-
```

**Base styles (from design tokens):**

```css
.home-item-wrap {
  background: #fef0f0;
  border: 1px solid #303133;
  border-radius: 15px;
  padding: 10px;
}```

### Home Item Inner

**Instances found:** 16

**CSS classes:** `.home-item-inner`

**HTML structure:**

```html
<div class="home-item-inner" data-v-6ca743f6=""><div class="img-box aspect-ratio-291-160" data-v-6ca743f6=""><img alt="Vita Student Lewisham Exchange" width="291" height="160" data-v-6ca743f6=""></div><div class="info-box" data-v-6ca743f6=""><p class="ellipsis title" data-v-6ca743f6="">Vita Student Lewisham Exchange</p><p class="address word-text" data-v-6ca743f6="">Exchange Point, Loampit Vale, London SE1…</p><p class="options word-text" data-v-6ca743f6=""></p><div class="house-distance" data-v-6ca743f6="" data-v-53ec8903=""><p class="name" data-v-53ec8903=""><span>1.22 mi</span> walk from Go
```

**Base styles (from design tokens):**

```css
.home-item-inner {
  background: #fef0f0;
  border: 1px solid #303133;
  border-radius: 15px;
  padding: 10px;
}```

### City Item

**Instances found:** 12

**CSS classes:** `.city-item`

**HTML structure:**

```html
<div class="city-item" data-v-d742d2a9=""><a href="/uk/london" class="city-link" data-v-d742d2a9=""><div class="city-image-wrapper" data-v-d742d2a9=""><img alt="London" class="city-image" data-v-d742d2a9=""><div class="city-overlay" data-v-d742d2a9=""></div><h3 class="city-name" data-v-d742d2a9="">London</h3></div></a></div>
```

**Base styles (from design tokens):**

```css
.city-item {
  background: #fef0f0;
  border: 1px solid #303133;
  border-radius: 15px;
  padding: 10px;
}```

### House Info Item

**Instances found:** 3

**CSS classes:** `.house-info-item`

**HTML structure:**

```html
<div class="house-info-item" data-v-7646928c=""><p class="icon" data-v-7646928c=""><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 48 48" class="svg-icon" data-v-7646928c="" data-v-9b8bc4d6=""><g stroke-width="2"><rect width="6" height="6" x="39" y="34" stroke="#180C32" stroke-linejoin="round" rx="3"></rect><path fill="#B6A6EF" fill-rule="evenodd" stroke="#B6A6EF" stroke-linejoin="round" d="M8 20h32a5 5 0 0 1 5 5v11H8V20Z" clip-rule="evenodd"></path><rect width="6" height="32" x="2" y="8" stroke="#180C32" stroke-linejoin="round" rx="3"></rect><path fill="#15CC7A" stroke="#15CC
```

**Base styles (from design tokens):**

```css
.house-info-item {
  background: #fef0f0;
  border: 1px solid #303133;
  border-radius: 15px;
  padding: 10px;
}```

### House Info Item Header

**Instances found:** 3

**CSS classes:** `.house-info-item-header`

**HTML structure:**

```html
<div class="house-info-item-header" data-v-7646928c=""><p class="house-info-item-header-title" data-v-7646928c="">2M+ Beds</p><!----></div>
```

**Base styles (from design tokens):**

```css
.house-info-item-header {
  background: #fef0f0;
  border: 1px solid #303133;
  border-radius: 15px;
  padding: 10px;
}```

### House Info Item Header Title

**Instances found:** 3

**CSS classes:** `.house-info-item-header-title`

**HTML structure:**

```html
<p class="house-info-item-header-title" data-v-7646928c="">2M+ Beds</p>
```

**Base styles (from design tokens):**

```css
.house-info-item-header-title {
  background: #fef0f0;
  border: 1px solid #303133;
  border-radius: 15px;
  padding: 10px;
}```

### House Info Item Desc

**Instances found:** 3

**CSS classes:** `.house-info-item-desc`

**HTML structure:**

```html
<p class="house-info-item-desc" data-v-7646928c="">Book your perfect accommodation from our abundant properties</p>
```

**Base styles (from design tokens):**

```css
.house-info-item-desc {
  background: #fef0f0;
  border: 1px solid #303133;
  border-radius: 15px;
  padding: 10px;
}```

## Navigation Items

### City Tab

**Instances found:** 22

**CSS classes:** `.city-tab`

**HTML structure:**

```html
<div class="city-tab" data-v-17c149b3="">Sydney</div>
```

**Base styles (from design tokens):**

```css
.city-tab {
  padding: 5px 10px;
  cursor: pointer;
}```

## Other Components

### Aspect Ratio 291 160

**Instances found:** 16

**CSS classes:** `.aspect-ratio-291-160` `.img-box`

**HTML structure:**

```html
<div class="img-box aspect-ratio-291-160" data-v-6ca743f6=""><img alt="Vita Student Lewisham Exchange" width="291" height="160" data-v-6ca743f6=""></div>
```

**Base styles (from design tokens):**

```css
.aspect-ratio-291-160 {
  background: #fef0f0;
  padding: 5px;
}```

### City Link

**Instances found:** 12

**CSS classes:** `.city-link`

**HTML structure:**

```html
<a href="/uk/london" class="city-link" data-v-d742d2a9=""><div class="city-image-wrapper" data-v-d742d2a9=""><img alt="London" class="city-image" data-v-d742d2a9=""><div class="city-overlay" data-v-d742d2a9=""></div><h3 class="city-name" data-v-d742d2a9="">London</h3></div></a>
```

**Base styles (from design tokens):**

```css
.city-link {
  background: #fef0f0;
  padding: 5px;
}```

### City Image Wrapper

**Instances found:** 12

**CSS classes:** `.city-image-wrapper`

**HTML structure:**

```html
<div class="city-image-wrapper" data-v-d742d2a9=""><img alt="London" class="city-image" data-v-d742d2a9=""><div class="city-overlay" data-v-d742d2a9=""></div><h3 class="city-name" data-v-d742d2a9="">London</h3></div>
```

**Base styles (from design tokens):**

```css
.city-image-wrapper {
  background: #fef0f0;
  padding: 5px;
}```

### City Image

**Instances found:** 12

**CSS classes:** `.city-image`

**HTML structure:**

```html
<img alt="London" class="city-image" data-v-d742d2a9="">
```

**Base styles (from design tokens):**

```css
.city-image {
  background: #fef0f0;
  padding: 5px;
}```

### City Overlay

**Instances found:** 12

**CSS classes:** `.city-overlay`

**HTML structure:**

```html
<div class="city-overlay" data-v-d742d2a9=""></div>
```

**Base styles (from design tokens):**

```css
.city-overlay {
  background: #fef0f0;
  padding: 5px;
}```

### City Name

**Instances found:** 12

**CSS classes:** `.city-name`

**HTML structure:**

```html
<h3 class="city-name" data-v-d742d2a9="">London</h3>
```

**Base styles (from design tokens):**

```css
.city-name {
  background: #fef0f0;
  padding: 5px;
}```

### Small Img

**Instances found:** 7

**CSS classes:** `.small-img`

**HTML structure:**

```html
<div class="small-img" style="width:196px;height:22px;background-size:232px 263.5px;background-position:-0px -22px;" data-v-90afdd49="" data-v-e3d16c73=""></div>
```

**Base styles (from design tokens):**

```css
.small-img {
  background: #fef0f0;
  padding: 5px;
}```

### Desc

**Instances found:** 3

**CSS classes:** `.desc`

**HTML structure:**

```html
<p class="desc" data-v-8a9ab0b8=""><i class="mfont" data-v-8a9ab0b8=""></i> Verified Listings</p>
```

**Base styles (from design tokens):**

```css
.desc {
  background: #fef0f0;
  padding: 5px;
}```

### Icon

**Instances found:** 3

**CSS classes:** `.icon`

**HTML structure:**

```html
<p class="icon" data-v-7646928c=""><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 48 48" class="svg-icon" data-v-7646928c="" data-v-9b8bc4d6=""><g stroke-width="2"><rect width="6" height="6" x="39" y="34" stroke="#180C32" stroke-linejoin="round" rx="3"></rect><path fill="#B6A6EF" fill-rule="evenodd" stroke="#B6A6EF" stroke-linejoin="round" d="M8 20h32a5 5 0 0 1 5 5v11H8V20Z" clip-rule="evenodd"></path><rect width="6" height="32" x="2" y="8" stroke="#180C32" stroke-linejoin="round" rx="3"></rect><path fill="#15CC7A" stroke="#15CC7A" d="M10 16a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v2H1
```

**Base styles (from design tokens):**

```css
.icon {
  background: #fef0f0;
  padding: 5px;
}```

### Svg Icon

**Instances found:** 3

**CSS classes:** `.svg-icon`

**HTML structure:**

```html
<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 48 48" class="svg-icon" data-v-7646928c="" data-v-9b8bc4d6=""><g stroke-width="2"><rect width="6" height="6" x="39" y="34" stroke="#180C32" stroke-linejoin="round" rx="3"></rect><path fill="#B6A6EF" fill-rule="evenodd" stroke="#B6A6EF" stroke-linejoin="round" d="M8 20h32a5 5 0 0 1 5 5v11H8V20Z" clip-rule="evenodd"></path><rect width="6" height="32" x="2" y="8" stroke="#180C32" stroke-linejoin="round" rx="3"></rect><path fill="#15CC7A" stroke="#15CC7A" d="M10 16a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v2H10v-2Z"></path><path stroke="#180C32
```

**Base styles (from design tokens):**

```css
.svg-icon {
  background: #fef0f0;
  padding: 5px;
}```

### Div

**Instances found:** 3

**HTML structure:**

```html
<div class="" data-v-7646928c=""><div class="house-info-item-header" data-v-7646928c=""><p class="house-info-item-header-title" data-v-7646928c="">2M+ Beds</p><!----></div><p class="house-info-item-desc" data-v-7646928c="">Book your perfect accommodation from our…</p><!----></div>
```

**Base styles (from design tokens):**

```css
.div {
  background: #fef0f0;
  padding: 5px;
}```

## Component Rules

- Match class names exactly from the patterns above
- Each component instance must be visually identical to others of its type
- Do not add extra wrappers or change the DOM structure
- Use `#303133` for all dividers within components

## Interactions & States (INTERACTIONS.md)

# Interaction Reference

> Micro-interactions extracted from live DOM. Recreate these exactly for authentic feel.

## Coverage

| Component Type | Count | States Captured |
|----------------|-------|----------------|
| Button | 2 | default, hover, focus |
| Link | 3 | default, hover, focus |
| Input | 2 | default, hover, focus |

## Transition System

These transition declarations were extracted from interactive elements:

```css
transition: 0.3s;
transition: all;
```

Apply these to all interactive elements. Never invent new durations or easings.

## Button Interactions

### Button 1 — ``

**States:**

- Default: `../screens/states/button-1-default.png`
- Hover: `../screens/states/button-1-hover.png`
- Focus: `../screens/states/button-1-focus.png`

**On hover:**

```css
/* background-color: rgba(0, 0, 0, 0) → */ background-color: rgb(34, 34, 34);
/* color: rgb(34, 34, 34) → */ color: rgb(255, 255, 255);
/* outline: rgb(34, 34, 34) none 3px → */ outline: rgb(255, 255, 255) none 3px;
/* outline-color: rgb(34, 34, 34) → */ outline-color: rgb(255, 255, 255);
```

**On focus:**

```css
/* outline: rgb(34, 34, 34) none 3px → */ outline: rgb(34, 34, 34) none 0px;
```

**Transition:** `0.3s`

### Button 2 — ``

**States:**

- Default: `../screens/states/button-2-default.png`
- Hover: `../screens/states/button-2-hover.png`
- Focus: `../screens/states/button-2-focus.png`

**On hover:**

```css
/* color: rgb(250, 215, 183) → */ color: rgb(34, 34, 34);
/* border-color: rgb(250, 215, 183) → */ border-color: rgb(34, 34, 34);
/* outline: rgb(250, 215, 183) none 3px → */ outline: rgb(34, 34, 34) none 3px;
/* outline-color: rgb(250, 215, 183) → */ outline-color: rgb(34, 34, 34);
```

**On focus:**

```css
/* color: rgb(250, 215, 183) → */ color: rgb(34, 34, 34);
/* border-color: rgb(250, 215, 183) → */ border-color: rgb(34, 34, 34);
/* outline: rgb(250, 215, 183) none 3px → */ outline: rgb(34, 34, 34) none 0px;
/* outline-color: rgb(250, 215, 183) → */ outline-color: rgb(34, 34, 34);
```

**Transition:** `0.3s`

## Link Interactions

### Link 1 — ``

**States:**

- Default: `../screens/states/link-1-default.png`
- Hover: `../screens/states/link-1-hover.png`
- Focus: `../screens/states/link-1-focus.png`

**On focus:**

```css
/* outline: rgb(255, 90, 95) none 3px → */ outline: rgb(255, 90, 95) none 0px;
```

**Transition:** `all`

### Link 2 — ``

**States:**

- Default: `../screens/states/link-2-default.png`
- Hover: `../screens/states/link-2-hover.png`
- Focus: `../screens/states/link-2-focus.png`

**On hover:**

```css
/* background-color: rgba(0, 0, 0, 0) → */ background-color: rgb(245, 245, 245);
```

**On focus:**

```css
/* outline: rgb(66, 198, 80) none 3px → */ outline: rgb(66, 198, 80) none 0px;
```

**Transition:** `all`

### Link 3 — ``

**States:**

- Default: `../screens/states/link-3-default.png`
- Hover: `../screens/states/link-3-hover.png`
- Focus: `../screens/states/link-3-focus.png`

**On hover:**

```css
/* background-color: rgba(0, 0, 0, 0) → */ background-color: rgb(245, 245, 245);
```

**On focus:**

```css
/* outline: rgb(255, 90, 95) none 3px → */ outline: rgb(255, 90, 95) none 0px;
```

**Transition:** `all`

## Input Interactions

### Input 1 — `Search City | University | Neighborhood `

**States:**

- Default: `../screens/states/input-1-default.png`
- Hover: `../screens/states/input-1-hover.png`
- Focus: `../screens/states/input-1-focus.png`

**On focus:**

```css
/* outline: rgb(34, 34, 34) none 3px → */ outline: rgb(34, 34, 34) none 0px;
```

**Transition:** `all`

### Input 2 — `Search City | University | Neighborhood `

**States:**

- Default: `../screens/states/input-2-default.png`
- Hover: `../screens/states/input-2-hover.png`
- Focus: `../screens/states/input-2-focus.png`

**On hover:**

```css
/* color: rgb(34, 34, 34) → */ color: rgb(102, 102, 102);
/* border-color: rgb(34, 34, 34) → */ border-color: rgb(102, 102, 102);
/* outline: rgb(34, 34, 34) none 3px → */ outline: rgb(102, 102, 102) none 3px;
/* outline-color: rgb(34, 34, 34) → */ outline-color: rgb(102, 102, 102);
```

**On focus:**

```css
/* color: rgb(34, 34, 34) → */ color: rgb(102, 102, 102);
/* border-color: rgb(34, 34, 34) → */ border-color: rgb(102, 102, 102);
/* outline: rgb(34, 34, 34) none 3px → */ outline: rgb(102, 102, 102) none 3px;
/* outline-color: rgb(34, 34, 34) → */ outline-color: rgb(102, 102, 102);
```

**Transition:** `all`

## Interaction Rules

- Hover effects include **color transitions** — use the extracted values, not approximations
- Focus states use **outline** (not box-shadow) — always match the extracted focus ring
- Transition durations in use: `0.3s`
- Always respect `prefers-reduced-motion` — set all transitions to `0s` when enabled

## Design Tokens — JSON Files

### tokens/colors.json
```json
{
  "$schema": "https://design-tokens.github.io/community-group/format/",
  "core": {
    "text-primary": {
      "value": "#222222",
      "role": "text-primary"
    },
    "background": {
      "value": "#ffffff",
      "role": "background",
      "name": "el-color-white"
    },
    "text-muted": {
      "value": "#555555",
      "role": "text-muted"
    },
    "border": {
      "value": "#303133",
      "role": "border",
      "name": "el-text-color-primary"
    },
    "surface": {
      "value": "#fef0f0",
      "role": "surface",
      "name": "el-color-danger-light-9"
    }
  },
  "status": {
    "danger": {
      "value": "#ff5a5f",
      "role": "danger"
    },
    "warning": {
      "value": "#faecd8",
      "role": "warning",
      "name": "el-color-warning-light-8"
    },
    "success": {
      "value": "#67c23a",
      "role": "success",
      "name": "el-color-success"
    }
  },
  "extended": {
    "el-color-primary-light-9": {
      "value": "#e7f2f5",
      "role": "info",
      "name": "el-color-primary-light-9"
    },
    "el-text-color-regular": {
      "value": "#666666",
      "role": "unknown",
      "name": "el-text-color-regular"
    },
    "color-0c7094": {
      "value": "#0c7094",
      "role": "unknown"
    },
    "el-color-info": {
      "value": "#999999",
      "role": "unknown",
      "name": "el-color-info"
    },
    "el-color-info-light-5": {
      "value": "#cccccc",
      "role": "unknown",
      "name": "el-color-info-light-5"
    },
    "el-color-black": {
      "value": "#000000",
      "role": "unknown",
      "name": "el-color-black"
    },
    "el-color-info-light-7": {
      "value": "#dedfe0",
      "role": "unknown",
      "name": "el-color-info-light-7"
    },
    "el-color-danger": {
      "value": "#f56c6c",
      "role": "unknown",
      "name": "el-color-danger"
    },
    "color-fad7b7": {
      "value": "#fad7b7",
      "role": "unknown"
    },
    "el-color-warning": {
      "value": "#e6a23c",
      "role": "unknown",
      "name": "el-color-warning"
    },
    "el-color-success-light-9": {
      "value": "#f0f9eb",
      "role": "unknown",
      "name": "el-color-success-light-9"
    },
    "color-963434": {
      "value": "#963434",
      "role": "unknown"
    }
  },
  "meta": {
    "theme": "light",
    "extracted": "2026-07-05"
  }
}
```

### tokens/spacing.json
```json
{
  "base": {
    "value": "5px",
    "description": "Grid unit — all spacing must be multiples of this"
  },
  "unit": "px",
  "scale": {
    "xs": {
      "value": "5px",
      "px": 5
    },
    "sm": {
      "value": "10px",
      "px": 10
    },
    "md": {
      "value": "15px",
      "px": 15
    },
    "lg": {
      "value": "20px",
      "px": 20
    },
    "xl": {
      "value": "25px",
      "px": 25
    },
    "2xl": {
      "value": "30px",
      "px": 30
    },
    "3xl": {
      "value": "35px",
      "px": 35
    },
    "4xl": {
      "value": "40px",
      "px": 40
    },
    "5xl": {
      "value": "45px",
      "px": 45
    },
    "6xl": {
      "value": "50px",
      "px": 50
    }
  },
  "multipliers": {
    "1x": {
      "value": "5px",
      "raw": 5
    },
    "2x": {
      "value": "10px",
      "raw": 10
    },
    "3x": {
      "value": "15px",
      "raw": 15
    },
    "4x": {
      "value": "20px",
      "raw": 20
    },
    "5x": {
      "value": "25px",
      "raw": 25
    },
    "6x": {
      "value": "30px",
      "raw": 30
    },
    "7x": {
      "value": "35px",
      "raw": 35
    },
    "8x": {
      "value": "40px",
      "raw": 40
    },
    "9x": {
      "value": "45px",
      "raw": 45
    },
    "10x": {
      "value": "50px",
      "raw": 50
    },
    "11x": {
      "value": "55px",
      "raw": 55
    },
    "12x": {
      "value": "60px",
      "raw": 60
    },
    "13x": {
      "value": "65px",
      "raw": 65
    },
    "14x": {
      "value": "70px",
      "raw": 70
    },
    "15x": {
      "value": "75px",
      "raw": 75
    },
    "16x": {
      "value": "80px",
      "raw": 80
    }
  },
  "meta": {
    "totalValues": 15,
    "min": 5,
    "max": 80
  }
}
```

### tokens/typography.json
```json
{
  "families": [
    "cfont",
    "Poppins"
  ],
  "scale": {
    "heading-1": {
      "fontFamily": "cfont",
      "fontSize": "160px",
      "fontWeight": "700",
      "lineHeight": null,
      "source": "css"
    },
    "heading-2": {
      "fontFamily": "cfont",
      "fontSize": "150px",
      "fontWeight": "700",
      "lineHeight": null,
      "source": "css"
    },
    "heading-3": {
      "fontFamily": "cfont",
      "fontSize": "146px",
      "fontWeight": "700",
      "lineHeight": null,
      "source": "css"
    },
    "body": {
      "fontFamily": "Poppins",
      "fontSize": "12px",
      "fontWeight": "400",
      "lineHeight": null,
      "source": "css"
    },
    "caption": {
      "fontFamily": "Poppins",
      "fontSize": "14px",
      "fontWeight": "400",
      "lineHeight": null,
      "source": "css"
    }
  },
  "fontFaces": [
    {
      "family": "Poppins",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/poppins/Poppins-Regular.woff2",
      "format": "woff2",
      "weight": "400"
    },
    {
      "family": "Poppins",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/poppins/Poppins-Regular.woff",
      "format": "woff2",
      "weight": "400"
    },
    {
      "family": "Poppins",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/poppins/Poppins-Regular.ttf",
      "format": "truetype",
      "weight": "400"
    },
    {
      "family": "Poppins",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/poppins/Poppins-Medium.woff2",
      "format": "woff2",
      "weight": "500"
    },
    {
      "family": "Poppins",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/poppins/Poppins-Medium.woff",
      "format": "woff2",
      "weight": "500"
    },
    {
      "family": "Poppins",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/poppins/Poppins-Medium.ttf",
      "format": "truetype",
      "weight": "500"
    },
    {
      "family": "Poppins",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/poppins/Poppins-SemiBold.woff2",
      "format": "woff2",
      "weight": "600"
    },
    {
      "family": "Poppins",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/poppins/Poppins-SemiBold.woff",
      "format": "woff2",
      "weight": "600"
    },
    {
      "family": "Poppins",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/poppins/Poppins-SemiBold.ttf",
      "format": "truetype",
      "weight": "600"
    },
    {
      "family": "cfont",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/pc_community_iconfont/iconfont.woff2",
      "format": "woff2",
      "weight": "400"
    },
    {
      "family": "cfont",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/pc_community_iconfont/iconfont.woff",
      "format": "woff2",
      "weight": "400"
    },
    {
      "family": "cfont",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/pc_community_iconfont/iconfont.ttf",
      "format": "truetype",
      "weight": "400"
    },
    {
      "family": "swiper-icons",
      "src": "data:application/font-woff;charset=utf-8;base64,\\ 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",
      "format": "truetype",
      "weight": "400"
    },
    {
      "family": "iconfont",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/iconfont/iconfont.woff2?t=1767669038123",
      "format": "truetype",
      "weight": "400"
    },
    {
      "family": "iconfont",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/iconfont/iconfont.woff?t=1767669038123",
      "format": "truetype",
      "weight": "400"
    },
    {
      "family": "iconfont",
      "src": "https://img.uhzcdn.com/static/wxapp/pc/font/iconfont/iconfont.ttf?t=1767669038123",
      "format": "truetype",
      "weight": "400"
    },
    {
      "family": "Poppins",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/Poppins-Regular.c33d1fd.woff2",
      "format": "woff2",
      "weight": "400"
    },
    {
      "family": "Poppins",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/Poppins-Regular.3320a2f.woff",
      "format": "woff",
      "weight": "400"
    },
    {
      "family": "Poppins",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/Poppins-Regular.093ee89.ttf",
      "format": "truetype",
      "weight": "400"
    },
    {
      "family": "Poppins",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/Poppins-Medium.f2d6767.woff2",
      "format": "woff2",
      "weight": "500"
    },
    {
      "family": "Poppins",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/Poppins-Medium.b9856b9.woff",
      "format": "woff",
      "weight": "500"
    },
    {
      "family": "Poppins",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/Poppins-Medium.bf59c68.ttf",
      "format": "truetype",
      "weight": "500"
    },
    {
      "family": "Poppins",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/Poppins-SemiBold.b2079ef.woff2",
      "format": "woff2",
      "weight": "600"
    },
    {
      "family": "Poppins",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/Poppins-SemiBold.ebbf097.woff",
      "format": "woff",
      "weight": "600"
    },
    {
      "family": "Poppins",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/Poppins-SemiBold.6f1520d.ttf",
      "format": "truetype",
      "weight": "600"
    },
    {
      "family": "iconfont",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/iconfont.a68876d.woff",
      "format": "woff",
      "weight": "400"
    },
    {
      "family": "iconfont",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/iconfont.97d526f.ttf",
      "format": "truetype",
      "weight": "400"
    },
    {
      "family": "ufont",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/icomoon.2e64b20.woff",
      "format": "woff",
      "weight": "400"
    },
    {
      "family": "ufont",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/icomoon.7b85c19.ttf",
      "format": "truetype",
      "weight": "400"
    },
    {
      "family": "cfont",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/iconfont.ad8b7b9.woff",
      "format": "woff",
      "weight": "400"
    },
    {
      "family": "cfont",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/iconfont.6e28a01.ttf",
      "format": "truetype",
      "weight": "400"
    },
    {
      "family": "element-icons",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/element-icons.535877f.woff",
      "format": "woff",
      "weight": "400"
    },
    {
      "family": "element-icons",
      "src": "https://static.uhzcdn.com/pc2020/prod/fonts/element-icons.732389d.ttf",
      "format": "truetype",
      "weight": "400"
    }
  ],
  "rules": {
    "maxSizesPerScreen": 4,
    "headingWeightRange": "600-700",
    "bodyWeight": 400,
    "lineHeightBody": 1.5,
    "lineHeightHeading": 1.2
  }
}
```

## Bundled Fonts (fonts/)

The following font files are bundled in the `fonts/` directory:

- `fonts/cfont-Regular.ttf`
- `fonts/cfont-Regular.woff`
- `fonts/cfont-Regular.woff2`
- `fonts/element-icons-Regular.ttf`
- `fonts/element-icons-Regular.woff`
- `fonts/iconfont-Regular.ttf`
- `fonts/iconfont-Regular.woff`
- `fonts/iconfont-Regular.woff2`
- `fonts/Poppins-500.ttf`
- `fonts/Poppins-500.woff`
- `fonts/Poppins-500.woff2`
- `fonts/Poppins-600.ttf`
- `fonts/Poppins-600.woff`
- `fonts/Poppins-600.woff2`
- `fonts/Poppins-Black.ttf`
- `fonts/Poppins-Bold.ttf`
- `fonts/Poppins-ExtraBold.ttf`
- `fonts/Poppins-ExtraLight.ttf`
- `fonts/Poppins-Light.ttf`
- `fonts/Poppins-Medium.ttf`
- `fonts/Poppins-Regular.ttf`
- `fonts/Poppins-Regular.woff`
- `fonts/Poppins-Regular.woff2`
- `fonts/Poppins-SemiBold.ttf`
- `fonts/Poppins-Thin.ttf`
- `fonts/ufont-Regular.ttf`
- `fonts/ufont-Regular.woff`

Use these local font files in `@font-face` declarations instead of fetching from Google Fonts.

## Screenshots Inventory (screens/)

> Study all screenshots carefully before implementing any UI. Match every visual detail exactly.

### Scroll Journey (screens/scroll/)

*Cinematic scroll states — page visual at each scroll depth*

![scroll-000.png](screens/scroll/scroll-000.png)

![scroll-017.png](screens/scroll/scroll-017.png)

![scroll-033.png](screens/scroll/scroll-033.png)

![scroll-050.png](screens/scroll/scroll-050.png)

![scroll-067.png](screens/scroll/scroll-067.png)

![scroll-083.png](screens/scroll/scroll-083.png)

![scroll-100.png](screens/scroll/scroll-100.png)

### Full Page Screenshots (screens/pages/)

*Full-page screenshots of each crawled URL*

![home.png](screens/pages/home.png)

### Section Clips (screens/sections/)

*Clipped individual sections and components*

![home-section-1.png](screens/sections/home-section-1.png)

### Interaction States (screens/states/)

*Hover, focus, and active state captures*

![button-1-default.png](screens/states/button-1-default.png)

![button-1-focus.png](screens/states/button-1-focus.png)

![button-1-hover.png](screens/states/button-1-hover.png)

![button-2-default.png](screens/states/button-2-default.png)

![button-2-focus.png](screens/states/button-2-focus.png)

![button-2-hover.png](screens/states/button-2-hover.png)

![input-1-default.png](screens/states/input-1-default.png)

![input-1-focus.png](screens/states/input-1-focus.png)

![input-1-hover.png](screens/states/input-1-hover.png)

![input-2-default.png](screens/states/input-2-default.png)

![link-1-default.png](screens/states/link-1-default.png)

![link-1-focus.png](screens/states/link-1-focus.png)

![link-1-hover.png](screens/states/link-1-hover.png)

![link-2-default.png](screens/states/link-2-default.png)

![link-2-focus.png](screens/states/link-2-focus.png)

![link-2-hover.png](screens/states/link-2-hover.png)

![link-3-default.png](screens/states/link-3-default.png)

![link-3-focus.png](screens/states/link-3-focus.png)

![link-3-hover.png](screens/states/link-3-hover.png)

### Screenshot Index (screens/INDEX.md)

# Screenshot Index

## Scroll Journey

> Shows the cinematic state at each point of the page

| Scroll | Y Position | File |
|--------|-----------|------|
| 0% | 0px | `screens/scroll/scroll-000.png` |
| 17% | 1198px | `screens/scroll/scroll-017.png` |
| 33% | 2326px | `screens/scroll/scroll-033.png` |
| 50% | 3524px | `screens/scroll/scroll-050.png` |
| 67% | 4722px | `screens/scroll/scroll-067.png` |
| 83% | 5850px | `screens/scroll/scroll-083.png` |
| 100% | 7048px | `screens/scroll/scroll-100.png` |

## Pages

| Page | URL | File |
|------|-----|------|
| uhomes.com | Student Accommodation, Housing, Flats, Apartments for Rent | `https://uhomes.com` | `screens/pages/home.png` |

## Sections

| Page | Section | File |
|------|---------|------|
| home | #1 ([class*="section"]) | `screens/sections/home-section-1.png` |

## Homepage Screenshots (screenshots/)

![homepage.png](screenshots/homepage.png)


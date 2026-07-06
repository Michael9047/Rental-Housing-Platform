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

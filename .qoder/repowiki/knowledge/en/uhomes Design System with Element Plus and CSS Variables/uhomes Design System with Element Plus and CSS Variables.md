---
kind: frontend_style
name: uhomes Design System with Element Plus and CSS Variables
category: frontend_style
scope:
    - '**'
source_files:
    - frontend/src/assets/uhomes-theme.css
    - frontend/src/assets/uhomes-design-tokens.json
    - frontend/src/main.ts
    - frontend/package.json
    - uhomes-design/tokens/colors.json
    - uhomes-design/tokens/spacing.json
    - uhomes-design/tokens/typography.json
    - frontend/src/layouts/DefaultLayout.vue
    - frontend/src/components/PropertyCard.vue
---

The frontend styling system is a hybrid approach combining the Element Plus Vue component library with a custom uhomes design system built on CSS custom properties (variables). The architecture separates design tokens from implementation through multiple layers.

**Design Token Layer**: The `uhomes-design/` directory serves as the source of truth for design tokens, organized in JSON format following the Design Tokens Community Group schema. Key token files include `colors.json` (brand colors, status colors mapped to Element Plus variables), `spacing.json` (5px-based spacing scale from xs to 16x), and `typography.json` (font families including Poppins and cfont, font faces with CDN sources, and typography rules). A parallel `frontend/src/assets/uhomes-design-tokens.json` mirrors these tokens for direct frontend consumption.

**CSS Variable Implementation**: The generated `frontend/src/assets/uhomes-theme.css` file defines CSS custom properties under the `--uh-` namespace covering brand colors (`--uh-brand-primary: #FF5A5F`), typography scales (body, section headings, hero headings), layout constraints (`--uh-layout-max-width: 1280px`), responsive breakpoints, and reusable utility classes like `.uh-container`, `.uh-section`, and button variants (`.uh-btn--primary`, `.uh-btn--outline`).

**Component Library Integration**: Element Plus is the primary UI framework, registered globally in `main.ts` with Chinese locale (`zh-cn`) and all icons auto-registered. Components use Element Plus primitives (`el-button`, `el-tag`, `el-input`, `el-menu`, `el-container`) while custom styling via scoped CSS overrides default appearance using CSS variables like `var(--primary)`, `var(--bg-white)`, `var(--text-primary)`.

**Styling Conventions**: Components follow BEM-like naming with hyphenated class names (e.g., `.property-card`, `.card-image`, `.card-body`, `.card-footer`). Styling uses CSS custom properties extensively rather than hardcoded values, with consistent patterns for hover states, shadows, and transitions. The layout system relies on Element Plus's container components (`el-header`, `el-aside`, `el-main`) with custom scoped styles for the default layout structure.

**Responsive Strategy**: Breakpoints are defined as CSS variables (`--uh-breakpoint-sm: 576px`, etc.) but actual responsive implementations appear limited — most components rely on flexbox/grid layouts rather than explicit media queries. The design tokens reference mobile-specific padding values suggesting planned responsive support.
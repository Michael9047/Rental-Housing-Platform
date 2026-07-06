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


Pure data-and-assets package with no runtime code; it is consumed as a source-of-truth by skillui's reverse-engineering pipeline.

- `tokens/*.json` — machine-readable design tokens in the community-design-tokens schema (`$schema` header): `colors.json` groups core/status/extended swatches with Element UI aliases, `spacing.json` defines a 5px base grid plus named scale and multiplier tables, `typography.json` declares families, type scale entries, font-face sources, and typographic rules.
- `fonts/` — local copies of every weight/format (ttf/woff/woff2) for Poppins, cfont, iconfont, ufont, element-icons, and swiper-icons referenced from `tokens/typography.json`'s `fontFaces` list.
- `screens/` — visual evidence organized by category (`pages`, `sections`, `states`, `scroll`) with an `INDEX.md` index; `screenshots/homepage.png` is the hero image cited in `DESIGN.md`.
- `references/` — human-authored style guides (ANIMATIONS, COMPONENTS, DESIGN, INTERACTIONS, LAYOUT, VISUAL_GUIDE) that complement the auto-generated top-level `DESIGN.md`.
- Top-level `DESIGN.md` is the single entry point: auto-generated summary (header notes "Reverse-engineered via static analysis by skillui", lists counts of colors/fonts/components) that re-publishes token tables, CSS variable mappings, component patterns, breakpoints, elevation/shadow tokens, motion guidelines, and agent prompt templates.
- `CLAUDE.md`, `SKILL.md`, `uhomes-design.skill` are skill-ui metadata files that register this directory as a consumable design-skill for downstream code generation.

Dependency direction is one-way: consuming modules read these JSON assets and Markdown docs; nothing inside this module imports or depends on them.
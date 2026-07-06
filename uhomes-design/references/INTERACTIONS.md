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


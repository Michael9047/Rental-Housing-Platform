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


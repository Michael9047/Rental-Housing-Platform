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


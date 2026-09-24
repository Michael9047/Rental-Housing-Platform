<template>
  <main class="bm-page">
    <header class="bm-page__header">
      <div class="bm-page__heading">
        <span v-if="eyebrow" class="bm-page__eyebrow">{{ eyebrow }}</span>
        <h2>{{ title }}</h2>
        <p v-if="description">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="bm-page__actions"><slot name="actions" /></div>
    </header>

    <slot name="summary" />
    <section v-if="$slots.toolbar" class="bm-page__toolbar"><slot name="toolbar" /></section>
    <section class="bm-page__content"><slot /></section>
  </main>
</template>

<script setup lang="ts">
// BM 工作台页面统一外壳：约束标题、操作区、筛选区与内容区布局。
defineProps<{
  title: string
  description?: string
  eyebrow?: string
}>()
</script>

<style scoped>
.bm-page { align-self: stretch; width: 100%; max-width: 1240px; margin: 0 auto; padding: 28px 32px 40px; }
.bm-page__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
.bm-page__heading { min-width: 0; }
.bm-page__eyebrow { display: block; margin-bottom: 7px; color: var(--primary); font-size: 12px; font-weight: 700; letter-spacing: .12em; }
.bm-page__heading h2 { margin: 0; color: var(--text-primary); font-size: 24px; line-height: 1.25; letter-spacing: -.02em; }
.bm-page__heading p { max-width: 720px; margin: 8px 0 0; color: var(--text-secondary); font-size: 14px; line-height: 1.65; }
.bm-page__actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 10px; }
.bm-page__toolbar { margin-bottom: 16px; padding: 14px 16px; background: var(--bg-white); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow-sm); }
.bm-page__content { width: 100%; min-width: 0; }
.bm-page,
.bm-page :deep(*) {
  transition-duration: 0s !important;
  animation-duration: 0s !important;
}
@media (max-width: 768px) {
  .bm-page { padding: 20px 16px 32px; }
  .bm-page__header { flex-direction: column; gap: 14px; }
  .bm-page__actions { width: 100%; justify-content: flex-start; }
}
</style>

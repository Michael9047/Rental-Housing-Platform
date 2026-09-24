<template>
  <section class="summary-strip" aria-label="业务概览">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      :class="['summary-item', { active: item.key === activeKey, clickable: item.clickable !== false }]"
      :disabled="item.clickable === false"
      @click="item.clickable === false ? undefined : $emit('select', item.key)"
    >
      <span class="summary-item__label">{{ item.label }}</span>
      <strong>{{ item.value }}</strong>
      <span v-if="item.note" class="summary-item__note">{{ item.note }}</span>
    </button>
  </section>
</template>

<script setup lang="ts">
// BM 工作台统一概览条：既可展示指标，也可作为轻量状态导航。
export interface BmSummaryItem {
  key: string
  label: string
  value: number | string
  note?: string
  clickable?: boolean
}

defineProps<{ items: BmSummaryItem[]; activeKey?: string }>()
defineEmits<{ select: [key: string] }>()
</script>

<style scoped>
.summary-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); margin-bottom: 18px; overflow: hidden; background: #fff; border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow-sm); }
.summary-item { position: relative; display: grid; gap: 4px; min-height: 92px; padding: 16px 18px; text-align: left; color: inherit; background: transparent; border: 0; border-right: 1px solid var(--border-light); font: inherit; }
.summary-item:last-child { border-right: 0; }
.summary-item.clickable { cursor: pointer; }
.summary-item.clickable:hover { background: #fffaf7; }
.summary-item.active { background: var(--primary-light); }
.summary-item.active::after { position: absolute; right: 16px; bottom: 0; left: 16px; height: 3px; content: ''; background: var(--primary); border-radius: 3px 3px 0 0; }
.summary-item__label { color: var(--text-secondary); font-size: 13px; }
.summary-item strong { color: var(--text-primary); font-size: 26px; line-height: 1.1; font-variant-numeric: tabular-nums; }
.summary-item__note { color: var(--text-muted); font-size: 12px; }
@media (max-width: 640px) {
  .summary-strip { grid-template-columns: repeat(2, 1fr); }
  .summary-item { border-bottom: 1px solid var(--border-light); }
}
</style>

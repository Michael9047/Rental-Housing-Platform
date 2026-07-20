<template>
  <el-card v-if="visibleRules.length > 0" shadow="never" class="info-card rental-rules-card">
    <template #header>
      <span class="card-header-text">📋 租房规则</span>
    </template>

    <div class="rules-list">
      <div
        v-for="rule in visibleRules"
        :key="rule.key"
        class="rule-item"
      >
        <span class="rule-icon">{{ rule.icon }}</span>
        <p class="rule-text">{{ rule.content }}</p>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Property, RentalRules } from '@/types/property'

const props = defineProps<{
  property: Property
}>()

// ── 规则定义（按展示顺序） ──
interface RuleDef {
  key: keyof RentalRules
  icon: string
}

const RULE_DEFS: RuleDef[] = [
  { key: 'cancellation_policy',       icon: '❌' },
  { key: 'check_out_rules',           icon: '🚪' },
  { key: 'pet_policy',                icon: '🐾' },
  { key: 'payment_rules',             icon: '💰' },
  { key: 'check_in_rules',            icon: '🛎️' },
  { key: 'room_change_rules',         icon: '🔄' },
  { key: 'sublet_rules',              icon: '📤' },
  { key: 'early_termination_rules',   icon: '✂️' },
  { key: 'renewal_rules',             icon: '🔁' },
  { key: 'guest_policy',              icon: '👥' },
  { key: 'quiet_hours',               icon: '🔇' },
  { key: 'smoking_policy',            icon: '🚭' },
  { key: 'common_area_rules',         icon: '🏋️' },
  { key: 'maintenance_rules',         icon: '🔧' },
]

interface VisibleRule {
  key: string
  icon: string
  content: string
}

const visibleRules = computed<VisibleRule[]>(() => {
  const rr: RentalRules | null | undefined = props.property.rental_rules
  if (!rr) return []

  return RULE_DEFS
    .filter((def) => {
      const v = rr[def.key]
      return v && typeof v === 'string' && v.trim().length > 0
    })
    .map((def) => ({
      key: def.key,
      icon: def.icon,
      content: (rr[def.key] as string).trim(),
    }))
})
</script>

<style scoped>
.rules-list {
  display: flex;
  flex-direction: column;
}

.rule-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--border-light);
}

.rule-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.rule-item:first-child {
  padding-top: 0;
}

.rule-icon {
  font-size: 18px;
  flex-shrink: 0;
  width: 28px;
  text-align: center;
  line-height: 1.5;
}

.rule-text {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
  margin: 0;
  flex: 1;
}

/* ── 暗色模式 ── */
[data-theme="dark"] .rule-text {
  color: #c8c8cc;
}
</style>

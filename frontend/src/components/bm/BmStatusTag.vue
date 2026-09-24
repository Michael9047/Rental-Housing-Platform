<template><el-tag :type="view.type" effect="light" :size="size">{{ view.label }}</el-tag></template>

<script setup lang="ts">
// BM 业务状态标签：集中维护订单、合约和租住关系的展示语义。
import { computed } from 'vue'

type TagType = 'success' | 'warning' | 'info' | 'danger' | 'primary'
const props = withDefaults(defineProps<{ domain:'order'|'contract'|'tenant'|'visit'; status:string; size?:'small'|'default'|'large' }>(), { size:'default' })
const maps:Record<string,Record<string,{label:string;type:TagType}>> = {
  order: { active:{label:'进行中',type:'warning'}, completed:{label:'预订成功',type:'success'}, cancelled:{label:'已取消',type:'info'} },
  contract: { draft:{label:'待签署',type:'warning'}, pending:{label:'待签署',type:'warning'}, generated:{label:'待签署',type:'warning'}, signed:{label:'已签署',type:'success'}, active:{label:'已生效',type:'success'}, effective:{label:'已生效',type:'success'}, terminated:{label:'已终止',type:'info'}, cancelled:{label:'已取消',type:'info'} },
  tenant: { active:{label:'在住',type:'success'}, notice_given:{label:'已通知退租',type:'warning'}, moved_out:{label:'已搬出',type:'info'} },
  visit: { pending:{label:'待处理',type:'warning'}, processed:{label:'已处理',type:'success'} },
}
const view = computed(() => maps[props.domain]?.[props.status] || { label:props.status || '状态未知', type:'info' as TagType })
</script>

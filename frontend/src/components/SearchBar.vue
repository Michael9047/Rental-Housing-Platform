<template>
  <div class="search-bar">
    <el-input
      v-model="query"
      size="large"
      :placeholder="placeholder"
      :prefix-icon="Search"
      class="search-input"
      @keyup.enter="handleSearch"
    >
      <template #append>
        <el-button :icon="Search" @click="handleSearch" />
      </template>
    </el-input>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'

const props = withDefaults(defineProps<{
  modelValue?: string
  placeholder?: string
}>(), {
  modelValue: '',
  placeholder: '搜索房源、小区、区域...',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  search: [value: string]
}>()

const query = ref(props.modelValue)

watch(() => props.modelValue, (val) => {
  query.value = val
})

watch(query, (val) => {
  emit('update:modelValue', val)
})

function handleSearch() {
  emit('search', query.value.trim())
}
</script>

<style scoped>
.search-bar {
  width: 100%;
}

.search-input {
  max-width: 600px;
}
</style>

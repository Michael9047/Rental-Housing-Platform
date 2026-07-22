<!-- 个人信息与紧急联系人共用的结构化行政区划选择器。 -->
<template>
  <div class="address-selector">
    <el-select v-model="model.country_code" filterable placeholder="国家/地区" :disabled="disabled" @change="changeCountry">
      <el-option v-for="country in addressCountries" :key="country.code" :label="country.name" :value="country.code" />
    </el-select>
    <template v-if="model.country_code === 'CN'">
      <el-select v-model="model.level1_code" filterable placeholder="省/自治区/直辖市" :disabled="disabled" @change="changeLevel1">
        <el-option v-for="item in divisions" :key="item.code" :label="item.name" :value="item.code" />
      </el-select>
      <el-select v-model="model.city_code" filterable placeholder="城市" :disabled="disabled || !model.level1_code" @change="changeCity">
        <el-option v-for="item in cities" :key="item.code" :label="item.name" :value="item.code" />
      </el-select>
      <el-select v-model="model.district_code" filterable placeholder="区/县" :disabled="disabled || !model.city_code" @change="changeDistrict">
        <el-option v-for="item in districts" :key="item.code" :label="item.name" :value="item.code" />
      </el-select>
    </template>
    <el-input v-else-if="model.country_code" v-model="model.level1_name" :disabled="disabled" placeholder="其他/手动填写省、州、城市及地区" @input="syncRegion" />
    <p v-if="model.country_code && model.country_code !== 'CN'" class="help-text">该国家暂无完整行政区数据，请手动填写行政区划。</p>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import divisionsData from 'china-division/dist/pca-code.json'
import { addressCountries } from '@/data/countries'
import { buildRegion, type StructuredAddress } from '@/types/address'

interface Division { code: string; name: string; children?: Division[] }
const model = defineModel<StructuredAddress>({ required: true })
const props = defineProps<{ disabled?: boolean }>()
const divisions = divisionsData as Division[]
const cities = computed(() => divisions.find((item) => item.code === model.value.level1_code)?.children || [])
const districts = computed(() => cities.value.find((item) => item.code === model.value.city_code)?.children || [])

function syncRegion() {
  model.value.region = buildRegion(model.value)
}
function changeCountry(code: string) {
  const country = addressCountries.find((item) => item.code === code)
  Object.assign(model.value, {
    country_name: country?.name || '', level1_code: '', level1_name: '', city_code: '',
    city_name: '', district_code: '', district_name: '',
  })
  syncRegion()
}
function changeLevel1(code: string) {
  Object.assign(model.value, { level1_name: divisions.find((item) => item.code === code)?.name || '', city_code: '', city_name: '', district_code: '', district_name: '' })
  syncRegion()
}
function changeCity(code: string) {
  Object.assign(model.value, { city_name: cities.value.find((item) => item.code === code)?.name || '', district_code: '', district_name: '' })
  syncRegion()
}
function changeDistrict(code: string) {
  model.value.district_name = districts.value.find((item) => item.code === code)?.name || ''
  syncRegion()
}

watch(() => model.value.address_line, (value) => { model.value.address_detail = value })
</script>

<style scoped>
.address-selector { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; grid-column: 1 / -1; }
.help-text { grid-column: 1 / -1; margin: 0; }
@media (max-width: 767px) { .address-selector { grid-template-columns: 1fr; } }
</style>

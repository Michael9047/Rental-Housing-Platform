<!-- 个人信息与紧急联系人共用的结构化行政区划选择器。 -->
<template>
  <div class="address-selector">
    <div class="address-field">
      <label class="address-label">国家/地区</label>
      <el-select v-model="model.country_code" filterable placeholder="请选择国家/地区" :disabled="disabled" @change="changeCountry">
        <el-option v-for="country in addressCountries" :key="country.code" :label="country.name" :value="country.code" />
      </el-select>
      <p class="help-text">请选择常住地址所在的国家或地区</p>
    </div>
    <template v-if="model.country_code === 'CN'">
      <div class="address-field">
        <label class="address-label">省/州</label>
        <el-select v-model="model.level1_code" filterable placeholder="请选择省/自治区/直辖市" :disabled="disabled" @change="changeLevel1">
          <el-option v-for="item in divisions" :key="item.code" :label="item.name" :value="item.code" />
        </el-select>
        <p class="help-text">请选择省、自治区或直辖市</p>
      </div>
      <div class="address-field">
        <label class="address-label">城市</label>
        <el-select v-model="model.city_code" filterable placeholder="请选择城市" :disabled="disabled || !model.level1_code" @change="changeCity">
          <el-option v-for="item in cities" :key="item.code" :label="item.name" :value="item.code" />
        </el-select>
        <p class="help-text">请先选择省/州后再选择城市</p>
      </div>
      <div class="address-field">
        <label class="address-label">区/县</label>
        <el-select v-model="model.district_code" filterable placeholder="请选择区/县" :disabled="disabled || !model.city_code" @change="changeDistrict">
          <el-option v-for="item in districts" :key="item.code" :label="item.name" :value="item.code" />
        </el-select>
        <p class="help-text">请先选择城市后再选择区/县</p>
      </div>
    </template>
    <div v-else-if="model.country_code" class="address-field">
      <label class="address-label">省/州、城市及地区</label>
      <el-input v-model="model.level1_name" :disabled="disabled" placeholder="请手动填写省、州、城市及地区" @input="syncRegion" />
      <p class="help-text">该国家暂无完整行政区数据，请手动填写行政区划</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import divisionsData from 'china-division/dist/pca-code.json'
import { addressCountries } from '@/data/countries'
import { buildRegion, type AddressFormLike } from '@/types/address'

interface Division { code: string; name: string; children?: Division[] }
const model = defineModel<AddressFormLike>({ required: true })
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
.address-selector { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); grid-column: 1 / -1; gap: 28px 48px; min-width: 0; }
.address-field { display: flex; flex-direction: column; width: 100%; min-width: 0; overflow: visible; }
.address-label { display: block; margin: 0 0 8px; color: #26364a; font-size: 16px; line-height: 22px; font-weight: 400; }
.address-field :deep(.el-select), .address-field :deep(.el-input) { width: 100%; min-width: 0; }
.address-field :deep(.el-select__wrapper), .address-field :deep(.el-input__wrapper) { width: 100%; min-height: var(--booking-control-height, 48px); height: var(--booking-control-height, 48px); padding: var(--booking-control-padding, 4px 12px); box-sizing: border-box; border-radius: var(--booking-control-radius, var(--radius-sm)); box-shadow: var(--booking-control-border, 0 0 0 1px var(--el-border-color) inset); }
.help-text { display: block; width: 100%; margin: 7px 0 0; padding: 0; color: #3f7fc4; font-size: 13px; font-weight: 400; line-height: 20px; white-space: normal; overflow: visible; word-break: break-word; }
@media (max-width: 899px) { .address-selector { grid-template-columns: minmax(0, 1fr); gap: 20px; } }
</style>

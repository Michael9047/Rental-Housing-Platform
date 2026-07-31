<template>
  <div class="create-page">
    <h2>{{ isCopy ? '复制户型' : (isEdit ? '编辑户型' : '发布户型') }}</h2>

    <el-card shadow="never" v-loading="formLoading">
      <template #header><span>{{ isEdit ? '编辑户型信息' : (isCopy ? '复制户型（可修改后保存）' : '户型信息') }}</span></template>

      <div v-if="formLoading" style="text-align:center;padding:40px;color:#909399">正在加载户型数据...</div>
      <template v-else>
        <el-alert v-if="!buildings.length && !isEdit"
          title="尚未创建任何公寓，发布户型前必须先去创建公寓"
          type="warning" :closable="false" show-icon style="margin-bottom:20px">
          <template #default>
            <el-button type="warning" size="small" @click="$router.push('/buildings')" style="margin-top:8px">前往创建公寓 →</el-button>
          </template>
        </el-alert>

        <el-form ref="formRef" :model="f" :rules="rules" label-width="100px" @submit.prevent="handleSubmit" :validate-on-rule-change="false">

          <!-- 所属公寓（必选） -->
          <el-form-item label="所属公寓" prop="institute_id">
            <div style="display:flex;gap:8px;width:100%">
              <el-select v-model="f.institute_id" placeholder="选择公寓（必选）" filterable style="flex:1">
                <el-option v-for="b in buildings" :key="b.id" :label="b.name" :value="b.id" />
              </el-select>
              <el-button type="primary" @click="showBuildingDialog=true">+ 新建公寓</el-button>
            </div>
          </el-form-item>

          <el-divider content-position="left">基础信息</el-divider>

          <el-form-item label="户型名称" prop="name">
            <el-input v-model="f.name" placeholder="如：Studio A、Ensuite B、2Bed Deluxe" maxlength="100" />
          </el-form-item>

          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="卧室数"><el-input-number v-model="f.bedrooms" :min="0" :max="10" controls-position="right" style="width:100%" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="厅数"><el-input-number v-model="f.hall_count" :min="0" :max="5" controls-position="right" style="width:100%" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="卫生间数"><el-input-number v-model="f.bathrooms" :min="0" :max="10" controls-position="right" style="width:100%" /></el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="套内面积(㎡)" prop="area_sqm">
                <el-input-number v-model="f.area_sqm" :min="1" :max="9999" :precision="2" controls-position="right" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="最短租期(月)">
                <el-input-number v-model="f.min_stay_months" :min="1" :max="24" controls-position="right" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-divider content-position="left">租金信息</el-divider>

          <el-form-item label="货币">
            <el-select v-model="f.currency" placeholder="选择货币" style="width:260px">
              <el-option v-for="c in currencies" :key="c.code" :label="`${c.name} ${c.symbol}`" :value="c.code">
                <span>{{ c.name }}</span>
                <span style="color:#909399;margin-left:8px">{{ c.symbol }}</span>
              </el-option>
            </el-select>
          </el-form-item>

          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item :label="'标准月租金('+currencySymbol+')'" prop="base_rent">
                <el-input-number v-model="f.base_rent" :min="0" :precision="0" controls-position="right" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="'押金金额('+currencySymbol+')'">
                <el-input-number v-model="f.deposit_amount" :min="0" :precision="0" controls-position="right" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="押金类型">
                <el-select v-model="f.deposit_type" style="width:100%">
                  <el-option label="押一付一" value="one_month" />
                  <el-option label="押一付三" value="one_three" />
                  <el-option label="押二付一" value="two_month" />
                  <el-option label="押三付一" value="three_month" />
                  <el-option label="押半付一" value="half_month" />
                  <el-option label="免押金" value="free" />
                  <el-option label="自定义" value="custom" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="起租时间">
                <el-input v-model="f.lease_start" placeholder="如 2026年9月 / 随时入住 / 即日起" maxlength="50" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="止租时间">
                <el-input v-model="f.lease_end" placeholder="如 2027年6月 / 租满一年" maxlength="50" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-divider content-position="left">专属优惠</el-divider>
          <el-form-item>
            <el-input v-model="f.special_offer" type="textarea" :rows="3" placeholder="如：早鸟优惠减200、老客户推荐返现100、包年免1个月租金、3人团购每人减50..." maxlength="500" show-word-limit />
          </el-form-item>

          <el-divider content-position="left">楼层差异化加价</el-divider>
          <el-form-item label="楼层加价规则">
            <div style="width:100%">
              <el-button size="small" type="primary" @click="addFloorTier" style="margin-bottom:8px">+ 添加楼层段</el-button>
              <el-table :data="floorPricingTable" border size="small" v-if="floorPricingTable.length">
                <el-table-column label="起始楼层" width="110">
                  <template #default="{row,$index}"><el-input-number v-model="row.floor_min" :min="0" size="small" controls-position="right" style="width:90px" /></template>
                </el-table-column>
                <el-table-column label="结束楼层" width="110">
                  <template #default="{row,$index}"><el-input-number v-model="row.floor_max" :min="0" size="small" controls-position="right" style="width:90px" /></template>
                </el-table-column>
                <el-table-column label="加价(¥/月)" width="130">
                  <template #default="{row,$index}"><el-input-number v-model="row.adjustment" :min="0" size="small" controls-position="right" style="width:110px" /></template>
                </el-table-column>
                <el-table-column label="操作" width="80">
                  <template #default="{ $index }"><el-button size="small" type="danger" text @click="floorPricingTable.splice($index,1)">删除</el-button></template>
                </el-table-column>
              </el-table>
            </div>
          </el-form-item>

          <el-divider content-position="left">配套设施</el-divider>

          <el-form-item label="房间配置">
            <el-checkbox-group v-model="selectedAmenities" class="amenity-group">
              <el-checkbox v-for="a in roomConfigAmenities" :key="a" :label="a" :value="a" border size="small" />
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="朝向/楼层">
            <el-checkbox-group v-model="selectedAmenities" class="amenity-group">
              <el-checkbox v-for="a in orientationAmenities" :key="a" :label="a" :value="a" border size="small" />
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="租金包含">
            <el-checkbox-group v-model="selectedAmenities" class="amenity-group">
              <el-checkbox v-for="a in billsAmenities" :key="a" :label="a" :value="a" border size="small" />
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="租住规则">
            <el-checkbox-group v-model="selectedAmenities" class="amenity-group">
              <el-checkbox v-for="a in ruleAmenities" :key="a" :label="a" :value="a" border size="small" />
            </el-checkbox-group>
          </el-form-item>

          <el-divider content-position="left">户型描述</el-divider>
          <el-form-item label="描述">
            <el-input v-model="f.description" type="textarea" :rows="4" placeholder="描述户型特点、朝向、采光等..." maxlength="2000" show-word-limit />
          </el-form-item>

          <!-- 户型图片上传 -->
          <el-divider content-position="left">户型图片</el-divider>
          <el-form-item label="平面图/效果图">
            <ImageUploader
              ref="imageUploaderRef"
              title="户型平面图/效果图"
              hint="支持上传户型平面布局图、效果图，至少3张，最多20张"
              :min-files="3"
              :max-files="20"
              v-model="uploadedImageUrls"
            />
          </el-form-item>

          <el-divider />
          <el-form-item>
            <el-button type="primary" size="large" native-type="submit" :loading="submitting" :disabled="!f.institute_id">
              {{ isEdit ? '保存修改' : (isCopy ? '创建副本' : '提交发布') }}
            </el-button>
            <el-button @click="$router.back()">取消</el-button>
          </el-form-item>
        </el-form>
      </template>
    </el-card>

    <!-- 创建公寓弹窗（完整版） -->
    <el-dialog v-model="showBuildingDialog" title="新建公寓" width="720px" :close-on-click-modal="false" @opened="onBldDialogOpened" @closed="onBldDialogClosed">
      <el-form :model="newBuilding" label-width="100px">
        <el-form-item label="公寓名称" required><el-input v-model="newBuilding.name" placeholder="中/英文均可" maxlength="200" /></el-form-item>
        <el-divider>📍 地址与定位</el-divider>
        <el-form-item label="国家"><el-autocomplete v-model="newBuilding.country" :fetch-suggestions="filterCountries" placeholder="输入或选择国家，如：英国、美国、日本" clearable style="width:100%" /></el-form-item>
        <el-form-item label="城市"><el-input v-model="newBuilding.city" placeholder="如：伦敦、上海、新加坡" maxlength="100" /></el-form-item>
        <el-form-item label="区域"><el-input v-model="newBuilding.district" placeholder="如：肯辛顿、浦东、市中心" maxlength="100" /></el-form-item>
        <el-form-item label="街道/门牌号"><el-input v-model="newBuilding.street" placeholder="如：105 Cheyne Walk 或 南京路100号" maxlength="200" /></el-form-item>
        <el-form-item label="邮编"><el-input v-model="newBuilding.postalCode" placeholder="选填" maxlength="20" style="width:200px" /></el-form-item>
        <el-form-item label="地图定位">
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
            <el-button type="primary" @click="geocodeStructured" :loading="geoLoading" :disabled="!(newBuilding.country || newBuilding.city)">📍 检索定位</el-button>
            <el-tag v-if="newBuilding.lat!=null && newBuilding.lng!=null" type="success" effect="dark" size="small">✅ 已定位</el-tag>
            <el-tag v-else type="danger" effect="dark" size="small">❌ 未定位</el-tag>
            <el-button size="small" type="danger" plain style="margin-left:auto" @click="clearBldAddressFields">🗑️ 清空</el-button>
          </div>
          <div ref="bldMapEl" style="width:100%;height:260px;border-radius:8px;border:1px solid #dcdfe6;"></div>
          <div style="color:#909399;font-size:12px;margin-top:4px">💡 填地址→检索定位；点地图→自动回填</div>
        </el-form-item>
        <el-divider>联系方式</el-divider>
        <el-form-item label="前台电话"><el-input v-model="newBuilding.contact_phone" /></el-form-item>
        <el-divider>公寓介绍</el-divider>
        <el-form-item><el-input v-model="newBuilding.description" type="textarea" :rows="3" maxlength="2000" show-word-limit /></el-form-item>
        <el-divider>🛡️ 安保</el-divider>
        <el-form-item><el-checkbox-group v-model="buildingAmenities" class="amenity-group"><el-checkbox v-for="a in securityAmenitiesBld" :key="a" :label="a" :value="a" border size="small" /></el-checkbox-group></el-form-item>
        <el-divider>🛎️ 服务</el-divider>
        <el-form-item><el-checkbox-group v-model="buildingAmenities" class="amenity-group"><el-checkbox v-for="a in serviceAmenitiesBld" :key="a" :label="a" :value="a" border size="small" /></el-checkbox-group></el-form-item>
        <el-divider>🏠 公用设施</el-divider>
        <el-form-item><el-checkbox-group v-model="buildingAmenities" class="amenity-group"><el-checkbox v-for="a in facilityAmenitiesBld" :key="a" :label="a" :value="a" border size="small" /></el-checkbox-group></el-form-item>
        <el-divider>⚽ 运动娱乐</el-divider>
        <el-form-item><el-checkbox-group v-model="buildingAmenities" class="amenity-group"><el-checkbox v-for="a in sportAmenitiesBld" :key="a" :label="a" :value="a" border size="small" /></el-checkbox-group></el-form-item>
        <el-divider>公寓公共图集</el-divider>
        <el-form-item label="公寓照片">
          <ImageUploader ref="bldImageUploaderRef" title="公寓外观、大堂、公共设施实拍" hint="至少3张，最多20张，首张为封面" :min-files="3" :max-files="20" v-model="buildingImages" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBuildingDialog=false">取消</el-button>
        <el-button type="primary" :loading="creatingBuilding" :disabled="!newBuilding.name.trim() || newBuilding.lat==null" @click="createBuilding">创建</el-button>
      </template>
    </el-dialog>

    <!-- 成功弹窗 -->
    <el-dialog v-model="showSuccessDialog" title="保存成功" width="420px" :close-on-click-modal="false">
      <el-result icon="success" title="户型已保存！" />
      <template #footer>
        <el-button type="primary" @click="goToList">返回户型管理</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { buildingService, type Building } from '@/services/building'
import { extractErrorMessage } from '@/services/api'
import api from '@/services/api'
import ImageUploader from '@/components/ImageUploader.vue'

const router = useRouter(); const route = useRoute()
const authStore = useAuthStore()

const isEdit = computed(() => route.name === 'edit-unit-type')
const isCopy = computed(() => route.name === 'copy-unit-type')
const editId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : null
})

const formRef = ref<FormInstance>(); const submitting = ref(false)
const showSuccessDialog = ref(false); const formLoading = ref(false)
const uploadedImageUrls = ref<string[]>([])
const imageUploaderRef = ref<InstanceType<typeof ImageUploader>>()

// 货币列表
const currencies = [
  { code: 'CNY', name: '人民币', symbol: '¥' },
  { code: 'USD', name: '美元', symbol: '$' },
  { code: 'GBP', name: '英镑', symbol: '£' },
  { code: 'EUR', name: '欧元', symbol: '€' },
  { code: 'AUD', name: '澳元', symbol: 'A$' },
  { code: 'SGD', name: '新币', symbol: 'S$' },
  { code: 'CAD', name: '加元', symbol: 'C$' },
  { code: 'HKD', name: '港币', symbol: 'HK$' },
  { code: 'JPY', name: '日元', symbol: '¥' },
  { code: 'KRW', name: '韩元', symbol: '₩' },
]
const currencySymbol = computed(() => {
  const c = currencies.find(c => c.code === f.currency)
  return c ? c.symbol : '¥'
})
const roomConfigAmenities = ['精装修','壁橱','空调','中央空调','WiFi','带厨房','带客厅','落地窗','独立卫浴','电梯']
const orientationAmenities = ['朝南','朝北','朝东','朝西','高楼层','顶层','底层/带院子']
const billsAmenities = ['包水电','包网络','包取暖']
const ruleAmenities = ['可养宠物','禁烟','禁派对','允许访客留宿','安静时段']
const selectedAmenities = ref<string[]>([])

const f = reactive({
  institute_id: null as number | null,
  name: '',
  bedrooms: 0, bathrooms: 0, hall_count: 0,
  area_sqm: undefined as number | undefined,
  base_rent: undefined as number | undefined,
  deposit_amount: undefined as number | undefined,
  deposit_type: undefined as string | undefined,
  lease_start: '' as string | undefined,
  lease_end: '' as string | undefined,
  currency: 'CNY' as string | undefined,
  special_offer: '' as string | undefined,
  min_stay_months: 3,
  description: '',
})

const floorPricingTable = reactive<Array<{ floor_min: number; floor_max: number; adjustment: number }>>([])

function addFloorTier() {
  const last = floorPricingTable[floorPricingTable.length - 1]
  floorPricingTable.push({
    floor_min: last ? last.floor_max + 1 : 1,
    floor_max: last ? last.floor_max + 5 : 5,
    adjustment: 0,
  })
}

const rules: FormRules = {
  institute_id: [{ required: true, message: '请选择公寓', trigger: 'change' }],
  name: [{ required: true, message: '请输入户型名称', trigger: 'blur' }],
  base_rent: [{ required: true, message: '请输入标准月租金', trigger: 'blur' }],
  area_sqm: [{ required: true, message: '请输入套内面积', trigger: 'blur' }],
}

// ── 公寓 ──
const buildings = ref<Building[]>([])
const showBuildingDialog = ref(false); const creatingBuilding = ref(false); const geoLoading = ref(false)
const buildingAmenities = ref<string[]>([]); const buildingImages = ref<string[]>([])
const bldImageUploaderRef = ref<InstanceType<typeof ImageUploader>>()
const bldMapEl = ref<HTMLElement|null>(null)

const countryOptions = ['中国','英国','美国','澳大利亚','加拿大','新加坡','日本','韩国','法国','德国','马来西亚','泰国']
function filterCountries(query: string, cb: Function) {
  if (!query) { cb(countryOptions.map(v => ({value:v}))); return }
  const q = query.toLowerCase()
  cb(countryOptions.filter(c => c.toLowerCase().includes(q) || c.includes(query)).map(v => ({value:v})))
}

const newBuilding = reactive({
  name: '', contact_phone: '', description: '',
  country: '', city: '', district: '', street: '', postalCode: '',
  lat: null as number|null, lng: null as number|null,
})

const securityAmenitiesBld = ['24小时安保','监控系统(CCTV)','智能门禁','电子门锁','前台/礼宾','消防系统','夜间巡逻']
const serviceAmenitiesBld = ['代收包裹','维修服务','公共区域保洁','定期社交活动','接机服务','班车接驳','入住礼包','管家服务']
const facilityAmenitiesBld = ['电梯','洗衣房','自行车库','停车场','公共厨房','快递柜/信箱','自习室','影音室','公共休闲区','屋顶露台','庭院/花园','会议室']
const sportAmenitiesBld = ['健身房','游泳池','篮球场','瑜伽室','游戏室','BBQ区','乒乓球/台球']

// ── 地图 ──
let bldMapInst:any=null, bldMarkerInst:any=null

function getL(){ return (window as any).L }
async function ensureLeaflet(){
  if(getL()) return getL()
  if(!document.getElementById('leaflet-css')){
    const c=document.createElement('link');c.id='leaflet-css';c.rel='stylesheet'
    c.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';document.head.appendChild(c)
  }
  return new Promise<any>(r=>{
    const s=document.createElement('script')
    s.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
    s.onload=()=>r(getL()); document.head.appendChild(s)
  })
}

async function initBldMap(lat:number|null, lng:number|null){
  await import('vue').then(m=>m.nextTick())
  if(!bldMapEl.value) return
  if(bldMapInst){ try{bldMapInst.remove()}catch(e){} bldMapInst=null; bldMarkerInst=null }
  const L = await ensureLeaflet()
  const center:[number,number] = (lat!=null&&lng!=null&&isFinite(lat)&&isFinite(lng)) ? [lat,lng] : [31.27,120.73]
  const zoom = (lat!=null&&lng!=null) ? 17 : 12
  bldMapInst = L.map(bldMapEl.value, {center, zoom})
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy;OSM',maxZoom:19}).addTo(bldMapInst)
  bldMapInst.on('click', (e:any)=>{ placeBldMarker(e.latlng.lat, e.latlng.lng, true) })
  if(lat!=null && lng!=null) placeBldMarker(lat, lng, false)
}

function placeBldMarker(lat:number, lng:number, rev:boolean){
  const L=getL(); if(!L||!bldMapInst) return
  if(bldMarkerInst) bldMarkerInst.setLatLng([lat,lng])
  else {
    bldMarkerInst = L.marker([lat,lng],{draggable:true}).addTo(bldMapInst)
    bldMarkerInst.on('dragend', ()=>{ const p=bldMarkerInst.getLatLng(); newBuilding.lat=p.lat; newBuilding.lng=p.lng })
  }
  newBuilding.lat=lat; newBuilding.lng=lng
  if(rev) reverseBldGeocode(lat,lng)
}

function destroyBldMap(){
  if(bldMapInst){ try{bldMapInst.remove()}catch(e){} }
  bldMapInst=null; bldMarkerInst=null
}

async function geocodeStructured(){
  if(!(newBuilding.country || newBuilding.city)){ElMessage.warning('请至少填写国家或城市');return}
  geoLoading.value=true
  try{
    const params=new URLSearchParams({format:'json',limit:'1'})
    if(newBuilding.street) params.set('street',newBuilding.street)
    if(newBuilding.city) params.set('city',newBuilding.city)
    if(newBuilding.country) params.set('country',newBuilding.country)
    if(newBuilding.postalCode) params.set('postalcode',newBuilding.postalCode)
    const r=await fetch(`https://nominatim.openstreetmap.org/search?${params}`,{headers:{'User-Agent':'RH/1.0'}})
    const d=await r.json()
    if(d.length>0){
      const lat=parseFloat(d[0].lat),lng=parseFloat(d[0].lon)
      placeBldMarker(lat,lng,false);bldMapInst?.setView([lat,lng],17)
      ElMessage.success(`已定位 (${lat.toFixed(4)}, ${lng.toFixed(4)})`)
    }else{ElMessage.warning('未找到该地址，请在地图上手动点击选点')}
  }catch(e){ElMessage.error('定位失败，请检查网络')}
  finally{geoLoading.value=false}
}

async function reverseBldGeocode(lat:number,lng:number){
  try{
    const r=await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&accept-language=zh`,{headers:{'User-Agent':'RH/1.0'}})
    const d=await r.json()
    if(!d?.address) return
    const a = d.address
    if (a.country && !newBuilding.country) newBuilding.country = a.country
    if (!newBuilding.city) newBuilding.city = a.city || a.town || a.municipality || a.village || a.hamlet || ''
    if (!newBuilding.district) newBuilding.district = a.suburb || a.borough || a.city_district || a.county || a.state_district || ''
    if (!newBuilding.street) { const road = a.road || a.pedestrian || a.path || a.footway || ''; const hn = a.house_number || ''; newBuilding.street = hn ? `${hn} ${road}`.trim() : road }
    if (!newBuilding.postalCode) newBuilding.postalCode = a.postcode || ''
    ElMessage.success('已从地图反向定位，地址字段已自动填充')
  }catch(e){}
}

function clearBldAddressFields(){
  newBuilding.country=''; newBuilding.city=''; newBuilding.district=''; newBuilding.street=''; newBuilding.postalCode=''
  newBuilding.lat=null; newBuilding.lng=null
  if(bldMarkerInst){ bldMarkerInst.remove(); bldMarkerInst=null }
  ElMessage.success('地址已清空，可在地图上点击选点')
}

async function onBldDialogOpened(){
  await import('vue').then(m=>m.nextTick())
  await initBldMap(newBuilding.lat, newBuilding.lng)
}

function onBldDialogClosed(){
  destroyBldMap()
  newBuilding.name=''; newBuilding.contact_phone=''; newBuilding.description=''
  newBuilding.country=''; newBuilding.city=''; newBuilding.district=''; newBuilding.street=''; newBuilding.postalCode=''
  newBuilding.lat=null; newBuilding.lng=null
  buildingAmenities.value=[]; buildingImages.value=[]
}

async function loadBuildings() {
  try { buildings.value = await buildingService.list({ limit: 200 }) } catch { /* */ }
}

async function createBuilding() {
  if (!newBuilding.name.trim()) { ElMessage.error('请输入公寓名称'); return }
  if (newBuilding.lat==null || newBuilding.lng==null) { ElMessage.warning('请先定位公寓坐标'); return }
  creatingBuilding.value = true
  try {
    const p: any = {
      name: newBuilding.name.trim(),
      country: newBuilding.country.trim()||null, city: newBuilding.city.trim()||null,
      district: newBuilding.district.trim()||null, street: newBuilding.street.trim()||null,
      postal_code: newBuilding.postalCode.trim()||null,
      contact_phone: newBuilding.contact_phone.trim()||null,
      description: newBuilding.description.trim()||null,
      amenities: buildingAmenities.value.length ? [...buildingAmenities.value] : null,
      image_urls: buildingImages.value.length ? [...buildingImages.value] : null,
      latitude: String(newBuilding.lat), longitude: String(newBuilding.lng),
    }
    const b = await buildingService.create(p)
    buildings.value.unshift(b); f.institute_id = b.id; showBuildingDialog.value = false
    onBldDialogClosed()
    ElMessage.success('公寓创建成功')
  } catch (e: any) { ElMessage.error(extractErrorMessage(e) || '创建失败') }
  finally { creatingBuilding.value = false }
}

// 加载已有户型（编辑/复制模式）
async function loadUnitType(id: number) {
  formLoading.value = true
  try {
    const r = await api.get(`/unit-types/${id}`)
    const ut = r.data
    f.institute_id = ut.institute_id
    f.name = isCopy.value ? `${ut.name} (副本)` : ut.name
    f.bedrooms = ut.bedrooms ?? 0
    f.bathrooms = ut.bathrooms ?? 0
    f.hall_count = ut.hall_count ?? 0
    f.area_sqm = ut.area_sqm ? Number(ut.area_sqm) : undefined
    f.base_rent = ut.base_rent ? Number(ut.base_rent) : undefined
    f.deposit_amount = ut.deposit_amount ?? undefined
    f.deposit_type = ut.deposit_type ?? undefined
    f.lease_start = ut.lease_start ?? ''
    f.lease_end = ut.lease_end ?? ''
    f.currency = ut.currency || 'CNY'
    f.special_offer = ut.special_offer ?? ''
    f.min_stay_months = ut.min_stay_months ?? 3
    f.description = ut.description ?? ''
    selectedAmenities.value = ut.amenities ?? []
    uploadedImageUrls.value = (ut.image_urls ?? []).map((u: string) => u.startsWith('/api') || u.startsWith('http') ? u : '/api/v1/uploads/' + u)
    if (ut.floor_pricing && Array.isArray(ut.floor_pricing)) {
      floorPricingTable.length = 0
      ut.floor_pricing.forEach((fp: any) => floorPricingTable.push({ ...fp }))
    }
  } catch (e: any) {
    ElMessage.error('加载户型数据失败')
  } finally { formLoading.value = false }
}

// 提交
async function handleSubmit() {
  if (!formRef.value) return
  if (!authStore.user) { ElMessage.error('请先登录'); return }
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (!f.institute_id) { ElMessage.error('请先选择公寓'); return }

  submitting.value = true
  const data: any = {
    institute_id: f.institute_id,
    name: f.name.trim(),
    bedrooms: f.bedrooms,
    bathrooms: f.bathrooms,
    hall_count: f.hall_count,
    area_sqm: f.area_sqm ? String(f.area_sqm) : null,
    base_rent: f.base_rent ? String(f.base_rent) : '0',
    deposit_amount: f.deposit_amount ?? null,
    deposit_type: f.deposit_type || null,
    lease_start: f.lease_start?.trim() || null,
    lease_end: f.lease_end?.trim() || null,
    currency: f.currency || null,
    special_offer: f.special_offer?.trim() || null,
    min_stay_months: f.min_stay_months,
    floor_pricing: floorPricingTable.length ? [...floorPricingTable] : null,
    amenities: selectedAmenities.value.length ? [...selectedAmenities.value] : null,
    image_urls: uploadedImageUrls.value.length ? [...uploadedImageUrls.value] : null,
    description: f.description.trim() || null,
  }

  try {
    if (isEdit.value && editId.value) {
      await api.patch(`/unit-types/${editId.value}`, data)
    } else {
      await api.post('/unit-types', data)
    }
    showSuccessDialog.value = true
  } catch (e: any) {
    ElMessage.error(extractErrorMessage(e) || '保存失败')
  } finally { submitting.value = false }
}

function goToList() {
  showSuccessDialog.value = false
  router.push('/unit-type/manage')
}

onMounted(async () => {
  await loadBuildings()
  if (route.params.id) await loadUnitType(Number(route.params.id))
})
</script>

<style scoped>
.create-page { max-width: 860px; margin: 0 auto }
h2 { font-size: 22px; color: #303133; margin-bottom: 20px }
.amenity-group { display: flex; flex-wrap: wrap; gap: 6px }
.amenity-group .el-checkbox { margin-right: 0 }
</style>

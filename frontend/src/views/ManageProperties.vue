<template>
  <div class="page-container">
    <div class="page-header">
      <h2>户型管理</h2>
      <div style="display:flex;gap:10px;align-items:center">
        <el-radio-group v-model="viewMode" size="small">
          <el-radio-button value="active">📋 管理中</el-radio-button>
          <el-radio-button value="trash">🗑️ 回收站</el-radio-button>
        </el-radio-group>
        <el-button v-if="viewMode==='active'" type="primary" @click="$router.push('/unit-type/create')">+ 发布户型</el-button>
        <el-button v-if="viewMode==='active'" type="success" @click="showBuildingDialog = true">+ 新建公寓</el-button>
      </div>
    </div>

    <!-- 回收站模式 -->
    <div v-if="viewMode==='trash'" v-loading="trashLoading">
      <div v-if="!trashItems.length && !trashLoading" style="text-align:center;padding:40px;color:#909399">🗑️ 回收站为空</div>
      <div class="ut-cards" v-if="trashItems.length">
        <div v-for="ut in trashItems" :key="ut.id" class="ut-card trash-item">
          <div class="utc-thumb">
            <img v-if="ut.image_urls?.[0]" :src="ut.image_urls[0]" alt="" />
            <span v-else>🏠</span>
          </div>
          <div class="utc-info">
            <div class="utc-name">{{ ut.name }}</div>
            <div class="utc-meta">
              <span class="utc-tag">{{ ut.bedrooms }}室{{ ut.hall_count }}厅{{ ut.bathrooms }}卫</span>
              <span class="utc-tag">{{ ut.area_sqm }}㎡</span>
              <span class="utc-tag">🏢 {{ ut.institute_name || '未知公寓' }}</span>
              <el-tag size="small" type="info">已删除</el-tag>
            </div>
          </div>
          <div class="utc-right">
            <el-tag size="small" type="info" style="margin-bottom:6px">已删除</el-tag>
            <div class="trash-time" v-if="ut.deleted_at" style="margin-bottom:6px">{{ fmtTime(ut.deleted_at) }}</div>
            <el-button size="small" type="primary" @click="restoreUnitType(ut.id)">🔄 恢复</el-button>
            <el-popconfirm title="确定永久删除？不可恢复！" @confirm="hardDeleteUnitType(ut.id)">
              <template #reference>
                <el-button size="small" type="danger" plain>💥 硬删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
    </div>

    <!-- 筛选栏（仅管理模式） -->
    <template v-if="viewMode==='active'">
    <el-card shadow="never" style="margin-bottom:16px">
      <el-row :gutter="12" align="middle">
        <el-col :span="4">
          <el-select v-model="filterInstituteId" placeholder="筛选公寓" clearable filterable style="width:100%">
            <el-option v-for="b in buildings" :key="b.id" :label="`${b.name} (${getUnitTypeCount(b.id)}个户型)`" :value="b.id" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-input-number v-model="filterRentMin" placeholder="最低租金" :min="0" controls-position="right" style="width:100%" />
        </el-col>
        <el-col :span="3">
          <el-input-number v-model="filterRentMax" placeholder="最高租金" :min="0" controls-position="right" style="width:100%" />
        </el-col>
        <el-col :span="3">
          <el-input-number v-model="filterAreaMin" placeholder="最小面积" :min="0" controls-position="right" style="width:100%" />
        </el-col>
        <el-col :span="3">
          <el-input-number v-model="filterAreaMax" placeholder="最大面积" :min="0" controls-position="right" style="width:100%" />
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="fetchList">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
        <el-col :span="4" style="text-align:right">
          <el-button size="small" @click="expandAll">全部展开</el-button>
          <el-button size="small" @click="collapseAll">全部折叠</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 按公寓分组 -->
    <div v-loading="loading">
      <template v-for="b in groupedBuildings" :key="b.id">
        <el-card v-if="getBuildingUnitTypes(b.id).length" shadow="never" class="building-card" style="margin-bottom:16px">
          <div class="building-header" @click="toggleExpand(b.id)">
            <div class="building-info">
              <span class="building-icon">🏢</span>
              <span class="building-name">{{ b.name }}</span>
              <el-tag size="small" type="info">{{ getBuildingUnitTypes(b.id).length }} 个户型</el-tag>
              <span v-if="b.address" class="building-addr">{{ b.address }}</span>
            </div>
            <div class="building-actions" @click.stop>
              <el-button size="small" @click="$router.push(`/unit-type/create?institute_id=${b.id}`)">+ 新增户型</el-button>
              <el-button size="small" @click="$router.push(`/buildings/${b.id}/unit-types`)">查看全部</el-button>
            </div>
            <div class="building-toggle">
              <span style="color:#909399;font-size:12px;margin-right:4px">{{ expandedIds.has(b.id) ? '收起' : '展开' }}</span>
              <span :class="{ rotated: expandedIds.has(b.id) }">▼</span>
            </div>
          </div>

          <div v-show="expandedIds.has(b.id)" class="building-table">
            <!-- 户型卡片列表 — 无需横向滚动，全部信息一目了然 -->
            <div class="ut-cards" v-if="getBuildingUnitTypes(b.id).length">
              <div v-for="ut in getBuildingUnitTypes(b.id)" :key="ut.id" class="ut-card">
                <!-- 左侧：户型图 -->
                <div class="utc-thumb">
                  <el-image v-if="ut.image_urls?.[0]" :src="ut.image_urls[0]" preview-teleported :preview-src-list="ut.image_urls" fit="cover" style="width:100%;height:100%" />
                  <span v-else class="utc-thumb-placeholder">🏠</span>
                </div>
                <!-- 中间：核心信息 -->
                <div class="utc-info">
                  <div class="utc-name">{{ ut.name }}</div>
                  <div class="utc-meta">
                    <span class="utc-tag">{{ ut.bedrooms }}室{{ ut.hall_count }}厅{{ ut.bathrooms }}卫</span>
                    <span class="utc-tag">{{ ut.area_sqm }}㎡</span>
                    <span class="utc-tag" :style="{ color: (ut.available_count > 0) ? 'var(--success)' : 'var(--danger)' }">
                      {{ ut.available_count ?? 0 }} / {{ ut.total_count ?? 0 }} 可租
                    </span>
                    <el-tag size="small" :type="ut.status==='available'?'success':'info'">{{ ut.status==='available'?'可租':'已租' }}</el-tag>
                  </div>
                  <div class="utc-amenities" v-if="ut.amenities?.length">
                    <span v-for="a in ut.amenities.slice(0, 6)" :key="a" class="utc-amenity">{{ a }}</span>
                    <span v-if="ut.amenities.length > 6" class="utc-amenity">+{{ ut.amenities.length - 6 }}</span>
                  </div>
                </div>
                <!-- 右侧：价格 + 操作 -->
                <div class="utc-right">
                  <div class="utc-price">
                    <span class="utc-price-val">{{ currencySym(ut.currency) }}{{ Number(ut.base_rent).toLocaleString() }}</span>
                    <span class="utc-price-unit">/月</span>
                  </div>
                  <div class="utc-deposit" v-if="ut.deposit_amount">
                    押金 {{ currencySym(ut.currency) }}{{ Number(ut.deposit_amount).toLocaleString() }}
                  </div>
                  <div class="utc-lease" v-if="ut.lease_start || ut.lease_end">
                    {{ ut.lease_start || '?' }} ~ {{ ut.lease_end || '?' }}
                  </div>
                  <div class="utc-actions">
                    <el-button size="small" @click="$router.push(`/unit-type/${ut.id}/edit`)">编辑</el-button>
                    <el-button size="small" @click="$router.push(`/unit-type/${ut.id}/copy`)">复制</el-button>
                    <el-button size="small" type="danger" plain @click="handleDelete(ut)">删除</el-button>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="utc-empty">该公寓暂无户型</div>
          </div>
        </el-card>
      </template>
    </div>
    </template>

    <el-empty v-if="!loading && !allUnitTypes.length && viewMode==='active'" description="暂无户型数据">
      <el-button type="primary" @click="$router.push('/unit-type/create')">发布第一个户型</el-button>
    </el-empty>

    <!-- 新建公寓弹窗 -->
    <el-dialog v-model="showBuildingDialog" title="新建公寓" width="720px" :close-on-click-modal="false" @opened="onBldDialogOpened" @closed="onBldDialogClosed">
      <el-form :model="newBuilding" label-width="100px">
        <el-form-item label="公寓名称" required><el-input v-model="newBuilding.name" placeholder="中/英文均可" maxlength="200" /></el-form-item>
        <el-divider>📍 地址与定位</el-divider>
        <el-form-item label="国家"><el-autocomplete v-model="newBuilding.country" :fetch-suggestions="filterCountries" placeholder="输入或选择国家" clearable style="width:100%" /></el-form-item>
        <el-form-item label="城市"><el-input v-model="newBuilding.city" placeholder="如：伦敦、上海" maxlength="100" /></el-form-item>
        <el-form-item label="区域"><el-input v-model="newBuilding.district" placeholder="如：肯辛顿、浦东" maxlength="100" /></el-form-item>
        <el-form-item label="街道/门牌号"><el-input v-model="newBuilding.street" placeholder="如：105 Cheyne Walk" maxlength="200" /></el-form-item>
        <el-form-item label="邮编"><el-input v-model="newBuilding.postalCode" placeholder="选填" maxlength="20" style="width:200px" /></el-form-item>
        <el-form-item label="地图定位">
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
            <el-button type="primary" @click="geocodeStructured" :loading="geoLoading" :disabled="!(newBuilding.country || newBuilding.city)">📍 检索定位</el-button>
            <el-tag v-if="newBuilding.lat!=null && newBuilding.lng!=null" type="success" effect="dark" size="small">✅ 已定位</el-tag>
            <el-tag v-else type="danger" effect="dark" size="small">❌ 未定位</el-tag>
            <el-button size="small" type="danger" plain style="margin-left:auto" @click="clearBldAddressFields">🗑️ 清空</el-button>
            <el-button size="small" type="warning" plain @click="newBuilding.city='BTN_TEST_'+Date.now().toString().slice(-5)">🧪 测试赋值</el-button>
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/services/api'
import { buildingService, type Building } from '@/services/building'
import ImageUploader from '@/components/ImageUploader.vue'

const allUnitTypes = ref<any[]>([])
const trashItems = ref<any[]>([])
const trashLoading = ref(false)
const viewMode = ref<'active'|'trash'>('active')
const currencyMap: Record<string, string> = { CNY:'¥', USD:'$', GBP:'£', EUR:'€', AUD:'A$', SGD:'S$', CAD:'C$', HKD:'HK$', JPY:'¥', KRW:'₩' }
function currencySym(code?: string) { return currencyMap[code || 'CNY'] || '¥' }
const buildings = ref<Building[]>([])
const loading = ref(false)
const expandedIds = ref(new Set<number>())
const filterInstituteId = ref<number | undefined>()
const filterRentMin = ref<number | undefined>()
const filterRentMax = ref<number | undefined>()
const filterAreaMin = ref<number | undefined>()
const filterAreaMax = ref<number | undefined>()

// 有户型的公寓
const groupedBuildings = computed(() => {
  return buildings.value.filter(b => getBuildingUnitTypes(b.id).length > 0)
})

function getUnitTypeCount(buildingId: number) {
  return allUnitTypes.value.filter(u => u.institute_id === buildingId).length
}

function getBuildingUnitTypes(buildingId: number) {
  let list = allUnitTypes.value.filter(u => u.institute_id === buildingId)
  if (filterRentMin.value != null) list = list.filter(u => Number(u.base_rent) >= filterRentMin.value!)
  if (filterRentMax.value != null) list = list.filter(u => Number(u.base_rent) <= filterRentMax.value!)
  if (filterAreaMin.value != null) list = list.filter(u => Number(u.area_sqm) >= filterAreaMin.value!)
  if (filterAreaMax.value != null) list = list.filter(u => Number(u.area_sqm) <= filterAreaMax.value!)
  return list
}

function toggleExpand(id: number) {
  if (expandedIds.value.has(id)) expandedIds.value.delete(id)
  else expandedIds.value.add(id)
  expandedIds.value = new Set(expandedIds.value)
}

function expandAll() {
  expandedIds.value = new Set(buildings.value.map(b => b.id))
}

function collapseAll() {
  expandedIds.value = new Set()
}

function resetFilters() {
  filterInstituteId.value = undefined
  filterRentMin.value = undefined; filterRentMax.value = undefined
  filterAreaMin.value = undefined; filterAreaMax.value = undefined
}

watch(viewMode, (v) => { if (v === 'trash') loadTrash() })
onMounted(() => { loadBuildings(); fetchList() })

async function loadTrash() {
  trashLoading.value = true
  try {
    const r = await api.get('/unit-types/recycle-bin', { params: { page_size: 2000 } })
    trashItems.value = (r.data.items || []).map((ut: any) => ({
      ...ut,
      image_urls: (ut.images || []).map((img: any) => '/api/v1/uploads/' + img.filename),
    }))
  } catch { /* */ }
  finally { trashLoading.value = false }
}

function fmtTime(iso: string): string { try { return new Date(iso).toLocaleString('zh-CN', { hour12: false }) } catch { return iso } }

async function restoreUnitType(id: number) {
  try {
    await api.post('/unit-types/' + id + '/restore')
    ElMessage.success('已恢复')
    loadTrash()
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '恢复失败')
  }
}

async function hardDeleteUnitType(id: number) {
  try {
    await api.delete('/unit-types/' + id + '/hard')
    ElMessage.success('已永久删除')
    loadTrash()
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function loadBuildings() {
  try { buildings.value = await buildingService.list({ limit: 200 }) } catch { /* */ }
}

// ═══ 新建公寓弹窗 ═══
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

let bldMapInst:any=null, bldMarkerInst:any=null
// 用 watch 桥接 Leaflet 异步回调和 Vue 响应式
const _geoTrigger = ref(0)
let _pendingGeoData: Record<string, string> | null = null
watch(_geoTrigger, async (val) => {
  console.log('[geo-watch] fired, tick=', val, 'data=', _pendingGeoData)
  if (!_pendingGeoData) return
  // 先清空所有地址字段
  newBuilding.country = ''
  newBuilding.city = ''
  newBuilding.district = ''
  newBuilding.street = ''
  newBuilding.postalCode = ''
  await import('vue').then(m => m.nextTick())
  console.log('[geo-watch] cleared, filling:', _pendingGeoData)
  // 再填入新值
  Object.assign(newBuilding, _pendingGeoData)
  console.log('[geo-watch] newBuilding after:', JSON.parse(JSON.stringify(newBuilding)))
  _pendingGeoData = null
})

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
    if(!r.ok) { ElMessage.warning('逆地理编码请求失败，请检查网络'); return }
    const d=await r.json()
    if(!d?.address) { ElMessage.warning('该位置无地址信息，请尝试其他位置'); return }
    const a = d.address
    const road = a.road || a.pedestrian || a.path || a.footway || ''
    const hn = a.house_number || ''
    _pendingGeoData = {
      country: a.country || newBuilding.country,
      city: a.city || a.town || a.municipality || a.village || a.hamlet || '',
      district: a.suburb || a.borough || a.city_district || a.county || a.state_district || '',
      street: hn ? `${hn} ${road}`.trim() : road,
      postalCode: a.postcode || newBuilding.postalCode,
    }
    console.log('[reverseGeocode] triggering watch with:', _pendingGeoData)
    _geoTrigger.value++
    console.log('[reverseGeocode] _geoTrigger =', _geoTrigger.value)
    ElMessage.success('已从地图反向定位，地址字段已自动填充')
  }catch(e){
    console.error('[reverseGeocode]', e)
    ElMessage.error('逆地理编码失败: ' + (e instanceof Error ? e.message : '网络异常，请稍后重试'))
  }
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
    await buildingService.create(p)
    showBuildingDialog.value = false
    onBldDialogClosed()
    ElMessage.success('公寓创建成功')
    loadBuildings()
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.response?.data?.error?.message || '创建失败')
  } finally { creatingBuilding.value = false }
}

async function fetchList() {
  loading.value = true
  try {
    const params: any = { page_size: 500 }
    if (filterInstituteId.value) params.institute_id = filterInstituteId.value
    const r = await api.get('/unit-types', { params })
    allUnitTypes.value = (r.data.items || []).map((ut: any) => ({
      ...ut,
      image_urls: (ut.images || []).map((img: any) => '/api/v1/uploads/' + img.filename),
    }))
    // 自动展开有数据的公寓
    expandedIds.value = new Set(
      buildings.value.filter(b => getBuildingUnitTypes(b.id).length > 0).map(b => b.id)
    )
  } catch { /* */ }
  finally { loading.value = false }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除户型「${row.name}」？该户型将进入回收站。`, '警告', { type: 'warning' })
    await api.delete('/unit-types/' + row.id)
    ElMessage.success('已移至回收站')
    allUnitTypes.value = allUnitTypes.value.filter(u => u.id !== row.id)
    loadTrash()
  } catch { /* cancelled */ }
}
</script>

<style scoped>
h2 { font-size: 22px; color: #303133; margin: 0 }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px }

.building-card { border-left: 3px solid var(--primary, #FF6B35) }
.building-header {
  display: flex; justify-content: space-between; align-items: center;
  cursor: pointer; user-select: none; padding: 4px 0;
}
.building-header:hover { opacity: 0.85 }
.building-info { display: flex; align-items: center; gap: 10px; flex: 1 }
.building-icon { font-size: 20px }
.building-name { font-weight: 600; font-size: 15px; color: #303133 }
.building-addr { color: #909399; font-size: 13px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
.building-actions { display: flex; gap: 6px; margin-right: 16px }
.building-toggle { display: flex; align-items: center; transition: transform 0.2s; cursor: pointer }
.building-toggle .rotated { transform: rotate(180deg) }
.building-table { margin-top: 12px }

/* ═══════════ 户型卡片 ═══════════ */
.ut-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ut-card {
  display: flex;
  align-items: stretch;
  gap: 0;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  overflow: hidden;
  transition: box-shadow 0.15s;
}

.ut-card:hover {
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}

/* 左侧缩略图 */
.utc-thumb {
  width: 100px;
  flex-shrink: 0;
  background: #f5f6f8;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 32px;
  color: #c0c4cc;
}

.utc-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.utc-thumb-placeholder {
  font-size: 32px;
  color: #c0c4cc;
}

/* 中间信息 */
.utc-info {
  flex: 1;
  min-width: 0;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.utc-name {
  font-size: 16px;
  font-weight: 700;
  color: #1a1a2e;
  line-height: 1.3;
}

.utc-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.utc-tag {
  font-size: 13px;
  color: #606266;
  background: #f5f7fa;
  padding: 2px 10px;
  border-radius: 6px;
  font-weight: 500;
}

.utc-amenities {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.utc-amenity {
  font-size: 11px;
  color: #909399;
  background: #fafafa;
  border: 1px solid #eee;
  padding: 2px 8px;
  border-radius: 4px;
}

/* 右侧价格+操作 */
.utc-right {
  flex-shrink: 0;
  padding: 14px 18px;
  border-left: 1px solid #f0f2f5;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 4px;
  min-width: 170px;
}

.utc-price {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.utc-price-val {
  font-size: 20px;
  font-weight: 700;
  color: #f56c6c;
}

.utc-price-unit {
  font-size: 13px;
  color: #909399;
}

.utc-deposit {
  font-size: 12px;
  color: #909399;
}

.utc-lease {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.utc-actions {
  display: flex;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.utc-empty {
  padding: 24px;
  text-align: center;
  color: #c0c4cc;
  font-size: 14px;
}
.trash-time {
  font-size: 11px;
  color: #c0c4cc;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .ut-card {
    flex-direction: column;
  }
  .utc-thumb {
    width: 100%;
    height: 140px;
  }
  .utc-right {
    border-left: none;
    border-top: 1px solid #f0f2f5;
    flex-direction: row;
    flex-wrap: wrap;
    justify-content: flex-start;
    gap: 10px;
    padding: 12px 18px;
  }
}
</style>

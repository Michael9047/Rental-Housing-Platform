<template>
  <BmPageShell eyebrow="BM WORKSPACE" title="户型管理" description="按公寓集中维护户型、库存与展示状态。">
    <template #actions>
      <div class="header-actions">
        <el-radio-group v-model="viewMode" size="small">
          <el-radio-button value="active">管理中</el-radio-button>
          <el-radio-button value="offline">已下架</el-radio-button>
          <el-radio-button value="trash">回收站</el-radio-button>
        </el-radio-group>
        <el-button v-if="viewMode==='active'" type="primary" @click="$router.push('/unit-type/create')">+ 发布户型</el-button>
        <el-button v-if="viewMode==='active'" @click="showBuildingDialog = true">+ 新建公寓</el-button>
      </div>
    </template>
    <template #summary><BmSummaryStrip :items="inventorySummary" :active-key="viewMode" @select="selectInventoryView" /></template>

    <!-- 三种状态共用同一筛选栏 -->
    <template #toolbar>
      <div class="unit-toolbar">
          <el-select v-model="filterInstituteId" placeholder="全部公寓" clearable filterable>
            <el-option v-for="b in buildings" :key="b.id" :label="`${b.name} (${getUnitTypeCount(b.id)}个户型)`" :value="b.id" />
          </el-select>
          <el-input-number v-model="filterRentMin" placeholder="最低租金" :min="0" controls-position="right" />
          <el-input-number v-model="filterRentMax" placeholder="最高租金" :min="0" controls-position="right" />
          <el-input-number v-model="filterAreaMin" placeholder="最小面积" :min="0" controls-position="right" />
          <el-input-number v-model="filterAreaMax" placeholder="最大面积" :min="0" controls-position="right" />
          <span class="filter-result">当前显示 {{ displayedUnitTypes.length }} 个户型</span>
          <el-button @click="resetFilters">重置</el-button>
      </div>
    </template>

    <el-table :data="displayedUnitTypes" v-loading="viewMode==='trash' ? trashLoading : loading" stripe
      :empty-text="viewMode==='trash' ? '回收站为空' : (viewMode==='offline' ? '暂无已下架户型' : '暂无户型数据')"
      table-layout="fixed" class="unit-table">
      <el-table-column label="户型" min-width="200">
        <template #default="{row}"><div class="unit-primary">
          <el-image v-if="row.image_urls?.[0]" :src="row.image_urls[0]" :preview-src-list="row.image_urls" preview-teleported fit="cover" />
          <div v-else class="unit-image-placeholder">暂无图片</div>
          <div class="primary-cell"><strong>{{ row.name }}</strong><span>{{ row.property_type || '类型待补充' }}</span></div>
        </div></template>
      </el-table-column>
      <el-table-column label="所属公寓" min-width="170" show-overflow-tooltip>
        <template #default="{row}"><div class="primary-cell"><strong>{{ unitBuilding(row)?.name || row.institute_name || '未知公寓' }}</strong><span>{{ buildingLocation(unitBuilding(row)) }}</span></div></template>
      </el-table-column>
      <el-table-column label="规格" width="130"><template #default="{row}"><div class="primary-cell"><strong>{{ row.bedrooms }}室 {{ row.hall_count }}厅 {{ row.bathrooms }}卫</strong><span>{{ row.area_sqm ? `${row.area_sqm}㎡` : '面积待补充' }}</span></div></template></el-table-column>
      <el-table-column label="订单 / 库存" width="115"><template #default="{row}"><strong class="inventory-value">{{ row.rented_count ?? 0 }} / {{ row.total_count ?? 0 }}</strong><div class="cell-note">生效订单 / 总量</div></template></el-table-column>
      <el-table-column label="租金" width="120"><template #default="{row}"><strong class="rent-value">{{ currencySym(row.currency) }}{{ Number(row.base_rent || 0).toLocaleString() }}</strong><span class="rent-period">{{ row.rent_period === 'weekly' ? '/周' : '/月' }}</span></template></el-table-column>
      <el-table-column v-if="viewMode!=='trash'" label="状态" width="105"><template #default="{row}"><el-tag :type="listingStatusTag(row.status)">{{ listingStatusLabel('unitType', row.status) }}</el-tag><div v-if="unitBuilding(row) && parentVisibilityHint(unitBuilding(row)?.status)" class="cell-note warning-note">{{ parentVisibilityHint(unitBuilding(row)?.status) }}</div></template></el-table-column>
      <el-table-column v-else label="删除时间" width="175"><template #default="{row}">{{ row.deleted_at ? fmtTime(row.deleted_at) : '-' }}</template></el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{row}">
          <template v-if="viewMode!=='trash'">
            <el-button link type="primary" @click="$router.push(`/unit-type/${row.id}/edit`)">编辑</el-button>
            <el-button v-if="listingPrimaryAction(row.status)==='offline'" link type="warning" @click="changeUnitLifecycle(row, 'offline')">下架</el-button>
            <el-button v-if="listingPrimaryAction(row.status)==='publish'" link type="success" @click="changeUnitLifecycle(row, 'publish')">重新上架</el-button>
            <el-dropdown trigger="click" @command="(command:string)=>handleUnitAction(row, command)"><el-button text>更多</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="copy">复制户型</el-dropdown-item><el-dropdown-item divided command="delete">移入回收站</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
          </template>
          <template v-else>
            <el-button link type="primary" @click="restoreUnitType(row.id)">恢复</el-button>
            <el-popconfirm title="确定永久删除？不可恢复！" @confirm="hardDeleteUnitType(row.id)"><template #reference><el-button link type="danger">永久删除</el-button></template></el-popconfirm>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <BuildingCreateDialog v-model="showBuildingDialog" @created="onSharedBuildingCreated" />
    <!-- 旧内联弹窗仅保留代码迁移期间参考，不再渲染。 -->
    <el-dialog v-if="false" v-model="showBuildingDialog" title="新建公寓" width="720px" :close-on-click-modal="false" @opened="onBldDialogOpened" @closed="onBldDialogClosed">
      <el-form :model="newBuilding" label-width="100px">
        <el-form-item label="公寓名称" required><el-input v-model="newBuilding.name" placeholder="中/英文均可" maxlength="200" /></el-form-item>
        <el-divider>📍 地址与定位</el-divider>
        <div v-if="bldFormVisible">
        <el-form-item label="国家"><el-autocomplete v-model="newBuilding.country" :fetch-suggestions="filterCountries" placeholder="输入或选择国家" clearable style="width:100%" /></el-form-item>
        <el-form-item label="城市"><el-input v-model="newBuilding.city" placeholder="如：伦敦、上海" maxlength="100" /></el-form-item>
        <el-form-item label="区域"><el-input v-model="newBuilding.district" placeholder="如：肯辛顿、浦东" maxlength="100" /></el-form-item>
        <el-form-item label="街道/门牌号"><el-input v-model="newBuilding.street" placeholder="如：105 Cheyne Walk" maxlength="200" /></el-form-item>
        <el-form-item label="邮编"><el-input v-model="newBuilding.postalCode" placeholder="选填" maxlength="20" style="width:200px" /></el-form-item>
        </div>
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
  </BmPageShell>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { toUserFriendly } from '@/services/api'
import { loadTiles, type TileHandle } from '@/services/tileDetector'
import { buildingService, type Building } from '@/services/building'
import { createLogger } from '@/utils/logger'
import ImageUploader from '@/components/ImageUploader.vue'
import BuildingCreateDialog from '@/components/building/BuildingCreateDialog.vue'
import BmPageShell from '@/components/bm/BmPageShell.vue'
import BmSummaryStrip, { type BmSummaryItem } from '@/components/bm/BmSummaryStrip.vue'
import { propertyService } from '@/services/property'
import { listingPrimaryAction, listingStatusLabel, listingStatusTag, parentVisibilityHint } from '@/utils/listingStatus'

const log = createLogger('ManageProperties')

const allUnitTypes = ref<any[]>([])
const trashItems = ref<any[]>([])
const trashLoading = ref(false)
const viewMode = ref<'active'|'offline'|'trash'>('active')
const currencyMap: Record<string, string> = { CNY:'¥', USD:'$', GBP:'£', EUR:'€', AUD:'A$', SGD:'S$', CAD:'C$', HKD:'HK$', JPY:'¥', KRW:'₩' }
function currencySym(code?: string) { return currencyMap[code || 'CNY'] || '¥' }
const buildings = ref<Building[]>([])
const loading = ref(false)
const filterInstituteId = ref<number | undefined>()
const filterRentMin = ref<number | undefined>()
const filterRentMax = ref<number | undefined>()
const filterAreaMin = ref<number | undefined>()
const filterAreaMax = ref<number | undefined>()
const inventorySummary = computed<BmSummaryItem[]>(() => [
  { key: 'active', label: '展示中', value: allUnitTypes.value.filter((item)=>item.status!=='offline').length, note: '租客端可见' },
  { key: 'offline', label: '已下架', value: allUnitTypes.value.filter((item)=>item.status==='offline').length, note: '保留资料与历史' },
  { key: 'trash', label: '回收站', value: trashItems.value.length, note: '可恢复或永久删除' },
])
const filteredTrashItems = computed(() => trashItems.value.filter((item) => {
  if (filterInstituteId.value && item.institute_id !== filterInstituteId.value) return false
  if (filterRentMin.value != null && Number(item.base_rent) < filterRentMin.value) return false
  if (filterRentMax.value != null && Number(item.base_rent) > filterRentMax.value) return false
  if (filterAreaMin.value != null && Number(item.area_sqm) < filterAreaMin.value) return false
  if (filterAreaMax.value != null && Number(item.area_sqm) > filterAreaMax.value) return false
  return true
}))
const filteredManagedItems = computed(() => allUnitTypes.value.filter((item) => {
  if (viewMode.value === 'offline' ? item.status !== 'offline' : item.status === 'offline') return false
  if (filterInstituteId.value && item.institute_id !== filterInstituteId.value) return false
  if (filterRentMin.value != null && Number(item.base_rent) < filterRentMin.value) return false
  if (filterRentMax.value != null && Number(item.base_rent) > filterRentMax.value) return false
  if (filterAreaMin.value != null && Number(item.area_sqm) < filterAreaMin.value) return false
  if (filterAreaMax.value != null && Number(item.area_sqm) > filterAreaMax.value) return false
  return true
}))
const displayedUnitTypes = computed(() => viewMode.value === 'trash' ? filteredTrashItems.value : filteredManagedItems.value)
const buildingsById = computed(() => new Map(buildings.value.map((building) => [building.id, building])))
function selectInventoryView(key:string) { viewMode.value = key as typeof viewMode.value }

function getUnitTypeCount(buildingId: number) {
  return allUnitTypes.value.filter(u => u.institute_id === buildingId).length
}

function unitBuilding(unitType: any): Building | undefined {
  return buildingsById.value.get(unitType.institute_id)
}

function buildingLocation(building?: Building): string {
  if (!building) return '公寓资料待补充'
  return [building.city, building.country].filter(Boolean).join(' · ') || building.address || '地区待补充'
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
      image_urls: ut.images?.length
        ? ut.images.map((img: any) => '/api/v1/uploads/' + img.filename)
        : (ut.image_urls || []),
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
    ElMessage.error(toUserFriendly(e))
  }
}

async function hardDeleteUnitType(id: number) {
  try {
    await api.delete('/unit-types/' + id + '/hard')
    ElMessage.success('已永久删除')
    loadTrash()
    fetchList()
  } catch (e: any) {
    ElMessage.error(toUserFriendly(e))
  }
}

async function loadBuildings() {
  try { buildings.value = await buildingService.list({ limit: 200 }) } catch { /* */ }
}

async function onSharedBuildingCreated() {
  await loadBuildings()
  await fetchList()
}

async function changeBuildingLifecycle(building: Building, action: 'offline'|'publish') {
  try {
    const result = action === 'offline' ? await buildingService.batchOffline([building.id]) : await buildingService.batchPublish([building.id])
    if (result.failed) throw new Error(result.errors?.[0]?.error || '公寓状态更新失败')
    ElMessage.success(action === 'offline' ? '公寓已下架' : '公寓已重新上架')
    await loadBuildings()
  } catch (e:any) { ElMessage.error(toUserFriendly(e)) }
}

async function changeUnitLifecycle(unitType:any, action:'offline'|'publish') {
  try {
    const result = action === 'offline' ? await propertyService.batchOffline([unitType.id]) : await propertyService.batchPublish([unitType.id])
    if (result.failed) {
      const failure = result.errors?.[0]
      if (action === 'publish') {
        const fieldLabels: Record<string, string> = {
          institute_id: '所属公寓', property_type: '户型类型', base_rent: '基础租金', currency: '币种',
          total_count: '总库存', available_count: '可用库存', available_from: '最早入住日期', image_urls: '户型图片',
        }
        const missing = (failure?.missing_fields || []).map((field:string) => fieldLabels[field] || field)
        const message = missing.length
          ? `该户型暂时不能公开展示，请先补充：${missing.join('、')}。`
          : (failure?.error || '户型重新上架失败')
        try {
          await ElMessageBox.confirm(message, '重新上架前需完善资料', { confirmButtonText: '前往编辑', cancelButtonText: '取消', type: 'warning' })
          location.href = `/unit-type/${unitType.id}/edit`
        } catch { /* 取消 */ }
        return
      }
      throw new Error(failure?.error || '户型状态更新失败')
    }
    ElMessage.success(action === 'offline' ? '户型已下架' : '户型已重新上架')
    await fetchList()
  } catch (e:any) {
    ElMessage.error(toUserFriendly(e))
  }
}

function handleUnitAction(unitType: any, command: string) {
  if (command === 'copy') location.href = `/unit-type/${unitType.id}/copy`
  if (command === 'delete') handleDelete(unitType)
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
const bldFormVisible = ref(true)

const securityAmenitiesBld = ['24小时安保','监控系统(CCTV)','智能门禁','电子门锁','前台/礼宾','消防系统','夜间巡逻']
const serviceAmenitiesBld = ['代收包裹','维修服务','公共区域保洁','定期社交活动','接机服务','班车接驳','入住礼包','管家服务']
const facilityAmenitiesBld = ['电梯','洗衣房','自行车库','停车场','公共厨房','快递柜/信箱','自习室','影音室','公共休闲区','屋顶露台','庭院/花园','会议室']
const sportAmenitiesBld = ['健身房','游泳池','篮球场','瑜伽室','游戏室','BBQ区','乒乓球/台球']

let bldMapInst:any=null, bldMarkerInst:any=null, _bldTileHandle: TileHandle|null=null

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
  bldMapInst = L.map(bldMapEl.value, {center, zoom, attributionControl: false})
  _bldTileHandle = await loadTiles(bldMapInst, newBuilding.country)
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
  _bldTileHandle?.destroy(); _bldTileHandle = null
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
    if (a.country) newBuilding.country = a.country
    newBuilding.city = a.city || a.town || a.municipality || a.village || a.hamlet || ''
    newBuilding.district = a.suburb || a.borough || a.city_district || a.county || a.state_district || ''
    newBuilding.street = hn ? `${hn} ${road}`.trim() : road
    if (a.postcode) newBuilding.postalCode = a.postcode
    // v-if 开关强制重建地址输入区
    bldFormVisible.value = false
    await import('vue').then(m => m.nextTick())
    bldFormVisible.value = true
    ElMessage.success('已从地图反向定位，地址字段已自动填充')
  }catch(e){
    log.error('逆地理编码失败', { action: 'reverseGeocode' }, e)
    ElMessage.error(toUserFriendly(e))
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
    ElMessage.error(toUserFriendly(e))
  } finally { creatingBuilding.value = false }
}

async function fetchList() {
  loading.value = true
  try {
    const params: any = { page_size: 500 }
    const r = await api.get('/unit-types', { params })
    allUnitTypes.value = (r.data.items || []).map((ut: any) => ({
      ...ut,
      image_urls: ut.images?.length
        ? ut.images.map((img: any) => '/api/v1/uploads/' + img.filename)
        : (ut.image_urls || []),
    }))
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
.header-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.unit-toolbar { display: grid; grid-template-columns: minmax(180px, 1.35fr) repeat(4, minmax(120px, 1fr)) auto auto; align-items: center; gap: 10px; }
.unit-toolbar :deep(.el-select), .unit-toolbar :deep(.el-input-number) { width: 100%; }
.filter-result { color: var(--text-muted); font-size: 13px; white-space: nowrap; }
.unit-table { width: 100%; overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius); }
.unit-primary { display: grid; grid-template-columns: 64px minmax(0, 1fr); align-items: center; gap: 12px; }
.unit-primary :deep(.el-image), .unit-image-placeholder { width: 64px; height: 48px; border-radius: 8px; }
.unit-primary :deep(.el-image) { background: var(--surface-muted); }
.unit-image-placeholder { display: grid; place-items: center; box-sizing: border-box; border: 1px dashed var(--border); background: var(--surface-muted); color: var(--text-muted); font-size: 11px; }
.primary-cell { display: grid; min-width: 0; gap: 4px; }
.primary-cell strong { overflow: hidden; color: var(--text-primary); text-overflow: ellipsis; white-space: nowrap; }
.primary-cell span, .cell-note { color: var(--text-muted); font-size: 12px; }
.inventory-value { color: var(--primary); font-size: 15px; }
.rent-value { color: #d95d2a; font-size: 15px; }
.rent-period { margin-left: 3px; color: var(--text-muted); font-size: 12px; }
.warning-note { margin-top: 5px; color: var(--warning, #b88230); white-space: normal; }

@media (max-width: 1100px) { .unit-toolbar { grid-template-columns: repeat(3, minmax(150px, 1fr)); } }
@media (max-width: 720px) { .header-actions { align-items: flex-start; flex-direction: column; } .unit-toolbar { grid-template-columns: 1fr; } }
</style>

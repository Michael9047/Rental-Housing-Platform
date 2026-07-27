<template>
  <div class="building-page">
    <h2>🏢 公寓管理</h2>
    <p class="sub">管理公寓信息，配置户型与人员。</p>

    <!-- 管理/回收站 切换 -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
      <el-radio-group v-model="viewMode" size="small">
        <el-radio-button value="active">📋 管理中</el-radio-button>
        <el-radio-button value="trash">🗑️ 回收站</el-radio-button>
      </el-radio-group>
      <el-button v-if="viewMode==='active'" type="primary" @click="openCreate">+ 新建公寓</el-button>
    </div>

    <!-- 管理模式：正常列表 -->
    <el-table v-if="viewMode==='active'" :data="buildings" v-loading="loading" border stripe>
      <el-table-column prop="name" label="公寓名称" min-width="160" />
      <el-table-column prop="address" label="地址" min-width="200" show-overflow-tooltip />
      <el-table-column prop="contact_phone" label="电话" width="130" />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{row}">
          <el-button size="small" @click="$router.push('/buildings/'+row.id+'/unit-types')">查看房型</el-button>
          <el-button size="small" @click="$router.push('/buildings/'+row.id+'/staff')">人员配置</el-button>
          <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="del(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 回收站模式 -->
    <div v-if="viewMode==='trash'" v-loading="trashLoading">
      <div v-if="!trashItems.length && !trashLoading" style="text-align:center;padding:40px;color:#909399">
        🗑️ 回收站为空
      </div>
      <div class="trash-cards" v-if="trashItems.length">
        <div v-for="b in trashItems" :key="b.id" class="trash-card">
          <div class="trash-card-left">
            <span class="trash-icon">🏢</span>
            <div class="trash-card-info">
              <div class="trash-card-name">{{ b.name }}</div>
              <div class="trash-card-meta" v-if="b.address">📍 {{ b.address }}</div>
              <div class="trash-card-meta" v-if="b.contact_phone">📞 {{ b.contact_phone }}</div>
            </div>
          </div>
          <div class="trash-card-right">
            <div style="text-align:right">
              <el-tag size="small" type="info">已删除</el-tag>
              <div class="trash-time" v-if="b.updated_at">{{ fmtTime(b.updated_at) }}</div>
            </div>
            <el-button size="small" type="primary" @click="restoreBuilding(b.id)">🔄 恢复</el-button>
            <el-popconfirm title="确定永久删除？不可恢复！" @confirm="hardDeleteBuilding(b.id)">
              <template #reference>
                <el-button size="small" type="danger" plain>💥 硬删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════ 新建/编辑对话框 ═══════ -->
    <el-dialog v-model="show" :title="editId?'编辑公寓':'新建公寓'" width="720px" :close-on-click-modal="false" @opened="onDialogOpened">
      <el-form ref="fRef" :model="f" label-width="100px">
        <el-form-item label="公寓名称" required><el-input v-model="f.name" placeholder="中/英文均可" maxlength="200" /></el-form-item>

        <!-- ═══ 结构化地址 + 地图定位 ═══ -->
        <el-divider>📍 地址与定位</el-divider>

        <!-- 国家：带建议的输入框，可自由输入/修改/删除 -->
        <el-form-item label="国家" required>
          <el-autocomplete v-model="f.country" :fetch-suggestions="filterCountries" placeholder="输入或选择国家，如：英国、美国、日本" clearable style="width:100%" />
        </el-form-item>

        <!-- 城市 -->
        <el-form-item label="城市">
          <el-input v-model="f.city" placeholder="如：伦敦、上海、新加坡" maxlength="100" />
        </el-form-item>

        <!-- 区域 -->
        <el-form-item label="区域">
          <el-input v-model="f.district" placeholder="如：肯辛顿、浦东、市中心" maxlength="100" />
        </el-form-item>

        <!-- 街道+门牌号 -->
        <el-form-item label="街道/门牌号">
          <el-input v-model="f.street" placeholder="如：105 Cheyne Walk 或 南京路100号" maxlength="200" />
        </el-form-item>

        <!-- 邮编 -->
        <el-form-item label="邮编">
          <el-input v-model="f.postalCode" placeholder="选填" maxlength="20" style="width:200px" />
        </el-form-item>

        <!-- 定位按钮 + 状态 + 清空 -->
        <el-form-item label="地图定位">
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
            <el-button type="primary" @click="geocodeStructured" :loading="geoLoading" :disabled="!canGeocode">
              📍 检索定位
            </el-button>
            <el-tag v-if="f.lat!=null && f.lng!=null" type="success" effect="dark" size="small">
              ✅ 已定位 ({{ f.lat.toFixed(4) }}, {{ f.lng.toFixed(4) }})
            </el-tag>
            <el-tag v-else type="danger" effect="dark" size="small">
              ❌ 未定位
            </el-tag>
            <el-button size="small" type="danger" plain style="margin-left:auto" @click="clearAddressFields">🗑️ 一键清空</el-button>
          </div>
          <div ref="mapEl" style="width:100%;height:280px;border-radius:8px;border:1px solid #dcdfe6;"></div>
          <div style="color:#909399;font-size:12px;margin-top:4px">
            💡 <b>正向</b>：填地址 → 检索定位；<b>反向</b>：点地图 → 自动回填
          </div>
        </el-form-item>

        <el-divider>联系方式</el-divider>
        <el-form-item label="负责人姓名"><el-input v-model="f.mgrName" /></el-form-item>
        <el-form-item label="负责人电话"><el-input v-model="f.mgrPhone" /></el-form-item>
        <el-form-item label="负责人邮箱"><el-input v-model="f.mgrEmail" /></el-form-item>
        <el-form-item label="前台电话"><el-input v-model="f.contact_phone" /></el-form-item>

        <el-divider>公寓介绍</el-divider>
        <el-form-item>
          <el-input v-model="f.description" type="textarea" :rows="10" maxlength="5000" show-word-limit />
        </el-form-item>

        <!-- 公寓配套 — 四大板块 -->
        <el-divider>🛡️ 安保</el-divider>
        <el-form-item>
          <el-checkbox-group v-model="selectedAmenities" class="amenity-group">
            <el-checkbox v-for="a in securityAmenities" :key="a" :label="a" :value="a" border size="small" />
          </el-checkbox-group>
        </el-form-item>

        <el-divider>🛎️ 服务</el-divider>
        <el-form-item>
          <el-checkbox-group v-model="selectedAmenities" class="amenity-group">
            <el-checkbox v-for="a in serviceAmenities" :key="a" :label="a" :value="a" border size="small" />
          </el-checkbox-group>
        </el-form-item>

        <el-divider>🏠 公用设施</el-divider>
        <el-form-item>
          <el-checkbox-group v-model="selectedAmenities" class="amenity-group">
            <el-checkbox v-for="a in facilityAmenities" :key="a" :label="a" :value="a" border size="small" />
          </el-checkbox-group>
        </el-form-item>

        <el-divider>⚽ 运动娱乐</el-divider>
        <el-form-item>
          <el-checkbox-group v-model="selectedAmenities" class="amenity-group">
            <el-checkbox v-for="a in sportAmenities" :key="a" :label="a" :value="a" border size="small" />
          </el-checkbox-group>
        </el-form-item>

        <!-- 特殊标记 -->
        <el-divider>🔖 特殊标记</el-divider>
        <el-form-item label="女生独栋">
          <el-switch v-model="f.femaleOnly" active-text="是" inactive-text="否" />
          <span style="color:#909399;font-size:12px;margin-left:8px">存在仅限女性住户入住的公寓楼栋</span>
        </el-form-item>
        <el-form-item label="支持情侣">
          <el-switch v-model="f.couplesAllowed" active-text="是" inactive-text="否" />
          <span style="color:#909399;font-size:12px;margin-left:8px">存在允许情侣双人入住同一房间</span>
        </el-form-item>

        <!-- 公寓公共图集 -->
        <el-divider>公寓公共图集</el-divider>
        <el-form-item label="公寓照片">
          <ImageUploader
            ref="imageUploaderRef"
            title="公寓楼栋外观、大堂、公共设施实拍"
            hint="至少3张，最多20张，支持拖拽排序，首张为封面"
            :min-files="3"
            :max-files="20"
            v-model="uploadedImages"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialog" :disabled="saving">取消</el-button>
        <el-tooltip :content="saveDisabledReason" :disabled="!saveDisabledReason" placement="top">
          <el-button type="primary" :loading="saving" :disabled="saving || !!saveDisabledReason" @click="save">确定保存</el-button>
        </el-tooltip>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { buildingService } from '@/services/building'
import api from '@/services/api'
import ImageUploader from '@/components/ImageUploader.vue'

const buildings = ref<any[]>([])
const trashItems = ref<any[]>([])
const loading = ref(false); const trashLoading = ref(false)
const show = ref(false); const saving = ref(false); const geoLoading = ref(false)
const editId = ref<number|null>(null)
const viewMode = ref<'active'|'trash'>('active')
const selectedAmenities = ref<string[]>([])
const uploadedImages = ref<string[]>([])
const imageUploaderRef = ref<InstanceType<typeof ImageUploader>>()
const mapEl = ref<HTMLElement|null>(null)
const f = reactive({
  name:'', address:'', contact_phone:'', description:'',
  country:'', city:'', district:'', street:'', postalCode:'',
  mgrName:'', mgrPhone:'', mgrEmail:'',
  lat:null as number|null, lng:null as number|null,
  femaleOnly:false, couplesAllowed:false
})

// 预定义国家列表（也可手动输入）
const countryOptions = ['中国','英国','美国','澳大利亚','加拿大','新加坡','日本','韩国','法国','德国','马来西亚','泰国']

// el-autocomplete 的筛选回调
function filterCountries(query: string, cb: Function) {
  if (!query) { cb(countryOptions.map(v => ({value:v}))); return }
  const q = query.toLowerCase()
  cb(countryOptions.filter(c => c.toLowerCase().includes(q) || c.includes(query)).map(v => ({value:v})))
}

// 是否可以执行地理编码（至少填了国家或城市）
const canGeocode = computed(() => !!(f.country || f.city))

// 保存按钮禁用逻辑：新建时必须有坐标
const saveDisabledReason = computed(() => {
  if (!editId.value && (f.lat == null || f.lng == null)) {
    return '请先点击「📍 检索定位」确认公寓坐标后再保存'
  }
  return ''
})

// 公寓级配套
const securityAmenities = ['24小时安保','监控系统(CCTV)','智能门禁','电子门锁','前台/礼宾','消防系统','夜间巡逻']
const serviceAmenities = ['代收包裹','维修服务','公共区域保洁','定期社交活动','接机服务','班车接驳','入住礼包','管家服务']
const facilityAmenities = ['电梯','洗衣房','自行车库','停车场','公共厨房','快递柜/信箱','自习室','影音室','公共休闲区','屋顶露台','庭院/花园','会议室']
const sportAmenities = ['健身房','游泳池','篮球场','瑜伽室','游戏室','BBQ区','乒乓球/台球']

// ── 地图 ──
let mapInst:any=null, markerInst:any=null

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
    s.onload=()=>r(getL())
    document.head.appendChild(s)
  })
}

async function initMap(lat:number|null, lng:number|null){
  await nextTick()
  if(!mapEl.value) return
  // 清理旧地图实例
  if(mapInst){ try{mapInst.remove()}catch(e){} mapInst=null;markerInst=null }
  const L = await ensureLeaflet()
  const center:[number,number] = (lat!=null&&lng!=null&&isFinite(lat)&&isFinite(lng)) ? [lat,lng] : [31.27,120.73]
  const zoom = (lat!=null&&lng!=null) ? 17 : 12
  mapInst = L.map(mapEl.value, {center, zoom})
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy;OSM',maxZoom:19}).addTo(mapInst)
  mapInst.on('click', (e:any)=>{ placeMarker(e.latlng.lat, e.latlng.lng, true) })
  if(lat!=null && lng!=null) placeMarker(lat, lng, false)
}

function placeMarker(lat:number, lng:number, rev:boolean){
  const L=getL(); if(!L||!mapInst) return
  if(markerInst) markerInst.setLatLng([lat,lng])
  else {
    markerInst = L.marker([lat,lng],{draggable:true}).addTo(mapInst)
    markerInst.on('dragend', ()=>{ const p=markerInst.getLatLng(); f.lat=p.lat; f.lng=p.lng })
  }
  f.lat=lat; f.lng=lng
  if(rev) reverseGeocode(lat,lng)
}

function destroyMap(){
  if(mapInst){ try{mapInst.remove()}catch(e){} }
  mapInst=null; markerInst=null
}

async function geocodeStructured(){
  if(!canGeocode.value){ElMessage.warning('请至少填写国家或城市');return}
  geoLoading.value=true
  try{
    // 使用 Nominatim 结构化查询
    const params=new URLSearchParams({format:'json',limit:'1'})
    if(f.street) params.set('street',f.street)
    if(f.city) params.set('city',f.city)
    if(f.country) params.set('country',f.country)
    if(f.postalCode) params.set('postalcode',f.postalCode)
    const r=await fetch(`https://nominatim.openstreetmap.org/search?${params}`,{headers:{'User-Agent':'RH/1.0'}})
    const d=await r.json()
    if(d.length>0){
      const lat=parseFloat(d[0].lat),lng=parseFloat(d[0].lon)
      placeMarker(lat,lng,false);mapInst?.setView([lat,lng],17)
      // 不回写地址字段，保持用户输入的结构化地址
      ElMessage.success(`已定位 (${lat.toFixed(4)}, ${lng.toFixed(4)})`)
    }else{ElMessage.warning('未找到该地址，请检查地址信息或在地图上手动点击选点')}
  }catch(e){ElMessage.error('定位失败，请检查网络连接')}
  finally{geoLoading.value=false}
}

async function reverseGeocode(lat:number,lng:number){
  // 逆地理编码：点击地图 → 解析 Nominatim 结构化地址 → 回填字段
  try{
    const r=await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&accept-language=zh`,{headers:{'User-Agent':'RH/1.0'}})
    const d=await r.json()
    if(!d?.address) return
    const a = d.address

    // 国家 — 优先用中文名（Nominatim 的 country 在某些地区返回本地语言）
    if (a.country && !f.country) f.country = a.country

    // 城市 — 按优先级尝试
    if (!f.city) f.city = a.city || a.town || a.municipality || a.village || a.hamlet || ''

    // 区域 — 区/县/街道办
    if (!f.district) f.district = a.suburb || a.borough || a.city_district || a.county || a.state_district || ''

    // 街道+门牌号
    if (!f.street) {
      const road = a.road || a.pedestrian || a.path || a.footway || ''
      const hn = a.house_number || ''
      f.street = hn ? `${hn} ${road}`.trim() : road
    }

    // 邮编
    if (!f.postalCode) f.postalCode = a.postcode || ''

    ElMessage.success('已从地图反向定位，地址字段已自动填充')
  }catch(e){}
}

// ═══ dialog 生命周期 ═══
// 用 @opened 事件（dialog 动画完成后触发）来初始化地图
async function onDialogOpened(){
  await nextTick()
  await initMap(f.lat, f.lng)
}

// 一键清空所有地址字段（方便反向定位测试）
function clearAddressFields(){
  f.country=''; f.city=''; f.district=''; f.street=''; f.postalCode=''
  f.lat=null; f.lng=null
  if(markerInst){ markerInst.remove(); markerInst=null }
  ElMessage.success('地址字段已清空，可在地图上点击进行反向定位')
}

// 关闭时清理地图
function closeDialog(){
  destroyMap()
  show.value = false
  // 重置表单
  Object.assign(f,{name:'',address:'',contact_phone:'',description:'',country:'',city:'',district:'',street:'',postalCode:'',mgrName:'',mgrPhone:'',mgrEmail:'',lat:null,lng:null,femaleOnly:false,couplesAllowed:false})
  selectedAmenities.value=[]
  uploadedImages.value=[]
  editId.value=null
}

// ═══ 监听 viewMode ═══
watch(viewMode, (v)=>{ if(v==='trash') loadTrash() })

// ═══ CRUD ═══
async function load(){loading.value=true;try{buildings.value=await buildingService.list({limit:200})}catch(e){}finally{loading.value=false}}
async function loadTrash(){trashLoading.value=true;try{const r=await api.get('/buildings/recycle-bin',{params:{limit:2000}});trashItems.value=r.data||[]}catch(e){}finally{trashLoading.value=false}}

function fmtTime(iso:string):string{try{return new Date(iso).toLocaleString('zh-CN',{hour12:false})}catch{return iso}}

async function restoreBuilding(id:number){try{await api.post('/buildings/'+id+'/restore');ElMessage.success('已恢复');loadTrash();load()}catch(e:any){ElMessage.error(e?.response?.data?.detail||'恢复失败')}}
async function hardDeleteBuilding(id:number){try{await api.delete('/buildings/'+id+'/hard');ElMessage.success('已永久删除');loadTrash();load()}catch(e:any){ElMessage.error(e?.response?.data?.detail||'删除失败')}}

async function openCreate(){
  editId.value=null
  Object.assign(f,{name:'',address:'',contact_phone:'',description:'',country:'',city:'',district:'',street:'',postalCode:'',mgrName:'',mgrPhone:'',mgrEmail:'',lat:null,lng:null,femaleOnly:false,couplesAllowed:false})
  selectedAmenities.value=[]; uploadedImages.value=[]
  show.value=true
}

async function openEdit(b:any){
  editId.value=b.id
  f.name=b.name||''; f.address=b.address||''; f.contact_phone=b.contact_phone||''; f.description=b.description||''
  // 加载结构化地址
  f.country=b.country||''; f.city=b.city||''; f.district=b.district||''; f.street=b.street||''; f.postalCode=b.postal_code||''
  const blat=parseFloat(b.latitude), blng=parseFloat(b.longitude)
  f.lat=isNaN(blat)?null:blat; f.lng=isNaN(blng)?null:blng
  f.femaleOnly=b.female_only===true; f.couplesAllowed=b.couples_allowed===true
  f.mgrName=''; f.mgrPhone=''; f.mgrEmail=''
  selectedAmenities.value=b.amenities||[]
  uploadedImages.value=(b.images||[]).map((img:any)=>img.filename?`/api/v1/uploads/${img.filename}`:'').filter(Boolean)
  try{
    const r=await api.get('/buildings/'+b.id+'/staff',{params:{_t:Date.now()}})
    const mgr=(r.data||[]).find((s:any)=>s.role==='manager')
    if(mgr){f.mgrName=mgr.name||'';f.mgrPhone=mgr.phone||'';f.mgrEmail=mgr.notes||''}
  }catch(e){}
  show.value=true
}

async function save(){
  if(!f.name.trim()){ElMessage.warning('请输入公寓名称');return}
  // 新建时必须定位
  if(!editId.value && (f.lat==null || f.lng==null)){
    ElMessage.warning('请先点击「📍 检索定位」确认公寓坐标')
    return
  }
  saving.value=true
  const p:any={
    name:f.name.trim(),
    country:f.country.trim()||null, city:f.city.trim()||null,
    district:f.district.trim()||null, street:f.street.trim()||null,
    postal_code:f.postalCode.trim()||null,
    contact_phone:f.contact_phone.trim(),
    description:f.description.trim(),manager_name:f.mgrName.trim(),manager_phone:f.mgrPhone.trim(),
    manager_email:f.mgrEmail.trim(),amenities:selectedAmenities.value.length?selectedAmenities.value:null,
    female_only:f.femaleOnly,couples_allowed:f.couplesAllowed,
  }
  if(f.lat!=null)p.latitude=String(f.lat); if(f.lng!=null)p.longitude=String(f.lng)
  // 只有在新创建或图片有变更时才传 image_urls
  if(!editId.value || uploadedImages.value.length>0){
    p.image_urls = uploadedImages.value.length?uploadedImages.value.map((u:any)=>typeof u==='string'?u:u.url||u):null
  }
  try{
    if(editId.value){await buildingService.update(editId.value,p);ElMessage.success('已保存')}
    else{await buildingService.create(p);ElMessage.success('已创建')}
    closeDialog();load()
  }catch(e:any){
    const msg=e?.response?.data?.error?.message||e?.response?.data?.detail||'保存失败'
    ElMessage.error(typeof msg==='string'?msg:'保存失败')
  }finally{saving.value=false}
}

async function del(id:number){
  try{await ElMessageBox.confirm('确定删除？该公寓将进入回收站。','确认',{type:'warning'});await buildingService.remove(id);ElMessage.success('已移至回收站');load();loadTrash()}catch(e){}
}

onMounted(()=>{load();loadTrash()})
</script>

<style scoped>
.building-page{max-width:960px;margin:0 auto}
h2{font-size:22px;color:#303133;margin-bottom:8px}
.sub{color:#909399;margin-bottom:20px;font-size:14px}
.amenity-group{display:flex;flex-wrap:wrap;gap:6px}
.amenity-group .el-checkbox{margin-right:0}

.trash-cards{display:flex;flex-direction:column;gap:8px}
.trash-card{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;background:#fff;border:1px solid #ebeef5;border-radius:12px;transition:box-shadow 0.15s}
.trash-card:hover{box-shadow:0 2px 12px rgba(0,0,0,0.06)}
.trash-card-left{display:flex;align-items:center;gap:14px;flex:1;min-width:0}
.trash-icon{font-size:28px;opacity:0.6}
.trash-card-info{min-width:0}
.trash-card-name{font-size:16px;font-weight:600;color:#303133}
.trash-card-meta{font-size:13px;color:#909399;margin-top:2px}
.trash-card-right{display:flex;align-items:center;gap:12px;flex-shrink:0}
.trash-time{font-size:11px;color:#c0c4cc;margin-top:3px;white-space:nowrap}
</style>

<template>
  <div class="building-page">
    <h2>🏢 公寓管理</h2>
    <p class="sub">管理公寓信息，配置户型与人员。</p>
    <el-button type="primary" @click="openCreate" style="margin-bottom:20px">+ 新建公寓</el-button>

    <el-table :data="buildings" v-loading="loading" border stripe>
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

    <el-dialog v-model="show" :title="editId?'编辑公寓':'新建公寓'" width="720px" :close-on-click-modal="false" @closed="onClose">
      <el-form ref="fRef" :model="f" label-width="100px">
        <el-form-item label="公寓名称" required><el-input v-model="f.name" placeholder="中/英文均可" maxlength="200" /></el-form-item>

        <!-- 地址 + 定位按钮 -->
        <el-form-item label="详细地址" required>
          <div style="display:flex;gap:8px;width:100%">
            <el-input v-model="f.address" placeholder="输入中/英文地址，点击定位按钮检索" maxlength="300" style="flex:1" @keyup.enter="geocode" />
            <el-button type="primary" @click="geocode" :loading="geoLoading">📍 定位</el-button>
          </div>
        </el-form-item>

        <!-- 地图 -->
        <el-form-item label="地图定位">
          <div id="osm-map" style="width:100%;height:280px;border-radius:8px;border:1px solid #dcdfe6;"></div>
          <div style="color:#909399;font-size:12px;margin-top:4px">可点击地图直接选点，或拖拽标记微调位置</div>
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
            hint="支持多图上传、拖拽排序，首张为封面。仅用于公寓公共展示，户型图/房间图在对应页面单独上传。"
            :min-files="0"
            :max-files="15"
            v-model="uploadedImages"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="show=false" :disabled="saving">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">确定保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { buildingService } from '@/services/building'
import api from '@/services/api'
import ImageUploader from '@/components/ImageUploader.vue'

const buildings = ref<any[]>([])
const loading = ref(false); const show = ref(false); const saving = ref(false); const geoLoading = ref(false)
const editId = ref<number|null>(null)
const selectedAmenities = ref<string[]>([])
const uploadedImages = ref<string[]>([])
const imageUploaderRef = ref<InstanceType<typeof ImageUploader>>()
const f = reactive({ name:'', address:'', contact_phone:'', description:'', mgrName:'', mgrPhone:'', mgrEmail:'', lat:null as number|null, lng:null as number|null, femaleOnly:false, couplesAllowed:false })

// 公寓级配套 — 四大板块（异乡好居风格）
const securityAmenities = ['24小时安保','监控系统(CCTV)','智能门禁','电子门锁','前台/礼宾','消防系统','夜间巡逻']
const serviceAmenities = ['代收包裹','维修服务','公共区域保洁','定期社交活动','接机服务','班车接驳','入住礼包','管家服务']
const facilityAmenities = ['电梯','洗衣房','自行车库','停车场','公共厨房','快递柜/信箱','自习室','影音室','公共休闲区','屋顶露台','庭院/花园','会议室']
const sportAmenities = ['健身房','游泳池','篮球场','瑜伽室','游戏室','BBQ区','乒乓球/台球']

// ── Leaflet ──
let map:any=null, marker:any=null, L:any=null
async function leaflet(){if(L)return L;if((window as any).L){L=(window as any).L;return L};return new Promise(r=>{const s=document.createElement('script');s.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';s.onload=()=>{L=(window as any).L;r(L)};document.head.appendChild(s)})}
async function initMap(lat:number|null,lng:number|null){
  await nextTick();await new Promise(r=>setTimeout(r,300))
  const el=document.getElementById('osm-map');if(!el||map)return
  const lib=await leaflet()
  const ok=lat!=null&&lng!=null&&isFinite(lat)&&isFinite(lng)
  map=lib.map('osm-map',{center:ok?[lat!,lng!]:[31.27,120.73],zoom:ok?17:12})
  lib.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy;OSM',maxZoom:19}).addTo(map)
  map.on('click',(e:any)=>putMarker(e.latlng.lat,e.latlng.lng,true))
  if(ok)putMarker(lat!,lng!,false)
  setTimeout(()=>map?.invalidateSize(),500)
}
function putMarker(lat:number,lng:number,rev:boolean){
  if(!L||!map)return
  if(marker)marker.setLatLng([lat,lng]);else{marker=L.marker([lat,lng],{draggable:true}).addTo(map);marker.on('dragend',()=>{const p=marker.getLatLng();f.lat=p.lat;f.lng=p.lng;revGeo(p.lat,p.lng)})}
  f.lat=lat;f.lng=lng;if(rev)revGeo(lat,lng)
}
async function geocode(){
  const a=f.address.trim();if(!a||a.length<2){ElMessage.warning('请先输入地址');return}
  geoLoading.value=true
  try{
    const r=await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(a)}&limit=1`,{headers:{'User-Agent':'RH/1.0'}})
    const d=await r.json()
    if(d.length>0){
      const lat=parseFloat(d[0].lat),lng=parseFloat(d[0].lon);putMarker(lat,lng,false);map?.setView([lat,lng],17)
      f.address=d[0].display_name;ElMessage.success('已定位')
    }else{ElMessage.warning('未找到该地址，请尝试更详细的地址或在地图上直接点击')}
  }catch(e){console.error('geocode err',e);ElMessage.error('定位失败')}
  finally{geoLoading.value=false}
}
async function revGeo(lat:number,lng:number){try{const r=await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`,{headers:{'User-Agent':'RH/1.0'}});const d=await r.json();if(d?.display_name)f.address=d.display_name}catch(e){}}

// ── CRUD ──
async function load(){loading.value=true;try{buildings.value=await buildingService.list({limit:200})}catch(e){console.error('load err',e)}finally{loading.value=false}}
function openCreate(){editId.value=null;Object.assign(f,{name:'',address:'',contact_phone:'',description:'',mgrName:'',mgrPhone:'',mgrEmail:'',lat:null,lng:null,femaleOnly:false,couplesAllowed:false});selectedAmenities.value=[];uploadedImages.value=[];show.value=true;nextTick(()=>initMap(null,null))}
async function openEdit(b:any){
  editId.value=b.id
  f.name=b.name||'';f.address=b.address||'';f.contact_phone=b.contact_phone||'';f.description=b.description||''
  f.lat=typeof b.latitude==='number'?b.latitude:null;f.lng=typeof b.longitude==='number'?b.longitude:null
  f.femaleOnly=b.female_only===true
  f.couplesAllowed=b.couples_allowed===true
  f.mgrName='';f.mgrPhone='';f.mgrEmail=''
  selectedAmenities.value=b.amenities||[]
  uploadedImages.value = (b.images||[]).map((img:any) => img.filename ? `/api/v1/uploads/${img.filename}` : '').filter(Boolean)
  try{const r=await api.get('/buildings/'+b.id+'/staff',{params:{_t:Date.now()}});const mgr=(r.data||[]).find((s:any)=>s.role==='manager');if(mgr){f.mgrName=mgr.name||'';f.mgrPhone=mgr.phone||'';f.mgrEmail=mgr.notes||''}}catch(e){console.error('staff load err',e)}
  show.value=true
  await nextTick()
  await initMap(f.lat,f.lng)
}
function onClose(){Object.assign(f,{name:'',address:'',contact_phone:'',description:'',mgrName:'',mgrPhone:'',mgrEmail:'',lat:null,lng:null,femaleOnly:false,couplesAllowed:false});selectedAmenities.value=[];uploadedImages.value=[];editId.value=null;if(map){map.remove();map=null;marker=null}}
async function save(){
  if(!f.name.trim()){ElMessage.warning('请输入公寓名称');return}
  saving.value=true
  const p:any={name:f.name.trim(),address:f.address.trim(),contact_phone:f.contact_phone.trim(),description:f.description.trim(),manager_name:f.mgrName.trim(),manager_phone:f.mgrPhone.trim(),manager_email:f.mgrEmail.trim(),amenities:selectedAmenities.value.length?selectedAmenities.value:null,female_only:f.femaleOnly,couples_allowed:f.couplesAllowed,image_urls:uploadedImages.value.length?uploadedImages.value.map((u:any)=>typeof u==='string'?u:u.url||u):null}
  if(f.lat!=null)p.latitude=String(f.lat);if(f.lng!=null)p.longitude=String(f.lng)
  try{
    if(editId.value){await buildingService.update(editId.value,p);ElMessage.success('已保存')}
    else{await buildingService.create(p);ElMessage.success('已创建')}
    show.value=false;load()
  }catch(e:any){
    const msg=e?.response?.data?.error?.message||e?.response?.data?.detail||'保存失败'
    ElMessage.error(typeof msg==='string'?msg:'保存失败')
  }finally{saving.value=false}
}
async function del(id:number){try{await ElMessageBox.confirm('确定删除？','确认',{type:'warning'});await buildingService.remove(id);ElMessage.success('已删除');load()}catch(e){}}
onMounted(()=>{if(!document.getElementById('leaflet-css')){const c=document.createElement('link');c.id='leaflet-css';c.rel='stylesheet';c.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';document.head.appendChild(c)};load()})
</script>

<style scoped>
.building-page{max-width:960px;margin:0 auto}
h2{font-size:22px;color:#303133;margin-bottom:8px}
.sub{color:#909399;margin-bottom:20px;font-size:14px}
.amenity-group{display:flex;flex-wrap:wrap;gap:6px}
.amenity-group .el-checkbox{margin-right:0}
</style>

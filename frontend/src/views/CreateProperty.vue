<template>
  <div class="create-page">
    <h2>{{ isEdit ? '编辑房源' : '发布房源' }}</h2>

    <!-- ====== 发布模式选择（仅新建时） ====== -->
    <el-card v-if="!isEdit" shadow="never" class="mode-card">
      <el-radio-group v-model="uploadMode" size="large">
        <el-radio-button value="single">📝 单个发布</el-radio-button>
        <el-radio-button value="batch">📦 批量导入</el-radio-button>
      </el-radio-group>
    </el-card>

    <!-- ====== 批量导入跳转 ====== -->
    <template v-if="uploadMode==='batch' && !isEdit">
      <div class="batch-redirect">
        <el-result icon="info" title="批量导入功能" sub-title="支持 Excel/CSV 批量上传整栋房间">
          <template #extra>
            <el-button type="primary" @click="$router.push('/property/import')">前往批量导入</el-button>
            <el-button @click="uploadMode='single'">返回单个发布</el-button>
          </template>
        </el-result>
      </div>
    </template>

    <!-- ====== 单个发布表单 ====== -->
    <template v-if="uploadMode==='single'">
      <!-- AI智能解析 -->
      <el-card shadow="never" class="smart-card">
        <template #header><div class="smart-header"><span>🤖 AI 智能识别 — 粘贴房源描述自动填充</span><el-tag v-if="parseResult" :type="parseResult.confidence==='high'?'success':'warning'" size="small">{{ parseResult.confidence==='high'?'高置信度':'部分识别' }}</el-tag></div></template>
        <el-input v-model="rawText" type="textarea" :rows="4" placeholder="粘贴房源描述，AI自动提取字段。例如：工业园区翰林缘单身公寓1201室，月租2200元，38㎡独立卫浴..." />
        <div class="smart-actions">
          <el-button type="primary" :loading="parsing" @click="smartParse" :disabled="!rawText.trim()">⚡ 快速识别</el-button>
          <el-button type="warning" :loading="llmParsing" @click="llmSmartParse" :disabled="!rawText.trim()">🔮 AI 深度解析</el-button>
          <el-button @click="rawText='';parseResult=null">清空</el-button>
        </div>
      </el-card>

      <!-- 智能估价 -->
      <el-card v-if="showRentEstimate" shadow="never" class="estimate-card">
        <template #header><span>💰 智能租金预估</span></template>
        <el-row :gutter="12"><el-col :span="8"><div class="est-box"><div class="est-l">建议下限</div><div class="est-v g">¥{{ rentEstimate.lower_bound?.toLocaleString() }}</div></div></el-col><el-col :span="8"><div class="est-box hl"><div class="est-l">预测租金</div><div class="est-v o">¥{{ rentEstimate.predicted?.toLocaleString() }}</div></div></el-col><el-col :span="8"><div class="est-box"><div class="est-l">建议上限</div><div class="est-v y">¥{{ rentEstimate.upper_bound?.toLocaleString() }}</div></div></el-col></el-row>
      </el-card>

      <!-- 表单 -->
      <el-card shadow="never" v-loading="formLoading">
        <template #header><span>{{ isEdit ? '编辑房源信息' : '房源信息' }}</span></template>

        <div v-if="formLoading" style="text-align:center;padding:40px;color:#909399">正在加载房源数据...</div>
        <template v-else>
        <!-- 无公寓拦截提示 -->
        <el-alert v-if="!buildings.length && !isEdit"
          title="尚未创建任何公寓，发布房源前必须先去创建公寓"
          type="warning" :closable="false" show-icon
          style="margin-bottom:20px">
          <template #default>
            <el-button type="warning" size="small" @click="$router.push('/buildings')" style="margin-top:8px">前往创建公寓 →</el-button>
          </template>
        </el-alert>

        <el-form ref="formRef" :model="f" :rules="rules" label-width="100px" @submit.prevent="handleSubmit" :validate-on-rule-change="false">

          <!-- 公寓绑定（必选） -->
          <el-form-item label="所属公寓" prop="institute_id">
            <div style="display:flex;gap:8px;width:100%">
              <el-select v-model="f.institute_id" placeholder="选择公寓（必选）" filterable style="flex:1" @change="onBuildingChange">
                <el-option v-for="b in buildings" :key="b.id" :label="b.name" :value="b.id" />
              </el-select>
              <el-button type="primary" plain @click="showBuildingDialog=true">+ 新建公寓</el-button>
            </div>
            <div v-if="!buildings.length" style="color:#f56c6c;font-size:12px;margin-top:4px">⚠️ 尚未创建公寓，发布房源前需先创建公寓</div>
          </el-form-item>

          <el-divider content-position="left">基础信息</el-divider>

          <el-row :gutter="16">
            <el-col :span="12"><el-form-item label="房号" prop="room_number"><el-input v-model="f.room_number" placeholder="如 1201" maxlength="20" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="房源标题" prop="title"><el-input v-model="f.title" placeholder="如：翰林缘精装单间" maxlength="50" /></el-form-item></el-col>
          </el-row>

          <el-form-item label="详细地址" prop="address"><el-input v-model="f.address" placeholder="含路名+小区+门牌号" /></el-form-item>
          <el-form-item label="所在区域" prop="district"><el-select v-model="f.district" @change="triggerRentEstimate"><el-option v-for="d in districts" :key="d" :label="d" :value="d" /></el-select></el-form-item>

          <el-row :gutter="16">
            <el-col :span="8"><el-form-item label="户型" prop="property_type"><el-select v-model="f.property_type"><el-option label="Studio/单间" value="studio" /><el-option label="Ensuite/套间" value="apartment" /><el-option label="Twin/双人间" value="shared" /><el-option label="Double/大床房" value="house" /></el-select></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="面积(㎡)" prop="area_sqm"><el-input-number v-model="f.area_sqm" :min="1" :max="999" controls-position="right" style="width:100%" @change="triggerRentEstimate" /></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="楼层"><el-input-number v-model="f.floor" :min="0" :max="99" controls-position="right" style="width:100%" /></el-form-item></el-col>
          </el-row>

          <el-divider content-position="left">租金信息</el-divider>
          <el-row :gutter="16">
            <el-col :span="8"><el-form-item label="月租金(元)" prop="price_monthly"><el-input-number v-model="f.price_monthly" :min="0" :precision="0" controls-position="right" style="width:100%" @change="onPriceChange" /></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="押金(元)" prop="deposit_amount"><el-input-number v-model="f.deposit_amount" :min="0" :precision="0" controls-position="right" style="width:100%" /></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="服务费率"><el-input-number v-model="f.service_fee_rate" :min="0" :max="1" :precision="2" :step="0.01" controls-position="right" style="width:100%" /><span style="font-size:12px;color:#909399;margin-left:4px">{{ ((f.service_fee_rate||0)*100).toFixed(0) }}%</span></el-form-item></el-col>
          </el-row>

          <el-divider content-position="left">配套设施</el-divider>
          <el-form-item label="配套标签">
            <el-checkbox-group v-model="selectedAmenities" class="amenity-group">
              <el-checkbox v-for="a in allAmenities" :key="a" :label="a" :value="a" border size="small" />
            </el-checkbox-group>
          </el-form-item>

          <el-divider content-position="left">房源描述</el-divider>
          <el-form-item label="描述">
            <el-input v-model="f.description" type="textarea" :rows="5" placeholder="描述房源特色、周边配套、适合人群等..." maxlength="500" show-word-limit @input="checkContentViolations" />
            <div v-if="contentWarning" style="color:#e6a23c;font-size:12px;margin-top:4px">⚠️ {{ contentWarning }}</div>
          </el-form-item>

          <!-- 图片上传 -->
          <el-divider content-position="left">房源实拍图片</el-divider>
          <ImageUploader
            ref="imageUploaderRef"
            title="房源实拍图片"
            hint="必填，最少上传3张，最多15张，支持JPG/PNG/WebP"
            :min-files="3"
            :max-files="15"
            v-model="uploadedImageUrls"
          />

          <el-divider content-position="left">坐标 (选填)</el-divider>
          <el-row :gutter="16"><el-col :span="12"><el-input v-model="f.latitude" placeholder="纬度 (如 31.315)" /></el-col><el-col :span="12"><el-input v-model="f.longitude" placeholder="经度 (如 120.715)" /></el-col></el-row>

          <el-divider />
          <el-form-item>
            <el-button type="primary" size="large" native-type="submit" :loading="submitting" :disabled="!f.institute_id">{{ isEdit?'保存修改':'提交发布' }}</el-button>
            <el-button @click="$router.back()">取消</el-button>
          </el-form-item>
        </el-form>
        </template><!-- v-else formLoading -->
      </el-card>
    </template>

    <!-- 创建公寓弹窗 -->
    <el-dialog v-model="showBuildingDialog" title="新建公寓" width="480px">
      <el-form :model="newBuilding" label-width="80px">
        <el-form-item label="公寓名称" required><el-input v-model="newBuilding.name" placeholder="如：翰林缘公寓" /></el-form-item>
        <el-form-item label="地址"><el-input v-model="newBuilding.address" placeholder="公寓详细地址" /></el-form-item>
        <el-form-item label="联系电话"><el-input v-model="newBuilding.contact_phone" placeholder="管理机构电话" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="newBuilding.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBuildingDialog=false">取消</el-button>
        <el-button type="primary" :loading="creatingBuilding" @click="createBuilding">创建</el-button>
      </template>
    </el-dialog>

    <!-- 提交成功弹窗 -->
    <el-dialog v-model="showSuccessDialog" :title="isEdit ? '保存成功' : '发布成功'" width="420px" :close-on-click-modal="false">
      <el-result icon="success" :title="isEdit ? '房源信息已更新！' : '房源已成功发布！'" :sub-title="createdStatus === 'pending_review' ? '状态：待人工审核，审核通过后学生端可见' : '状态：已上架，学生端可见'" />
      <template #footer>
        <el-button type="primary" @click="goToManage">返回房源管理</el-button>
        <el-button @click="goToDetail" v-if="createdId">查看房源详情</el-button>
        <el-button v-if="!isEdit" type="primary" @click="continueAdd">继续新增房间</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, computed, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { usePropertyStore } from '@/stores/property'
import { getImageUrl } from '@/utils/image'
import { useAuthStore } from '@/stores/auth'
import { propertyService } from '@/services/property'
import { buildingService, type Building } from '@/services/building'
import { extractErrorMessage } from '@/services/api'
import ImageUploader from '@/components/ImageUploader.vue'
import type { PropertyType } from '@/types/property'
import type { RentEstimate, ParsedProperty } from '@/types/admin'

const router = useRouter(); const route = useRoute()
const propertyStore = usePropertyStore(); const authStore = useAuthStore()

const uploadMode = ref<'single'|'batch'>('single')
const isEdit = computed(() => route.name === 'edit-property')
const editId = computed(() => (route.name === 'edit-property' && route.params.id) ? Number(route.params.id) : null)
const formRef = ref<FormInstance>(); const submitting = ref(false)
const createdId = ref<number|null>(null); const showSuccessDialog = ref(false)
const createdStatus = ref<string>('available')
const uploadingImages = ref(false)
const formLoading = ref(false)
const uploadedImageUrls = ref<string[]>([])
const imageUploaderRef = ref<InstanceType<typeof ImageUploader>>()

const districts = ['工业园区','姑苏区','高新区','吴中区','相城区','吴江区','昆山市','太仓市','常熟市','张家港市']
const allAmenities = ['独立卫浴','包水电','WiFi','空调','洗衣机','冰箱','暖气','阳台','健身房','自习室','游泳池','停车场','24小时前台','校车接驳','签证咨询','可养宠物','近地铁','精装修']
const selectedAmenities = ref<string[]>([])

const f = reactive({
  title:'', address:'', district:'', institute_id: null as number|null,
  room_number:'', floor:undefined as number|undefined,
  price_monthly:undefined as number|undefined, deposit_amount:undefined as number|undefined,
  bedrooms:0, bathrooms:1, area_sqm:undefined as number|undefined,
  property_type:'studio' as PropertyType, service_fee_rate:undefined as number|undefined,
  description:'', latitude:'' as string|undefined, longitude:'' as string|undefined,
})

const rules: FormRules = {
  institute_id:[{required:true,message:'请选择公寓',trigger:'change'}],
  title:[{required:true,message:'请输入房源标题',trigger:'blur'}],
  address:[{required:true,message:'请输入详细地址',trigger:'blur'}],
  district:[{required:true,message:'请选择区域',trigger:'change'}],
  price_monthly:[{required:true,message:'请输入月租金',trigger:'blur'}],
  area_sqm:[{required:true,message:'请输入面积',trigger:'blur'}],
  property_type:[{required:true,message:'请选择户型',trigger:'change'}],
}

// 公寓
const buildings = ref<Building[]>([]); const showBuildingDialog = ref(false); const creatingBuilding = ref(false)
const newBuilding = reactive({name:'',address:'',contact_phone:'',description:''})

async function loadBuildings() {
  try { buildings.value = await buildingService.list({limit:200}) } catch {}
}
function onBuildingChange() { if (f.institute_id && !f.address) { const b = buildings.value.find(x => x.id===f.institute_id); if (b?.address) f.address = b.address } }
async function createBuilding() {
  if (!newBuilding.name.trim()) { ElMessage.error('请输入公寓名称'); return }
  creatingBuilding.value = true
  try {
    const b = await buildingService.create({name:newBuilding.name,address:newBuilding.address,contact_phone:newBuilding.contact_phone,description:newBuilding.description})
    buildings.value.unshift(b); f.institute_id = b.id; showBuildingDialog.value = false
    newBuilding.name='';newBuilding.address='';newBuilding.contact_phone='';newBuilding.description=''
    ElMessage.success('公寓创建成功')
  } catch (e:any) { ElMessage.error(extractErrorMessage(e)||'创建失败') }
  finally { creatingBuilding.value = false }
}

// AI 解析
const rawText = ref(''); const parsing = ref(false); const llmParsing = ref(false)
const parseResult = ref<ParsedProperty|null>(null)
const cn: Record<string,number>={一:1,二:2,两:2,三:3,四:4,五:5,六:6,七:7,八:8,九:9,十:10}
function pcn(s:string):number{return cn[s]??parseInt(s)}
function smartParse(){/* same regex logic as before */parsing.value=true;parseResult.value=null;const t=rawText.value
  const rp=[/(\d+)室(\d+)厅(\d+)卫/,/(\d+)室(\d+)厅/,/(\d+)室(\d+)卫/]
  let br=-1,bh=-1;for(const p of rp){const m=t.match(p);if(!m)continue;br=pcn(m[1]);if(m[3])bh=pcn(m[3]);break}
  if(br===-1){const m=t.match(/(\d+)\s*室/);if(m)br=parseInt(m[1])}
  if(bh===-1){const m=t.match(/(\d+)\s*卫/);if(m)bh=parseInt(m[1])}
  if(bh===-1&&/独立卫浴|独卫/.test(t))bh=1
  const am=t.match(/(\d+(?:\.\d+)?)\s*(?:平米|平方米|㎡|平)/);const area=am?parseFloat(am[1]):undefined
  const rts=[/月租\s*(\d+(?:\.\d+)?)/,/(\d+(?:\.\d+)?)\s*元?\s*[\/每]\s*月/,/租金\s*(\d+(?:\.\d+)?)/]
  let rent:number|undefined;for(const p of rts){const m=t.match(p);if(m){rent=parseFloat(m[1]);break}}
  const dm=t.match(/押金\s*(\d+(?:\.\d+)?)/)||t.match(/押[一1]付[三3]/);const deposit=dm?(dm[1]?parseFloat(dm[1]):(rent??0)):undefined
  let pt:PropertyType|undefined;if(/别墅/.test(t))pt='house';else if(/单间|单身公寓/.test(t))pt='studio';else if(/合租/.test(t))pt='shared';else if(/公寓/.test(t))pt='apartment'
  let dist='';for(const d of districts){if(t.includes(d)){dist=d;break}}
  let addr='';const adm=t.match(/([^，,。.！!；;]+?(?:路|街|道|巷|弄|号|小区|花园|苑|城|湾|岸|郡|府|广场)[^，,。.！!；;]*)/);if(adm)addr=adm[1].trim()
  let title='';if(dist)title+=dist;if(addr)title+=addr.replace(/^\S+区/,'').slice(0,8);if(pt)title+=({apartment:'公寓',house:'别墅',studio:'单间',shared:'合租'})[pt]
  const rm=t.match(/(\d{2,4})\s*(?:室|房间|号)/);if(rm)f.room_number=rm[1]
  if(title)f.title=title;if(addr)f.address=addr;if(dist)f.district=dist;if(rent)f.price_monthly=rent;if(deposit)f.deposit_amount=deposit;if(br>0)f.bedrooms=br;if(bh>0)f.bathrooms=bh;if(area)f.area_sqm=area;if(pt)f.property_type=pt;f.description=t
  parsing.value=false;parseResult.value={confidence:'medium'};ElMessage.success('识别完成，请核对');triggerRentEstimate()
}
async function llmSmartParse(){llmParsing.value=true;try{const r=await propertyService.parseDescription(rawText.value);parseResult.value=r;if(r.title)f.title=r.title;if(r.address)f.address=r.address;if(r.district)f.district=r.district;if(r.price_monthly)f.price_monthly=r.price_monthly;if(r.deposit_amount)f.deposit_amount=r.deposit_amount;if(r.area_sqm)f.area_sqm=r.area_sqm;if(r.property_type)f.property_type=r.property_type as PropertyType;if(r.description)f.description=r.description;if(r.amenities)selectedAmenities.value=r.amenities;if(r.room_number)f.room_number=r.room_number;ElMessage.success('AI深度解析完成')}catch(e:any){ElMessage.error(extractErrorMessage(e)||'解析失败')}finally{llmParsing.value=false}}

// 租金预估
const rentEstimate = ref<RentEstimate>({predicted:0,lower_bound:0,upper_bound:0,feature_importance:{}})
const showRentEstimate = ref(false);let et:ReturnType<typeof setTimeout>|null=null
function triggerRentEstimate(){if(et)clearTimeout(et);et=setTimeout(async()=>{if(!f.area_sqm)return;try{const r=await propertyService.estimateRent({area_sqm:f.area_sqm,bedrooms:f.bedrooms,bathrooms:f.bathrooms,district:f.district||undefined,property_type:f.property_type,deposit_amount:f.deposit_amount});rentEstimate.value=r;showRentEstimate.value=true}catch{}},500)}
function onPriceChange(v:number|undefined){if(v&&rentEstimate.value.predicted>0){const d=Math.abs(v-rentEstimate.value.predicted)/rentEstimate.value.predicted;if(d>0.3)ElMessage.warning(`出价 ¥${v} 与预估偏差${(d*100).toFixed(0)}%，建议核实`)}}

// 内容违规检测
const contentWarning = ref('')
function checkContentViolations(){
  const t=f.description||'';const violations:string[]=[]
  if(/(?:\+86|1[3-9]\d{9}|微信|wechat|wx|qq|手机|电话|拨打|联系我|私聊|加我|扫码|二维码)/i.test(t))violations.push('检测到疑似联系方式或引流内容，房源可能被驳回')
  if(/第一|最好|唯一|顶级|最便宜|绝对|100%|免费|不限/.test(t))violations.push('检测到广告极限词，建议修改')
  contentWarning.value=violations.join('；')
}

// 提交
async function handleSubmit(){
  if(!formRef.value)return;if(!authStore.user){ElMessage.error('请先登录');return}
  const valid=await formRef.value?.validate().catch(()=>false);if(!valid)return
  if(!f.institute_id){ElMessage.error('请先选择或创建公寓');return}
  // 图片校验：至少3张
  if (uploadedImageUrls.value.length < 3 && !isEdit.value) {
    ElMessage.error('请至少上传3张房源实拍图'); return
  }
  submitting.value=true
  // 合并配套标签到描述
  let desc=f.description||''
  if(selectedAmenities.value.length)desc+='\n\n配套设施：'+selectedAmenities.value.join('、')
  try{
    const data={
      title:f.title,address:f.address,district:f.district,
      price_monthly:f.price_monthly!,property_type:f.property_type,
      landlord_id:authStore.user.id,institute_id:f.institute_id,
      bedrooms:f.bedrooms,bathrooms:f.bathrooms,
      area_sqm:f.area_sqm,deposit_amount:f.deposit_amount,
      description:desc||undefined,service_fee_rate:f.service_fee_rate,
      room_number:f.room_number||undefined,floor:f.floor,
      latitude:f.latitude?Number(f.latitude):undefined,longitude:f.longitude?Number(f.longitude):undefined,
      image_urls: uploadedImageUrls.value,
    } as any
    if(isEdit.value&&editId.value){const r=await propertyStore.update(editId.value,data);createdId.value=editId.value;createdStatus.value=r.status}
    else{const r=await propertyStore.create(data);createdId.value=r.id;createdStatus.value=r.status}
    showSuccessDialog.value=true
  }catch(e:any){
    const msg = extractErrorMessage(e)
    if(msg)ElMessage.error(msg)
    else ElMessage.error('发布失败，请检查网络连接或联系管理员')
  }finally{submitting.value=false}
}
function goToDetail(){showSuccessDialog.value=false;if(createdId.value)router.push(`/property/${createdId.value}`)}
function goToManage(){showSuccessDialog.value=false;router.push('/property/manage')}
function continueAdd(){showSuccessDialog.value=false;Object.assign(f,{title:'',address:'',room_number:'',price_monthly:undefined,deposit_amount:undefined,area_sqm:undefined,bedrooms:0,bathrooms:1,description:'',latitude:'',longitude:''});selectedAmenities.value=[];parseResult.value=null;showRentEstimate.value=false;rawText.value='';formRef.value?.resetFields()}

function toNum(v: any): number | undefined {
  if (v === null || v === undefined) return undefined
  const n = Number(v)
  return isNaN(n) ? undefined : n
}

async function populateForm(propertyId: number) {
  formLoading.value = true
  try {
    await propertyStore.fetchById(propertyId)
    const p = propertyStore.currentProperty
    if (!p) { ElMessage.error('未找到该房源'); formLoading.value = false; return }

    f.title = String(p.title ?? '')
    f.address = String(p.address ?? '')
    f.district = String(p.district ?? '')
    f.room_number = String((p as any).room_number ?? '')
    f.description = String(p.description ?? '')
    f.price_monthly = toNum(p.price_monthly)
    f.area_sqm = toNum(p.area_sqm)
    f.deposit_amount = toNum(p.deposit_amount)
    f.service_fee_rate = toNum(p.service_fee_rate)
    f.floor = toNum((p as any).floor)
    f.bedrooms = toNum(p.bedrooms) ?? 0
    f.bathrooms = toNum(p.bathrooms) ?? 1
    f.property_type = p.property_type || 'studio'
    f.institute_id = toNum((p as any).institute_id) ?? null
    f.latitude = p.latitude ? String(p.latitude) : ''
    f.longitude = p.longitude ? String(p.longitude) : ''

    selectedAmenities.value = []
    if (p.description) {
      const m = p.description.match(/配套设施：(.+)/)
      if (m) selectedAmenities.value = m[1].split('、').filter(Boolean)
    }
    rawText.value = p.description || ''
    uploadedImageUrls.value = (p.images?.length)
      ? p.images.map(img => getImageUrl(img.filename))
      : []
    formLoading.value = false
  } catch (e: any) {
    ElMessage.error('加载房源数据失败')
    formLoading.value = false
  }
}

onMounted(async () => {
  await loadBuildings()
  if (route.params.id) await populateForm(Number(route.params.id))
})
</script>

<style scoped>
.create-page{max-width:860px;margin:0 auto}h2{font-size:22px;color:#303133;margin-bottom:20px}
.mode-card{margin-bottom:20px;text-align:center}
.smart-card{margin-bottom:20px;border:2px dashed #c0c4cc}.smart-header{display:flex;justify-content:space-between;align-items:center}.smart-actions{margin-top:12px;display:flex;gap:12px}
.estimate-card{margin-bottom:20px;background:linear-gradient(135deg,#fff 0%,#fff8f2 100%)}
.est-box{text-align:center;padding:10px;border-radius:8px}.est-box.hl{background:#fff4ed;border:1px solid #ffd4b8}.est-l{font-size:12px;color:#909399}.est-v{font-size:22px;font-weight:700}.est-v.o{color:#FF6B35}.est-v.g{color:#67c23a}.est-v.y{color:#e6a23c}
.amenity-group{display:flex;flex-wrap:wrap;gap:6px}.amenity-group .el-checkbox{margin-right:0}
.batch-redirect{margin-top:40px}
</style>

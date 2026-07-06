<template>
  <div class="batch-page">
    <h2>📦 批量导入房源</h2>

    <!-- 公寓选择（必选，所有导入房间归属同一公寓） -->
    <el-card v-if="!selectedBuilding" shadow="never" class="building-card">
      <template #header><span>🏢 第一步：选择目标公寓</span></template>
      <el-alert v-if="!buildings.length" title="尚未创建任何公寓，请先创建公寓再批量导入" type="warning" :closable="false" show-icon>
        <template #default><el-button type="warning" size="small" style="margin-top:8px" @click="$router.push('/buildings')">前往创建公寓 →</el-button></template>
      </el-alert>
      <div v-else style="display:flex;gap:12px;align-items:center">
        <el-select v-model="selectedBuildingId" placeholder="选择公寓（必选）" filterable style="flex:1" size="large">
          <el-option v-for="b in buildings" :key="b.id" :label="b.name + (b.address?' — '+b.address:'')" :value="b.id" />
        </el-select>
        <el-button type="primary" size="large" :disabled="!selectedBuildingId" @click="confirmBuilding">确认，进入导入 →</el-button>
        <el-button size="large" @click="showNewBuildingDialog=true">+ 新建公寓</el-button>
      </div>
    </el-card>

    <!-- 新建公寓弹窗 -->
    <el-dialog v-model="showNewBuildingDialog" title="新建公寓" width="440px">
      <el-form :model="newBuilding" label-width="80px">
        <el-form-item label="公寓名称" required><el-input v-model="newBuilding.name" placeholder="如：翰林缘公寓" /></el-form-item>
        <el-form-item label="地址"><el-input v-model="newBuilding.address" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showNewBuildingDialog=false">取消</el-button><el-button type="primary" :loading="creatingB" @click="createBuilding">创建</el-button></template>
    </el-dialog>

    <!-- 导入步骤 -->
    <template v-if="selectedBuilding">
      <div class="building-badge">
        <el-tag type="success" size="large" effect="dark">🏢 {{ selectedBuilding.name }}</el-tag>
        <el-button size="small" @click="selectedBuilding=null;selectedBuildingId=null" style="margin-left:12px">更换公寓</el-button>
      </div>

      <el-steps :active="step" finish-status="success" align-center style="margin-bottom:32px">
        <el-step title="下载模板" /><el-step title="上传文件" /><el-step title="预览确认" /><el-step title="导入结果" />
      </el-steps>

    <!-- Step 1: 下载模板 -->
    <el-card v-if="step===0" shadow="never">
      <template #header><span>第一步：下载标准模板</span></template>
      <p style="color:#606266;margin-bottom:16px">请下载模板文件，按照表头格式填写房源信息。模板支持中英文列名自动匹配。</p>
      <el-button type="primary" size="large" @click="downloadTemplate">📥 下载 CSV/Excel 模板</el-button>
      <el-button size="large" style="margin-left:12px" @click="step=1">已下载，下一步 →</el-button>
    </el-card>

    <!-- Step 2: 上传 -->
    <el-card v-if="step===1" shadow="never">
      <template #header><span>第二步：上传填写好的文件</span></template>
      <div class="drop-zone" :class="{active:isDragging}" @click="triggerFileInput" @dragover.prevent="isDragging=true" @dragleave.prevent="isDragging=false" @drop.prevent="onFileDrop">
        <input ref="fileInputRef" type="file" accept=".csv,.xlsx,.xls" style="display:none" @change="onFileInputChange" />
        <template v-if="!batchFile"><el-icon :size="48" color="#c0c4cc"><UploadFilled /></el-icon><p style="color:#606266;margin-top:12px">点击或拖拽文件到此处</p><p style="font-size:13px;color:#909399">.csv / .xlsx / .xls，最大 10MB，最多 500 行</p></template>
        <template v-else><el-icon :size="36" color="#67c23a"><CircleCheckFilled /></el-icon><p style="font-weight:600;margin:8px 0">{{ batchFile.name }}</p><p style="font-size:13px;color:#909399">{{ formatSize(batchFile.size) }}</p><el-button type="danger" plain size="small" @click.stop="clearFile">移除</el-button></template>
      </div>
      <div v-if="batchFile && batchTotalRows>0" style="margin-top:16px">
        <el-descriptions :column="3" border size="small"><el-descriptions-item label="总行数">{{ batchTotalRows }}</el-descriptions-item><el-descriptions-item label="列数">{{ batchHeaders.length }}</el-descriptions-item><el-descriptions-item label="已识别列">{{ Object.keys(columnMapping.matched||{}).length }}</el-descriptions-item></el-descriptions>
        <el-alert v-if="missingRequired.length" :title="'⚠️ 缺少必填列：'+missingRequiredLabel" type="error" :closable="false" show-icon style="margin:12px 0" />
        <el-button type="primary" size="large" style="width:100%;margin-top:12px" @click="step=2">预览数据 →</el-button>
      </div>
    </el-card>

    <!-- Step 3: 预览确认 -->
    <el-card v-if="step===2" shadow="never">
      <template #header><span>第三步：预览数据并确认导入</span></template>
      <div class="preview-info">
        <el-tag v-for="h in batchHeaders" :key="h" :type="columnMapping.confidence[h]==='exact'?'success':'warning'" size="small" class="mapping-tag">{{ h }} → {{ columnMapping.matched[h]||'未识别' }}<span v-if="REQUIRED.includes(columnMapping.matched[h])" style="color:#f56c6c">*</span></el-tag>
      </div>
      <p class="section-title">数据预览（前 5 行）：</p>
      <el-table :data="batchPreviewRows.slice(0,5)" border stripe size="small" max-height="240"><el-table-column v-for="h in batchHeaders" :key="h" :prop="h" :label="h" min-width="120" show-overflow-tooltip /></el-table>
      <el-alert v-if="batchOutlierRows.length" :title="'⚠️ IQR检测：'+batchOutlierRows.length+' 行可能存在异常数据'" type="warning" :closable="false" show-icon style="margin:12px 0" />

      <!-- 楼栋共用照片（选填） -->
      <div v-if="selectedBuilding" style="margin-top:16px">
        <ImageUploader
          ref="batchImageUploaderRef"
          title="楼栋公共配套图片（选填）"
          hint="本照片仅作为楼栋公共配套图（大堂、电梯、外观等），房间独立实拍图需在房源编辑页面单独补充上传"
          :min-files="0"
          :max-files="8"
          upload-url="/upload/temp/batch"
          v-model="batchImageUrls"
        />
      </div>
      <div v-else style="margin-top:16px;padding:12px;background:#fafafa;border-radius:8px;color:#909399;text-align:center">
        请先选择所属公寓楼栋后才可上传共用图片
      </div>

      <div style="margin-top:12px;display:flex;gap:12px">
        <el-radio-group v-model="importMode"><el-radio value="flexible">柔性模式（合规行直接入库，错误行跳过）</el-radio><el-radio value="strict">严格模式（有错全部不入库）</el-radio></el-radio-group>
      </div>
      <div style="margin-top:16px;display:flex;gap:12px">
        <el-button size="large" @click="step=1">← 重新选择文件</el-button>
        <el-button type="primary" size="large" :loading="batchImporting" style="flex:1" @click="doImport">开始导入（{{ batchTotalRows }} 条）</el-button>
      </div>
    </el-card>

    <!-- Step 4: 结果 -->
    <el-card v-if="step===3 && batchResult" shadow="never">
      <template #header><span>{{ importIsError?'❌ 导入失败':batchResult.failed_records>0?'⚠️ 部分成功':'✅ 导入全部成功' }}</span></template>
      <el-alert v-if="fileLevelError" :title="fileLevelError.error" type="error" :closable="false" show-icon style="margin-bottom:16px" />
      <el-row v-if="!fileLevelError" :gutter="20"><el-col :span="6"><el-statistic title="总计" :value="batchResult.total_records" /></el-col><el-col :span="6"><el-statistic title="成功"><template #default><span style="color:#67c23a;font-size:28px;font-weight:700">{{ batchResult.success_records }}</span></template></el-statistic></el-col><el-col :span="6"><el-statistic title="失败"><template #default><span :style="{color:batchResult.failed_records>0?'#f56c6c':'#909399',fontSize:'28px',fontWeight:'700'}">{{ batchResult.failed_records }}</span></template></el-statistic></el-col><el-col :span="6"><el-statistic title="AI待复核"><template #default><span :style="{color:aiReviewCount>0?'#e6a23c':'#909399',fontSize:'28px',fontWeight:'700'}">{{ aiReviewCount }}</span></template></el-statistic></el-col></el-row>
      <el-alert v-if="aiReviewCount>0" :title="'AI检测：'+aiReviewCount+' 条房源标记为「待人工审核」（租金/面积异常），已入库但学生端暂不展示，需管理员审核后上架'" type="warning" :closable="false" show-icon style="margin:12px 0" />
      <div v-if="!fileLevelError&&rowErrors.length" class="error-section">
        <h4>失败详情（{{ rowErrors.length }} 条）</h4>
        <el-table :data="rowErrors" border stripe size="small" max-height="400"><el-table-column prop="row" label="行号" width="70"/><el-table-column prop="error" label="错误原因" show-overflow-tooltip><template #default="{row}"><span :style="{color:row.type==='duplicate'?'#e6a23c':row.type==='missing_field'?'#f56c6c':row.type==='format_error'?'#409eff':'#909399'}">{{ row.error }}</span></template></el-table-column><el-table-column label="类型" width="90"><template #default="{row}"><el-tag :type="row.type==='duplicate'?'warning':row.type==='missing_field'?'danger':row.type==='format_error'?'':'info'" size="small">{{ row.type==='duplicate'?'重复':row.type==='missing_field'?'缺字段':row.type==='format_error'?'格式错':'其他' }}</el-tag></template></el-table-column></el-table>
        <div style="margin-top:12px;display:flex;gap:12px">
          <el-button type="warning" size="small" @click="downloadErrorTable" v-if="batchResult.id&&batchResult.failed_records>0">📥 下载仅含错误行的表格（可修改后重传）</el-button>
          <el-button size="small" @click="retryBatchImport" v-if="batchResult.id&&batchResult.failed_records>0">重试失败行</el-button>
        </div>
      </div>
      <div style="margin-top:16px;display:flex;gap:12px">
        <el-button v-if="batchResult.success_records>0" type="success" @click="goToList">查看房源列表 →</el-button>
        <el-button @click="resetAll">重新导入</el-button>
      </div>
    </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UploadFilled, CircleCheckFilled } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import { adminService } from '@/services/admin'
import { buildingService, type Building } from '@/services/building'
import { extractErrorMessage } from '@/services/api'
import ImageUploader from '@/components/ImageUploader.vue'
import type { ImportResult, ColumnMapping } from '@/types/admin'

const router = useRouter()

// 公寓选择
const buildings = ref<Building[]>([])
const selectedBuildingId = ref<number|null>(null)
const selectedBuilding = ref<Building|null>(null)
const showNewBuildingDialog = ref(false); const creatingB = ref(false)
const newBuilding = reactive({name:'',address:''})

async function loadBuildings(){try{buildings.value=await buildingService.list({limit:200})}catch{}}
function confirmBuilding(){const b=buildings.value.find(x=>x.id===selectedBuildingId.value);if(b){selectedBuilding.value=b;step.value=0}}
async function createBuilding(){if(!newBuilding.name.trim()){ElMessage.error('请输入公寓名称');return};creatingB.value=true;try{const b=await buildingService.create({name:newBuilding.name,address:newBuilding.address});buildings.value.unshift(b);selectedBuildingId.value=b.id;selectedBuilding.value=b;showNewBuildingDialog.value=false;newBuilding.name='';newBuilding.address='';ElMessage.success('公寓创建成功');step.value=0}catch(e:any){ElMessage.error(extractErrorMessage(e)||'创建失败')}finally{creatingB.value=false}}

const step = ref(0); const isDragging = ref(false)
const fileInputRef = ref<HTMLInputElement>(); const batchFile = ref<File|null>(null)
const batchHeaders = ref<string[]>([]); const batchPreviewRows = ref<Record<string,string>[]>([])
const batchTotalRows = ref(0); const batchOutlierRows = ref<number[]>([])
const columnMapping = ref<ColumnMapping>({matched:{},unmatched:[],confidence:{}})
const batchImporting = ref(false); const batchResult = ref<ImportResult|null>(null)
const importMode = ref<'flexible'|'strict'>('flexible')
const batchImageUrls = ref<string[]>([])
const batchImageUploaderRef = ref<InstanceType<typeof ImageUploader>>()
const REQUIRED = ['title','address','district','price_monthly']

const missingRequired = computed(()=>{const m=new Set(Object.values(columnMapping.value.matched||{}));return REQUIRED.filter(f=>!m.has(f))})
const missingRequiredLabel = computed(()=>missingRequired.value.map(f=>({title:'房源标题',address:'详细地址',district:'所在区域',price_monthly:'月租金'})[f]||f).join('、'))
const importIsError = computed(()=>batchResult.value?.status==='failed'||(batchResult.value?.success_records===0&&batchResult.value?.failed_records===0))
const fileLevelError = computed(()=>batchResult.value?.error_log?.find((e:any)=>e.row===0)||null)
const rowErrors = computed(()=>(batchResult.value?.error_log||[]).filter((e:any)=>e.row!==0&&e.type!=='ai_review'))
const aiReviewCount = computed(()=>(batchResult.value?.error_log||[]).filter((e:any)=>e.type==='ai_review').reduce((s:number,e:any)=>s+(parseInt(e.error)||1),0)||0)

const ALIAS: Record<string,string>={'title':'title','房源标题':'title','标题':'title','名称':'title','address':'address','地址':'address','详细地址':'address','位置':'address','district':'district','区域':'district','地区':'district','所在区域':'district','城市':'district','price_monthly':'price_monthly','月租金':'price_monthly','租金':'price_monthly','月租':'price_monthly','价格':'price_monthly','area_sqm':'area_sqm','面积':'area_sqm','平方米':'area_sqm','㎡':'area_sqm','bedrooms':'bedrooms','卧室':'bedrooms','卧室数':'bedrooms','室':'bedrooms','bathrooms':'bathrooms','卫生间':'bathrooms','卫':'bathrooms','浴室':'bathrooms','property_type':'property_type','类型':'property_type','房源类型':'property_type','description':'description','描述':'description','房源描述':'description','简介':'description','备注':'description','deposit_amount':'deposit_amount','押金':'deposit_amount','押金金额':'deposit_amount','保证金':'deposit_amount','service_fee_rate':'service_fee_rate','服务费':'service_fee_rate','服务费比例':'service_fee_rate','building_name':'building_name','公寓名称':'building_name','公寓':'building_name','room_number':'room_number','房号':'room_number','房间号':'room_number','floor':'floor','楼层':'floor','latitude':'latitude','纬度':'latitude','lat':'latitude','longitude':'longitude','经度':'longitude','lng':'longitude'}

function formatSize(b:number):string{if(b<1024)return b+' B';if(b<1024*1024)return(b/1024).toFixed(1)+' KB';return(b/(1024*1024)).toFixed(2)+' MB'}
function downloadTemplate(){adminService.downloadTemplate().then(blob=>{const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download='import_template.xlsx';a.click();URL.revokeObjectURL(u);ElMessage.success('下载成功')}).catch(()=>ElMessage.error('下载失败'))}
function downloadErrorTable(){if(!batchResult.value?.id)return;adminService.downloadErrorTable(batchResult.value.id).then(blob=>{const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download='errors.xlsx';a.click();URL.revokeObjectURL(u)}).catch(()=>ElMessage.error('下载失败'))}

function triggerFileInput(){fileInputRef.value?.click()}
function onFileInputChange(e:Event){const f=(e.target as HTMLInputElement).files?.[0];if(f)processFile(f);(e.target as HTMLInputElement).value=''}
function onFileDrop(e:DragEvent){isDragging.value=false;const f=e.dataTransfer?.files?.[0];if(f)processFile(f)}
function clearFile(){batchFile.value=null;batchHeaders.value=[];batchPreviewRows.value=[];batchTotalRows.value=0;batchOutlierRows.value=[];columnMapping.value={matched:{},unmatched:[],confidence:{}};batchResult.value=null}

function parseFile(raw:File):Promise<{headers:string[];rows:Record<string,string>[]}>{return new Promise((resolve,reject)=>{const ext=(raw.name.split('.').pop()||'').toLowerCase();const reader=new FileReader();reader.onload=(e)=>{try{const data=new Uint8Array(e.target!.result as ArrayBuffer);if(ext==='csv'){const text=new TextDecoder('utf-8').decode(data);const lines=text.trim().split('\n');if(!lines.length){resolve({headers:[],rows:[]});return};const headers=lines[0].split(',').map(h=>h.trim().replace(/^"|"$/g,''));const rows=lines.slice(1).map(line=>{const vals:string[]=[];let cur='',iq=false;for(const ch of line){if(ch==='"')iq=!iq;else if(ch===','&&!iq){vals.push(cur.trim());cur=''}else cur+=ch};vals.push(cur.trim());const row:Record<string,string>={};headers.forEach((h,i)=>{row[h]=(vals[i]||'').trim().replace(/^"|"$/g,'')});return row});resolve({headers,rows})}else{const wb=XLSX.read(data,{type:'array'});const ws=wb.Sheets[wb.SheetNames[0]];const sd=XLSX.utils.sheet_to_json<(string|number|null)[]>(ws,{header:1});if(!sd.length){resolve({headers:[],rows:[]});return};const headers=sd[0].map(h=>String(h||'').trim());const rows:Record<string,string>[]=[];for(let i=1;i<sd.length;i++){const ra=sd[i] as (string|number|null)[];if(!ra||ra.every(c=>!c))continue;const row:Record<string,string>={};headers.forEach((h,j)=>{row[h]=String(ra[j]||'').trim()});rows.push(row)};resolve({headers,rows})}}catch(err){reject(err)}};reader.onerror=()=>reject(new Error('读取失败'));reader.readAsArrayBuffer(raw)})}

async function processFile(raw:File){if(!raw?.name){ElMessage.error('无法读取文件');return};const ext=(raw.name.split('.').pop()||'').toLowerCase();if(!['csv','xlsx','xls'].includes(ext)){ElMessage.error('仅支持.csv/.xlsx/.xls');return};if(raw.size>10*1024*1024){ElMessage.error('文件不超过10MB');return};clearFile();batchFile.value=raw;try{const {headers,rows}=await parseFile(raw);if(!headers.length){ElMessage.error('文件无内容或格式无法识别');return};if(!rows.length){ElMessage.error('未检测到有效数据，仅有表头');batchFile.value=null;return};if(rows.length>500){ElMessage.error('最多500行，当前'+rows.length+'行');batchFile.value=null;return};batchHeaders.value=headers;batchPreviewRows.value=rows.slice(0,5);batchTotalRows.value=rows.length;const matched:Record<string,string>={};const unmatched:string[]=[];const cf:Record<string,string>={};for(const h of headers){if(!h){unmatched.push('(空)');continue};const k=h.toLowerCase().trim().replace(/\(.*?\)/g,'').replace(/\*$/,'');if(ALIAS[k]){matched[h]=ALIAS[k];cf[h]='exact'}else if(ALIAS[h.toLowerCase().trim()]){matched[h]=ALIAS[h.toLowerCase().trim()];cf[h]='exact'}else{unmatched.push(h)}};columnMapping.value={matched,unmatched,confidence:cf};const prices=rows.map(r=>parseFloat(r['price_monthly']||r['月租金']||r['price']||'0')).filter(p=>p>0);if(prices.length>=4){const s=[...prices].sort((a,b)=>a-b);const q1=s[Math.floor(s.length*.25)];const q3=s[Math.floor(s.length*.75)];const iqr=q3-q1;const up=q3+1.5*iqr;const lo=q1-1.5*iqr;const ol:number[]=[];rows.forEach((r,i)=>{const v=parseFloat(r['price_monthly']||r['月租金']||r['price']||'0');if(v>up||v<lo)ol.push(i+2)});batchOutlierRows.value=ol};step.value=2}catch(e:any){ElMessage.error(e.message||'文件解析失败');batchFile.value=null}}

async function doImport(){
  if(!batchFile.value)return
  if(!batchHeaders.value.length){ElMessage.error('无法识别表头，请使用模板格式');return}
  if(!batchTotalRows.value){ElMessage.error('未检测到有效数据');return}
  if(missingRequired.value.length){ElMessage.error('缺少必填列：'+missingRequiredLabel.value);return}
  batchImporting.value=true;batchResult.value=null
  try{
    const r=await adminService.uploadImport(batchFile.value,selectedBuilding.value?.id);batchResult.value=r;step.value=3
    if(r.failed_records===0&&r.success_records>0){ElMessage.success(`全部导入成功！共${r.success_records}条，跳转至房源列表...`);setTimeout(()=>router.push('/property/manage'),1500)}
    else if(r.success_records>0){ElMessage.warning(`成功${r.success_records}条，失败${r.failed_records}条`)}
    else{ElMessage.error(`全部${r.failed_records}条未通过校验`)}
  }catch(e:any){ElMessage.error(extractErrorMessage(e)||'导入失败');step.value=2}
  finally{batchImporting.value=false}
}
async function retryBatchImport(){if(!batchResult.value?.id)return;try{const r=await adminService.retryImportTask(batchResult.value.id);batchResult.value=r;ElMessage.success('重试完成')}catch(e:any){ElMessage.error(extractErrorMessage(e)||'重试失败')}}
function goToList(){router.push('/property/manage')}
function resetAll(){step.value=0;clearFile()}
onMounted(loadBuildings)
</script>

<style scoped>
.batch-page{max-width:960px;margin:0 auto}h2{font-size:22px;color:#303133;margin-bottom:24px}
.drop-zone{border:2px dashed #dcdfe6;border-radius:12px;padding:40px;text-align:center;cursor:pointer;transition:all .3s}.drop-zone:hover,.drop-zone.active{border-color:#FF6B35;background:#fff8f2}
.preview-info{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}.mapping-tag{margin:0}
.section-title{font-weight:600;font-size:14px;margin:16px 0 8px}.error-section h4{font-size:14px;color:#f56c6c;margin-bottom:10px}
</style>

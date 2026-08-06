<!-- BM 将已在 Dropbox Sign 中创建的模板安全绑定到自己管理的公寓。 -->
<template>
  <div class="page-container">
    <div class="header"><div><h2>Dropbox Sign 模板绑定</h2><p>模板文件与签名字段在 Dropbox Sign 配置；此处只保存公寓、模板 ID、租客签署角色和自动填写字段映射。</p></div><el-button @click="load">重新加载</el-button></div>
    <el-alert v-if="config && (!config.api_key_configured || !config.client_id_configured)" type="warning" :closable="false" title="Dropbox Sign 尚未完成服务端配置：可以先保存模板映射，但不能发起真实嵌入式签署。" />
    <el-alert v-else-if="config" type="success" :closable="false" :title="config.test_mode ? 'Dropbox Sign 测试模式已配置：签署不具法律效力。' : 'Dropbox Sign 服务端配置已就绪。'" />

    <el-card v-loading="loading" class="form-card">
      <el-form label-position="top">
        <el-form-item label="管理公寓" required><el-select v-model="form.institute_id" placeholder="选择公寓" @change="selectBinding"><el-option v-for="item in buildings" :key="item.id" :value="item.id" :label="`${item.name_cn || item.name} · ${item.business_id || '无 business_id'}`" /></el-select></el-form-item>
        <el-form-item label="Dropbox Sign Template ID" required>
          <el-input v-model.trim="form.provider_template_id" placeholder="从 Dropbox Sign 模板详情复制 template_id" />
          <el-button text type="primary" :loading="templateLoading" @click="loadDropboxTemplates">从 Dropbox 读取模板</el-button>
          <el-select v-if="remoteTemplates.length" v-model="selectedRemoteTemplateId" placeholder="选择已读取的 Dropbox 模板" @change="applyRemoteTemplate">
            <el-option v-for="item in remoteTemplates" :key="item.template_id" :value="item.template_id" :label="item.title || item.template_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="租客签署角色" required><el-input v-model.trim="form.signer_role" placeholder="例如 TENANT" /><div class="hint">必须与 Dropbox 模板内的 signer role 完全一致；本平台将租客作为该角色发起嵌入式签署。</div></el-form-item>
        <el-divider>自动填写字段映射</el-divider>
        <p class="hint">左侧填写 Dropbox Sign 模板中的 Merge Field 名称；右侧选择平台提供的数据。字段名区分大小写。</p>
        <div v-for="(row,index) in mappingRows" :key="index" class="mapping-row"><el-input v-model.trim="row.templateField" placeholder="Dropbox Merge Field，例如 tenant_name_cn" /><el-select v-model="row.sourceField" placeholder="选择平台字段"><el-option v-for="source in sourceFields" :key="source.value" :value="source.value" :label="source.label" /></el-select><el-button text type="danger" @click="mappingRows.splice(index,1)">删除</el-button></div>
        <el-button text type="primary" @click="mappingRows.push({templateField:'',sourceField:''})">+ 添加字段映射</el-button>
        <div class="actions"><el-button type="primary" :loading="saving" @click="save">保存绑定</el-button><el-button v-if="activeBinding" type="danger" plain :loading="saving" @click="deactivate">停用此绑定</el-button></div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { extractErrorMessage } from '@/services/api'

interface Building { id:number; name:string; name_cn:string|null; business_id:string|null }
interface Binding { id:string; institute_id:number|null; provider_template_id:string; signer_role:string; field_mapping:Record<string,string>; is_active:boolean }
interface MappingRow { templateField:string; sourceField:string }
interface RemoteTemplate { template_id:string; title:string|null; signer_roles:string[] }
const buildings=ref<Building[]>([]), bindings=ref<Binding[]>([]), loading=ref(false), saving=ref(false), activeBinding=ref<Binding|null>(null)
const remoteTemplates=ref<RemoteTemplate[]>([]), selectedRemoteTemplateId=ref(''), templateLoading=ref(false)
const config=ref<{api_key_configured:boolean;client_id_configured:boolean;webhook_enabled:boolean;test_mode:boolean}|null>(null)
const form=ref({institute_id:undefined as number|undefined,provider_template_id:'',signer_role:'TENANT'})
const mappingRows=ref<MappingRow[]>([])
const sourceFields=[
  {value:'agreement_number',label:'合同编号'}, {value:'order_number',label:'订单编号'},
  {value:'tenant_name_cn',label:'租客中文姓名'}, {value:'tenant_name_en',label:'租客英文姓名'}, {value:'tenant_email',label:'租客邮箱'}, {value:'tenant_phone',label:'租客电话'}, {value:'tenant_school',label:'租客学校'}, {value:'tenant_passport',label:'租客护照号'},
  {value:'landlord_or_provider_name',label:'房东/公寓供应方名称'}, {value:'property_name',label:'公寓名称'}, {value:'property_address',label:'公寓地址'}, {value:'property_id',label:'公寓业务编号'}, {value:'unit_type_name',label:'户型名称'}, {value:'room_number',label:'BM确认房号'},
  {value:'commencement_date',label:'合同开始/入住日期'}, {value:'end_date',label:'合同结束日期'}, {value:'lease_months',label:'租期（月）'}, {value:'monthly_rent',label:'月租'}, {value:'rent_currency',label:'币种'}, {value:'security_deposit',label:'押金'}, {value:'utilities_deposit',label:'杂费押金'}, {value:'payment_due_day',label:'每月付款日'}, {value:'generated_date',label:'合同生成日期'},
  {value:'tenant.chinese_name',label:'租客中文姓名'}, {value:'tenant.given_name',label:'租客英文名'}, {value:'tenant.surname',label:'租客英文姓'},
  {value:'tenant.email',label:'租客邮箱'}, {value:'tenant.phone',label:'租客电话'}, {value:'tenant.birth_date',label:'租客出生日期'},
  {value:'booking.contract_start',label:'入住/合同开始日期'}, {value:'booking.contract_end',label:'合同结束日期'}, {value:'booking.room_number',label:'BM确认房号'}, {value:'contract.agreement_number',label:'合同编号'},
]
function selectBinding(){const binding=bindings.value.find(item=>item.institute_id===form.value.institute_id&&item.is_active)||null;activeBinding.value=binding;if(binding){form.value.provider_template_id=binding.provider_template_id;form.value.signer_role=binding.signer_role;mappingRows.value=Object.entries(binding.field_mapping||{}).map(([templateField,sourceField])=>({templateField,sourceField}))}else{form.value.provider_template_id='';form.value.signer_role='TENANT';mappingRows.value=[]}}
async function loadDropboxTemplates(){templateLoading.value=true;try{const result=await api.get('/contracts/dropbox-sign/templates',{params:{query:'Lease Agreement'},suppressGlobalError:true} as any);remoteTemplates.value=result.data.items||[];if(!remoteTemplates.value.length)ElMessage.info('当前 Dropbox 账号下未找到可访问的 Lease Agreement 模板')}catch(error:any){ElMessage.error(extractErrorMessage(error)||'无法读取 Dropbox Sign 模板，请检查本地 API Key 配置')}finally{templateLoading.value=false}}
function applyRemoteTemplate(){const item=remoteTemplates.value.find(template=>template.template_id===selectedRemoteTemplateId.value);if(!item)return;form.value.provider_template_id=item.template_id;if(item.signer_roles.length===1)form.value.signer_role=item.signer_roles[0]}
async function load(){loading.value=true;try{const [buildingResult,bindingResult,configResult]=await Promise.all([api.get('/buildings/managed',{params:{limit:200},suppressGlobalError:true} as any),api.get('/contracts/dropbox-sign/bindings',{suppressGlobalError:true} as any),api.get('/contracts/dropbox-sign/configuration-status',{suppressGlobalError:true} as any)]);buildings.value=buildingResult.data.items||[];bindings.value=bindingResult.data||[];config.value=configResult.data;if(form.value.institute_id)selectBinding()}catch(error:any){ElMessage.error(extractErrorMessage(error)||'Dropbox Sign 模板配置加载失败')}finally{loading.value=false}}
async function save(){if(!form.value.institute_id||!form.value.provider_template_id||!form.value.signer_role){ElMessage.warning('请选择公寓，并填写 Template ID 和租客签署角色');return}const field_mapping:Record<string,string>={};for(const row of mappingRows.value){if(!row.templateField&&!row.sourceField)continue;if(!row.templateField||!row.sourceField){ElMessage.warning('每条字段映射都必须完整');return}field_mapping[row.templateField]=row.sourceField}saving.value=true;try{const payload={institute_id:form.value.institute_id,provider_template_id:form.value.provider_template_id,signer_role:form.value.signer_role,field_mapping};if(activeBinding.value){await api.put(`/contracts/dropbox-sign/bindings/${activeBinding.value.id}`,payload,{suppressGlobalError:true} as any)}else{await api.post('/contracts/dropbox-sign/bindings',payload,{suppressGlobalError:true} as any)}ElMessage.success('Dropbox Sign 模板绑定已保存');await load();selectBinding()}catch(error:any){ElMessage.error(extractErrorMessage(error)||'保存 Dropbox Sign 模板绑定失败')}finally{saving.value=false}}
async function deactivate(){if(!activeBinding.value)return;try{await ElMessageBox.confirm('停用后，新订单不会再使用此 Dropbox 模板；历史签署记录不会删除。','停用模板绑定',{type:'warning'});saving.value=true;await api.delete(`/contracts/dropbox-sign/bindings/${activeBinding.value.id}`,{suppressGlobalError:true} as any);ElMessage.success('模板绑定已停用');await load();selectBinding()}catch(error:any){if(error!=='cancel')ElMessage.error(extractErrorMessage(error)||'停用模板绑定失败')}finally{saving.value=false}}
onMounted(load)
</script>

<style scoped>
.page-container{max-width:980px;margin:0 auto;padding:24px}.header{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:16px}.header h2{margin:0}.header p,.hint{color:#687080;line-height:1.6}.form-card{margin-top:16px}.el-select{width:100%}.mapping-row{display:grid;grid-template-columns:minmax(200px,1fr) minmax(240px,1fr) auto;gap:10px;align-items:center;margin:10px 0}.actions{display:flex;gap:10px;margin-top:24px}@media(max-width:700px){.header{flex-direction:column}.mapping-row{grid-template-columns:1fr}.page-container{padding:16px}}
</style>

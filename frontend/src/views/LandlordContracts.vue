<template>
  <div class="page-container">
    <header class="page-header">
      <div><h2>房号确认</h2><p>确认实际可交付房号后，订单才能进入合同签署。</p></div>
      <div class="actions"><el-button @click="loadQueue">重新加载</el-button><el-button @click="$router.push('/contracts/templates')">合同模板管理</el-button></div>
    </header>
    <el-alert title="确认房号会锁定该房号，并将订单置为“待合同签署”；请核对入住日期和租期后操作。" type="warning" :closable="false" />
    <el-table v-loading="loading" :data="items" stripe empty-text="当前没有待确认房号的订单" class="queue">
      <el-table-column label="订单" width="90"><template #default="{row}">#{{ row.booking_id }}</template></el-table-column>
      <el-table-column label="租客" min-width="120"><template #default="{row}">{{ row.tenant_name }}</template></el-table-column>
      <el-table-column label="租客电话" min-width="130"><template #default="{row}">{{ row.tenant_phone || '未填写' }}</template></el-table-column>
      <el-table-column label="公寓信息" min-width="160"><template #default="{row}"><strong>{{ row.institute_name }}</strong></template></el-table-column>
      <el-table-column label="户型信息" min-width="150"><template #default="{row}">{{ row.unit_type_name || '未关联户型' }}</template></el-table-column>
      <el-table-column label="公寓方确认房号" min-width="250"><template #default="{row}"><el-input v-model="roomNumbers[row.booking_id]" placeholder="请输入公寓方确认的真实房号，例如 1401" clearable /><div class="room-hint">无需预加载房号；首次确认时系统会登记并锁定。{{ row.available_rooms.length ? `已登记可用：${row.available_rooms.map(room => room.room_number).join('、')}` : '' }}</div></template></el-table-column>
      <el-table-column label="操作" width="210" fixed="right"><template #default="{row}"><el-button type="primary" :disabled="!isValidRoom(row)" :loading="confirmingBookingId===row.booking_id" @click="confirmRoom(row)">确认</el-button><el-button type="danger" plain @click="cancelBooking(row)">取消订单</el-button></template></el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { extractErrorMessage } from '@/services/api'
interface Room { id:string; room_number:string; floor:string|null; status:string; unit_type_id:number|null }
interface QueueItem { booking_id:number; tenant_name:string; tenant_phone:string|null; institute_name:string; unit_type_name:string|null; available_rooms:Room[] }
const loading=ref(false), confirmingBookingId=ref<number|null>(null), items=ref<QueueItem[]>([]), roomNumbers=ref<Record<number,string>>({})
async function loadQueue(){ loading.value=true; try { const {data}=await api.get('/room-confirmations/pending'); items.value=data.items||[] } catch (error:any) { ElMessage.error(error?.response?.status===403?'当前账号没有房号确认权限':'房号确认队列加载失败，请重试') } finally { loading.value=false } }
function isValidRoom(item:QueueItem){return Boolean(roomNumbers.value[item.booking_id]?.trim())}
async function confirmRoom(item:QueueItem){ if(!isValidRoom(item))return; const roomNumber=roomNumbers.value[item.booking_id].trim(); confirmingBookingId.value=item.booking_id; try { const {data}=await api.post(`/room-confirmations/${item.booking_id}/confirm`,{room_number:roomNumber},{suppressGlobalError:true} as any); ElMessage.success(`房号 ${data.room_number} 已确认并锁定，合同已生成并发送给租客`); delete roomNumbers.value[item.booking_id]; await loadQueue() } catch(error:any){ const message=extractErrorMessage(error); ElMessage.error(message||'房号确认失败，请稍后重试') } finally { confirmingBookingId.value=null } }
async function cancelBooking(item:QueueItem){ try { await ElMessageBox.confirm(`确定取消订单 #${item.booking_id}？此操作会通知租客。`,'取消订单',{type:'warning',confirmButtonText:'确认取消'}); await api.post(`/room-confirmations/${item.booking_id}/cancel`); ElMessage.success('订单已取消，租客已收到通知'); await loadQueue() } catch(error:any) { if(error !== 'cancel') ElMessage.error(error?.response?.data?.detail||'取消订单失败') } }
onMounted(loadQueue)
</script>

<style scoped>
.page-container{max-width:1280px;margin:0 auto;padding:24px}.page-header{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:16px}.page-header h2{margin:0;font-size:24px}.page-header p{margin:6px 0 0;color:#687080}.actions{display:flex;gap:8px}.queue{margin-top:16px}.queue strong{font-weight:600}.queue span{font-size:12px;color:#687080}.room-hint{margin-top:6px;color:#687080;font-size:12px;line-height:1.5;word-break:break-all}@media(max-width:700px){.page-container{padding:16px}.page-header{flex-direction:column}.actions{width:100%;flex-wrap:wrap}}
</style>

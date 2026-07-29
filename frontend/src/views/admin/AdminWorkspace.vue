<template>
  <div class="workspace-page">
    <!-- ===== 顶部用户信息头部 ===== -->
    <el-card shadow="never" class="user-card">
      <div class="user-info">
        <el-avatar :size="64" :icon="UserFilled" />
        <div class="user-detail">
          <div class="user-name-row">
            <span class="user-name">{{ adminName }}</span>
            <el-tag type="danger" size="small" effect="dark">公寓运营管理员</el-tag>
            <el-tag v-if="verified" type="success" size="small">✓ 企业认证</el-tag>
            <el-tag v-else type="warning" size="small">待认证</el-tag>
          </div>
          <div class="user-contact">
            <span>📧 {{ adminEmail }}</span>
            <span>📱 {{ adminPhone }}</span>
            <span>🏢 负责片区：{{ adminDistrict }}</span>
            <span>📅 注册于 {{ adminSince }}</span>
          </div>
        </div>
        <div class="user-actions">
          <el-button type="primary" round @click="showEditProfile = true">编辑资料</el-button>
          <el-button round @click="showUploadQualification = true">资质上传</el-button>
        </div>
      </div>
    </el-card>

    <!-- ===== 统计卡片 ===== -->
    <div class="stats-grid">
      <div class="stat-card" v-for="s in statsCards" :key="s.label" @click="activeTab = s.tab">
        <span class="stat-icon">{{ s.icon }}</span>
        <div class="stat-info">
          <div class="stat-num">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-sub" v-if="s.sub">{{ s.sub }}</div>
        </div>
      </div>
    </div>

    <!-- ===== Tab 主体 ===== -->
    <el-card shadow="never" class="tabs-card">
      <el-tabs v-model="activeTab" class="workspace-tabs" type="border-card">
        <!-- Tab1: 托管房源管理 -->
        <el-tab-pane label="🏠 房源管理" name="properties">
          <div class="tab-toolbar">
            <el-radio-group v-model="propertyFilter" size="small">
              <el-radio-button value="all">全部 ({{ mockProperties.length }})</el-radio-button>
              <el-radio-button value="vacant">空置 ({{ vacantCount }})</el-radio-button>
              <el-radio-button value="rented">已出租 ({{ rentedCount }})</el-radio-button>
              <el-radio-button value="maintenance">维护中</el-radio-button>
              <el-radio-button value="pending">待上架</el-radio-button>
            </el-radio-group>
            <div>
              <el-button type="primary" size="small" @click="handleBatchAdd">批量新增</el-button>
              <el-button size="small" @click="handleBatchPublish">批量上架</el-button>
              <el-button size="small" type="warning" @click="handleBatchOffline">批量下架</el-button>
            </div>
          </div>
          <el-table :data="filteredProperties" stripe>
            <el-table-column type="selection" width="40" />
            <el-table-column label="地址" prop="address" min-width="180" />
            <el-table-column label="户型" width="90">
              <template #default="{ row }">{{ row.bedrooms }}室{{ row.bathrooms }}卫</template>
            </el-table-column>
            <el-table-column label="月租" width="100">
              <template #default="{ row }">¥{{ row.price }}</template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="statusTag(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="当前租客" width="100" prop="tenant" />
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="editProperty(row)">编辑</el-button>
                <el-button size="small" text type="warning" @click="maintainProperty(row)">维修</el-button>
                <el-button size="small" text @click="viewPropertyBookings(row)">预约记录</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- TabX: 房源审核 -->
        <el-tab-pane label="🔍 房源审核" name="review">
          <div class="tab-toolbar">
            <span style="color:#606266;font-size:14px">待审核房源由AI批量导入自动标记，需人工确认后上架</span>
            <el-button type="primary" size="small" @click="loadPendingReviews" :loading="reviewLoading">刷新</el-button>
          </div>
          <el-table :data="pendingReviews" stripe v-loading="reviewLoading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column label="封面" width="80">
              <template #default="{ row }">
                <span v-if="!row.images?.length" style="color:#c0c4cc;font-size:12px">无图</span>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
            <el-table-column prop="district" label="区域" width="90" />
            <el-table-column label="月租" width="100" align="right">
              <template #default="{ row }">¥{{ row.price_monthly }}</template>
            </el-table-column>
            <el-table-column label="面积" width="80" align="right">
              <template #default="{ row }">{{ row.area_sqm || '-' }}㎡</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag type="warning" size="small">⏳ 待审核</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="发布时间" width="110">
              <template #default="{ row }">{{ formatReviewDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button type="success" size="small" @click="reviewApprove(row)">✅ 通过</el-button>
                <el-button type="danger" size="small" plain @click="reviewReject(row)">❌ 驳回</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!reviewLoading && !pendingReviews.length" description="暂无待审核房源 🎉" />
        </el-tab-pane>

        <!-- Tab2: 看房预约管理 -->
        <el-tab-pane label="📅 预约管理" name="bookings">
          <div class="tab-toolbar">
            <el-radio-group v-model="bookingFilter" size="small">
              <el-radio-button value="all">全部 ({{ mockBookings.length }})</el-radio-button>
              <el-radio-button value="pending">待审核 ({{ pendingBookingCount }})</el-radio-button>
              <el-radio-button value="approved">已同意</el-radio-button>
              <el-radio-button value="rejected">已拒绝</el-radio-button>
              <el-radio-button value="cancelled">已取消</el-radio-button>
            </el-radio-group>
            <div>
              <el-button type="primary" size="small" @click="handleBatchRemind">批量发送提醒</el-button>
            </div>
          </div>
          <el-table :data="filteredBookings" stripe>
            <el-table-column label="房源" prop="property" min-width="160" />
            <el-table-column label="租客" prop="tenant" width="100" />
            <el-table-column label="手机" prop="phone" width="120" />
            <el-table-column label="预约时间" prop="date" width="110" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="bookingStatusTag(row.status)" size="small">{{ row.statusText }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="240">
              <template #default="{ row }">
                <el-button size="small" type="success" @click="approveBooking(row)">确认</el-button>
                <el-button size="small" type="danger" @click="rejectBooking(row)">驳回</el-button>
                <el-button size="small" text @click="viewTenantInfo(row)">租客信息</el-button>
                <el-button size="small" text type="warning" @click="markVisited(row)">已接待</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab3: 租赁合约管理 -->
        <el-tab-pane label="📄 合约管理" name="contracts">
          <div class="tab-toolbar">
            <el-radio-group v-model="contractFilter" size="small">
              <el-radio-button value="active">生效中 ({{ activeContractCount }})</el-radio-button>
              <el-radio-button value="expiring">即将到期</el-radio-button>
              <el-radio-button value="renewal">待续签</el-radio-button>
              <el-radio-button value="deposit">待签约定金</el-radio-button>
              <el-radio-button value="terminated">已解约</el-radio-button>
            </el-radio-group>
            <div>
              <el-button type="primary" size="small" @click="batchGenerateContracts">批量生成合同</el-button>
              <el-button size="small" @click="batchExportContracts">批量导出</el-button>
              <el-button size="small" type="warning" @click="batchRenewContracts">批量续租</el-button>
            </div>
          </div>
          <el-table :data="filteredContracts" stripe>
            <el-table-column label="合同编号" width="140" prop="id" />
            <el-table-column label="房源" prop="property" min-width="160" />
            <el-table-column label="租客" prop="tenant" width="100" />
            <el-table-column label="租期" width="180">
              <template #default="{ row }">{{ row.startDate }} ~ {{ row.endDate }}</template>
            </el-table-column>
            <el-table-column label="月租金" width="100" prop="rent" />
            <el-table-column label="押金" width="90" prop="deposit" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === '生效中' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="viewContract(row)">查看</el-button>
                <el-button size="small" text type="danger" @click="terminateContract(row)">解约</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab4: 财务收支 -->
        <el-tab-pane label="💰 财务中心" name="finance">
          <el-row :gutter="16" class="finance-summary">
            <el-col :span="6"><el-card shadow="hover"><el-statistic title="本月应收" :value="98500" prefix="¥" /></el-card></el-col>
            <el-col :span="6"><el-card shadow="hover"><el-statistic title="已收租金" :value="76200" prefix="¥" /></el-card></el-col>
            <el-col :span="6"><el-card shadow="hover"><el-statistic title="定金收入" :value="24500" prefix="¥" /></el-card></el-col>
            <el-col :span="6"><el-card shadow="hover"><el-statistic title="逾期未缴" :value="3" suffix="户"><template #suffix><el-tag type="danger" size="small">待催缴</el-tag></template></el-statistic></el-card></el-col>
          </el-row>
          <div class="tab-toolbar">
            <el-radio-group v-model="financeTab" size="small">
              <el-radio-button value="deposit">定金订单</el-radio-button>
              <el-radio-button value="rent">月度租金</el-radio-button>
              <el-radio-button value="ledger">收支明细</el-radio-button>
              <el-radio-button value="withdraw">提现管理</el-radio-button>
            </el-radio-group>
            <el-button type="primary" size="small">导出月度报表</el-button>
          </div>
          <el-table :data="financeData" stripe>
            <el-table-column label="流水号" prop="id" width="160" />
            <el-table-column label="类型" prop="type" width="100" />
            <el-table-column label="关联房源" prop="property" min-width="140" />
            <el-table-column label="租客" prop="tenant" width="90" />
            <el-table-column label="金额" prop="amount" width="110" />
            <el-table-column label="时间" prop="date" width="110" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === '已到账' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab5: 在住租客 -->
        <el-tab-pane label="👥 租客管理" name="tenants">
          <el-table :data="mockTenants" stripe>
            <el-table-column label="租客" prop="name" width="100" />
            <el-table-column label="手机" prop="phone" width="130" />
            <el-table-column label="入住房源" prop="property" min-width="160" />
            <el-table-column label="合同编号" prop="contractId" width="140" />
            <el-table-column label="月租金" prop="rent" width="100" />
            <el-table-column label="缴费状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.payStatus === '正常' ? 'success' : 'warning'" size="small">{{ row.payStatus }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="租期到期" prop="endDate" width="110" />
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="viewTenantDetail(row)">详情</el-button>
                <el-button size="small" text @click="viewTenantPayments(row)">缴费记录</el-button>
                <el-button size="small" text type="warning" @click="viewTenantRepairs(row)">报修</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab6: 维修工单 -->
        <el-tab-pane label="🔧 维修工单" name="repairs">
          <el-table :data="mockRepairs" stripe>
            <el-table-column label="工单号" prop="id" width="100" />
            <el-table-column label="房源" prop="property" min-width="160" />
            <el-table-column label="报修租客" prop="tenant" width="100" />
            <el-table-column label="问题描述" prop="desc" min-width="180" />
            <el-table-column label="报修时间" prop="date" width="110" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="repairStatusTag(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="assignRepair(row)">派单</el-button>
                <el-button size="small" type="success" @click="completeRepair(row)">完成</el-button>
                <el-button size="small" text @click="uploadRepairProof(row)">凭证</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab7: 咨询&消息 -->
        <el-tab-pane label="💬 消息中心" name="messages">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-card shadow="never" class="msg-card">
                <template #header><span>📩 租客咨询</span></template>
                <div v-for="m in mockMessages" :key="m.id" class="msg-item">
                  <div class="msg-header">
                    <strong>{{ m.tenant }}</strong>
                    <span class="msg-time">{{ m.time }}</span>
                    <el-tag v-if="!m.read" type="danger" size="small">新</el-tag>
                  </div>
                  <p class="msg-text">{{ m.text }}</p>
                  <el-button size="small" text type="primary" @click="replyMessage(m)">回复</el-button>
                </div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never" class="msg-card">
                <template #header><span>🔔 系统通知</span></template>
                <div v-for="n in mockSysNotices" :key="n.id" class="msg-item">
                  <span class="msg-time">{{ n.time }}</span>
                  <p class="msg-text">{{ n.text }}</p>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>

        <!-- Tab8: 门店设置 -->
        <el-tab-pane label="⚙️ 门店设置" name="settings">
          <el-row :gutter="24">
            <el-col :span="12">
              <el-card shadow="never" class="setting-card">
                <template #header>🔐 账号安全</template>
                <el-form label-width="100px">
                  <el-form-item label="工作手机"><el-input v-model="adminPhone" /></el-form-item>
                  <el-form-item label="登录密码"><el-input type="password" model-value="********" /></el-form-item>
                  <el-form-item label="企业微信"><el-tag type="success">已绑定</el-tag> <el-button size="small" text type="warning">解绑</el-button></el-form-item>
                  <el-form-item><el-button type="primary" size="small">保存修改</el-button></el-form-item>
                </el-form>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never" class="setting-card">
                <template #header>🏦 对公收款账户</template>
                <el-form label-width="100px">
                  <el-form-item label="开户银行"><el-input value="中国工商银行" /></el-form-item>
                  <el-form-item label="对公账号"><el-input value="6222 **** **** 8832" /></el-form-item>
                  <el-form-item label="账户名称"><el-input value="XX公寓管理有限公司" /></el-form-item>
                  <el-form-item><el-button type="primary" size="small">更新账户</el-button></el-form-item>
                </el-form>
              </el-card>
            </el-col>
          </el-row>
          <el-row :gutter="24" style="margin-top:16px">
            <el-col :span="12">
              <el-card shadow="never" class="setting-card">
                <template #header>📋 门店资质</template>
                <div class="qualification-list">
                  <div class="qual-item"><span>营业执照</span><el-tag type="success" size="small">已上传</el-tag><el-button size="small" text>查看</el-button></div>
                  <div class="qual-item"><span>产权合规材料</span><el-tag type="warning" size="small">待更新</el-tag><el-button size="small" text type="primary">上传</el-button></div>
                  <div class="qual-item"><span>运营人身份证</span><el-tag type="success" size="small">已认证</el-tag><el-button size="small" text>查看</el-button></div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never" class="setting-card">
                <template #header>🔔 消息推送设置</template>
                <div class="notif-switches">
                  <el-switch v-model="pushSettings.sms" active-text="短信通知" />
                  <el-switch v-model="pushSettings.site" active-text="站内通知" />
                  <el-switch v-model="pushSettings.booking" active-text="新预约提醒" />
                  <el-switch v-model="pushSettings.rent" active-text="租金到账通知" />
                  <el-switch v-model="pushSettings.expire" active-text="合约到期预警" />
                </div>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 编辑资料弹窗 -->
    <el-dialog v-model="showEditProfile" title="编辑管理员资料" width="500px">
      <el-form label-width="100px">
        <el-form-item label="头像"><el-upload action="#" :auto-upload="false" :show-file-list="false"><el-button size="small" round>更换头像</el-button></el-upload></el-form-item>
        <el-form-item label="工作手机"><el-input v-model="adminPhone" /></el-form-item>
        <el-form-item label="收款账户"><el-input placeholder="对公银行账号" /></el-form-item>
        <el-form-item label="运营简介"><el-input type="textarea" :rows="3" placeholder="介绍您的公寓运营经验..." /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showEditProfile = false">取消</el-button><el-button type="primary" @click="showEditProfile = false">保存</el-button></template>
    </el-dialog>

    <!-- 资质上传弹窗 -->
    <el-dialog v-model="showUploadQualification" title="资质材料上传" width="500px">
      <el-form label-width="120px">
        <el-form-item label="营业执照"><el-upload action="#" :auto-upload="false"><el-button type="primary" size="small">选择文件</el-button></el-upload></el-form-item>
        <el-form-item label="产权合规材料"><el-upload action="#" :auto-upload="false"><el-button type="primary" size="small">选择文件</el-button></el-upload></el-form-item>
        <el-form-item label="身份证核验"><el-upload action="#" :auto-upload="false"><el-button type="primary" size="small">选择文件</el-button></el-upload></el-form-item>
      </el-form>
      <template #footer><el-button @click="showUploadQualification = false">取消</el-button><el-button type="primary" @click="showUploadQualification = false">提交审核</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { UserFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// ── 管理员信息 ──
const adminName = ref('张经理')
const adminEmail = ref('zhang@rental.com')
const adminPhone = ref('139****5678')
const adminDistrict = ref('朝阳区·海淀区')
const adminSince = ref('2025-03-15')
const verified = ref(true)

const showEditProfile = ref(false)
const showUploadQualification = ref(false)

// ── 统计卡片 ──
const statsCards = [
  { icon: '🏠', label: '管理房源', value: 48, sub: `空置12 · 已租32 · 待上架4`, tab: 'properties' },
  { icon: '📅', label: '待处理预约', value: 8, sub: `今日看房 3 人次`, tab: 'bookings' },
  { icon: '💰', label: '本月应收', value: '¥98,500', sub: `待确认定金5 · 逾期3户`, tab: 'finance' },
  { icon: '📄', label: '合同统计', value: 35, sub: `30天内到期 6 份`, tab: 'contracts' },
  { icon: '🔧', label: '待处理工单', value: 4, sub: `报修2 · 投诉1 · 换房1`, tab: 'repairs' },
  { icon: '👁️', label: '今日访客', value: 156, sub: `咨询量 23 条`, tab: 'messages' },
]

// ── Tab 状态 ──
const activeTab = ref('properties')
const propertyFilter = ref('all')
const bookingFilter = ref('all')
const contractFilter = ref('active')
const financeTab = ref('deposit')
const pushSettings = reactive({ sms: true, site: true, booking: true, rent: true, expire: true })

// ── 辅助函数 ──
const statusTag = (s: string) => ({ '空置': 'info', '已出租': 'success', '维护中': 'warning', '待上架': 'danger' }[s] || 'info') as 'info'|'success'|'warning'|'danger'
const bookingStatusTag = (s: string) => ({ 'pending': 'warning', 'approved': 'success', 'rejected': 'danger', 'cancelled': 'info' }[s] || 'info') as 'warning'|'success'|'danger'|'info'
const repairStatusTag = (s: string) => ({ '待处理': 'danger', '已派单': 'warning', '维修中': '', '已完成': 'success' }[s] || 'info') as 'danger'|'warning'|''|'success'|'info'

// ── Mock 数据 ──
const mockProperties = [
  { id: 1, address: '朝阳区建国路88号 阳光花园 3-1502', bedrooms: 2, bathrooms: 1, price: 6500, status: '空置', tenant: '—' },
  { id: 2, address: '海淀区中关村南大街12号 融科A座', bedrooms: 1, bathrooms: 1, price: 4500, status: '已出租', tenant: '李明' },
  { id: 3, address: '西城区新文化街56号 学区房', bedrooms: 3, bathrooms: 2, price: 12000, status: '已出租', tenant: '王芳' },
  { id: 4, address: '丰台区丰台南路188号 独栋', bedrooms: 5, bathrooms: 3, price: 25000, status: '空置', tenant: '—' },
  { id: 5, address: '朝阳区望京街10号 望京SOHO', bedrooms: 1, bathrooms: 1, price: 3800, status: '维护中', tenant: '—' },
  { id: 6, address: '东城区南锣鼓巷18号 四合院', bedrooms: 1, bathrooms: 1, price: 3000, status: '待上架', tenant: '—' },
  { id: 7, address: '朝阳区朝阳公园南路 观湖国际', bedrooms: 3, bathrooms: 2, price: 15000, status: '空置', tenant: '—' },
]

const vacantCount = computed(() => mockProperties.filter(p => p.status === '空置').length)
const rentedCount = computed(() => mockProperties.filter(p => p.status === '已出租').length)
const filteredProperties = computed(() => {
  if (propertyFilter.value === 'all') return mockProperties
  const map: Record<string, string> = { vacant: '空置', rented: '已出租', maintenance: '维护中', pending: '待上架' }
  return mockProperties.filter(p => p.status === map[propertyFilter.value])
})

const mockBookings = [
  { id: 1, property: '朝阳区阳光花园 3-1502', tenant: '刘先生', phone: '138****2345', date: '2026-06-28', status: 'pending', statusText: '待审核' },
  { id: 2, property: '丰台区独栋别墅', tenant: '赵女士', phone: '139****6789', date: '2026-06-29', status: 'pending', statusText: '待审核' },
  { id: 3, property: '海淀区融科A座', tenant: '孙先生', phone: '136****8901', date: '2026-06-27', status: 'approved', statusText: '已同意' },
  { id: 4, property: '朝阳区望京SOHO', tenant: '周女士', phone: '137****3456', date: '2026-06-26', status: 'rejected', statusText: '已拒绝' },
]
const pendingBookingCount = computed(() => mockBookings.filter(b => b.status === 'pending').length)
const filteredBookings = computed(() => {
  if (bookingFilter.value === 'all') return mockBookings
  return mockBookings.filter(b => b.status === bookingFilter.value)
})

const mockContracts = [
  { id: 'HT20260601001', property: '海淀区融科A座', tenant: '李明', startDate: '2026-06-01', endDate: '2027-05-31', rent: '¥4,500', deposit: '¥4,500', status: '生效中' },
  { id: 'HT20260515002', property: '西城区学区房', tenant: '王芳', startDate: '2026-05-15', endDate: '2027-05-14', rent: '¥12,000', deposit: '¥12,000', status: '生效中' },
  { id: 'HT20260301003', property: '朝阳区观湖国际', tenant: '张伟', startDate: '2026-03-01', endDate: '2026-08-31', rent: '¥15,000', deposit: '¥15,000', status: '即将到期' },
  { id: 'HT20260620004', property: '朝阳区阳光花园', tenant: '刘先生', startDate: '—', endDate: '—', rent: '¥6,500', deposit: '¥6,500', status: '待签约定金' },
]
const activeContractCount = computed(() => mockContracts.filter(c => c.status === '生效中').length)
const filteredContracts = computed(() => {
  if (contractFilter.value === 'active') return mockContracts.filter(c => c.status === '生效中')
  if (contractFilter.value === 'expiring') return mockContracts.filter(c => c.status === '即将到期')
  if (contractFilter.value === 'deposit') return mockContracts.filter(c => c.status === '待签约定金')
  return mockContracts
})

const financeData = [
  { id: 'PAY20260628001', type: '定金', property: '朝阳区阳光花园', tenant: '刘先生', amount: '¥6,500', date: '2026-06-28', status: '已到账' },
  { id: 'PAY20260625002', type: '租金', property: '海淀区融科A座', tenant: '李明', amount: '¥4,500', date: '2026-06-25', status: '已到账' },
  { id: 'PAY20260620003', type: '租金', property: '西城区学区房', tenant: '王芳', amount: '¥12,000', date: '2026-06-20', status: '待确认' },
  { id: 'PAY20260615004', type: '维修支出', property: '朝阳区望京SOHO', tenant: '—', amount: '-¥800', date: '2026-06-15', status: '已支出' },
]

const mockTenants = [
  { name: '李明', phone: '138****2345', property: '海淀区融科A座', contractId: 'HT20260601001', rent: '¥4,500', payStatus: '正常', endDate: '2027-05-31' },
  { name: '王芳', phone: '139****6789', property: '西城区学区房', contractId: 'HT20260515002', rent: '¥12,000', payStatus: '正常', endDate: '2027-05-14' },
  { name: '张伟', phone: '136****8901', property: '朝阳区观湖国际', contractId: 'HT20260301003', rent: '¥15,000', payStatus: '逾期', endDate: '2026-08-31' },
]

const mockRepairs = [
  { id: 'WO001', property: '朝阳区阳光花园 3-1502', tenant: '刘先生', desc: '主卧空调不制冷，需维修', date: '2026-06-27', status: '待处理' },
  { id: 'WO002', property: '海淀区融科A座', tenant: '李明', desc: '厨房水槽漏水', date: '2026-06-25', status: '已派单' },
  { id: 'WO003', property: '西城区学区房', tenant: '王芳', desc: '热水器无法正常加热', date: '2026-06-22', status: '维修中' },
]

const mockMessages = [
  { id: 1, tenant: '刘先生', time: '10分钟前', text: '请问明天下午可以看房吗？我对朝阳区那套两居室很感兴趣。', read: false },
  { id: 2, tenant: '赵女士', time: '1小时前', text: '独栋别墅的定金我已经支付了，请查收。', read: false },
  { id: 3, tenant: '孙先生', time: '昨天', text: '请问合同什么时候可以签？', read: true },
]

const mockSysNotices = [
  { id: 1, time: '今天 09:30', text: '🔔 刘先生预约明天看房 — 朝阳区阳光花园 3-1502' },
  { id: 2, time: '今天 08:00', text: '💰 李明已缴纳6月租金 ¥4,500 — 海淀区融科A座' },
  { id: 3, time: '昨天 18:00', text: '⚠️ 张伟租约将于8月31日到期，请及时续签' },
]

// ── 操作函数 ──
function editProperty(row: any) { ElMessage.info(`编辑房源: ${row.address}`) }
function maintainProperty(row: any) { ElMessage.info(`标记维修: ${row.address}`) }
function viewPropertyBookings(row: any) { ElMessage.info(`查看预约记录: ${row.address}`) }
function handleBatchAdd() { ElMessage.info('批量新增房源') }
function handleBatchPublish() { ElMessage.info('批量上架房源') }
function handleBatchOffline() { ElMessage.info('批量下架房源') }

function approveBooking(row: any) { ElMessage.success(`已确认 ${row.tenant} 的看房预约`) }
function rejectBooking(row: any) { ElMessage.info(`已驳回 ${row.tenant} 的看房预约`) }
function handleBatchRemind() { ElMessage.info('批量发送看房提醒') }
function viewTenantInfo(row: any) { ElMessage.info(`查看租客信息: ${row.tenant}`) }
function markVisited(row: any) { ElMessage.success(`已标记 ${row.tenant} 为已接待`) }

function batchGenerateContracts() { ElMessage.info('批量生成电子合同') }
function batchExportContracts() { ElMessage.info('批量导出合同') }
function batchRenewContracts() { ElMessage.info('批量发起续租') }
function viewContract(row: any) { ElMessage.info(`查看合同: ${row.id}`) }
function terminateContract(row: any) { ElMessageBox.confirm(`确定解除合同 ${row.id}？`, '确认解约', { type: 'warning' }).then(() => ElMessage.success('已发起解约')) }

function viewTenantDetail(row: any) { ElMessage.info(`查看租客详情: ${row.name}`) }
function viewTenantPayments(row: any) { ElMessage.info(`查看缴费记录: ${row.name}`) }
function viewTenantRepairs(row: any) { ElMessage.info(`查看报修历史: ${row.name}`) }

function assignRepair(row: any) { ElMessage.success(`工单 ${row.id} 已派单`) }
function completeRepair(row: any) { ElMessage.success(`工单 ${row.id} 已标记完成`) }
function uploadRepairProof(row: any) { ElMessage.info(`上传维修凭证: ${row.id}`) }

function replyMessage(m: any) { ElMessage.info(`回复 ${m.tenant} 的消息`) }

// ── 房源审核（真实数据）───
import { adminService } from '@/services/admin'
import type { Property } from '@/types/property'

const reviewLoading = ref(false)
const pendingReviews = ref<Property[]>([])

function formatReviewDate(d: string) {
  return new Date(d).toLocaleDateString('zh-CN')
}

async function loadPendingReviews() {
  reviewLoading.value = true
  try {
    pendingReviews.value = await adminService.getPendingProperties()
  } catch {
    ElMessage.error('加载待审核房源失败')
  } finally {
    reviewLoading.value = false
  }
}

async function reviewApprove(row: Property) {
  try {
    await adminService.moderateProperty(row.id, 'available')
    ElMessage.success(`房源 #${row.id} 已通过审核并上架`)
    loadPendingReviews()
  } catch { ElMessage.error('操作失败') }
}

async function reviewReject(row: Property) {
  try {
    await ElMessageBox.confirm('确认驳回该房源？', '驳回确认', { type: 'warning' })
    await adminService.moderateProperty(row.id, 'offline')
    ElMessage.success(`房源 #${row.id} 已驳回`)
    loadPendingReviews()
  } catch { /* cancelled */ }
}

// 页面加载时自动拉取
loadPendingReviews()
</script>

<style scoped>
.workspace-page { max-width: 1200px; margin: 0 auto; }

/* ── User Card ── */
.user-card { margin-bottom: 20px; }
.user-info { display: flex; align-items: center; gap: 20px; }
.user-detail { flex: 1; }
.user-name-row { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.user-name { font-size: 20px; font-weight: 700; color: var(--text-primary); }
.user-contact { display: flex; gap: 20px; font-size: 13px; color: var(--text-muted); flex-wrap: wrap; }
.user-actions { display: flex; gap: 10px; flex-shrink: 0; }

/* ── Stats Grid ── */
.stats-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 20px; }
.stat-card { background: var(--bg-white); border-radius: var(--radius); border: 1px solid var(--border); padding: 14px 12px; display: flex; align-items: center; gap: 10px; cursor: pointer; transition: all 0.2s; min-height: 70px; }
.stat-card:hover { border-color: var(--primary); box-shadow: var(--shadow); transform: translateY(-2px); }
.stat-icon { font-size: 24px; }
.stat-num { font-size: 20px; font-weight: 700; color: var(--text-primary); }
.stat-label { font-size: 12px; color: var(--text-muted); }
.stat-sub { font-size: 11px; color: var(--text-muted); margin-top: 2px; }

/* ── Tabs ── */
.tabs-card { border-radius: var(--radius) !important; }
.workspace-tabs :deep(.el-tabs__item) { font-size: 14px; font-weight: 500; }
.tab-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }

/* ── Finance ── */
.finance-summary { margin-bottom: 16px; }

/* ── Messages ── */
.msg-card { height: 400px; overflow-y: auto; }
.msg-item { padding: 10px 0; border-bottom: 1px solid var(--border-light); }
.msg-item:last-child { border-bottom: none; }
.msg-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.msg-time { font-size: 12px; color: var(--text-muted); margin-left: auto; }
.msg-text { font-size: 13px; color: var(--text-secondary); margin: 4px 0; }

/* ── Settings ── */
.setting-card { margin-bottom: 16px; }
.qualification-list { display: flex; flex-direction: column; gap: 12px; }
.qual-item { display: flex; align-items: center; gap: 12px; font-size: 14px; }
.notif-switches { display: flex; flex-direction: column; gap: 12px; }
</style>

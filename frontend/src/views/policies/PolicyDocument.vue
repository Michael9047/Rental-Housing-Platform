<!-- 政策文档通用展示页——根据 route meta.policyKey 渲染对应内容 -->
<template>
  <div class="policy-document-page">
    <div class="policy-header">
      <el-button text :icon="ArrowLeft" @click="$router.back()">返回</el-button>
      <h2>{{ currentPolicy.title }}</h2>
    </div>
    <el-card shadow="never" class="policy-card">
      <div class="policy-body">
        <pre>{{ currentPolicy.content }}</pre>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()

const policyKey = computed(() => (route.meta.policyKey as string) || 'booking-authorization')

interface PolicyInfo {
  title: string
  content: string
}

const POLICIES: Record<string, PolicyInfo> = {
  'booking-authorization': {
    title: '订房授权书',
    content: `订房授权书

一、授权范围
本协议旨在授权平台代为办理房源预订相关事宜。

二、授权内容
1. 您授权平台将您提供的个人信息（包括但不限于姓名、联系方式、证件信息等）提交给房源供应方用于预订申请。
2. 您确认所提供的信息真实、准确、完整。

三、授权期限
本授权自您确认提交之日起生效，至预订流程完成或您主动撤销授权时终止。

四、信息使用
您的个人信息仅用于房源预订目的，平台将采取合理措施保护您的信息安全。

五、撤销授权
您有权随时通过平台客服渠道撤销本授权，撤销后平台将停止使用您的信息进行预订。

六、其他
本授权书的最终解释权归平台所有。如有争议，双方应友好协商解决。`
  },
  'cross-border-data': {
    title: '个人信息出境授权声明',
    content: `个人信息出境授权声明

一、声明目的
根据相关法律法规，您的个人信息在跨境传输前需要获得您的明确授权。

二、出境信息范围
本次出境的信息包括：
· 身份信息：姓名、性别、出生日期
· 联系信息：联系电话、电子邮箱、住址
· 教育信息：学校名称、专业、入学年级
· 担保人信息：姓名、联系方式、住址
· 紧急联系人信息：姓名、联系方式、住址

三、出境目的
将上述信息提供给境外房源供应方，仅用于房源预订申请。

四、接收方
房源所在国家/地区的公寓管理方及其指定的物业管理公司。

五、保护措施
我们将采取合同约定、技术加密等措施保障您的个人信息在境外的安全。

六、您的权利
您有权随时撤回本授权。撤回后我们将停止继续传输您的信息，但不影响撤回前已进行的处理。`
  },
  'privacy': {
    title: '隐私政策',
    content: `隐私政策

一、信息收集
我们收集的信息包括：
· 注册信息：用户名、密码、联系方式
· 个人资料：姓名、证件信息、教育背景
· 使用信息：浏览记录、搜索历史、预订记录
· 设备信息：IP地址、设备型号、操作系统

二、信息使用
我们使用收集的信息用于：
· 提供和改进房源搜索与预订服务
· 处理支付和合同签署
· 发送服务相关通知
· 保障账户和交易安全

三、信息存储
您的信息存储在安全的服务器上，我们将采取合理的技术和管理措施保护您的信息安全。

四、信息共享
未经您的明确同意，我们不会将您的个人信息分享给第三方，但以下情况除外：
· 完成房源预订所需的信息提交
· 法律法规要求的披露
· 保护平台、用户或公众的合法权益

五、您的权利
· 访问和更正您的个人信息
· 删除您的账户和相关数据
· 撤回授权同意
· 导出您的数据副本

六、联系我们
如对隐私政策有任何疑问，请通过平台客服渠道联系我们。`
  },
  'cancellation': {
    title: '公寓退订政策',
    content: `公寓退订政策

一、免责退订条件
以下情况可申请免责退订：
1. 签证被拒：需提供官方拒签证明文件
2. 学校录取被撤回：需提供学校官方通知
3. 入住前30天以上取消：扣除服务费后退还剩余款项

二、普通退订
1. 入住前15-30天取消：退还50%预付租金
2. 入住前7-14天取消：退还30%预付租金
3. 入住前7天内取消：预付租金不予退还

三、退订流程
1. 通过平台提交退订申请
2. 上传相关证明材料（如适用）
3. 平台审核（1-3个工作日）
4. 审核通过后，退款将原路返回（5-10个工作日）

四、特殊说明
· 服务费一经支付不予退还
· 已签署合同的情况按合同条款执行
· 平台保留根据实际情况调整退订政策的权利`
  }
}

const currentPolicy = computed<PolicyInfo>(() => {
  return POLICIES[policyKey.value] || { title: '协议文档', content: '文档内容暂无' }
})
</script>

<style scoped>
.policy-document-page {
  max-width: 860px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.policy-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.policy-header h2 {
  margin: 0;
  font-size: 20px;
}

.policy-card {
  margin-bottom: 16px;
}

.policy-body {
  padding: 8px 0;
}

.policy-body pre {
  margin: 0;
  white-space: pre-wrap;
  font: inherit;
  line-height: 1.9;
  color: var(--text-primary);
}
</style>

<template>
  <main class="policy-page">
    <el-card class="policy-card" shadow="never">
      <template #header>
        <div class="policy-header">
          <el-button text @click="router.back()">← 返回</el-button>
          <h1>{{ policy.title }}</h1>
        </div>
      </template>

      <p class="updated-at">最近更新：2026 年 7 月 22 日</p>
      <section v-for="section in policy.sections" :key="section.title">
        <h2>{{ section.title }}</h2>
        <p>{{ section.content }}</p>
      </section>
    </el-card>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

interface PolicySection {
  title: string
  content: string
}

interface PolicyContent {
  title: string
  sections: PolicySection[]
}

const route = useRoute()
const router = useRouter()

const policies: Record<string, PolicyContent> = {
  'booking-authorization': {
    title: '预订授权说明',
    sections: [
      { title: '授权范围', content: '提交预订申请即表示您授权平台将必要的申请资料提供给房源管理方，用于资格审核、合同准备和入住安排。' },
      { title: '信息准确性', content: '请确保提交的信息真实、完整、有效。因信息错误造成的审核延误由申请人自行承担。' },
    ],
  },
  'cross-border-data': {
    title: '跨境数据传输说明',
    sections: [
      { title: '适用场景', content: '预订境外房源时，必要资料可能传输至房源所在国家或地区的管理方和服务提供商。' },
      { title: '保护措施', content: '平台仅传输履行预订与租赁服务所需的信息，并要求接收方采取合理的安全保护措施。' },
    ],
  },
  privacy: {
    title: '预订隐私说明',
    sections: [
      { title: '信息使用', content: '个人信息仅用于身份核验、预订审核、合同签署、付款与入住服务。' },
      { title: '信息保存', content: '平台会在法律要求和服务所需的期限内保存信息，超过期限后将删除或匿名化处理。' },
    ],
  },
  cancellation: {
    title: '取消与退款规则',
    sections: [
      { title: '取消申请', content: '取消规则以具体房源和订单页面展示的条款为准。提交申请前请仔细确认付款节点和退款条件。' },
      { title: '退款时效', content: '符合退款条件的款项将在审核完成后原路退回，实际到账时间取决于支付机构。' },
    ],
  },
}

const policy = computed<PolicyContent>(() => {
  const key = String(route.meta.policyKey || '')
  return policies[key] || policies.privacy
})
</script>

<style scoped>
.policy-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 32px 20px 64px;
}

.policy-card {
  background: #fff;
}

.policy-header {
  display: flex;
  align-items: center;
  gap: 16px;
}

.policy-header h1 {
  margin: 0;
  font-size: 24px;
}

.updated-at {
  color: #909399;
  margin-bottom: 28px;
}

section + section {
  margin-top: 28px;
}

h2 {
  font-size: 18px;
  margin-bottom: 10px;
}

p {
  line-height: 1.8;
}
</style>

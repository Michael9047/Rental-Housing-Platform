<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="720px"
    class="agreement-dialog"
  >
    <div class="agreement-content">
      <div v-if="type === 'booking'">
        <h3>订房授权书</h3>
        <p class="agreement-date">授权日期：{{ currentDate }}</p>
        
        <h4>一、授权人信息</h4>
        <div class="info-table">
          <div class="table-row">
            <span class="table-label">中文姓名：</span>
            <span class="table-value">{{ bookingFlow.applicant.chinese_name || '________' }}</span>
          </div>
          <div class="table-row">
            <span class="table-label">拼音姓名：</span>
            <span class="table-value">{{ bookingFlow.applicant.surname_pinyin }} {{ bookingFlow.applicant.given_name_pinyin || '________' }}</span>
          </div>
          <div class="table-row">
            <span class="table-label">联系电话：</span>
            <span class="table-value">{{ bookingFlow.applicant.phone || '________' }}</span>
          </div>
          <div class="table-row">
            <span class="table-label">电子邮箱：</span>
            <span class="table-value">{{ bookingFlow.applicant.email || '________' }}</span>
          </div>
        </div>

        <h4>二、授权事项</h4>
        <p>本人（授权人）在此不可撤销地授权本平台及其合作的海外公寓供应商（以下简称"被授权人"），根据本人提交的预订申请信息，代表本人办理以下公寓预订相关事宜：</p>
        <ol class="agreement-list">
          <li>向公寓管理方提交预订申请，确认房源可用性、价格及入住资格审核；</li>
          <li>代为签署电子订房确认函、入住协议及相关法律文件；</li>
          <li>代为缴纳预订押金、首月租金及其他相关费用（以公寓规定为准）；</li>
          <li>在预订成功后，代为接收并转递公寓方发送的入住指南、门禁信息等资料；</li>
          <li>在符合退订政策的情况下，代为办理退订申请及退款手续；</li>
          <li>向学校或相关机构提交住宿证明文件（如适用）；</li>
          <li>处理预订过程中出现的问题和纠纷，维护授权人的合法权益。</li>
        </ol>

        <h4>三、授权期限</h4>
        <p>本授权书自授权人确认之日起生效，至本次预订相关的所有事项（包括入住、续租或退租）全部办理完毕之日止。</p>

        <h4>四、授权人声明与保证</h4>
        <ol class="agreement-list">
          <li>本人已仔细阅读并完全理解本授权书的所有条款；</li>
          <li>本人承诺所提供的所有预订信息（包括但不限于身份信息、联系方式、留学信息等）均真实、准确、完整；</li>
          <li>本人知晓并同意被授权人按照公寓方的要求处理预订相关事宜；</li>
          <li>本人愿意承担因提供虚假信息或违反预订条款而产生的全部责任和损失；</li>
          <li>本人确认已充分了解所预订房源的价格、租期、退订政策等重要信息。</li>
        </ol>

        <h4>五、免责条款</h4>
        <p>被授权人仅作为授权人的代理人办理预订事宜，不对公寓方的服务质量、房源状况等承担直接责任。如因公寓方原因导致预订无法完成或产生纠纷，被授权人将协助授权人与公寓方协商解决。</p>

        <h4>六、争议解决</h4>
        <p>因本授权书引起的或与本授权书有关的任何争议，双方应首先通过友好协商解决；协商不成的，任何一方均有权向本平台所在地有管辖权的人民法院提起诉讼。</p>
      </div>

      <div v-else-if="type === 'data'">
        <h3>个人信息出境授权声明</h3>
        <p class="agreement-date">声明日期：{{ currentDate }}</p>

        <h4>一、声明背景</h4>
        <p>本人（以下简称"授权人"）为完成海外公寓预订申请，需要将部分个人信息跨境传输至海外公寓供应商及相关合作机构。根据《中华人民共和国个人信息保护法》等相关法律法规的要求，本人在此作出如下授权声明：</p>

        <h4>二、出境信息范围</h4>
        <p>本人同意将以下个人信息传输至境外接收方：</p>
        <div class="info-category">
          <h5>（一）基本身份信息</h5>
          <ul>
            <li>姓名（中文及拼音）</li>
            <li>性别</li>
            <li>出生日期</li>
            <li>国籍/地区</li>
            <li>护照号码（如适用）</li>
          </ul>
        </div>
        <div class="info-category">
          <h5>（二）联系方式</h5>
          <ul>
            <li>手机号码</li>
            <li>电子邮箱地址</li>
          </ul>
        </div>
        <div class="info-category">
          <h5>（三）住址信息</h5>
          <ul>
            <li>国内联系地址</li>
            <li>邮政编码</li>
          </ul>
        </div>
        <div class="info-category">
          <h5>（四）留学相关信息</h5>
          <ul>
            <li>学校名称</li>
            <li>入学年级</li>
            <li>专业名称（英文）</li>
          </ul>
        </div>
        <div class="info-category">
          <h5>（五）担保人及紧急联系人信息</h5>
          <ul>
            <li>担保人姓名、联系方式、地址</li>
            <li>紧急联系人姓名、联系方式、地址</li>
          </ul>
        </div>

        <h4>三、信息使用目的</h4>
        <p>上述信息仅用于以下目的：</p>
        <ol class="agreement-list">
          <li>审核预订申请资格；</li>
          <li>办理入住登记及合同签署；</li>
          <li>履行当地法律法规要求的报备义务；</li>
          <li>紧急情况下的联系与协助；</li>
          <li>提供预订相关的客户服务。</li>
        </ol>

        <h4>四、信息安全保障</h4>
        <p>本平台承诺将严格按照《中华人民共和国个人信息保护法》及相关法律法规的要求，采取必要的技术和管理措施保护您的个人信息安全。具体措施包括但不限于：</p>
        <ul>
          <li>数据加密传输和存储；</li>
          <li>访问控制和权限管理；</li>
          <li>定期安全审计和风险评估；</li>
          <li>与境外接收方签订数据处理协议，明确保密义务和安全责任。</li>
        </ul>

        <h4>五、授权性质</h4>
        <p>本授权为本人自愿作出，本人有权随时撤回授权。撤回授权应通过书面形式通知本平台。但撤回前基于授权已进行的信息处理活动不受影响。</p>

        <h4>六、法律效力</h4>
        <p>本人确认已充分了解信息出境的相关风险，并自愿承担由此产生的法律后果。本声明自本人确认之日起生效。</p>
      </div>

      <div v-else-if="type === 'privacy'">
        <h3>隐私政策</h3>
        <p class="agreement-date">生效日期：2024年1月1日</p>

        <h4>一、引言</h4>
        <p>我们非常重视您的个人信息保护。本隐私政策旨在向您说明我们如何收集、使用、存储和保护您的个人信息，以及您享有的相关权利。请在使用我们的服务前仔细阅读本政策。</p>

        <h4>二、信息收集</h4>
        <p>我们会收集您在使用服务过程中主动提供的信息，以及通过合法方式获取的信息：</p>
        <div class="info-category">
          <h5>（一）注册及账户信息</h5>
          <p>当您注册账户时，我们会收集您的用户名、密码、手机号码、电子邮箱等信息。</p>
        </div>
        <div class="info-category">
          <h5>（二）预订信息</h5>
          <p>当您进行房源预订时，我们会收集您的身份信息、联系方式、住址、留学信息、担保人信息等。</p>
        </div>
        <div class="info-category">
          <h5>（三）支付信息</h5>
          <p>当您进行支付时，我们会收集必要的支付信息（如银行卡号、支付账户等），但不会存储您的完整支付密码。</p>
        </div>
        <div class="info-category">
          <h5>（四）使用行为信息</h5>
          <p>我们会收集您使用服务时的行为信息，包括浏览记录、搜索记录、预订记录等，用于优化服务和提供个性化推荐。</p>
        </div>

        <h4>三、信息使用</h4>
        <p>收集的信息将用于以下目的：</p>
        <ol class="agreement-list">
          <li>提供房源搜索、预订、支付等核心服务；</li>
          <li>客户服务与售后支持；</li>
          <li>产品优化与个性化推荐；</li>
          <li>安全风控与反欺诈；</li>
          <li>法律法规要求的合规处理；</li>
          <li>与合作方共享以完成预订服务（需单独授权）。</li>
        </ol>

        <h4>四、信息存储与安全</h4>
        <div class="info-category">
          <h5>（一）存储期限</h5>
          <p>我们会在实现信息使用目的所需的最短期限内保留您的个人信息。超出保留期限后，我们会对您的个人信息进行删除或匿名化处理。</p>
        </div>
        <div class="info-category">
          <h5>（二）安全措施</h5>
          <p>我们采用行业标准的安全技术和管理措施，包括但不限于：</p>
          <ul>
            <li>数据加密传输（HTTPS/SSL）</li>
            <li>数据加密存储</li>
            <li>访问控制和权限管理</li>
            <li>安全审计和监控</li>
            <li>定期安全培训</li>
          </ul>
        </div>

        <h4>五、信息共享</h4>
        <p>未经您的同意，我们不会向第三方共享您的个人信息，以下情况除外：</p>
        <ol class="agreement-list">
          <li>为完成预订服务必要的公寓供应商、支付机构等合作方（已签订数据处理协议）；</li>
          <li>法律法规要求或司法机关依法定程序要求；</li>
          <li>为保护用户或公众合法权益所必需；</li>
          <li>与关联公司共享（需遵守相同的隐私保护标准）。</li>
        </ol>

        <h4>六、您的权利</h4>
        <p>根据《中华人民共和国个人信息保护法》，您享有以下权利：</p>
        <div class="info-category">
          <h5>（一）查询权</h5>
          <p>您有权查询您的个人信息收集、使用情况。</p>
        </div>
        <div class="info-category">
          <h5>（二）更正权</h5>
          <p>您有权更正或补充您的个人信息。</p>
        </div>
        <div class="info-category">
          <h5>（三）删除权</h5>
          <p>在符合法定条件的情况下，您有权要求我们删除您的个人信息。</p>
        </div>
        <div class="info-category">
          <h5>（四）撤回授权权</h5>
          <p>您有权撤回已作出的授权同意，但撤回前基于授权已进行的信息处理活动不受影响。</p>
        </div>
        <div class="info-category">
          <h5>（五）信息可携权</h5>
          <p>您有权获取您的个人信息副本，并要求我们将您的个人信息转移至其他数据处理者。</p>
        </div>

        <h4>七、政策更新</h4>
        <p>我们可能会适时更新本隐私政策。更新后的政策将在平台上公布，并通过站内信、邮件等方式通知您。重大变更将给予您合理的过渡期。</p>

        <h4>八、联系我们</h4>
        <p>如果您对本隐私政策有任何疑问或建议，或者需要行使您的权利，请通过以下方式联系我们：</p>
        <ul>
          <li>客服热线：400-xxx-xxxx</li>
          <li>电子邮箱：privacy@example.com</li>
          <li>办公地址：北京市xxx区xxx路xxx号</li>
        </ul>
      </div>

      <div v-else-if="type === 'cancel'">
        <h3>公寓退订政策</h3>
        <p class="agreement-date">适用日期：2024年1月1日</p>

        <h4>一、总则</h4>
        <p>本政策适用于通过本平台预订的所有海外公寓房源。请在预订前仔细阅读以下退订政策，确认您理解并同意相关条款。一旦提交预订申请并支付押金，即视为您已接受本政策的所有条款。</p>

        <h4>二、免责退订（全额退款）</h4>
        <p>符合以下情况的，可申请全额退款（押金+已缴租金），平台服务费予以退还：</p>
        <div class="info-category">
          <h5>（一）签证被拒</h5>
          <p>需在入住日前30天以上提供官方拒签证明，经审核确认后予以全额退款。</p>
        </div>
        <div class="info-category">
          <h5>（二）学校Offer被撤回</h5>
          <p>需提供学校官方撤回通知或相关证明文件，经审核确认后予以全额退款。</p>
        </div>
        <div class="info-category">
          <h5>（三）公寓方原因导致无法入住</h5>
          <p>如房间已被超额预订、设施重大故障等原因导致无法入住，公寓方应提供替代房源或予以全额退款。</p>
        </div>
        <div class="info-category">
          <h5>（四）不可抗力</h5>
          <p>因自然灾害、战争、疫情等不可抗力因素导致无法入住，经双方协商后予以全额退款。</p>
        </div>

        <h4>三、常规退订</h4>
        <p>除免责情况外，退订将按以下标准扣除费用：</p>
        <table class="cancel-table">
          <thead>
            <tr>
              <th>退订时间</th>
              <th>违约金标准</th>
              <th>退款说明</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>入住日前60天及以上</td>
              <td>扣除1个月租金</td>
              <td>押金及剩余租金退还</td>
            </tr>
            <tr>
              <td>入住日前30-59天</td>
              <td>扣除2个月租金</td>
              <td>押金及剩余租金退还</td>
            </tr>
            <tr>
              <td>入住日前15-29天</td>
              <td>扣除3个月租金</td>
              <td>押金及剩余租金退还</td>
            </tr>
            <tr>
              <td>入住日前14天内</td>
              <td>扣除全部租金</td>
              <td>仅退还押金（如适用）</td>
            </tr>
            <tr>
              <td>入住后</td>
              <td>不予退款</td>
              <td>按租赁合同约定处理</td>
            </tr>
          </tbody>
        </table>

        <h4>四、服务费政策</h4>
        <p>平台服务费在以下情况下不予退还：</p>
        <ol class="agreement-list">
          <li>已成功提交预订申请并被公寓方确认后，无论任何原因退订；</li>
          <li>因用户提供虚假信息导致申请被拒；</li>
          <li>用户违反预订条款导致公寓方取消预订。</li>
        </ol>
        <p>以下情况服务费予以退还：</p>
        <ol class="agreement-list" start="4">
          <li>因公寓方原因导致无法入住；</li>
          <li>因签证被拒或学校Offer被撤回（需提供官方证明）。</li>
        </ol>

        <h4>五、退款流程</h4>
        <ol class="agreement-list">
          <li>用户提交退订申请，说明退订原因并提供相关证明材料；</li>
          <li>平台审核申请材料，必要时与公寓方核实；</li>
          <li>审核通过后，平台计算应退金额；</li>
          <li>款项在15-30个工作日内原路退回；</li>
          <li>汇率波动产生的差额由用户承担。</li>
        </ol>

        <h4>六、特殊说明</h4>
        <ol class="agreement-list">
          <li>不同公寓可能存在差异，具体退订条款以公寓方最终确认的合同文本为准；</li>
          <li>长租预订（12个月及以上）的退订政策可能有所不同，具体以预订时的说明为准；</li>
          <li>如遇特殊情况，平台可根据实际情况与用户协商处理；</li>
          <li>本政策未尽事宜，参照相关法律法规及平台其他规定执行。</li>
        </ol>

        <h4>七、争议解决</h4>
        <p>因退订产生的争议，双方应首先通过友好协商解决；协商不成的，任何一方均有权向本平台所在地有管辖权的人民法院提起诉讼。</p>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button type="primary" @click="visible = false">我已阅读</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useBookingFlowStore } from '@/stores/bookingFlow'

const props = defineProps<{
  modelValue: boolean
  type: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()

const bookingFlow = useBookingFlowStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const dialogTitle = computed(() => {
  const titles: Record<string, string> = {
    booking: '订房授权书',
    data: '个人信息出境授权声明',
    privacy: '隐私政策',
    cancel: '公寓退订政策',
  }
  return titles[props.type] || '协议内容'
})

const currentDate = computed(() => {
  const now = new Date()
  return `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`
})
</script>

<style scoped>
.agreement-content {
  max-height: 60vh;
  overflow-y: auto;
  padding: 0 8px;
  line-height: 1.8;
  font-size: 14px;
  color: var(--text-secondary);
}

.agreement-content h3 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 16px;
  text-align: center;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--primary);
}

.agreement-content h4 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 24px 0 12px;
}

.agreement-content h5 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 12px 0 8px;
}

.agreement-content p {
  margin: 8px 0;
  text-indent: 2em;
}

.agreement-content ul,
.agreement-content ol {
  padding-left: 2em;
  margin: 8px 0;
}

.agreement-content li {
  padding: 4px 0;
}

.agreement-content strong {
  color: var(--text-primary);
}

.agreement-date {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  margin-bottom: 20px !important;
  text-indent: 0 !important;
}

.info-table {
  background: var(--bg-light);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 16px;
}

.table-row {
  display: flex;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-light);
}

.table-row:last-child {
  border-bottom: none;
}

.table-label {
  width: 120px;
  font-weight: 500;
  color: var(--text-secondary);
}

.table-value {
  flex: 1;
  color: var(--text-primary);
}

.info-category {
  margin-bottom: 12px;
}

.agreement-list {
  list-style-type: decimal;
}

.agreement-list li {
  margin-bottom: 6px;
}

.signature-section {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}

.signature-line {
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--text-primary);
}

.cancel-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 16px;
}

.cancel-table th,
.cancel-table td {
  border: 1px solid var(--border);
  padding: 10px;
  text-align: center;
  font-size: 13px;
}

.cancel-table th {
  background: var(--bg-light);
  font-weight: 600;
  color: var(--text-primary);
}

.cancel-table td {
  color: var(--text-secondary);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}
</style>

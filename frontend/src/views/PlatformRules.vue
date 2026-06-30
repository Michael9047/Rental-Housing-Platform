<template>
  <div class="static-page">
    <el-card shadow="never" class="content-card">
      <h1>📋 平台规则</h1>
      <p class="update-date">最后更新：2026年6月</p>

      <section>
        <h2>一、用户注册与账户管理</h2>
        <ul>
          <li>用户注册时需提供真实有效的个人信息，包括但不限于手机号码、电子邮箱等。</li>
          <li>用户应妥善保管账户及密码，因账户密码泄露导致的一切后果由用户自行承担。</li>
          <li>平台禁止一人注册多个账户进行恶意操作，一经发现，平台有权永久封禁相关账户。</li>
          <li>租客需完成实名认证后方可签署电子租赁合同。</li>
        </ul>
      </section>

      <section>
        <h2>二、房源发布规范</h2>
        <ul>
          <li>房东/公寓运营商发布的房源信息必须真实、准确，包括但不限于房屋地址、户型、面积、租金等。</li>
          <li>禁止发布虚假房源、重复房源或以低价引流等违规信息。</li>
          <li>房源图片须为待出租房屋的真实照片，不得使用虚假图片或过度美化。</li>
          <li>平台有权对发布的房源进行审核，不符合规范的房源将被下架处理。</li>
        </ul>
      </section>

      <section>
        <h2>三、预约看房规则</h2>
        <ul>
          <li>租客可通过平台在线预约看房，选择期望的看房日期和时间段。</li>
          <li>房东应在24小时内确认或拒绝预约请求，逾期未处理的预约将自动取消。</li>
          <li>租客如需取消预约，应提前通知房东；无故爽约将影响账户信用评级。</li>
          <li>同一房源同一时间段仅接受一位租客预约看房。</li>
        </ul>
      </section>

      <section>
        <h2>四、押金与支付规则</h2>
        <ul>
          <li>租客确认租房后需支付押金，押金金额由房东设定并在房源详情页公示。</li>
          <li>押金支付通过平台合作的第三方支付渠道完成，平台保障资金安全。</li>
          <li>租期届满且房屋无损坏的，押金将在退房后7个工作日内原路退还。</li>
          <li>服务费按押金的一定比例收取，具体费率在支付页明确展示。</li>
        </ul>
      </section>

      <section>
        <h2>五、合同签署与履行</h2>
        <ul>
          <li>押金支付成功后，平台将自动生成电子租赁合同，合同具有法律效力。</li>
          <li>租客和房东应如实填写合同信息，因虚假信息导致的纠纷由责任方承担。</li>
          <li>合同签署后，双方应严格履行合同约定的各项义务。</li>
          <li>如需提前解约，应按照合同约定的解约条款执行。</li>
        </ul>
      </section>

      <section>
        <h2>六、禁止行为</h2>
        <ul>
          <li>禁止利用平台从事任何违法违规活动，包括但不限于诈骗、传销、非法集资等。</li>
          <li>禁止发布含有色情、暴力、政治敏感或其他违法内容的文字或图片。</li>
          <li>禁止骚扰、辱骂、威胁其他用户或平台工作人员。</li>
          <li>禁止使用爬虫、机器人等自动化工具批量抓取平台数据。</li>
        </ul>
      </section>

      <section>
        <h2>七、违规处理</h2>
        <ul>
          <li>平台将根据违规行为的严重程度，采取警告、限制功能、冻结账户、永久封禁等措施。</li>
          <li>用户对处理结果有异议的，可通过客服渠道提出申诉。</li>
          <li>因违规行为给平台或其他用户造成损失的，违规用户应承担相应的赔偿责任。</li>
        </ul>
      </section>

      <p class="footer-note">本平台规则最终解释权归 AI 全球公寓租赁平台所有。如有疑问，请联系在线客服。</p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.static-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 16px 48px;
}

.content-card {
  border-radius: 12px;
  padding: 8px;
}

h1 {
  font-size: 28px;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.update-date {
  color: var(--text-muted);
  font-size: 13px;
  margin-bottom: 32px;
}

section {
  margin-bottom: 28px;
}

h2 {
  font-size: 18px;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-light);
}

ul {
  list-style: disc;
  padding-left: 24px;
  color: var(--text-secondary);
  line-height: 1.9;
  font-size: 14px;
}

ul li {
  margin-bottom: 4px;
}

.footer-note {
  margin-top: 32px;
  padding-top: 16px;
  border-top: 1px solid var(--border-light);
  color: var(--text-muted);
  font-size: 13px;
  text-align: center;
}
</style>

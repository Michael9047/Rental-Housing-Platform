<template>
  <div class="static-page">
    <el-card shadow="never" class="content-card">
      <h1>🔒 隐私政策</h1>
      <p class="update-date">最后更新：2026年6月</p>

      <section>
        <h2>一、信息收集</h2>
        <p>在您使用 AI 全球公寓租赁平台（以下简称"本平台"）的过程中，我们可能会收集以下类型的信息：</p>
        <ul>
          <li><strong>注册信息</strong>：用户名、手机号码、电子邮箱、登录密码等。</li>
          <li><strong>实名认证信息</strong>：真实姓名、身份证号码、身份证照片等（仅在签署合同前需要）。</li>
          <li><strong>租房行为数据</strong>：浏览记录、搜索偏好、预约历史、收藏房源等。</li>
          <li><strong>设备信息</strong>：设备型号、操作系统版本、IP 地址、浏览器类型等。</li>
          <li><strong>位置信息</strong>：用于地图找房和房源定位功能（需您授权）。</li>
        </ul>
      </section>

      <section>
        <h2>二、信息使用</h2>
        <p>我们收集的信息将用于以下目的：</p>
        <ul>
          <li>为您提供房源搜索、推荐、预约看房、支付押金、签署合同等服务。</li>
          <li>优化平台功能和用户体验，包括个性化房源推荐。</li>
          <li>保障平台安全，防范欺诈和滥用行为。</li>
          <li>履行法律法规规定的义务，如实名制要求。</li>
          <li>向您发送订单通知、支付确认、合同更新等服务相关消息。</li>
        </ul>
      </section>

      <section>
        <h2>三、信息共享</h2>
        <p>我们承诺不会将您的个人信息出售给第三方。在以下情况下，我们可能会共享您的信息：</p>
        <ul>
          <li><strong>与房东/公寓运营商共享</strong>：预约看房时，您的姓名和联系方式将提供给房东。</li>
          <li><strong>支付服务提供商</strong>：支付押金时，必要的支付信息将传递给微信支付/支付宝。</li>
          <li><strong>法律法规要求</strong>：根据法律规定或政府部门的要求提供相关信息。</li>
          <li><strong>经您同意</strong>：在获得您明确同意的情况下与其他方共享。</li>
        </ul>
      </section>

      <section>
        <h2>四、信息保护</h2>
        <p>我们采取以下措施保护您的个人信息安全：</p>
        <ul>
          <li>使用 SSL/TLS 加密技术保护数据在传输过程中的安全。</li>
          <li>密码采用 bcrypt 哈希加密存储，平台无法获知您的明文密码。</li>
          <li>敏感数据（如身份证号、手机号）在展示时进行脱敏处理。</li>
          <li>实施严格的访问控制策略，仅授权人员可接触用户数据。</li>
          <li>定期进行安全审计和漏洞扫描，及时修复安全缺陷。</li>
        </ul>
      </section>

      <section>
        <h2>五、Cookie 与缓存</h2>
        <ul>
          <li>本平台使用必要的 Cookie 来维持您的登录状态和会话信息。</li>
          <li>您可以在浏览器设置中禁用 Cookie，但可能导致部分功能无法正常使用。</li>
          <li>平台会将您的登录凭证（Access Token）存储在浏览器本地存储中，以便在会话期间保持登录。</li>
        </ul>
      </section>

      <section>
        <h2>六、您的权利</h2>
        <p>根据相关法律法规，您享有以下权利：</p>
        <ul>
          <li><strong>查询权</strong>：您可以在个人中心查看您的个人信息。</li>
          <li><strong>更正权</strong>：您可以通过编辑资料功能修改您的个人信息。</li>
          <li><strong>删除权</strong>：您可以申请注销账户，我们将删除您的个人信息（法律法规要求保留的除外）。</li>
          <li><strong>撤回同意</strong>：您可以随时撤回对非必要信息收集的授权。</li>
        </ul>
      </section>

      <section>
        <h2>七、未成年人保护</h2>
        <ul>
          <li>本平台主要面向成年人提供服务。未满18周岁的未成年人应在监护人陪同下使用本平台。</li>
          <li>我们不会主动收集未成年人的个人信息。如发现误收集，请及时联系我们删除。</li>
        </ul>
      </section>

      <section>
        <h2>八、政策更新</h2>
        <ul>
          <li>我们可能会不时更新本隐私政策。重大变更将通过平台公告或短信通知您。</li>
          <li>继续使用本平台即表示您同意更新后的隐私政策。</li>
        </ul>
      </section>

      <section>
        <h2>九、联系我们</h2>
        <p>如您对本隐私政策有任何疑问或建议，请通过以下方式联系我们：</p>
        <ul>
          <li>在线客服：点击页面底部「客服中心」进入在线对话</li>
          <li>电子邮箱：privacy@rental-housing.com</li>
        </ul>
      </section>
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

p {
  color: var(--text-secondary);
  line-height: 1.8;
  font-size: 14px;
  margin-bottom: 8px;
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
</style>

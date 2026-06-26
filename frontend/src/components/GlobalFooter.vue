<template>
  <footer class="global-footer">
    <div class="footer-content">
      <div class="footer-services">
        <span class="footer-item">🏠 AI国内租房检索</span>
        <span class="footer-divider">｜</span>
        <span class="footer-item">🌍 海外留学生公寓预订</span>
        <span class="footer-divider">｜</span>
        <span class="footer-item">💰 线上押金支付</span>
        <span class="footer-divider">｜</span>
        <span class="footer-item">📄 电子合同签署</span>
        <span class="footer-divider">｜</span>
        <span class="footer-item">🎓 签证租房咨询</span>
      </div>
      <div class="footer-bottom">
        <span class="footer-item">客服中心</span>
        <span class="footer-divider">｜</span>
        <span class="footer-item">平台规则</span>
        <span class="footer-divider">｜</span>
        <span class="footer-item">隐私政策</span>
        <span class="footer-divider">｜</span>
        <span class="footer-copy">© 2026 AI全球公寓租赁平台</span>
      </div>
    </div>
  </footer>
</template>

<script setup lang="ts">
</script>

<style scoped>
.global-footer {
  background: var(--bg-white);
  border-top: 1px solid var(--border);
  padding: 20px 24px;
  margin-top: auto;
}

.footer-content {
  max-width: 1200px;
  margin: 0 auto;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.footer-services {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  flex-wrap: wrap;
}

.footer-bottom {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  flex-wrap: wrap;
}

.footer-item {
  font-size: 13px;
  color: var(--text-muted);
}

.footer-divider {
  color: var(--border);
  font-size: 12px;
}

.footer-copy {
  font-size: 12px;
  color: var(--text-muted);
}
</style>

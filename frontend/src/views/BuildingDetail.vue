<template>
  <div class="bd-page" v-loading="loading">
    <template v-if="building && !loading">
      <!-- ═══ 1. 头部：左70%标题+地址+简介 / 右30%评分+预约 ═══ -->
      <section class="bd-header">
        <div class="hd-split">
          <div class="hd-left">
            <h1 class="hd-title">{{ building.name }}</h1>
            <p class="hd-addr">{{ building.address || '地址未设置' }}</p>
            <p class="hd-desc">{{ building.description || '暂无介绍' }}</p>
          </div>
          <div class="hd-right">
            <div class="score-card safety">
              <div class="sc-label">安全综合评分</div>
              <div class="sc-num">{{ building.safety_score ?? '--' }}</div>
              <div class="sc-sub">/10</div>
            </div>
            <div class="score-card ai">
              <div class="sc-label">AI综合评分</div>
              <div class="sc-num">{{ building.ai_score ?? '--' }}</div>
              <div class="sc-sub" v-if="building.ai_score">/10</div>
            </div>
            <el-button type="primary" size="large" class="hd-book-btn" @click="showContactDialog = true">📅 预约看房</el-button>
          </div>
        </div>
      </section>

      <!-- ═══ 2. 照片轮播（左右切换 + 圆点指示器） ═══ -->
      <section class="bd-gallery" v-if="galleryImages.length">
        <div class="gal-carousel">
          <button class="gal-arrow gal-prev" @click="prevSlide" :disabled="slideIdx === 0">&#10094;</button>
          <div class="gal-main" @click="openLightbox(slideIdx)">
            <img v-if="galleryImages[slideIdx]" :src="imgUrl(galleryImages[slideIdx].filename)" alt="" />
          </div>
          <button class="gal-arrow gal-next" @click="nextSlide" :disabled="slideIdx >= galleryImages.length - 1">&#10095;</button>
        </div>
        <div class="gal-dots">
          <span v-for="(_, i) in galleryImages" :key="i" :class="{ active: i === slideIdx }" @click="slideIdx = i" />
        </div>
      </section>
      <section v-else class="bd-gallery">
        <el-empty description="暂无图片" :image-size="60" />
      </section>

      <!-- ═══ 3. 地理位置 + 地图 ═══ -->
      <section class="bd-map">
        <h2 class="sec-title">📍 地理位置</h2>
        <p class="map-addr">{{ building.address || '地址未设置' }}</p>
        <div v-if="building.latitude" ref="mapContainer" class="map-box"></div>
        <p v-else class="map-empty">暂无地图坐标</p>
      </section>

      <!-- ═══ 4. 配套设施（4栏卡片） ═══ -->
      <section class="bd-amenity" v-if="amenityCards.length">
        <h2 class="sec-title">配套设施与服务</h2>
        <div class="am-grid">
          <div v-for="card in amenityCards" :key="card.name" class="am-card">
            <div class="am-head">
              <span class="am-icon">{{ card.icon }}</span>
              <span class="am-name">{{ card.name }}</span>
              <span class="am-count">({{ card.tags.length }})</span>
            </div>
            <div class="am-tags">
              <span v-for="t in card.tags" :key="t" class="am-tag">{{ t }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- ═══ 5. 特殊标记（独立区块） ═══ -->
      <section class="bd-special" v-if="specialMarkers.length">
        <h2 class="sec-title">特别说明</h2>
        <div class="sp-bar">
          <span v-for="m in specialMarkers" :key="m.label" class="sp-tag">{{ m.icon }} {{ m.label }}</span>
        </div>
      </section>

      <!-- ═══ 6. AI 占位 ═══ -->
      <section class="bd-ai">
        <h2 class="sec-title">🔍 地图周边检测</h2>
        <div class="ai-box">🤖<p>AI 智能周边分析即将上线</p></div>
      </section>

      <!-- ═══ 7. 户型卡片 ═══ -->
      <section class="bd-units" v-if="building.unit_types?.length">
        <h2 class="sec-title">🏠 可选户型 ({{ building.unit_types.length }})</h2>
        <div class="ut-card" v-for="ut in building.unit_types" :key="ut.id">
          <!-- 横线上方：图 + 信息 + 价格 -->
          <div class="ut-above">
            <div class="ut-img" @click="openUnitGallery(ut)">
              <img v-if="ut.images?.[0]" :src="imgUrl(ut.images[0].filename)" alt="" />
              <span v-else class="ut-img-empty">暂无图片</span>
              <span v-if="ut.images?.length > 1" class="ut-img-num">{{ ut.images.length }}张</span>
            </div>
            <div class="ut-info">
              <h3 class="ut-name">{{ ut.name }}</h3>
              <div class="ut-attrs">
                <span>🛏 {{ ut.bedrooms }}室</span>
                <span>🚿 {{ ut.bathrooms }}卫</span>
                <span v-if="ut.hall_count">🛋 {{ ut.hall_count }}厅</span>
                <span v-if="ut.area_sqm">📐 {{ ut.area_sqm }}㎡</span>
                <span>📅 最短{{ ut.min_stay_months || 3 }}个月</span>
              </div>
              <div v-if="ut.rental_requirements || ut.special_offer || ut.description" class="ut-details">
                <p v-if="ut.rental_requirements"><b>📋 租房要求：</b>{{ ut.rental_requirements }}</p>
                <p v-if="ut.special_offer"><b>🎁 专属优惠：</b>{{ ut.special_offer }}</p>
                <p v-if="ut.description"><b>📝 户型描述：</b>{{ ut.description }}</p>
              </div>
            </div>
            <div class="ut-price-col">
              <div class="ut-rent">¥{{ ut.base_rent }}<em>/月</em></div>
              <div class="ut-deposit" v-if="ut.deposit_amount">押金 ¥{{ ut.deposit_amount }}</div>
              <el-button class="ut-book" @click="handleBook(ut.id)">立即预定</el-button>
            </div>
          </div>
          <!-- 横线下方：标签 4个一排 -->
          <div class="ut-divider" v-if="ut.amenities?.length"></div>
          <div class="ut-below" v-if="ut.amenities?.length">
            <span v-for="a in ut.amenities" :key="a" class="ut-tag">✅ {{ a }}</span>
          </div>
        </div>
      </section>
    </template>

    <!-- 预约看房弹窗 -->
    <el-dialog v-model="showContactDialog" title="预约看房申请" width="480px" :close-on-click-modal="false">
      <el-form :model="visitForm" :rules="visitRules" ref="visitFormRef" label-width="80px">
        <el-form-item label="手机号码" prop="guestPhone">
          <el-input v-model="visitForm.guestPhone" placeholder="请输入您的手机号码" maxlength="32" />
        </el-form-item>
        <el-form-item label="看房留言">
          <el-input v-model="visitForm.guestMessage" type="textarea" :rows="3" placeholder="选填：期望看房时间、特殊需求等" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <div v-if="building?.staff?.length" style="margin-top:16px;padding-top:16px;border-top:1px solid #eee">
        <div style="font-size:14px;font-weight:600;color:#303133;margin-bottom:8px">📋 公寓联系人</div>
        <div v-for="s in building.staff" :key="s.name" class="ct-item">
          <div class="ct-name">{{ s.name }} <el-tag size="small">{{ s.role === 'manager' ? '负责人' : s.role }}</el-tag></div>
          <div v-if="s.phone" class="ct-info">📞 {{ s.phone }}</div>
          <div v-if="s.wechat" class="ct-info">💬 微信：{{ s.wechat }}</div>
          <div v-if="s.email" class="ct-info">📧 {{ s.email }}</div>
          <el-image v-if="s.wechat_qr" :src="imgUrl(s.wechat_qr)" :preview-src-list="[imgUrl(s.wechat_qr)]" style="width:80px;height:80px;margin-top:4px;border-radius:6px;cursor:pointer" fit="cover" />
        </div>
      </div>
      <template #footer>
        <el-button @click="showContactDialog = false">取消</el-button>
        <el-button type="primary" :loading="visitSubmitting" @click="submitVisit">发送</el-button>
      </template>
    </el-dialog>

    <el-empty v-if="error && !loading" :description="error" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/services/api'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

const route = useRoute(); const router = useRouter()
const loading = ref(true); const error = ref('')
const building = ref<any>(null); const showContactDialog = ref(false)
const mapContainer = ref<HTMLElement | null>(null); let mapInstance: L.Map | null = null

// 预约看房表单
const visitFormRef = ref()
const visitSubmitting = ref(false)
const visitForm = ref({ guestPhone: '', guestMessage: '' })
const visitRules = { guestPhone: [{ required: true, message: '请输入手机号码', trigger: 'blur' }, { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }] }

async function submitVisit() {
  if (!visitFormRef.value) return
  const valid = await visitFormRef.value.validate().catch(() => false)
  if (!valid) return
  visitSubmitting.value = true
  try {
    await api.post('/apartment/submitVisitApply', {
      apartmentId: building.value.id,
      guestPhone: visitForm.value.guestPhone.trim(),
      guestMessage: visitForm.value.guestMessage.trim(),
    })
    ElMessage.success('预约信息已发送给公寓管理员')
    showContactDialog.value = false
    visitForm.value = { guestPhone: '', guestMessage: '' }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '发送失败，请重试')
  } finally { visitSubmitting.value = false }
}

const imgUrl = (fn: string) => '/api/v1/uploads/' + fn

watch(building, async (val) => {
  if (val?.latitude) { await nextTick(); setTimeout(() => { initMap(); mapInstance?.invalidateSize() }, 400) }
})

const CATS: Record<string, { name: string; icon: string; items: string[] }> = {
  '安保': { name:'安保设施', icon:'🛡️', items:['24小时安保','监控系统(CCTV)','智能门禁','电子门锁','前台/礼宾','消防系统','夜间巡逻'] },
  '服务': { name:'公寓服务', icon:'🛎️', items:['代收包裹','维修服务','公共区域保洁','定期社交活动','接机服务','班车接驳','入住礼包','管家服务'] },
  '公用设施': { name:'公用设施', icon:'🏠', items:['电梯','洗衣房','自行车库','停车场','公共厨房','快递柜/信箱','自习室','影音室','公共休闲区','屋顶露台','庭院/花园','会议室'] },
  '运动娱乐': { name:'运动&娱乐', icon:'⚽', items:['健身房','游泳池','篮球场','瑜伽室','游戏室','BBQ区','乒乓球/台球'] },
}

const galleryImages  = computed(() => building.value?.images || [])
const slideIdx = ref(0)
function prevSlide() { if (slideIdx.value > 0) slideIdx.value-- }
function nextSlide() { if (slideIdx.value < galleryImages.value.length - 1) slideIdx.value++ }
watch(galleryImages, () => { if (slideIdx.value >= galleryImages.value.length) slideIdx.value = 0 })

const amenityCards = computed(() => {
  const tags: string[] = building.value?.amenities || []
  if (!tags.length) return []
  return Object.values(CATS).map(c => ({ ...c, tags: c.items.filter(t => tags.includes(t)) })).filter(c => c.tags.length)
})

const specialMarkers = computed(() => {
  const m: { icon: string; label: string }[] = []
  if (building.value?.female_only) m.push({ icon:'🚺', label:'仅限女生入住' })
  if (building.value?.couples_allowed) m.push({ icon:'💑', label:'支持情侣入住' })
  return m
})

function openUnitGallery(ut: any) {
  const imgs = ut.images || []; if (!imgs.length) return; let i = 0
  const o = document.createElement('div'); o.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.92);z-index:9999;display:flex;align-items:center;justify-content:center'
  const el = document.createElement('img'); el.src = imgUrl(imgs[0].filename); el.style.cssText = 'max-width:90vw;max-height:85vh;object-fit:contain;border-radius:8px'
  o.appendChild(el)
  if (imgs.length > 1) {
    ['left','right'].forEach((dir, di) => {
      const b = document.createElement('button'); b.innerHTML = di ? '&#10095;' : '&#10094;'
      b.style.cssText = `position:absolute;${dir}:20px;top:50%;transform:translateY(-50%);background:rgba(255,255,255,.2);border:none;color:#fff;font-size:36px;padding:16px 20px;cursor:pointer;border-radius:8px`
      b.onclick = (e) => { e.stopPropagation(); const n = di ? i+1 : i-1; if (n>=0 && n<imgs.length) { i=n; el.src=imgUrl(imgs[i].filename) } }
      o.appendChild(b)
    })
  }
  const c = document.createElement('button'); c.innerHTML='&times;'; c.style.cssText='position:absolute;top:16px;right:24px;background:none;border:none;color:#fff;font-size:32px;cursor:pointer'
  c.onclick=(e)=>{e.stopPropagation();o.remove()}; o.appendChild(c); o.onclick=()=>o.remove(); document.body.appendChild(o)
}

function handleBook(id: number) {
  // 两层结构：直接用 unit_type_id 预订
  const ut = building.value?.unit_types?.find((u: any) => u.id === id)
  if (!ut) return ElMessage.warning('户型不存在')
  if (!ut.has_vacancy && ut.available_count <= 0) return ElMessage.warning('该户型暂无空房')
  router.push({ name: 'booking-move-in-date', params: { propertyId: String(id) } })
}

let lIdx = 0
function openLightbox(index: number) {
  const imgs = galleryImages.value; if (!imgs.length) return; lIdx = index
  const o = document.createElement('div'); o.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.92);z-index:9999;display:flex;align-items:center;justify-content:center'
  const el = document.createElement('img'); el.src = imgUrl(imgs[lIdx].filename); el.style.cssText = 'max-width:90vw;max-height:85vh;object-fit:contain;border-radius:8px'
  o.appendChild(el)
  const mkBtn = (dir: string) => { const b=document.createElement('button'); b.innerHTML=dir==='prev'?'&#10094;':'&#10095;'; b.style.cssText='position:absolute;top:50%;transform:translateY(-50%);background:rgba(255,255,255,.2);border:none;color:#fff;font-size:36px;padding:16px 20px;cursor:pointer;border-radius:8px;z-index:1'; b.style[dir==='prev'?'left':'right']='20px'; return b }
  const prev = mkBtn('prev'); prev.onclick=(e)=>{e.stopPropagation();if(lIdx>0){lIdx--;el.src=imgUrl(imgs[lIdx].filename)}}; o.appendChild(prev)
  const next = mkBtn('next'); next.onclick=(e)=>{e.stopPropagation();if(lIdx<imgs.length-1){lIdx++;el.src=imgUrl(imgs[lIdx].filename)}}; o.appendChild(next)
  const cnt = document.createElement('div'); cnt.textContent=`${lIdx+1}/${imgs.length}`; cnt.style.cssText='position:absolute;top:16px;left:50%;transform:translateX(-50%);color:#fff;font-size:16px'; o.appendChild(cnt)
  const cl = document.createElement('button'); cl.innerHTML='&times;'; cl.style.cssText='position:absolute;top:16px;right:24px;background:none;border:none;color:#fff;font-size:32px;cursor:pointer'
  cl.onclick=(e)=>{e.stopPropagation();o.remove()}; o.appendChild(cl); o.onclick=()=>o.remove(); document.body.appendChild(o)
}

function initMap() {
  if (!building.value?.latitude || !mapContainer.value) return
  mapInstance?.remove(); mapInstance = null
  mapInstance = L.map(mapContainer.value, { center:[building.value.latitude,building.value.longitude], zoom:15, scrollWheelZoom:true, dragging:true })
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution:'© OpenStreetMap' }).addTo(mapInstance)
  L.marker([building.value.latitude,building.value.longitude]).addTo(mapInstance)
}

onMounted(async () => {
  try { const r = await api.get(`/buildings/${route.params.id}/tenant-detail`); building.value = r.data }
  catch (e: any) { error.value = e?.response?.status === 404 ? '公寓不存在' : '加载失败' }
  finally { loading.value = false }
})
</script>

<style scoped>
.bd-page { max-width: 100%; margin: 0; padding: 0 48px 80px; background: #f5f6f8; min-height: 100vh }
.sec-title { font-size: 18px; font-weight: 700; margin: 0 0 16px; color: #1a1a2e; padding-left: 12px; position: relative }
.sec-title::before { content:''; position:absolute; left:0; top:2px; bottom:2px; width:3px; border-radius:2px; background:#FF6B35 }

/* ═══ 1. 头部 7:3 ═══ */
.bd-header { padding: 28px 0 24px }
.hd-split { display: flex; gap: 36px; align-items: flex-start }
.hd-left { flex: 7; min-width: 0 }
.hd-right { flex: 3; display: flex; flex-direction: column; gap: 14px; min-width: 260px }
.hd-title { font-size: 32px; font-weight: 800; margin: 0 0 6px; color: #1a1a2e; letter-spacing: .5px; line-height: 1.2 }
.hd-addr { font-size: 15px; color: #888; margin: 0 0 14px }
.hd-desc { color: #555; line-height: 1.7; font-size: 16px; margin: 0; white-space: pre-wrap; max-height: 180px; overflow: auto }
.score-card { display:flex; flex-direction:column; align-items:center; justify-content:center; width:100%; height:86px; border-radius:14px; background:#fff; box-shadow:0 2px 12px rgba(0,0,0,.06); transition:transform .2s }
.score-card:hover { transform:translateY(-2px) }
.score-card.safety { border:2px solid #e8f5e9; background:linear-gradient(135deg,#f1f8e9,#fff) }
.score-card.ai { border:2px solid #e3f2fd; background:linear-gradient(135deg,#e8f0fe,#fff) }
.sc-label { font-size:13px; color:#999; margin-bottom:4px }
.sc-num { font-size:30px; font-weight:800; color:#1a1a2e; line-height:1 }
.sc-sub { font-size:11px; color:#999; margin-top:2px }
.hd-book-btn { font-size: 16px; padding: 14px 0; border-radius: 10px; font-weight: 600; letter-spacing: 2px; width: 100% }

/* ═══ 2. 图片轮播 ═══ */
.bd-gallery { margin-bottom: 24px }
.gal-carousel { display: flex; align-items: center; gap: 0; position: relative }
.gal-arrow { flex-shrink: 0; width: 44px; height: 64px; border: none; background: rgba(255,255,255,.85); color: #555; font-size: 22px; cursor: pointer; border-radius: 8px; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 6px rgba(0,0,0,.06); transition: all .2s; z-index: 1 }
.gal-arrow:hover:not(:disabled) { background: #fff; box-shadow: 0 3px 12px rgba(0,0,0,.1) }
.gal-arrow:disabled { opacity: .2; cursor: default }
.gal-main { flex: 1; aspect-ratio: 2.6/1; border-radius: 10px; overflow: hidden; cursor: pointer; margin: 0 10px; box-shadow: 0 2px 12px rgba(0,0,0,.06) }
.gal-main img { width: 100%; height: 100%; object-fit: cover; transition: transform .4s }
.gal-main:hover img { transform: scale(1.02) }
.gal-dots { display: flex; justify-content: center; gap: 8px; margin-top: 10px }
.gal-dots span { width: 8px; height: 8px; border-radius: 50%; background: #d4d8e0; cursor: pointer; transition: all .3s }
.gal-dots span.active { background: #FF6B35; width: 22px; border-radius: 4px }

/* ═══ 3. 地图 ═══ */
.bd-map { background: #fff; border-radius: 14px; padding: 24px 28px; margin-bottom: 24px; box-shadow: 0 2px 10px rgba(0,0,0,.03) }
.map-addr { font-size: 14px; color: #777; margin-bottom: 10px }
.map-box { width: 100%; height: 340px; min-height: 340px; border-radius: 10px; overflow: hidden; border: 1px solid #eee; z-index: 1; position: relative }
:deep(.map-box .leaflet-tile) { visibility: visible !important }
.map-empty { color: #999; text-align: center; padding: 50px }

/* ═══ 4. 配套设施4栏 ═══ */
.bd-amenity { background: #fff; border-radius: 14px; padding: 24px 28px; margin-bottom: 24px; box-shadow: 0 2px 10px rgba(0,0,0,.03) }
.am-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px }
.am-card { border: 1px solid #eee; border-radius: 10px; padding: 16px; background: #fafbfc }
.am-head { display: flex; align-items: center; gap: 6px; margin-bottom: 10px }
.am-icon { font-size: 16px }
.am-name { font-size: 14px; font-weight: 700; color: #444 }
.am-count { font-size: 12px; color: #999; margin-left: auto }
.am-tags { display: flex; flex-wrap: wrap; gap: 5px }
.am-tag { font-size: 11px; padding: 3px 8px; background: #fff; border: 1px solid #e8e8e8; border-radius: 3px; color: #666 }

/* ═══ 6. AI ═══ */
.bd-ai { background: #fff; border-radius: 14px; padding: 24px 28px; margin-bottom: 24px; box-shadow: 0 2px 10px rgba(0,0,0,.03) }
.ai-box { text-align: center; padding: 40px; background: linear-gradient(135deg,#f8f9ff,#f0f4ff); border: 2px dashed #d4daf0; border-radius: 10px; color: #999; font-size: 15px }

/* ═══ 5. 特殊标记 ═══ */
.bd-special { background: #fff; border-radius: 14px; padding: 24px 28px; margin-bottom: 24px; box-shadow: 0 2px 10px rgba(0,0,0,.03) }
.sp-bar { display: flex; gap: 16px; flex-wrap: wrap }
.sp-tag { font-size: 17px; font-weight: 700; padding: 14px 28px; background: linear-gradient(135deg,#fff3e0,#ffe0b2); border: 2px solid #ff9800; border-radius: 10px; color: #e65100 }

/* ═══ 7. 户型卡片 ═══ */
.bd-units { margin-bottom: 24px }
.ut-card { padding: 20px; margin-bottom: 14px; background: #fff; border: 1px solid #f0f0f0; border-radius: 14px; transition: all .25s; box-shadow: 0 2px 8px rgba(0,0,0,.02) }
.ut-card:hover { box-shadow: 0 4px 20px rgba(0,0,0,.06); transform: translateY(-1px) }
.ut-above { display: flex; gap: 18px; align-items: flex-start }
.ut-img { width: 220px; height: 165px; flex-shrink: 0; border-radius: 10px; overflow: hidden; position: relative; cursor: pointer; background: #f5f7fa }
.ut-img img { width: 100%; height: 100%; object-fit: cover; transition: transform .4s }
.ut-img:hover img { transform: scale(1.05) }
.ut-img-empty { display: flex; align-items: center; justify-content: center; height: 100%; color: #c0c4cc; font-size: 13px }
.ut-img-num { position: absolute; bottom: 6px; right: 6px; background: rgba(0,0,0,.5); color: #fff; font-size: 11px; padding: 2px 8px; border-radius: 4px }
.ut-info { flex: 1; min-width: 0 }
.ut-name { font-size: 18px; font-weight: 700; color: #1a1a2e; margin: 0 0 6px }
.ut-attrs { display: flex; gap: 10px; flex-wrap: wrap; color: #888; font-size: 13px; margin-bottom: 8px }
.ut-details p { font-size: 14px; color: #666; line-height: 1.7; margin: 0 0 3px }
.ut-details b { color: #444 }
.ut-price-col { flex-shrink: 0; text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 4px }
.ut-rent { font-size: 24px; font-weight: 800; color: #e94560; line-height: 1 }
.ut-rent em { font-size: 12px; font-weight: 400; color: #999; font-style: normal }
.ut-deposit { font-size: 13px; color: #999 }
.ut-book { margin-top: 8px; padding: 10px 28px; font-size: 14px; font-weight: 600; letter-spacing: 1px; border-radius: 8px; border: none; background: linear-gradient(135deg,#e94560,#ff6b6b); color: #fff }
.ut-book:hover { background: linear-gradient(135deg,#d63850,#f05555); box-shadow: 0 4px 14px rgba(233,69,96,.25) }
.ut-divider { height: 1px; background: #eee; margin: 12px 0 }
.ut-below { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px }
.ut-tag { font-size: 14px; padding: 7px 12px; background: #f0f7f0; color: #4a7c4f; border-radius: 4px; text-align: center }

/* ═══ 弹窗 ═══ */
.ct-list { display: flex; flex-direction: column; gap: 12px }
.ct-item { padding: 14px; background: linear-gradient(135deg,#f8f9fb,#f0f4ff); border-radius: 10px; border: 1px solid #eef; font-size: 14px; color: #555 }
.ct-name { font-size: 16px; font-weight: 700; color: #1a1a2e; margin-bottom: 6px; display: flex; align-items: center; gap: 8px }
</style>

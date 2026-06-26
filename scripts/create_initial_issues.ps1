# 批量创建初始任务 Issue，自动带标签和模块

$repo = "Michael9047/Rental-Housing-Platform"
$tasks = @(
    @{title="[contract] 前端租赁合同签署页面"; body="## 任务描述`n`n前端目前缺少合同相关视图，需要开发合同签署页面。`n`n## 验收标准`n- [ ] 租客可在线查看合同内容`n- [ ] 支持手写签名 / 勾选同意`n- [ ] 签署后状态实时更新`n- [ ] 对接后端 /api/v1/contracts 接口"; labels="task,frontend,contract,high"},
    @{title="[contract] 房东合同模板管理页面"; body="## 任务描述`n`n房东需要能创建和管理租赁合同模板。`n`n## 验收标准`n- [ ] 房东可创建合同模板（填空式）`n- [ ] 模板列表 + 编辑/删除`n- [ ] 模板字段：租金、押金、租期、违约金等"; labels="task,frontend,contract,medium"},
    @{title="[payment] 前端支付流程页面"; body="## 任务描述`n`n前端缺少支付相关页面，需要对接微信支付流程。`n`n## 验收标准`n- [ ] 支付发起页面（押金/租金）`n- [ ] 支付状态轮询 + 结果展示`n- [ ] 对接后端 /api/v1/payments 接口`n- [ ] 支付失败重试机制"; labels="task,frontend,payment,high"},
    @{title="[payment] 后端支付回调幂等性加固"; body="## 任务描述`n`n微信支付回调可能重复发送，需要确保支付回调处理的幂等性。`n`n## 验收标准`n- [ ] 回调接口检查 transaction_id 去重`n- [ ] 数据库层面唯一约束防止重复入账`n- [ ] 补充 test_payments.py 回调幂等测试"; labels="task,backend,payment,high"},
    @{title="[map] 前端房源地图搜索页面"; body="## 任务描述`n`n基于高德地图组件开发房源地图搜索功能。`n`n## 验收标准`n- [ ] 地图上展示房源标记点`n- [ ] 点击标记弹出房源卡片`n- [ ] 支持拖拽地图重新搜索`n- [ ] 周边 POI 叠加展示"; labels="task,frontend,map,poi,medium"},
    @{title="[poi] 后端 POI 数据定时刷新"; body="## 任务描述`n`n房源周边的 POI 数据需要定期刷新，保证数据时效性。`n`n## 验收标准`n- [ ] Celery 定时任务每日刷新 POI`n- [ ] 只刷新 30 天内未更新的房源`n- [ ] 异常房源跳过并记录日志`n- [ ] 补充 test_poi_generation.py 定时任务测试"; labels="task,backend,poi,medium"},
    @{title="[notification] 消息通知中心 UI 完善"; body="## 任务描述`n`nNotifications.vue 已存在，需要完善交互体验。`n`n## 验收标准`n- [ ] 未读消息红点角标`n- [ ] 消息分类 Tab（系统/预约/支付/聊天）`n- [ ] 一键全部已读`n- [ ] WebSocket 实时推送新消息"; labels="task,frontend,notification,medium"},
    @{title="[search] 前端语义搜索优化"; body="## 任务描述`n`n当前搜索页面需要增强语义搜索体验。`n`n## 验收标准`n- [ ] 搜索框支持自然语言输入『近地铁两室一厅』`n- [ ] 搜索结果高亮匹配关键词`n- [ ] 无结果时展示推荐房源`n- [ ] 搜索历史记录"; labels="task,frontend,search,low"},
    @{title="[chat] 聊天消息已读/未读状态"; body="## 任务描述`n`n当前聊天功能缺少消息已读状态追踪。`n`n## 验收标准`n- [ ] 后端 ChatMessage 模型添加 read_at 字段`n- [ ] WebSocket 发送已读回执`n- [ ] 前端展示『已读』/『未读』状态`n- [ ] 补充 test_chat.py 已读状态测试"; labels="task,backend,frontend,chat,medium"},
    @{title="[auth] 手机验证码登录"; body="## 任务描述`n`n当前只有密码登录，需要增加短信验证码登录方式。`n`n## 验收标准`n- [ ] 后端发送验证码接口（对接 SMS 服务）`n- [ ] 验证码 60 秒防刷 + Redis 存储`n- [ ] 前端验证码登录页面`n- [ ] 补充 test_auth.py 验证码登录测试"; labels="task,backend,frontend,auth,medium"},
    @{title="[images] 房源图片懒加载 + 缩略图优化"; body="## 任务描述`n`n房源列表页图片加载慢，需要懒加载和缩略图优化。`n`n## 验收标准`n- [ ] 前端图片懒加载（Intersection Observer）`n- [ ] 后端生成 200x150 缩略图`n- [ ] 列表用缩略图，详情用原图`n- [ ] 图片加载骨架屏占位"; labels="task,frontend,backend,images,low"},
    @{title="[wechat] 小程序首页房源列表"; body="## 任务描述`n`n微信小程序目录已创建，需要开发首页房源列表。`n`n## 验收标准`n- [ ] 小程序首页展示房源列表`n- [ ] 下拉刷新 + 上拉加载更多`n- [ ] 基础筛选（区域、价格、户型）`n- [ ] 点击进入房源详情"; labels="task,wechat-miniprogram,property,high"},
    @{title="[admin] 后台支付订单管理"; body="## 任务描述`n`n后台管理缺少支付订单管理页面。`n`n## 验收标准`n- [ ] 支付订单列表 + 搜索/筛选`n- [ ] 订单详情（支付状态、金额、时间）`n- [ ] 异常订单手动处理（退款标记）`n- [ ] 对接后端 /api/v1/admin 支付接口"; labels="task,frontend,admin,payment,medium"},
    @{title="[backend] 补充后端测试覆盖率"; body="## 任务描述`n`n当前缺少 contracts、payments 模块的后端测试。`n`n## 验收标准`n- [ ] 新建 test_contracts.py（CRUD + 签署流程）`n- [ ] 新建 test_payments.py（创建订单 + 回调）`n- [ ] 整体测试覆盖率 > 80%`n- [ ] CI 中 pytest 全部通过"; labels="task,backend,test,high"},
    @{title="[docs] 后端 API 文档补全"; body="## 任务描述`n`nFastAPI 自动生成的 /docs 缺少中文描述和示例。`n`n## 验收标准`n- [ ] 所有路由添加中文 summary/description`n- [ ] 请求体添加 example 示例`n- [ ] 响应模型添加字段说明`n- [ ] README 中链接 Swagger / ReDoc"; labels="documentation,backend,low"}
)

foreach ($task in $tasks) {
    Write-Host "创建: $($task.title) ..." -NoNewline
    $labelArgs = ($task.labels -split "," | ForEach-Object { "--label"; $_.Trim() })
    gh issue create `
        --repo $repo `
        --title $task.title `
        --body $task.body `
        $labelArgs 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✓" -ForegroundColor Green
    } else {
        Write-Host " ✗" -ForegroundColor Red
    }
}

Write-Host "`n全部完成！打开看板查看: https://github.com/Michael9047/Rental-Housing-Platform/projects" -ForegroundColor Green

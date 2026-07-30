# 测试账号

> 本文件仅为开发者本地测试参考，不包含真实密码。  
> 数据库重建后需重新创建这些账号。

## 登录地址

http://localhost:5173/login

## 账号列表

| 用户名 | 密码 | 角色 | 用途 |
|--------|------|------|------|
| `111` | `11111111` | tenant (租客) | 报修申请 + 确认完工 |
| `landlord_test` | `test123456` | landlord (房东) | 房源管理 + 派单 |
| `apt_worker` | `apt123456` | maintenance_worker (公寓维修工) | 接单→维修→完成 |
| `no_worker_ll` | `nw123456` | landlord (房东·无工人) | 测试智能跳过→后台派单 |
| `plat_worker` | `plat123456` | maintenance_worker (网站维修工) | 被Admin分配派单 |
| `admin_test` | `admin123456` | admin (管理员) | 后台派单 + 看板 |
| `bd_test` | `test123456` | bd_manager (BD经理) | 数据台 + 房源管理 |

## 演示流程

### 场景A：房东有工人
1. `111` 登录 → 个人中心 → 报修 → 选 Property#6 → 提交
2. `landlord_test` 登录 → 报修管理 → 派单给 `apt_worker`
3. `apt_worker` 登录 → 工单中心 → 开始工作 → 完成
4. `111` 登录 → 查看详情 → 确认修好

### 场景B：房东无工人（智能跳过）
1. `111` 登录 → 报修 → 选 Property#5 → 提交（自动标记"待后台派单"）
2. `admin_test` 登录 → 报修管理 → 点「待派单」→ 派单给 `plat_worker`
3. `plat_worker` 登录 → 工单中心 → 开始工作 → 完成
4. `111` 登录 → 确认修好

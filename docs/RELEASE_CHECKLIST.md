# 上线交付清单

## 上线前

- 从 `.env.example` 创建服务器私有的 `.env.prod`，不得把真实密钥提交或放进交付 ZIP。
- 设置强随机 `POSTGRES_PASSWORD`、`REDIS_PASSWORD`、`AUTH_SECRET_KEY`，并配置实际域名的 `FRONTEND_URL` 与 `CORS_ORIGINS`。
- 确认 `DEBUG=false`、`ENVIRONMENT=production`，以及 `BULK_IMPORT_ENABLED=false`。
- 配置域名、HTTPS 证书与 80/443 防火墙规则。

## 部署

```bash
unzip rental-housing-release-20260813.zip
cd rental-housing-release-20260813
cp .env.example .env.prod
# 编辑 .env.prod，填入服务器真实密钥和域名
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
curl http://localhost/api/v1/health
```

## 必验流程

1. 租客支付成功后，BM 收到通知并进入“合约管理 → 待确认房号”。
2. BM 确认房号、生成合同；租客签约后订单显示“预订成功”。
3. 已支付或已签合同的订单不显示支付倒计时，也不可再次支付。
4. BM 订单管理中：`paid`、`contract_ready` 为“进行中”；已签合同为“预订成功”。
5. 批量导入接口返回禁用状态，线上不开放。

完整部署说明见 `DEPLOYMENT.md`。

"""
模型训练脚本 — 由 Celery 定时任务或 API 触发

训练流程:
  1. 从数据库加载房源数据（排除已下线/维护中的脏数据）
  2. IQR 过滤极端标签
  3. 特征工程 → XGBoost 训练
  4. 评估 → 达标则自动保存，不达标则告警
  5. 写入数据库 ml_models 表记录训练历史

触发方式:
  - Celery 定时任务: 每天凌晨 2:00
  - API 手动触发: POST /api/v1/ml/train
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def fetch_training_data(db_session_factory) -> list[dict]:
    """
    从数据库获取训练数据

    筛选条件:
      - status in ('available', 'rented') — 排除 maintenance/offline
      - price_monthly > 0 — 排除未定价房源
      - 创建时间在最近 12 个月内 — 市场变化快，旧数据可能过时
    """
    from datetime import timedelta

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.property import Property, PropertyStatus

    cutoff = datetime.now(timezone.utc) - timedelta(days=365)

    async with db_session_factory() as session:
        result = await session.execute(
            select(Property).where(
                Property.status.in_([PropertyStatus.available, PropertyStatus.rented]),
                Property.price_monthly > 0,
                Property.created_at >= cutoff,
            )
        )
        properties = result.scalars().all()

        return [
            {
                "area_sqm": float(p.area_sqm) if p.area_sqm else None,
                "bedrooms": p.bedrooms,
                "bathrooms": p.bathrooms,
                "deposit_amount": p.deposit_amount,
                "service_fee_rate": p.service_fee_rate,
                "district": p.district,
                "property_type": p.property_type.value if p.property_type else "apartment",
                "latitude": float(p.latitude) if p.latitude else None,
                "longitude": float(p.longitude) if p.longitude else None,
                "price_monthly": float(p.price_monthly),
            }
            for p in properties
        ]


async def train_and_evaluate(
    db_session_factory,
    *,
    force: bool = False,
) -> dict:
    """
    执行完整训练流程

    返回:
        {"status": "success"|"skipped"|"failed", "metrics": {...}}
    """
    from app.ml.rent_predictor import RentPredictor, ModelMetrics

    # 1. 获取数据
    data = await fetch_training_data(db_session_factory)
    logger.info("获取训练数据: %d 条", len(data))

    if len(data) < 20:
        return {
            "status": "skipped",
            "reason": f"训练数据不足: {len(data)} 条（需要 ≥20 条）",
        }

    # 2. 训练
    predictor = RentPredictor()
    try:
        metrics = predictor.train(data)
    except Exception as exc:
        logger.exception("训练失败")
        return {"status": "failed", "reason": str(exc)}

    # 3. 达标检查
    passes = (
        metrics.mae < 800 and           # MAE < 800 元
        metrics.mape < 20.0 and         # MAPE < 20%
        metrics.r2 > 0.3                # R² > 0.3（有基本解释力）
    )

    if not passes and not force:
        logger.warning(
            "模型指标不达标: MAE=%.0f, MAPE=%.1f%%, R²=%.3f",
            metrics.mae, metrics.mape, metrics.r2,
        )
        return {
            "status": "skipped",
            "reason": "模型指标不达标（MAE>800 或 MAPE>20% 或 R²<0.3）",
            "metrics": _metrics_to_dict(metrics),
        }

    # 4. 保存
    filepath = predictor.save()
    logger.info("模型已保存: %s", filepath)

    return {
        "status": "success",
        "filepath": filepath,
        "metrics": _metrics_to_dict(metrics),
    }


def _metrics_to_dict(m) -> dict:
    return {
        "mae": m.mae,
        "mape": m.mape,
        "rmse": m.rmse,
        "r2": m.r2,
        "n_samples": m.n_samples,
        "n_features": m.n_features,
        "trained_at": m.trained_at,
        "district_report": m.district_report,
    }

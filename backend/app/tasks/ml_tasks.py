"""
ML 定时训练 & 异步任务

Celery Beat 配置（backend/app/celery_app.py 中注册）:
    celery_app.conf.beat_schedule = {
        "ml-daily-training": {
            "task": "train_rent_model",
            "schedule": crontab(hour=2, minute=7),  # 每天凌晨 2:07
        },
    }
"""
import asyncio
import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="train_rent_model",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def train_rent_model() -> dict:
    """
    定时训练租金预测模型

    每天凌晨 2:07 自动执行:
      1. 从数据库加载最近 12 个月房源
      2. 特征工程 → XGBoost 训练 → 评估
      3. 达标自动保存 → 不达标跳过
    """

    async def _run() -> dict:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.core.config import get_settings
        from app.ml.train import train_and_evaluate

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        try:
            result = await train_and_evaluate(session_factory, force=False)
            logger.info("定时训练完成: %s", result.get("status"))
            return result
        except Exception as exc:
            logger.exception("定时训练失败")
            return {"status": "failed", "reason": str(exc)}
        finally:
            await engine.dispose()

    return asyncio.run(_run())

import os

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "rental_housing",
    broker=settings.redis_url,
    backend=settings.redis_url,
    # app/tasks/__init__.py 是空的且没有 autodiscover_tasks，worker 只会注册这里列出的
    # 模块。漏掉任何一个，对应的 .delay() 到了 worker 就是 unregistered task。
    include=[
        "app.tasks.embedding_tasks",
        "app.tasks.import_tasks",
        "app.tasks.ml_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.payment_tasks",
        "app.tasks.poi_tasks",
    ],
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
)

celery_app.conf.update(
    broker_connection_retry_on_startup=False,
    broker_connection_timeout=2,
    broker_connection_max_retries=0,
    task_always_eager=os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").lower() == "true",
    task_eager_propagates=os.environ.get("CELERY_TASK_EAGER_PROPAGATES", "").lower() == "true",
    task_routes={
        "app.tasks.embedding_tasks.*": {"queue": "embedding"},
        "app.tasks.import_tasks.*": {"queue": "import"},
        "generate_map_pois_for_property": {"queue": "poi"},
        "backfill_all_map_pois": {"queue": "poi"},
        "refresh_stale_map_pois": {"queue": "poi"},
    },
    beat_schedule={
        "refresh-stale-map-pois": {
            "task": "refresh_stale_map_pois",
            "schedule": settings.poi_refresh_interval_seconds,
        },
    },
)

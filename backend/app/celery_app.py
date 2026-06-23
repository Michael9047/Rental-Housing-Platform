from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "rental_housing",
    broker=settings.redis_url,
    backend=settings.redis_url,
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
    task_routes={
        "app.tasks.embedding_tasks.*": {"queue": "embedding"},
        "app.tasks.import_tasks.*": {"queue": "import"},
    },
)

import os

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
    include=["app.tasks.payment_tasks"],
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
    },
    beat_schedule={
        "payment-expiring-3h-reminder-every-5-minutes": {
            "task": "send_payment_expiring_3h_reminders",
            "schedule": 300.0,
        },
        "contract-expiring-12h-reminder-every-5-minutes": {
            "task": "send_contract_expiring_12h_reminders",
            "schedule": 300.0,
        },
    },
)

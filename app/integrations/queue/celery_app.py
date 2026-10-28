from celery import Celery

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging


def create_celery_app(settings: Settings | None = None) -> Celery:
    configure_logging()
    resolved_settings = settings or get_settings()
    celery_app = Celery(
        "nota_tecnica",
        broker=resolved_settings.redis_url,
        backend=resolved_settings.redis_url,
    )
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        imports=(
            "app.integrations.queue.payment_tasks",
            "app.integrations.queue.notification_tasks",
        ),
        beat_schedule={
            "recover-pending-payments": {"task": "payments.recover_pending", "schedule": 60.0},
            "recover-pending-notifications": {
                "task": "notifications.recover_pending",
                "schedule": 60.0,
            },
        },
        broker_connection_timeout=2,
        task_publish_retry=False,
    )
    return celery_app


celery_app = create_celery_app()

from celery import Celery

from app.core.config import Settings, get_settings


def create_celery_app(settings: Settings | None = None) -> Celery:
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
    )
    return celery_app


celery_app = create_celery_app()

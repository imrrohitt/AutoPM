from celery import Celery
from celery.signals import worker_process_init

import core.models_registry  # noqa: F401 — register all SQLAlchemy mappers
from core.config import get_settings
from core.database import engine

settings = get_settings()

celery_app = Celery(
    "autopm",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

celery_app.autodiscover_tasks(["modules.agent"])


@worker_process_init.connect
def _dispose_sqlalchemy_pool_after_fork(**kwargs: object) -> None:
    """Drop connections inherited from the parent process (prefork workers)."""
    engine.sync_engine.dispose()


import modules.agent.tasks  # noqa: E402, F401

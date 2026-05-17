"""
Celery application — gevent pool (greenlets, not prefork).

Set AUTOPM_CELERY_GEVENT=1 in the worker process only (see scripts/dev-celery.sh).
Do not patch when the API imports this module for .delay().
"""

import os

if os.environ.get("AUTOPM_CELERY_GEVENT", "").lower() in ("1", "true", "yes"):
    from gevent import monkey

    monkey.patch_all()

from celery import Celery
from celery.signals import worker_init
from kombu import Queue

import core.models_registry  # noqa: F401 — register all SQLAlchemy mappers
from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "autopm",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Pool is selected via CLI: celery worker -P gevent (see scripts/dev-celery.sh)
celery_app.conf.update(
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_default_queue="agent",
    task_queues=(
        Queue("agent"),
        Queue("default"),
    ),
    task_routes={
        "run_agent_task": {"queue": "agent"},
    },
    broker_connection_retry_on_startup=True,
)

celery_app.autodiscover_tasks(["modules.agent"])


@worker_init.connect
def _on_worker_init(**kwargs: object) -> None:
    """Gevent workers share one process — no prefork pool to dispose."""
    from core.database import engine

    engine.sync_engine.dispose(close=False)


import modules.agent.tasks  # noqa: E402, F401

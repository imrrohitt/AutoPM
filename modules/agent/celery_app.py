"""
Celery application — gevent pool (greenlets, not prefork).

Set AUTOPM_CELERY_GEVENT=1 in the worker process only (see scripts/dev-celery.sh).
Agent jobs run in a subprocess (modules.agent.run_cli) so asyncio/asyncpg stay isolated.
Do not patch when the API imports this module for .delay().
"""

import os

if os.environ.get("AUTOPM_CELERY_GEVENT", "").lower() in ("1", "true", "yes"):
    from gevent import monkey

    # Patch sockets/subprocess for greenlets; keep asyncio + threading native for agent CLI.
    if not monkey.is_module_patched("socket"):
        monkey.patch_all(asyncio=False, thread=False, subprocess=True)

from celery import Celery
from celery.signals import worker_init
from kombu import Exchange, Queue

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
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="agent",
    task_queues=(
        Queue("agent", Exchange("agent", type="direct"), routing_key="agent"),
        Queue("default", Exchange("default", type="direct"), routing_key="default"),
    ),
    task_routes={
        "run_agent_task": {"queue": "agent"},
        # Prefork only — asyncio + asyncpg (gevent subprocess causes LoopExit on Linux).
        "check_story_agent_schedules": {"queue": "agent"},
    },
    beat_schedule={
        "check-story-agent-schedules": {
            "task": "check_story_agent_schedules",
            "schedule": 60.0,
            "options": {"queue": "agent"},
        },
    },
    broker_connection_retry_on_startup=True,
)

celery_app.autodiscover_tasks(["modules.agent"])


@worker_init.connect
def _on_worker_init(**kwargs: object) -> None:
    """Gevent workers share one process — no prefork pool to dispose."""
    from core.database import engine

    engine.sync_engine.dispose(close=False)


import modules.agent.schedule_tasks  # noqa: E402, F401
import modules.agent.tasks  # noqa: E402, F401

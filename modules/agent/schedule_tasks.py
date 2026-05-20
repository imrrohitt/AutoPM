"""Celery beat task: poll DB for due story agent schedules."""

from __future__ import annotations

import asyncio
import logging

import core.models_registry  # noqa: F401
from core.database import celery_async_session
from modules.agent.celery_app import celery_app
from modules.agent.schedule_service import StoryAgentScheduleService
from modules.agent.tasks import _gevent_worker, run_python_module_subprocess

logger = logging.getLogger(__name__)


async def _process_due_schedules_async() -> int:
    async with celery_async_session() as db:
        return await StoryAgentScheduleService(db).process_due_schedules()


def _execute_check_schedules() -> int:
    # Gevent default worker: no asyncio.run() / asyncpg in-process.
    if _gevent_worker():
        returncode = run_python_module_subprocess("modules.agent.schedule_cli")
        if returncode != 0:
            raise RuntimeError(f"schedule_cli exited with code {returncode}")
        return 0
    return asyncio.run(_process_due_schedules_async())


@celery_app.task(name="check_story_agent_schedules", queue="default")
def check_story_agent_schedules() -> int:
    """Run every minute via Celery beat; enqueue due story agent runs."""
    try:
        triggered = _execute_check_schedules()
        if triggered:
            logger.info("check_story_agent_schedules: triggered %s run(s)", triggered)
        return triggered
    except Exception:
        logger.exception("check_story_agent_schedules failed")
        raise

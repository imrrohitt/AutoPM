"""Celery beat task: poll DB for due story agent schedules."""

from __future__ import annotations

import asyncio
import logging

import core.models_registry  # noqa: F401
from core.database import celery_async_session
from modules.agent.celery_app import celery_app
from modules.agent.schedule_service import StoryAgentScheduleService

logger = logging.getLogger(__name__)


async def _process_due_schedules_async() -> int:
    async with celery_async_session() as db:
        return await StoryAgentScheduleService(db).process_due_schedules()


@celery_app.task(name="check_story_agent_schedules", queue="agent")
def check_story_agent_schedules() -> int:
    """
    Run every minute via Celery beat on the agent (prefork) queue.

    Must not run on the gevent default queue — asyncio/asyncpg and gevent
    subprocess polling cause LoopExit on Linux servers.
    """
    try:
        triggered = asyncio.run(_process_due_schedules_async())
        if triggered:
            logger.info("check_story_agent_schedules: triggered %s run(s)", triggered)
        return triggered
    except Exception:
        logger.exception("check_story_agent_schedules failed")
        raise

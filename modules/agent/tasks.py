import asyncio
import uuid

import core.models_registry  # noqa: F401 — register all SQLAlchemy mappers
from core.database import celery_async_session
from modules.agent.celery_app import celery_app
from modules.agent.service import AgentService


async def _run_agent_async(run_id: uuid.UUID) -> None:
    async with celery_async_session() as db:
        from sqlalchemy import select

        from modules.agent.models import AgentRun
        from modules.agent.story_worker import StoryAgentWorker

        result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            return
        if run.run_type == "story":
            await StoryAgentWorker(db, run_id).execute()
        else:
            await AgentService(db).execute_run(run_id)


@celery_app.task(name="run_agent_task", bind=True, max_retries=0)
def run_agent_task(self, run_id: str) -> None:
    asyncio.run(_run_agent_async(uuid.UUID(run_id)))

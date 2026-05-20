import asyncio
import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import core.models_registry  # noqa: F401 — register all SQLAlchemy mappers
from core.database import celery_async_session
from modules.agent.celery_app import celery_app
from modules.agent.service import AgentService

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _gevent_worker() -> bool:
    return os.environ.get("AUTOPM_CELERY_GEVENT", "").lower() in ("1", "true", "yes")


async def _run_agent_async(run_id: uuid.UUID) -> None:
    async with celery_async_session() as db:
        from sqlalchemy import select

        from modules.agent.models import AgentRun
        from modules.agent.story_worker import StoryAgentWorker

        result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            logger.warning("run_agent_async: run not found %s", run_id)
            return
        logger.info("run_agent_async: executing run_id=%s type=%s", run_id, run.run_type)
        if run.run_type == "story":
            await StoryAgentWorker(db, run_id).execute()
        else:
            await AgentService(db).execute_run(run_id)


async def _mark_run_failed(run_id: uuid.UUID, error: str) -> None:
    from sqlalchemy import select

    from modules.agent.models import AgentRun

    async with celery_async_session() as db:
        result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run or run.status in ("completed", "failed", "cancelled"):
            return
        run.status = "failed"
        run.error_message = error[:2000]
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()


def run_python_module_subprocess(module: str, *args: str) -> int:
    """
    Spawn a clean Python process (asyncio + asyncpg safe).

    Under gevent, use gevent.subprocess so wait() yields to the hub (stdlib
    subprocess.run() blocks the worker and triggers LoopExit in Celery's pool).
    """
    cmd = [sys.executable, "-m", module, *args]
    logger.info("spawning subprocess: %s", " ".join(cmd))
    env = os.environ.copy()
    cwd = str(_REPO_ROOT)

    if _gevent_worker():
        # Run blocking subprocess in a real OS thread (avoids gevent LoopExit on poll/wait).
        from gevent.threadpool import ThreadPool

        pool = ThreadPool(1)
        result = pool.spawn(
            subprocess.run,
            cmd,
            cwd=cwd,
            env=env,
            check=False,
        ).get()
        return result.returncode

    return subprocess.run(cmd, cwd=cwd, env=env).returncode


def _run_in_subprocess(run_id: uuid.UUID, *extra_cli_args: str) -> None:
    returncode = run_python_module_subprocess(
        "modules.agent.run_cli", str(run_id), *extra_cli_args
    )
    logger.info("agent subprocess finished run_id=%s exit=%s", run_id, returncode)
    if returncode != 0:
        raise RuntimeError(f"Agent subprocess exited with code {returncode}")


def _execute_run(run_id: uuid.UUID) -> None:
    # Prefork agent worker: asyncio in-process (fast, no subprocess).
    # Gevent worker (fallback): isolated CLI subprocess with cooperative polling.
    if _gevent_worker():
        _run_in_subprocess(run_id)
    else:
        asyncio.run(_run_agent_async(run_id))


def _execute_mark_failed(run_id: uuid.UUID, error: str) -> None:
    if _gevent_worker():
        _run_in_subprocess(run_id, "--mark-failed", error[:500])
    else:
        asyncio.run(_mark_run_failed(run_id, error))


@celery_app.task(
    name="run_agent_task",
    bind=True,
    max_retries=0,
    queue="agent",
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_agent_task(self, run_id: str) -> None:
    """Execute agent run (gevent: isolated subprocess; prefork: asyncio in worker)."""
    parsed_id = uuid.UUID(run_id)
    logger.info("run_agent_task starting run_id=%s pool_gevent=%s", run_id, _gevent_worker())
    try:
        _execute_run(parsed_id)
        logger.info("run_agent_task finished run_id=%s", run_id)
    except Exception as exc:
        logger.exception("run_agent_task failed run_id=%s", run_id)
        try:
            _execute_mark_failed(parsed_id, str(exc))
        except Exception:
            logger.exception("could not mark run failed run_id=%s", run_id)
        raise


def dispatch_agent_run(run_id: uuid.UUID) -> None:
    """Enqueue agent work on the agent queue (used by API and stale-run recovery)."""
    run_agent_task.apply_async(args=[str(run_id)], queue="agent")

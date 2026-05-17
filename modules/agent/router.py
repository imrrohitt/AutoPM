import asyncio
import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import async_session_factory
from core.dependencies import get_current_user, get_db
from modules.agent.models import AgentRun
from modules.agent.schemas import AgentLogResponse, AgentRunDetailResponse, AgentRunResponse
from modules.agent.service import AgentService
from modules.users.models import User

router = APIRouter(tags=["agent"])


@router.post("/stories/{story_id}/agent/run", response_model=AgentRunResponse)
async def start_story_agent_run(
    story_id: UUID,
    project_id: Annotated[UUID, Query(description="Project ID for the story")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AgentService(db).queue_story_run(current_user, project_id, story_id)


@router.get("/stories/{story_id}/agent/runs", response_model=list[AgentRunResponse])
async def list_story_agent_runs(
    story_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AgentService(db).list_runs_for_story(current_user, story_id)


@router.post("/tickets/{ticket_id}/agent/run", response_model=AgentRunResponse)
async def start_agent_run(
    ticket_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AgentService(db).queue_run(current_user, ticket_id)


@router.get("/tickets/{ticket_id}/agent/runs", response_model=list[AgentRunResponse])
async def list_ticket_agent_runs(
    ticket_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AgentService(db).list_runs_for_ticket(current_user, ticket_id)


@router.post("/agent/runs/{run_id}/cancel", response_model=AgentRunResponse)
async def cancel_agent_run(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AgentService(db).cancel_run(current_user, run_id)


@router.get("/agent/runs/{run_id}", response_model=AgentRunDetailResponse)
async def get_agent_run(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AgentService(db).get_run(current_user, run_id)


@router.get("/agent/runs/{run_id}/logs", response_model=list[AgentLogResponse])
async def get_agent_run_logs(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AgentService(db).list_logs(current_user, run_id)


@router.get("/agent/runs/{run_id}/stream")
async def stream_agent_logs(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await AgentService(db).get_run(current_user, run_id)

    async def event_generator():
        last_created_at: datetime | None = None
        idle_ticks = 0
        while True:
            batch: list = []
            async with async_session_factory() as session:
                service = AgentService(session)
                batch = await service.get_logs_after(run_id, last_created_at)
                for log in batch:
                    payload = {
                        "id": str(log.id),
                        "run_id": str(log.run_id),
                        "level": log.level,
                        "step": log.step,
                        "message": log.message,
                        "metadata": log.log_metadata,
                        "created_at": log.created_at.isoformat(),
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    last_created_at = log.created_at
                    idle_ticks = 0

                run_result = await session.execute(select(AgentRun).where(AgentRun.id == run_id))
                run = run_result.scalar_one_or_none()

            if run and run.status in ("completed", "failed", "cancelled"):
                yield f"data: {json.dumps({'type': 'done', 'status': run.status})}\n\n"
                break

            if not batch:
                idle_ticks += 1
            if idle_ticks > 120:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

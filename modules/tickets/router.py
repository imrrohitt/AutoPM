from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_current_user, get_db
from modules.tickets.schemas import (
    CommentCreate,
    CommentResponse,
    TicketCreate,
    TicketResponse,
    TicketUpdate,
)
from modules.tickets.service import TicketService
from modules.users.models import User

router = APIRouter(tags=["tickets"])


@router.get("/stories/{story_id}/tickets", response_model=list[TicketResponse])
async def list_tickets(
    story_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await TicketService(db).list_by_story(current_user, story_id)


@router.post("/stories/{story_id}/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    story_id: UUID,
    payload: TicketCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await TicketService(db).create(current_user, story_id, payload)


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await TicketService(db).get(current_user, ticket_id)


@router.patch("/tickets/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: UUID,
    payload: TicketUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await TicketService(db).update(current_user, ticket_id, payload)


@router.delete("/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(
    ticket_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await TicketService(db).delete(current_user, ticket_id)


@router.post("/tickets/{ticket_id}/enable-agent", response_model=TicketResponse)
async def enable_agent_on_ticket(
    ticket_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await TicketService(db).enable_agent(current_user, ticket_id)


@router.post("/tickets/{ticket_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    ticket_id: UUID,
    payload: CommentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await TicketService(db).add_comment(current_user, ticket_id, payload)


@router.get("/tickets/{ticket_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    ticket_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await TicketService(db).list_comments(current_user, ticket_id)

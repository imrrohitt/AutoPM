"""story agent runs and agent memory

Revision ID: 006
Revises: 005
Create Date: 2026-05-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("agent_runs", sa.Column("run_type", sa.String(32), nullable=False, server_default="ticket"))
    op.add_column(
        "agent_runs",
        sa.Column("conversation_memory", postgresql.JSONB(), nullable=True),
    )
    op.add_column("agent_runs", sa.Column("current_ticket_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_agent_runs_story_id",
        "agent_runs",
        "stories",
        ["story_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_agent_runs_story_id", "agent_runs", ["story_id"])
    op.alter_column("agent_runs", "ticket_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)

    op.create_table(
        "agent_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_key", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_agent_memory_run_id", "agent_memory", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_memory_run_id", table_name="agent_memory")
    op.drop_table("agent_memory")
    op.alter_column("agent_runs", "ticket_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_index("ix_agent_runs_story_id", table_name="agent_runs")
    op.drop_constraint("fk_agent_runs_story_id", "agent_runs", type_="foreignkey")
    op.drop_column("agent_runs", "current_ticket_id")
    op.drop_column("agent_runs", "conversation_memory")
    op.drop_column("agent_runs", "run_type")
    op.drop_column("agent_runs", "story_id")

"""agent run file changes for workspace UI

Revision ID: 007
Revises: 006
Create Date: 2026-05-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_run_file_changes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("before_content", sa.Text(), nullable=True),
        sa.Column("after_content", sa.Text(), nullable=True),
        sa.Column("change_type", sa.String(32), nullable=False, default="read"),
        sa.Column("thought", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_run_file_changes_run_id", "agent_run_file_changes", ["run_id"])
    op.create_unique_constraint(
        "uq_agent_run_file_changes_run_path",
        "agent_run_file_changes",
        ["run_id", "path"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_agent_run_file_changes_run_path", "agent_run_file_changes", type_="unique")
    op.drop_index("ix_agent_run_file_changes_run_id", table_name="agent_run_file_changes")
    op.drop_table("agent_run_file_changes")

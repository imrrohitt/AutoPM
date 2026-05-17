"""pgvector semantic memory for project-level agent recall

Revision ID: 009
Revises: 008
Create Date: 2026-05-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# BAAI/bge-small-en-v1.5 (fastembed default family)
EMBEDDING_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "project_semantic_memory",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "story_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("memory_tier", sa.String(32), nullable=False),
        sa.Column("memory_type", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute(
        f"ALTER TABLE project_semantic_memory "
        f"ADD COLUMN embedding vector({EMBEDDING_DIM}) NOT NULL"
    )
    op.create_index(
        "ix_project_semantic_memory_project_tier",
        "project_semantic_memory",
        ["project_id", "memory_tier"],
    )
    op.create_index(
        "ix_project_semantic_memory_run",
        "project_semantic_memory",
        ["run_id"],
    )
    op.execute(
        """
        CREATE INDEX ix_project_semantic_memory_embedding_hnsw
        ON project_semantic_memory
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_project_semantic_memory_embedding_hnsw", table_name="project_semantic_memory")
    op.drop_index("ix_project_semantic_memory_run", table_name="project_semantic_memory")
    op.drop_index("ix_project_semantic_memory_project_tier", table_name="project_semantic_memory")
    op.drop_table("project_semantic_memory")

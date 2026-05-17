"""github_connections nullable repo fields for token-only setup

Revision ID: 005
Revises: 004
Create Date: 2026-05-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("github_connections", "repo_owner", existing_type=sa.Text(), nullable=True)
    op.alter_column("github_connections", "repo_name", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("github_connections", "repo_owner", existing_type=sa.Text(), nullable=False)
    op.alter_column("github_connections", "repo_name", existing_type=sa.Text(), nullable=False)

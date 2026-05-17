import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class GitHubConnection(Base):
    __tablename__ = "github_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    github_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    repo_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    index_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")

    project: Mapped["Project"] = relationship("Project", back_populates="github_connection")  # noqa: F821

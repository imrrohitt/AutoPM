"""Agent run workspace: file-level changes for Cursor-style UI."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.models import AgentRun, AgentRunFileChange
from modules.github.git_client import GitHubClient
from modules.github.models import GitHubConnection
from modules.github.service import GitHubService

MAX_FILE_CHARS = 120_000


def _clip(text: str | None) -> str | None:
    if text is None:
        return None
    if len(text) <= MAX_FILE_CHARS:
        return text
    return text[:MAX_FILE_CHARS] + "\n… (truncated)"


class RunWorkspaceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        run_id: uuid.UUID,
        path: str,
        *,
        before_content: str | None = None,
        after_content: str | None = None,
        change_type: str = "read",
        thought: str | None = None,
    ) -> AgentRunFileChange:
        path = path.strip().lstrip("/")
        result = await self.db.execute(
            select(AgentRunFileChange).where(
                AgentRunFileChange.run_id == run_id,
                AgentRunFileChange.path == path,
            )
        )
        row = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)

        if row:
            if before_content is not None and row.before_content is None:
                row.before_content = _clip(before_content)
            if after_content is not None:
                row.after_content = _clip(after_content)
            if change_type:
                row.change_type = change_type
            if thought:
                row.thought = thought[:2000]
            row.updated_at = now
        else:
            row = AgentRunFileChange(
                run_id=run_id,
                path=path,
                before_content=_clip(before_content),
                after_content=_clip(after_content),
                change_type=change_type,
                thought=thought[:2000] if thought else None,
                updated_at=now,
            )
            self.db.add(row)

        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def list_changes(self, run_id: uuid.UUID) -> list[AgentRunFileChange]:
        result = await self.db.execute(
            select(AgentRunFileChange)
            .where(AgentRunFileChange.run_id == run_id)
            .order_by(AgentRunFileChange.updated_at)
        )
        return list(result.scalars().all())

    async def get_changes_after(
        self, run_id: uuid.UUID, since: datetime | None
    ) -> list[AgentRunFileChange]:
        q = select(AgentRunFileChange).where(AgentRunFileChange.run_id == run_id)
        if since:
            q = q.where(AgentRunFileChange.updated_at > since)
        q = q.order_by(AgentRunFileChange.updated_at)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def build_workspace(self, run: AgentRun) -> dict:
        conn_result = await self.db.execute(
            select(GitHubConnection).where(GitHubConnection.project_id == run.project_id)
        )
        conn = conn_result.scalar_one_or_none()
        changes = await self.list_changes(run.id)

        tree: list[str] = []
        repo_owner = conn.repo_owner if conn else None
        repo_name = conn.repo_name if conn else None
        branch = run.branch_name or (conn.default_branch if conn else "main")

        if conn and conn.repo_owner and conn.repo_name:
            token = await GitHubService(self.db).get_decrypted_token(run.project_id)
            if token:
                git = GitHubClient(token)
                try:
                    tree = await git.list_tree_paths(
                        conn.repo_owner, conn.repo_name, branch, limit=300
                    )
                except Exception:
                    tree = await git.list_tree_paths(
                        conn.repo_owner, conn.repo_name, conn.default_branch, limit=300
                    )

        change_paths = {c.path for c in changes}
        merged_tree = sorted(set(tree) | change_paths)

        return {
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "branch": branch,
            "tree": merged_tree,
            "changes": [
                {
                    "path": c.path,
                    "change_type": c.change_type,
                    "before_content": c.before_content,
                    "after_content": c.after_content,
                    "thought": c.thought,
                    "updated_at": c.updated_at.isoformat(),
                }
                for c in changes
            ],
        }

    def change_to_sse_payload(self, change: AgentRunFileChange) -> dict:
        return {
            "type": "file_change",
            "path": change.path,
            "change_type": change.change_type,
            "before_content": change.before_content,
            "after_content": change.after_content,
            "thought": change.thought,
            "updated_at": change.updated_at.isoformat(),
        }

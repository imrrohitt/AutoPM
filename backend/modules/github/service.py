import uuid
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.encryption import decrypt_value, encrypt_value
from core.exceptions import NotFoundError
from modules.github.models import GitHubConnection
from modules.github.schemas import (
    GitHubConnectRequest,
    GitHubConnectionResponse,
    GitHubIndexStatusResponse,
    GitHubRepoItem,
)
from modules.projects.models import Project
from modules.users.models import User

GITHUB_API = "https://api.github.com"


class GitHubService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _to_response(self, conn: GitHubConnection) -> GitHubConnectionResponse:
        has_repo = bool(conn.repo_owner and conn.repo_name)
        return GitHubConnectionResponse(
            id=conn.id,
            project_id=conn.project_id,
            repo_owner=conn.repo_owner,
            repo_name=conn.repo_name,
            default_branch=conn.default_branch,
            connected_at=conn.connected_at,
            last_indexed_at=conn.last_indexed_at,
            index_status=conn.index_status,
            has_token=bool(conn.github_token_encrypted),
            is_connected=has_repo,
        )

    async def _get_project(self, project_id: uuid.UUID, company_id: uuid.UUID) -> Project:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.company_id == company_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project not found")
        return project

    async def _get_connection_row(self, project_id: uuid.UUID) -> GitHubConnection | None:
        result = await self.db.execute(
            select(GitHubConnection).where(GitHubConnection.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def get_connection(self, user: User, project_id: uuid.UUID) -> GitHubConnectionResponse | None:
        await self._get_project(project_id, user.company_id)
        conn = await self._get_connection_row(project_id)
        if not conn:
            return None
        return self._to_response(conn)

    async def save_token(
        self, user: User, project_id: uuid.UUID, github_token: str
    ) -> GitHubConnectionResponse:
        await self._get_project(project_id, user.company_id)
        await self._validate_token(github_token)

        conn = await self._get_connection_row(project_id)
        if conn:
            conn.github_token_encrypted = encrypt_value(github_token)
            if not conn.repo_owner:
                conn.index_status = "token_saved"
        else:
            conn = GitHubConnection(
                project_id=project_id,
                github_token_encrypted=encrypt_value(github_token),
                repo_owner=None,
                repo_name=None,
                default_branch="main",
                index_status="token_saved",
            )
            self.db.add(conn)

        await self.db.commit()
        await self.db.refresh(conn)
        return self._to_response(conn)

    async def connect(
        self, user: User, project_id: uuid.UUID, payload: GitHubConnectRequest
    ) -> GitHubConnectionResponse:
        await self._get_project(project_id, user.company_id)
        conn = await self._get_connection_row(project_id)

        if payload.github_token:
            await self._validate_token(payload.github_token)
            encrypted = encrypt_value(payload.github_token)
        elif conn:
            encrypted = conn.github_token_encrypted
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Save a GitHub token first or include github_token in the request",
            )

        if not conn:
            conn = GitHubConnection(
                project_id=project_id,
                github_token_encrypted=encrypted,
                repo_owner=payload.repo_owner,
                repo_name=payload.repo_name,
                default_branch=payload.default_branch,
                index_status="pending",
            )
            self.db.add(conn)
        else:
            conn.github_token_encrypted = encrypted
            conn.repo_owner = payload.repo_owner
            conn.repo_name = payload.repo_name
            conn.default_branch = payload.default_branch
            conn.index_status = "pending"

        await self.db.commit()
        await self.db.refresh(conn)
        return self._to_response(conn)

    async def disconnect(self, user: User, project_id: uuid.UUID) -> None:
        await self._get_project(project_id, user.company_id)
        conn = await self._get_connection_row(project_id)
        if not conn:
            raise NotFoundError("GitHub connection not found")
        await self.db.delete(conn)
        await self.db.commit()

    async def list_repos_for_project(self, user: User, project_id: uuid.UUID) -> list[GitHubRepoItem]:
        await self._get_project(project_id, user.company_id)
        conn = await self._get_connection_row(project_id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Save a GitHub token for this project first",
            )
        token = decrypt_value(conn.github_token_encrypted)
        return await self._fetch_repos(token)

    async def _fetch_repos(self, github_token: str) -> list[GitHubRepoItem]:
        await self._validate_token(github_token)
        repos: list[GitHubRepoItem] = []
        page = 1

        async with httpx.AsyncClient(timeout=30.0) as client:
            while page <= 5:
                response = await client.get(
                    f"{GITHUB_API}/user/repos",
                    headers=self._headers(github_token),
                    params={"per_page": 100, "page": page, "sort": "updated"},
                )
                response.raise_for_status()
                data = response.json()
                if not data:
                    break

                for item in data:
                    repos.append(
                        GitHubRepoItem(
                            owner=item["owner"]["login"],
                            name=item["name"],
                            full_name=item["full_name"],
                            default_branch=item.get("default_branch") or "main",
                            private=item.get("private", False),
                        )
                    )
                if len(data) < 100:
                    break
                page += 1

        return repos

    async def trigger_index(self, user: User, project_id: uuid.UUID) -> GitHubIndexStatusResponse:
        await self._get_project(project_id, user.company_id)
        conn = await self._get_connection_row(project_id)
        if not conn or not conn.repo_owner or not conn.repo_name:
            raise NotFoundError("GitHub repository not connected for this project")

        conn.index_status = "indexing"
        await self.db.commit()

        token = decrypt_value(conn.github_token_encrypted)
        await self._build_codebase_summary(token, conn.repo_owner, conn.repo_name, conn.default_branch)

        conn.index_status = "ready"
        conn.last_indexed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(conn)
        return GitHubIndexStatusResponse(
            index_status=conn.index_status,
            last_indexed_at=conn.last_indexed_at,
        )

    async def get_index_status(self, user: User, project_id: uuid.UUID) -> GitHubIndexStatusResponse:
        await self._get_project(project_id, user.company_id)
        conn = await self._get_connection_row(project_id)
        if not conn:
            raise NotFoundError("GitHub connection not found")
        return GitHubIndexStatusResponse(
            index_status=conn.index_status,
            last_indexed_at=conn.last_indexed_at,
        )

    async def get_decrypted_token(self, project_id: uuid.UUID) -> str | None:
        conn = await self._get_connection_row(project_id)
        if not conn:
            return None
        return decrypt_value(conn.github_token_encrypted)

    async def get_codebase_summary(self, project_id: uuid.UUID) -> str:
        conn = await self._get_connection_row(project_id)
        if not conn or not conn.repo_owner or not conn.repo_name:
            return "No GitHub repository connected."
        if conn.index_status != "ready":
            return f"Repository index status: {conn.index_status}"
        token = decrypt_value(conn.github_token_encrypted)
        return await self._build_codebase_summary(
            token, conn.repo_owner, conn.repo_name, conn.default_branch
        )

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        if token.startswith("github_pat_"):
            authorization = f"Bearer {token}"
        else:
            authorization = f"token {token}"
        return {
            "Authorization": authorization,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _validate_token(self, token: str) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{GITHUB_API}/user", headers=self._headers(token))
            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid GitHub token",
                )
            response.raise_for_status()

    async def _build_codebase_summary(
        self, token: str, owner: str, repo: str, branch: str
    ) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            tree_resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
                headers=self._headers(token),
                params={"recursive": "1"},
            )
            if tree_resp.status_code != 200:
                ref_resp = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}",
                    headers=self._headers(token),
                )
                ref_resp.raise_for_status()
                default_branch = ref_resp.json().get("default_branch", "main")
                tree_resp = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{default_branch}",
                    headers=self._headers(token),
                    params={"recursive": "1"},
                )
            tree_resp.raise_for_status()
            tree = tree_resp.json()

        paths = [
            item["path"]
            for item in tree.get("tree", [])
            if item.get("type") == "blob"
            and not any(p in item["path"] for p in (".git/", "node_modules/", "__pycache__/"))
        ]
        paths = paths[:200]
        return (
            f"Repository: {owner}/{repo}\n"
            f"Branch: {branch}\n"
            f"Indexed files ({len(paths)} shown, max 200):\n"
            + "\n".join(f"- {p}" for p in paths)
        )

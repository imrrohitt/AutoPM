"""GitHub REST API for branches, files, commits, PRs, and merges."""

import base64
from dataclasses import dataclass

import httpx

GITHUB_API = "https://api.github.com"


@dataclass
class RepoRef:
    owner: str
    name: str
    default_branch: str


class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self._headers = self._build_headers(token)

    @staticmethod
    def _build_headers(token: str) -> dict[str, str]:
        if token.startswith("github_pat_"):
            auth = f"Bearer {token}"
        else:
            auth = f"token {token}"
        return {
            "Authorization": auth,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_default_branch_sha(self, owner: str, repo: str, branch: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}",
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()["object"]["sha"]

    async def create_branch(self, owner: str, repo: str, branch_name: str, from_sha: str) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/refs",
                headers=self._headers,
                json={"ref": f"refs/heads/{branch_name}", "sha": from_sha},
            )
            if r.status_code == 422:
                existing = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch_name}",
                    headers=self._headers,
                )
                if existing.status_code == 200:
                    return
                if "already exists" in r.text.lower():
                    return
            r.raise_for_status()

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str | None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
                headers=self._headers,
                params={"ref": ref},
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return None
            raw = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return raw

    async def upsert_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        branch: str,
        message: str,
    ) -> None:
        sha = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            existing = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
                headers=self._headers,
                params={"ref": branch},
            )
            if existing.status_code == 200:
                sha = existing.json().get("sha")

            body: dict = {
                "message": message,
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": branch,
            }
            if sha:
                body["sha"] = sha

            r = await client.put(
                f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
                headers=self._headers,
                json=body,
            )
            r.raise_for_status()

    async def list_tree_paths(self, owner: str, repo: str, branch: str, limit: int = 150) -> list[str]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
                headers=self._headers,
                params={"recursive": "1"},
            )
            if r.status_code != 200:
                repo_r = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}",
                    headers=self._headers,
                )
                repo_r.raise_for_status()
                branch = repo_r.json().get("default_branch", branch)
                r = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
                    headers=self._headers,
                    params={"recursive": "1"},
                )
            r.raise_for_status()
            paths = [
                item["path"]
                for item in r.json().get("tree", [])
                if item.get("type") == "blob"
                and not any(x in item["path"] for x in (".git/", "node_modules/", "__pycache__/", ".venv/"))
            ]
            return paths[:limit]

    async def find_open_pull_request(
        self,
        owner: str,
        repo: str,
        head: str,
        base: str,
    ) -> tuple[int, str] | None:
        """Return open PR number and URL for head→base, if one exists."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
                headers=self._headers,
                params={
                    "head": f"{owner}:{head}",
                    "base": base,
                    "state": "open",
                    "per_page": 10,
                },
            )
            r.raise_for_status()
            for pr in r.json():
                if pr.get("head", {}).get("ref") == head and pr.get("base", {}).get("ref") == base:
                    return pr["number"], pr["html_url"]
        return None

    async def branch_ahead_by(self, owner: str, repo: str, base: str, head: str) -> int:
        """How many commits head is ahead of base (0 if identical or unreachable)."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/compare/{base}...{head}",
                headers=self._headers,
            )
            if r.status_code != 200:
                return 0
            return int(r.json().get("ahead_by") or 0)

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> tuple[int, str, bool]:
        """Create PR or return existing open PR. Returns (number, url, reused_existing)."""
        existing = await self.find_open_pull_request(owner, repo, head, base)
        if existing:
            return existing[0], existing[1], True

        ahead = await self.branch_ahead_by(owner, repo, base, head)
        if ahead == 0:
            raise ValueError(
                f"Branch '{head}' has no commits ahead of '{base}' — "
                "nothing to open a pull request for"
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
                headers=self._headers,
                json={"title": title, "body": body, "head": head, "base": base},
            )
            if r.status_code == 422:
                # Usually: PR already exists for this branch (re-run on same story)
                existing = await self.find_open_pull_request(owner, repo, head, base)
                if existing:
                    return existing[0], existing[1], True
                try:
                    detail = r.json()
                    msg = detail.get("message", r.text)
                    errors = detail.get("errors") or []
                    if errors:
                        msg = f"{msg} — {errors}"
                except Exception:
                    msg = r.text
                raise ValueError(f"GitHub could not create pull request: {msg}") from None

            r.raise_for_status()
            data = r.json()
            return data["number"], data["html_url"], False

    async def merge_pull_request(self, owner: str, repo: str, pr_number: int) -> bool:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.put(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/merge",
                headers=self._headers,
                json={"merge_method": "squash"},
            )
            if r.status_code in (200, 201):
                return True
            return False

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/files",
                headers=self._headers,
                params={"per_page": 100},
            )
            r.raise_for_status()
            return r.json()

    async def get_pr_files_summary(self, owner: str, repo: str, pr_number: int) -> str:
        files = await self.get_pr_files(owner, repo, pr_number)
        lines = []
        for f in files:
            lines.append(f"- {f['filename']} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})")
        return "\n".join(lines) or "No files changed"

    async def get_pr_files_detail(self, owner: str, repo: str, pr_number: int) -> str:
        """Full patches for review (truncated per file)."""
        files = await self.get_pr_files(owner, repo, pr_number)
        parts: list[str] = []
        for f in files:
            parts.append(
                f"### {f['filename']} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})\n"
                f"```diff\n{(f.get('patch') or '(binary or too large)')[:8000]}\n```"
            )
        return "\n\n".join(parts) or "No files changed"

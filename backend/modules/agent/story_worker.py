"""Story-level AI agent: branch → tickets → commit → PR → review → merge."""

import json
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from modules.agent.memory import AgentMemoryStore
from modules.agent.models import AgentRun
from modules.agent.service import AgentService, _slugify
from modules.github.git_client import GitHubClient
from modules.github.models import GitHubConnection
from modules.github.service import GitHubService
from modules.llm.client import chat_completion
from modules.llm.service import LLMService
from modules.projects.models import Project
from modules.stories.models import Story
from modules.tickets.models import Ticket

settings = get_settings()

FILE_CHANGE_PROMPT = """You are an expert software engineer. Respond with ONLY valid JSON (no markdown fences).

Schema:
{
  "analysis": "brief reasoning",
  "files": [{"path": "relative/path/from/repo/root", "content": "full file content"}],
  "commit_message": "conventional commit message"
}

Rules:
- Only include files you are changing or creating
- Provide COMPLETE file contents, not diffs
- Keep changes minimal and focused on the ticket
- If no code change needed, return "files": []
"""

REVIEW_PROMPT = """You are a senior code reviewer. Respond with ONLY valid JSON:
{"approved": true|false, "feedback": "...", "fix_files": [{"path": "...", "content": "..."}]}

Approve only if work meets acceptance criteria. If not approved, provide fix_files with complete contents."""


def _extract_json(text: str) -> dict:
    if not text or not text.strip():
        raise ValueError(
            "LLM returned an empty response. Use a stronger model "
            "(e.g. llama3.2, qwen2.5-coder) in project LLM settings."
        )
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        preview = text[:300].replace("\n", " ")
        raise ValueError(
            f"LLM did not return valid JSON. Response preview: {preview!r}"
        ) from None


class StoryAgentWorker:
    def __init__(self, db: AsyncSession, run_id: uuid.UUID):
        self.db = db
        self.run_id = run_id
        self.agent = AgentService(db)
        self.memory = AgentMemoryStore(db, run_id)

    async def execute(self) -> None:
        result = await self.db.execute(select(AgentRun).where(AgentRun.id == self.run_id))
        run = result.scalar_one_or_none()
        if not run or run.run_type != "story" or not run.story_id:
            return
        if run.status == "cancelled":
            return

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        await self.db.commit()

        try:
            story = await self._get_story(run.story_id)
            project = await self._get_project(run.project_id)
            tickets = await self._get_work_tickets(run.story_id)

            if not tickets:
                raise ValueError("No open tickets in this story to work on")

            conn = await self._get_github_connection(run.project_id)
            llm_config, api_key = await LLMService(self.db).get_api_key(run.project_id)
            token = await GitHubService(self.db).get_decrypted_token(run.project_id)
            if not token:
                raise ValueError("GitHub not connected for this project")

            git = GitHubClient(token)
            owner, repo = conn.repo_owner, conn.repo_name
            base_branch = conn.default_branch

            branch_name = f"autopm/story-{story.id.hex[:8]}-{_slugify(story.title)}"
            run.branch_name = branch_name
            await self.db.commit()

            await self.agent.add_log(
                self.run_id, "info", "branch", f"Creating branch {branch_name} from {base_branch}"
            )
            sha = await git.get_default_branch_sha(owner, repo, base_branch)
            await git.create_branch(owner, repo, branch_name, sha)

            tree_paths = await git.list_tree_paths(owner, repo, base_branch)
            await self.memory.set("codebase_tree", "\n".join(tree_paths[:120]))
            await self.memory.set(
                "story_context",
                f"Story: {story.title}\n{story.description or ''}\n\nAcceptance:\n{story.acceptance_criteria or 'N/A'}",
            )

            conversation: list[dict[str, str]] = []

            for ticket in tickets:
                if await self._is_cancelled():
                    return

                run.current_ticket_id = ticket.id
                ticket.status = "in_progress"
                await self.db.commit()

                await self.agent.add_log(
                    self.run_id,
                    "info",
                    "ticket_start",
                    f"Working on ticket: {ticket.title}",
                    {"ticket_id": str(ticket.id)},
                )

                file_changes = await self._work_ticket(
                    git,
                    owner,
                    repo,
                    branch_name,
                    story,
                    project,
                    ticket,
                    tree_paths,
                    llm_config,
                    api_key,
                    conversation,
                )

                for fc in file_changes:
                    await git.upsert_file(
                        owner,
                        repo,
                        fc["path"],
                        fc["content"],
                        branch_name,
                        fc.get("commit_message", f"autopm: {ticket.title}"),
                    )
                    await self.agent.add_log(
                        self.run_id,
                        "success",
                        "commit",
                        f"Updated {fc['path']}",
                        {"path": fc["path"]},
                    )

                await self.memory.append(
                    "completed_tickets",
                    f"- {ticket.title}: {len(file_changes)} file(s)",
                )
                ticket.status = "review"
                await self.db.commit()

            await self.agent.add_log(self.run_id, "info", "pr_create", "Opening pull request")
            pr_body = await self._build_pr_body(story, tickets)
            pr_number, pr_url = await git.create_pull_request(
                owner,
                repo,
                title=f"[AutoPM] {story.title}",
                body=pr_body,
                head=branch_name,
                base=base_branch,
            )
            run.pr_number = pr_number
            run.pr_url = pr_url
            await self.db.commit()
            await self.agent.add_log(
                self.run_id, "success", "pr_created", f"PR #{pr_number} opened", {"pr_url": pr_url}
            )

            merged = await self._review_and_merge_loop(
                git, owner, repo, pr_number, story, llm_config, api_key, branch_name, conversation
            )

            if merged:
                story.status = "done"
                for t in tickets:
                    if t.status == "review":
                        t.status = "done"
                await self.agent.add_log(self.run_id, "success", "merged", f"PR #{pr_number} merged")
            else:
                await self.agent.add_log(
                    self.run_id,
                    "warning",
                    "review",
                    "PR needs manual review — not auto-merged",
                )

            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.agent.add_log(self.run_id, "success", "done", "Story AI work completed")

        except Exception as e:
            await self.db.rollback()
            result = await self.db.execute(select(AgentRun).where(AgentRun.id == self.run_id))
            run = result.scalar_one_or_none()
            if run:
                run.status = "failed"
                run.error_message = str(e)[:2000]
                run.completed_at = datetime.now(timezone.utc)
                await self.agent.add_log(self.run_id, "error", "failed", str(e)[:500])
                await self.db.commit()

    async def _work_ticket(
        self,
        git: GitHubClient,
        owner: str,
        repo: str,
        branch: str,
        story: Story,
        project: Project,
        ticket: Ticket,
        tree_paths: list[str],
        llm_config,
        api_key: str | None,
        conversation: list[dict[str, str]],
    ) -> list[dict]:
        memory_snapshot = await self.memory.load_all()
        sample_files = []
        for path in tree_paths[:30]:
            if any(path.endswith(ext) for ext in (".py", ".ts", ".tsx", ".js", ".md", ".json")):
                content = await git.get_file_content(owner, repo, path, branch)
                if content and len(content) < 8000:
                    sample_files.append(f"### {path}\n```\n{content[:4000]}\n```")
                if len(sample_files) >= 5:
                    break

        user_prompt = f"""PROJECT: {project.name}
GOALS: {project.goals or 'N/A'}
TECH: {project.tech_stack or 'N/A'}

STORY: {story.title}
ACCEPTANCE: {story.acceptance_criteria or 'N/A'}

TICKET: {ticket.title}
TYPE: {ticket.type} | PRIORITY: {ticket.priority}
DESCRIPTION:
{ticket.description}

PRIOR WORK:
{memory_snapshot.get('completed_tickets', 'None yet')}

REPO FILE TREE (sample):
{chr(10).join(tree_paths[:80])}

EXISTING FILE SAMPLES:
{chr(10).join(sample_files) if sample_files else 'No samples loaded'}

Implement this ticket now."""

        messages = [
            {"role": "system", "content": FILE_CHANGE_PROMPT},
            *conversation[-6:],
            {"role": "user", "content": user_prompt},
        ]

        await self.agent.add_log(self.run_id, "info", "llm", f"LLM planning changes for: {ticket.title}")
        raw = await chat_completion(
            llm_config, api_key, messages, max_tokens=8192, json_mode=True
        )
        conversation.append({"role": "user", "content": user_prompt})
        conversation.append({"role": "assistant", "content": raw})

        result = await self.db.execute(select(AgentRun).where(AgentRun.id == self.run_id))
        run = result.scalar_one()
        await self.memory.save_conversation(run, conversation)

        try:
            parsed = _extract_json(raw)
        except ValueError:
            await self.agent.add_log(
                self.run_id, "warning", "llm", "Retrying with stricter JSON prompt"
            )
            retry_messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "Your previous reply was not valid JSON. "
                        "Reply again with ONLY a JSON object matching the schema. No prose."
                    ),
                }
            ]
            raw = await chat_completion(
                llm_config, api_key, retry_messages, max_tokens=8192, json_mode=True
            )
            conversation.append({"role": "assistant", "content": raw})
            await self.memory.save_conversation(run, conversation)
            parsed = _extract_json(raw)
        await self.agent.add_log(
            self.run_id,
            "info",
            "thinking",
            parsed.get("analysis", "Planning complete")[:500],
        )

        files = parsed.get("files") or []
        commit_msg = parsed.get("commit_message", f"autopm: {ticket.title}")
        return [
            {"path": f["path"], "content": f["content"], "commit_message": commit_msg}
            for f in files
            if f.get("path") and f.get("content") is not None
        ]

    async def _review_and_merge_loop(
        self,
        git: GitHubClient,
        owner: str,
        repo: str,
        pr_number: int,
        story: Story,
        llm_config,
        api_key: str | None,
        branch: str,
        conversation: list[dict[str, str]],
    ) -> bool:
        for attempt in range(2):
            if await self._is_cancelled():
                return False

            diff_summary = await git.get_pr_files_summary(owner, repo, pr_number)
            await self.agent.add_log(
                self.run_id, "info", "review", f"Review attempt {attempt + 1}"
            )

            messages = [
                {"role": "system", "content": REVIEW_PROMPT},
                {
                    "role": "user",
                    "content": f"STORY: {story.title}\nACCEPTANCE:\n{story.acceptance_criteria}\n\nPR DIFF:\n{diff_summary}",
                },
            ]
            raw = await chat_completion(
                llm_config, api_key, messages, max_tokens=4096, json_mode=True
            )
            review = _extract_json(raw)

            if review.get("approved"):
                await self.agent.add_log(
                    self.run_id, "success", "review", review.get("feedback", "Approved")
                )
                merged = await git.merge_pull_request(owner, repo, pr_number)
                return merged

            await self.agent.add_log(
                self.run_id,
                "warning",
                "review",
                review.get("feedback", "Changes requested")[:500],
            )
            fix_files = review.get("fix_files") or []
            if not fix_files:
                return False

            for fc in fix_files:
                if fc.get("path") and fc.get("content"):
                    await git.upsert_file(
                        owner,
                        repo,
                        fc["path"],
                        fc["content"],
                        branch,
                        f"autopm: review fix attempt {attempt + 1}",
                    )
                    await self.agent.add_log(
                        self.run_id, "info", "fix", f"Applied review fix to {fc['path']}"
                    )

        return False

    async def _build_pr_body(self, story: Story, tickets: list[Ticket]) -> str:
        ticket_lines = "\n".join(f"- [{t.type}] {t.title}" for t in tickets)
        return f"""## AutoPM Story PR

**Story:** {story.title}

{story.description or ''}

### Acceptance criteria
{story.acceptance_criteria or 'N/A'}

### Tickets addressed
{ticket_lines}

---
*Automated by AutoPM AI agent*
"""

    async def _is_cancelled(self) -> bool:
        result = await self.db.execute(select(AgentRun).where(AgentRun.id == self.run_id))
        run = result.scalar_one_or_none()
        return run is not None and run.status == "cancelled"

    async def _get_story(self, story_id: uuid.UUID) -> Story:
        result = await self.db.execute(select(Story).where(Story.id == story_id))
        story = result.scalar_one_or_none()
        if not story:
            raise ValueError("Story not found")
        return story

    async def _get_project(self, project_id: uuid.UUID) -> Project:
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")
        return project

    async def _get_work_tickets(self, story_id: uuid.UUID) -> list[Ticket]:
        result = await self.db.execute(
            select(Ticket)
            .where(
                Ticket.story_id == story_id,
                Ticket.status.in_(("open", "in_progress")),
            )
            .order_by(Ticket.priority.desc(), Ticket.created_at)
        )
        return list(result.scalars().all())

    async def _get_github_connection(self, project_id: uuid.UUID) -> GitHubConnection:
        result = await self.db.execute(
            select(GitHubConnection).where(GitHubConnection.project_id == project_id)
        )
        conn = result.scalar_one_or_none()
        if not conn or not conn.repo_owner or not conn.repo_name:
            raise ValueError("GitHub repository must be connected with a selected repo")
        return conn

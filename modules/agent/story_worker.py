"""Story-level AI agent: plan → explore → implement → PR → review (OpenHands-inspired loop)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from modules.agent.context import (
    explore_ticket_context,
    fetch_agent_docs,
    fetch_files,
    format_files_for_prompt,
)
from modules.agent.project_intelligence import build_project_intelligence
from modules.agent.loop import TicketAgentLoop
from modules.agent.memory import AgentMemoryStore, load_prior_story_learnings
from modules.agent.semantic_memory import SemanticMemoryStore
from modules.agent.work_scope import build_work_scope
from modules.agent.models import AgentRun
from modules.agent.parsing import extract_json
from modules.agent.planner import create_story_plan, order_tickets_by_plan, plan_to_memory_text
from modules.agent.prompts import REVIEW_PROMPT
from modules.agent.quality import validate_patch
from modules.agent.service import AgentService, _slugify
from modules.agent.workspace import RunWorkspaceService
from modules.github.git_client import GitHubClient
from modules.github.models import GitHubConnection
from modules.github.service import GitHubService
from modules.llm.client import chat_completion
from modules.llm.service import LLMService
from modules.projects.models import Project
from modules.stories.models import Story
from modules.tickets.models import Ticket

settings = get_settings()


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
            tickets = await self._resolve_work_tickets(story)

            conn = await self._get_github_connection(run.project_id)
            llm_config, api_key = await LLMService(self.db).get_api_key(run.project_id)
            token = await GitHubService(self.db).get_decrypted_token(run.project_id)
            if not token:
                raise ValueError("GitHub not connected for this project")

            git = GitHubClient(token)
            owner, repo = conn.repo_owner, conn.repo_name
            base_branch = conn.default_branch

            semantic = SemanticMemoryStore(self.db, run.project_id)
            prior_learnings = await load_prior_story_learnings(
                self.db, run.story_id, exclude_run_id=self.run_id
            )
            recall_query = "\n".join(
                filter(
                    None,
                    [
                        story.title,
                        story.description or "",
                        story.acceptance_criteria or "",
                    ],
                )
            )
            semantic_hits = await semantic.recall(
                recall_query, limit=8, story_id=run.story_id
            )
            semantic_block = SemanticMemoryStore.format_hits(
                semantic_hits, header="Project semantic memory (pgvector)"
            )
            if semantic_block:
                prior_learnings = (
                    f"{prior_learnings}\n\n{semantic_block}".strip()
                    if prior_learnings
                    else semantic_block
                )
            if prior_learnings:
                await self.memory.set("prior_learnings", prior_learnings)
                await self.agent.add_log(
                    self.run_id, "info", "memory", "Loaded learnings from prior story runs"
                )

            codebase_summary = await GitHubService(self.db).get_codebase_summary(run.project_id)
            await self.memory.set("codebase_summary", codebase_summary[:8000])

            branch_name = f"autopm/story-{story.id.hex[:8]}-{_slugify(story.title)}"
            run.branch_name = branch_name
            await self.db.commit()

            await self.agent.add_log(
                self.run_id, "info", "branch", f"Creating branch {branch_name} from {base_branch}"
            )
            sha = await git.get_default_branch_sha(owner, repo, base_branch)
            await git.create_branch(owner, repo, branch_name, sha)

            tree_paths = await git.list_tree_paths(owner, repo, base_branch)
            await self.memory.set("codebase_tree", "\n".join(tree_paths[:200]))
            await self.memory.set(
                "story_context",
                f"Story: {story.title}\n{story.description or ''}\n\nAcceptance:\n{story.acceptance_criteria or 'N/A'}",
            )

            agent_docs = await fetch_agent_docs(
                git, owner, repo, branch_name, fallback_ref=base_branch
            )
            agent_instructions = ""
            if agent_docs:
                agent_instructions = "\n\n".join(
                    f"## {d.path}\n{d.content[:2000]}" for d in agent_docs
                )
                await self.memory.set("agent_instructions", agent_instructions)
                await self.agent.add_log(
                    self.run_id,
                    "info",
                    "context",
                    f"Loaded project docs: {', '.join(d.path for d in agent_docs)}",
                )

            project_intelligence = build_project_intelligence(
                project,
                tree_paths,
                agent_instructions=agent_instructions,
            )
            await self.memory.set("project_intelligence", project_intelligence)
            await semantic.remember_long_term(
                project_intelligence[:8000],
                "project_intelligence",
                story_id=run.story_id,
            )
            await self.agent.add_log(
                self.run_id,
                "info",
                "intelligence",
                "Built OpenHands-style project intelligence brief",
            )

            await self.agent.add_log(self.run_id, "info", "plan", "Creating execution plan")
            plan = await create_story_plan(
                llm_config,
                api_key,
                project_name=project.name,
                project_goals=project.goals,
                tech_stack=project.tech_stack,
                story=story,
                tickets=tickets,
                codebase_summary=codebase_summary,
                prior_learnings=prior_learnings,
                project_intelligence=project_intelligence,
            )
            work_scope = build_work_scope(
                story, tickets[0], tree_paths, project_intelligence=project_intelligence
            )
            constraints = list(plan.get("constraints") or [])
            constraints.append(work_scope.hint.split("\n")[0])
            plan["constraints"] = constraints
            await semantic.remember_short_term(
                plan_to_memory_text(plan)[:4000],
                "execution_plan",
                story_id=run.story_id,
                run_id=self.run_id,
            )
            await self.memory.set("execution_plan", plan_to_memory_text(plan))
            await self.agent.add_log(
                self.run_id,
                "info",
                "plan",
                plan.get("summary", "Plan ready")[:500],
            )
            tickets = order_tickets_by_plan(tickets, plan)

            conversation: list[dict[str, str]] = [
                {
                    "role": "system",
                    "content": (
                        f"EXECUTION PLAN:\n{plan_to_memory_text(plan)}\n\n"
                        f"CONSTRAINTS:\n" + "\n".join(f"- {c}" for c in (plan.get("constraints") or []))
                    ),
                }
            ]

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
                    base_branch,
                    story,
                    project,
                    ticket,
                    tree_paths,
                    llm_config,
                    api_key,
                    conversation,
                    codebase_summary,
                    plan,
                    semantic,
                )

                workspace = RunWorkspaceService(self.db)
                for fc in file_changes:
                    path = fc["path"]
                    before = await git.get_file_content(
                        owner, repo, path, base_branch
                    )
                    await git.upsert_file(
                        owner,
                        repo,
                        path,
                        fc["content"],
                        branch_name,
                        fc.get("commit_message", f"autopm: {ticket.title}"),
                    )
                    await workspace.record(
                        self.run_id,
                        path,
                        before_content=before,
                        after_content=fc["content"],
                        change_type="committed",
                    )
                    await self.agent.add_log(
                        self.run_id,
                        "success",
                        "file_change",
                        f"Committed {path}",
                        {"path": path, "change_type": "committed"},
                    )

                paths = [fc["path"] for fc in file_changes]
                if paths:
                    await self.memory.remember_files_touched(paths)
                await self.memory.append(
                    "completed_tickets",
                    f"- {ticket.title}: {len(file_changes)} file(s)",
                )
                await self.memory.remember_decision(
                    f"Completed {ticket.title} with {len(file_changes)} file change(s)"
                )
                await semantic.remember_long_term(
                    f"{story.title} — {ticket.title}: "
                    f"{len(file_changes)} file(s) — {', '.join(paths[:12])}",
                    "implementation",
                    story_id=run.story_id,
                )
                ticket.status = "review"
                await self.db.commit()

            await self.agent.add_log(self.run_id, "info", "pr_create", "Opening pull request")
            pr_body = await self._build_pr_body(story, tickets, plan)
            pr_number, pr_url, pr_reused = await git.create_pull_request(
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
            if pr_reused:
                await self.agent.add_log(
                    self.run_id,
                    "info",
                    "pr_created",
                    f"Reusing existing PR #{pr_number} (new commits on branch)",
                    {"pr_url": pr_url},
                )
            else:
                await self.agent.add_log(
                    self.run_id,
                    "success",
                    "pr_created",
                    f"PR #{pr_number} opened",
                    {"pr_url": pr_url},
                )

            primary_ticket = tickets[0]
            if story.auto_merge:
                merged = await self._auto_merge_if_quality_ok(
                    git, owner, repo, pr_number, story, primary_ticket
                )
            else:
                merged = await self._review_and_merge_loop(
                    git,
                    owner,
                    repo,
                    pr_number,
                    story,
                    llm_config,
                    api_key,
                    branch_name,
                    conversation,
                    primary_ticket,
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
        base_branch: str,
        story: Story,
        project: Project,
        ticket: Ticket,
        tree_paths: list[str],
        llm_config,
        api_key: str | None,
        conversation: list[dict[str, str]],
        codebase_summary: str,
        plan: dict,
        semantic: SemanticMemoryStore,
    ) -> list[dict]:
        memory_snapshot = await self.memory.load_all()
        prior_learnings = memory_snapshot.get("prior_learnings", "")
        project_intelligence = memory_snapshot.get("project_intelligence", "")
        prior_work = memory_snapshot.get("completed_tickets", "")
        work_scope = build_work_scope(
            story, ticket, tree_paths, project_intelligence=project_intelligence
        )

        await self.agent.add_log(
            self.run_id,
            "info",
            "explore",
            f"Exploring codebase for: {ticket.title}",
        )
        exploration = await explore_ticket_context(
            llm_config,
            api_key,
            project_name=project.name,
            project_goals=project.goals,
            tech_stack=project.tech_stack,
            story=story,
            ticket=ticket,
            tree_paths=tree_paths,
            prior_work=prior_work,
            codebase_summary=codebase_summary,
            project_intelligence=project_intelligence,
            work_scope=work_scope,
        )
        await self.memory.remember_exploration(ticket.id, exploration)
        reasoning = exploration.get("reasoning", "")
        approach = exploration.get("approach", "")
        await semantic.remember_short_term(
            f"Explore {ticket.title}: {reasoning}\nApproach: {approach}",
            "exploration",
            story_id=story.id,
            run_id=self.run_id,
        )
        await self.agent.add_log(
            self.run_id,
            "info",
            "explore",
            (reasoning or "Exploration complete")[:500],
            {
                "paths": exploration.get("relevant_paths", [])[:12],
                "approach": approach[:300],
            },
        )

        explore_paths = exploration.get("relevant_paths") or []
        explored_files = await fetch_files(
            git,
            owner,
            repo,
            branch,
            explore_paths[:8],
            fallback_ref=base_branch,
        )
        exploration_block = format_files_for_prompt(explored_files)
        if exploration_block != "No file contents loaded.":
            await self.memory.set(f"explore_files_{ticket.id}", exploration_block[:14000])

        await self.agent.add_log(
            self.run_id,
            "info",
            "loop",
            f"Starting OpenHands agent loop for: {ticket.title}",
        )

        agent_loop = TicketAgentLoop(
            self.db,
            self.run_id,
            self.agent,
            self.memory,
            git,
            owner,
            repo,
            branch,
            base_branch,
            story,
            project,
            ticket,
            tree_paths,
            llm_config,
            api_key,
            plan,
        )

        staged = await agent_loop.run(
            agent_instructions=memory_snapshot.get("agent_instructions", ""),
            prior_learnings=prior_learnings,
            codebase_summary=codebase_summary,
            execution_plan=memory_snapshot.get("execution_plan", plan_to_memory_text(plan)),
            project_intelligence=project_intelligence,
            exploration=exploration,
            exploration_block=exploration_block,
        )

        result = await self.db.execute(select(AgentRun).where(AgentRun.id == self.run_id))
        run = result.scalar_one()
        conversation.extend(agent_loop.store.to_messages()[-10:])
        await self.memory.save_conversation(run, conversation)

        await self.memory.remember_json(
            f"implementation_{ticket.id}",
            {"paths": [x["path"] for x in staged], "steps": len(agent_loop.store.events)},
        )
        return staged

    async def _auto_merge_if_quality_ok(
        self,
        git: GitHubClient,
        owner: str,
        repo: str,
        pr_number: int,
        story: Story,
        ticket: Ticket,
    ) -> bool:
        """Story has auto_merge: skip LLM review; merge when automated quality gates pass."""
        memory = await self.memory.load_all()
        tree_paths = [
            p.strip()
            for p in (memory.get("codebase_tree") or "").splitlines()
            if p.strip()
        ]
        await self.agent.add_log(
            self.run_id,
            "info",
            "auto_merge",
            "Auto-merge enabled — skipping human review; checking quality gates",
        )
        pr_files = await git.get_pr_files(owner, repo, pr_number)
        work_scope = build_work_scope(story, ticket, tree_paths)
        patch_issues: list[str] = []
        for pf in pr_files:
            patch_issues.extend(
                validate_patch(
                    pf["filename"],
                    pf.get("patch"),
                    ticket,
                    story,
                    tree_paths=tree_paths,
                    work_scope=work_scope,
                )
            )
        if patch_issues:
            await self.agent.add_log(
                self.run_id,
                "warning",
                "auto_merge",
                "Auto-merge skipped — quality gate failed:\n"
                + "\n".join(f"- {i}" for i in patch_issues[:6])[:500],
            )
            return False
        merged = await git.merge_pull_request(owner, repo, pr_number)
        if merged:
            await self.agent.add_log(
                self.run_id,
                "success",
                "auto_merge",
                f"PR #{pr_number} auto-merged (no human review required)",
            )
        return merged

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
        ticket: Ticket,
    ) -> bool:
        memory = await self.memory.load_all()
        plan_context = memory.get("execution_plan", "")

        for attempt in range(3):
            if await self._is_cancelled():
                return False

            pr_files = await git.get_pr_files(owner, repo, pr_number)
            patch_issues: list[str] = []
            tree_paths = [
                p.strip()
                for p in (memory.get("codebase_tree") or "").splitlines()
                if p.strip()
            ]
            work_scope = build_work_scope(story, ticket, tree_paths)
            for pf in pr_files:
                patch_issues.extend(
                    validate_patch(
                        pf["filename"],
                        pf.get("patch"),
                        ticket,
                        story,
                        tree_paths=tree_paths,
                        work_scope=work_scope,
                    )
                )
            if patch_issues and attempt == 0:
                await self.agent.add_log(
                    self.run_id,
                    "warning",
                    "quality",
                    "PR failed automated quality gate:\n"
                    + "\n".join(f"- {i}" for i in patch_issues[:6])[:500],
                )

            diff_detail = await git.get_pr_files_detail(owner, repo, pr_number)
            await self.agent.add_log(
                self.run_id, "info", "review", f"Review attempt {attempt + 1}"
            )

            messages = [
                {"role": "system", "content": REVIEW_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"STORY: {story.title}\n"
                        f"DESCRIPTION: {story.description or ''}\n"
                        f"ACCEPTANCE:\n{story.acceptance_criteria}\n\n"
                        f"PLAN:\n{plan_context[:2000]}\n\n"
                        f"COMPLETED WORK:\n{memory.get('completed_tickets', '')}\n\n"
                        f"AUTOMATED ISSUES:\n"
                        f"{chr(10).join(patch_issues) if patch_issues else 'None'}\n\n"
                        f"PR PATCHES:\n{diff_detail[:12000]}"
                    ),
                },
            ]
            raw = await chat_completion(
                llm_config, api_key, messages, max_tokens=4096, json_mode=True
            )
            review = extract_json(raw)

            if patch_issues:
                review["approved"] = False
                review["feedback"] = (
                    (review.get("feedback") or "")
                    + "\nAutomated quality gate failed."
                ).strip()

            if review.get("approved") and not patch_issues:
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
                    await self.memory.remember_files_touched([fc["path"]])

        return False

    async def _build_pr_body(self, story: Story, tickets: list[Ticket], plan: dict) -> str:
        memory = await self.memory.load_all()
        ticket_lines = "\n".join(f"- [{t.type}] {t.title}" for t in tickets)
        changes = memory.get("completed_tickets", "See commits")
        files_touched = memory.get("files_touched", "")
        return f"""## AutoPM Story PR

**Story:** {story.title}

{story.description or ''}

### Acceptance criteria
{story.acceptance_criteria or 'N/A'}

### What changed
{changes}

### Files touched
```
{files_touched or 'N/A'}
```

### Execution plan
{plan.get('summary', 'N/A')}

### Architecture notes
{plan.get('architecture_notes', 'N/A')}

### Testing strategy
{plan.get('testing_strategy', 'Manual verification')}

### Tickets addressed
{ticket_lines}

---
*Automated by AutoPM AI agent — quality-gated, OpenHands-inspired loop*
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

    async def _resolve_work_tickets(self, story: Story) -> list[Ticket]:
        """Find tickets to work on; reopen completed ones on re-run; create from story if empty."""
        result = await self.db.execute(
            select(Ticket)
            .where(Ticket.story_id == story.id)
            .order_by(Ticket.priority.desc(), Ticket.created_at)
        )
        all_tickets = list(result.scalars().all())

        actionable = [t for t in all_tickets if t.status in ("open", "in_progress")]
        if actionable:
            return actionable

        if all_tickets:
            for ticket in all_tickets:
                ticket.status = "open"
            if story.status == "done":
                story.status = "in_progress"
            await self.db.commit()
            await self.agent.add_log(
                self.run_id,
                "info",
                "tickets",
                f"Reopened {len(all_tickets)} ticket(s) for a new agent run",
            )
            return all_tickets

        description = story.description or story.acceptance_criteria or story.title
        if story.acceptance_criteria and story.acceptance_criteria not in description:
            description = f"{description}\n\nAcceptance criteria:\n{story.acceptance_criteria}"

        ticket = Ticket(
            story_id=story.id,
            project_id=story.project_id,
            title=f"Implement: {story.title}",
            description=description,
            type="task",
            priority="high",
            status="open",
            agent_enabled=True,
        )
        self.db.add(ticket)
        if story.status == "done":
            story.status = "in_progress"
        await self.db.commit()
        await self.db.refresh(ticket)
        await self.agent.add_log(
            self.run_id,
            "info",
            "tickets",
            "No tickets found — created one from the story description",
        )
        return [ticket]

    async def _get_github_connection(self, project_id: uuid.UUID) -> GitHubConnection:
        result = await self.db.execute(
            select(GitHubConnection).where(GitHubConnection.project_id == project_id)
        )
        conn = result.scalar_one_or_none()
        if not conn or not conn.repo_owner or not conn.repo_name:
            raise ValueError("GitHub repository must be connected with a selected repo")
        return conn

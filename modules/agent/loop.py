"""OpenHands reasoning-action loop: condense → reason → security → act → observe."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.agent_context import AgentContext, build_story_context
from modules.agent.models import AgentRun
from modules.agent.condenser import rolling_condense
from modules.agent.context import fetch_files, score_paths_by_keywords
from modules.agent.events import AgentEvent, EventStore
from modules.agent.memory import AgentMemoryStore
from modules.agent.parsing import extract_json
from modules.agent.prompts import IMPLEMENT_RETRY_PROMPT
from modules.agent.quality import resolve_paths
from modules.agent.task_scope import infer_task_kind, is_path_in_scope, scope_hint_for_kind
from modules.agent.security import analyze_action, validate_staged_writes
from modules.agent.service import AgentService
from modules.agent.step_log import persist_event
from modules.agent.workspace import RunWorkspaceService
from modules.agent.tools import TOOL_INSTRUCTIONS, ToolState, execute_tool
from modules.github.git_client import GitHubClient
from modules.llm.client import chat_completion
from modules.projects.models import Project
from modules.stories.models import Story
from modules.tickets.models import Ticket

ACTION_ALIASES = {
    "read": "read_file",
    "write": "write_file",
    "list": "list_tree",
    "search": "search_files",
    "complete": "finish",
    "done": "finish",
}


class TicketAgentLoop:
    """
    Per-ticket step loop (OpenHands Agent.step pattern).
    Tuned for small models (gemma, qwen2.5-coder:1.5b): bootstrap context,
    auto-finish after valid writes, stuck recovery, one-shot fallback.
    """

    def __init__(
        self,
        db: AsyncSession,
        run_id: uuid.UUID,
        agent: AgentService,
        memory: AgentMemoryStore,
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
        plan: dict,
        *,
        max_steps: int = 20,
    ):
        self.db = db
        self.run_id = run_id
        self.agent = agent
        self.memory = memory
        self.llm_config = llm_config
        self.api_key = api_key
        self.max_steps = max_steps
        self.tool_state = ToolState(
            git=git,
            owner=owner,
            repo=repo,
            branch=branch,
            base_branch=base_branch,
            tree_paths=tree_paths,
            story=story,
            ticket=ticket,
        )
        self.store = EventStore()
        self.existing_by_path: dict[str, str | None] = {}
        self._ctx: AgentContext | None = None
        self._plan = plan
        self._project = project
        self._story = story
        self._ticket = ticket
        self._recent_actions: list[str] = []
        self._steps_since_condense = 0
        self._last_thought = ""
        self._workspace = RunWorkspaceService(db)

    async def run(
        self,
        *,
        agent_instructions: str = "",
        prior_learnings: str = "",
        codebase_summary: str = "",
        execution_plan: str = "",
        project_intelligence: str = "",
        exploration: dict | None = None,
        exploration_block: str = "",
    ) -> list[dict]:
        from modules.agent.planner import plan_to_memory_text

        self._task_kind = infer_task_kind(self._ticket, self._story)

        self._ctx = build_story_context(
            self._project,
            self._story,
            self._ticket,
            agent_instructions=agent_instructions,
            execution_plan=execution_plan or plan_to_memory_text(self._plan),
            prior_learnings=prior_learnings,
            codebase_summary=codebase_summary,
            project_intelligence=project_intelligence,
            exploration_block=exploration_block,
            task_kind=self._task_kind,
        )

        small_model_note = (
            "\n\nSMALL MODEL MODE: Use at most 4 tool steps — "
            "1) search_files or list_tree 2) read_file 3) write_file with FULL content "
            "4) finish. After a successful write_file you may call finish immediately."
        )
        scope_note = f"\n\n{scope_hint_for_kind(self._task_kind)}"
        system_prompt = (
            self._ctx.build_system_prompt(TOOL_INSTRUCTIONS) + scope_note + small_model_note
        )
        system_event = AgentEvent(
            event_type="system", source="agent", content=system_prompt
        )
        self.store.append(system_event)
        await persist_event(self.agent, self.run_id, system_event, step_override="loop_start")

        await self._bootstrap_reads()

        task_msg = (
            f"Complete ticket: {self._ticket.title}\n"
            f"{self._ticket.description}\n\n"
        )
        if exploration:
            paths = ", ".join((exploration.get("relevant_paths") or [])[:8])
            task_msg += (
                f"EXPLORATION PLAN:\n"
                f"Reasoning: {exploration.get('reasoning', '')}\n"
                f"Approach: {exploration.get('approach', '')}\n"
                f"Target paths: {paths}\n"
                f"Risks: {', '.join(exploration.get('risks') or [])}\n\n"
            )
        if self.existing_by_path:
            task_msg += (
                "Bootstrap: key files are already loaded in observations below. "
                "Your NEXT action should be write_file (full file content), then finish.\n\n"
            )
        else:
            task_msg += (
                "Workflow: search_files → read_file → write_file (complete body) → finish.\n\n"
            )
        knowledge = self._ctx.active_knowledge(task_msg)
        if knowledge:
            task_msg = f"{knowledge}\n\n{task_msg}"

        self.store.append(
            AgentEvent(event_type="message", source="user", content=task_msg)
        )
        await persist_event(self.agent, self.run_id, self.store.events[-1])

        for step in range(self.max_steps):
            if await self._cancelled():
                return []

            self._steps_since_condense += 1
            if self._steps_since_condense >= 4 and len(self.store.events) > 28:
                condensed = await rolling_condense(
                    self.llm_config, self.api_key, self.store, max_events=32
                )
                if condensed:
                    self._steps_since_condense = 0
                    await persist_event(self.agent, self.run_id, self.store.events[-1])

            hint = self._phase_hint(step)
            if hint:
                hint_event = AgentEvent(
                    event_type="message", source="user", content=hint
                )
                self.store.append(hint_event)
                await persist_event(self.agent, self.run_id, hint_event)

            messages = self.store.to_messages()
            raw = await chat_completion(
                self.llm_config,
                self.api_key,
                messages,
                max_tokens=8192,
                json_mode=True,
            )

            action, args, thought = self._parse_step(raw)
            if not action:
                await self._observation(
                    "error",
                    "Invalid step JSON. Use: {\"thought\":\"...\",\"action\":\"read_file\",\"args\":{\"path\":\"...\"}}",
                )
                continue

            action_event = AgentEvent(
                event_type="action",
                source="agent",
                content=thought,
                metadata={"tool": action, "args": args, "thought": thought},
            )
            self.store.append(action_event)
            await persist_event(self.agent, self.run_id, action_event)
            if step > 0 and step % 4 == 0:
                run_row = await self.db.execute(
                    select(AgentRun).where(AgentRun.id == self.run_id)
                )
                run_obj = run_row.scalar_one_or_none()
                if run_obj:
                    await self.memory.save_conversation(
                        run_obj, self.store.to_messages()
                    )
            self._track_action(action)
            self._last_thought = thought
            if thought and action != "think":
                await self.memory.remember_thought(thought)
            if action == "think":
                await self.memory.remember_decision(f"Think: {args.get('note', thought)[:300]}")

            if self._is_stuck():
                await self._observation(
                    "stuck",
                    "You are repeating the same action. "
                    "If you have read the file, use write_file next, then finish.",
                )

            security = analyze_action(
                action,
                args,
                ticket=self._ticket,
                story=self._story,
                tree_paths=self.tool_state.tree_paths,
                existing_by_path=self.existing_by_path,
            )
            if not security.allowed:
                await self._observation(
                    action,
                    f"BLOCKED ({security.risk}): {security.reason}. Fix and retry.",
                    blocked=True,
                )
                retry = IMPLEMENT_RETRY_PROMPT.format(
                    issues=f"- Security ({security.risk}): {security.reason}"
                )
                self.store.append(
                    AgentEvent(event_type="message", source="user", content=retry)
                )
                await persist_event(self.agent, self.run_id, self.store.events[-1])
                continue

            observation = await execute_tool(self.tool_state, action, args)

            if action == "read_file" and not observation.startswith("Error"):
                path = args.get("path", "")
                resolved = resolve_paths([path], self.tool_state.tree_paths)
                if resolved:
                    path = resolved[0]
                    self.existing_by_path[path] = observation
                    await self._workspace.record(
                        self.run_id,
                        path,
                        before_content=observation,
                        change_type="read",
                        thought=self._last_thought,
                    )

            if action == "write_file" and not observation.startswith("Error"):
                path = args.get("path", "")
                resolved = resolve_paths([path], self.tool_state.tree_paths)
                if resolved:
                    path = resolved[0]
                    before = self.existing_by_path.get(path)
                    content = args.get("content", "")
                    await self._workspace.record(
                        self.run_id,
                        path,
                        before_content=before,
                        after_content=content,
                        change_type="staged",
                        thought=self._last_thought,
                    )

            await self._observation(action, observation)

            if action == "write_file" and self.tool_state.staged_writes:
                completed = await self._try_complete_staged()
                if completed is not None:
                    return completed

            if action == "finish":
                completed = await self._try_complete_staged()
                if completed is not None:
                    return completed
                await self._observation(
                    "finish",
                    "finish rejected: no valid staged files. write_file first with full content.",
                )

        completed = await self._try_complete_staged()
        if completed is not None:
            await self.agent.add_log(
                self.run_id, "info", "loop", "Auto-completed with staged valid writes"
            )
            return completed

        if self.existing_by_path and not self.tool_state.staged_writes:
            fallback = await self._fallback_implement()
            if fallback:
                return fallback

        raise ValueError(
            f"Agent loop exceeded {self.max_steps} steps without completing the ticket. "
            "Try qwen2.5-coder:7b or llama3.2 for better results."
        )

    async def _bootstrap_reads(self) -> None:
        """Pre-load likely files (OpenHands-style scaffold for weak models)."""
        paths = score_paths_by_keywords(
            self.tool_state.tree_paths,
            self.tool_state.ticket,
            self.tool_state.story,
            limit=8,
            task_kind=self._task_kind,
        )
        text = f"{self._ticket.title} {self._ticket.description or ''}".lower()
        if self._task_kind == "docs" and "readme" in text:
            for candidate in ("README.md", "readme.md", "Readme.md"):
                if candidate in self.tool_state.tree_paths:
                    if candidate not in paths:
                        paths.insert(0, candidate)
                    break

        if self._task_kind == "css":
            paths = [
                p
                for p in paths
                if is_path_in_scope(p, "css", self.tool_state.tree_paths)
            ][:6]

        for path in paths[:3]:
            resolved = resolve_paths([path], self.tool_state.tree_paths)
            if not resolved:
                continue
            path = resolved[0]
            files = await fetch_files(
                self.tool_state.git,
                self.tool_state.owner,
                self.tool_state.repo,
                self.tool_state.branch,
                [path],
                fallback_ref=self.tool_state.base_branch,
            )
            if not files:
                continue
            self.existing_by_path[path] = files[0].content
            self.tool_state.files_read.add(path)
            preview = files[0].content[:12000]
            self.store.append(
                AgentEvent(
                    event_type="observation",
                    source="environment",
                    content=f"BOOTSTRAP read {path}:\n{preview}",
                    metadata={"tool": "read_file", "bootstrap": True},
                )
            )
            await persist_event(
                self.agent,
                self.run_id,
                self.store.events[-1],
                step_override="bootstrap",
                message_override=f"Pre-loaded {path} ({len(files[0].content)} chars)",
            )

    async def _try_complete_staged(self) -> list[dict] | None:
        if not self.tool_state.staged_writes:
            return None
        issues = validate_staged_writes(
            self.tool_state.staged_writes,
            self._ticket,
            self._story,
            self.tool_state.tree_paths,
            self.existing_by_path,
        )
        if issues:
            issue_text = "\n".join(f"- {i}" for i in issues[:8])
            await self._observation("quality", f"Quality gate failed:\n{issue_text}")
            retry = IMPLEMENT_RETRY_PROMPT.format(issues=issue_text)
            self.store.append(
                AgentEvent(event_type="message", source="user", content=retry)
            )
            await persist_event(self.agent, self.run_id, self.store.events[-1])
            self.tool_state.staged_writes = []
            return None
        await self.memory.remember_json(
            f"loop_result_{self._ticket.id}",
            {"paths": [w["path"] for w in self.tool_state.staged_writes], "auto_finish": True},
        )
        return list(self.tool_state.staged_writes)

    async def _fallback_implement(self) -> list[dict] | None:
        """One-shot implement when loop read files but never wrote (small model recovery)."""
        await self.agent.add_log(
            self.run_id, "warning", "loop", "Fallback: one-shot implement after loop stall"
        )
        from modules.agent.prompts import FILE_CHANGE_PROMPT

        file_blocks = "\n\n".join(
            f"### {path}\n```\n{(content or '')[:8000]}\n```"
            for path, content in self.existing_by_path.items()
        )
        user = f"""TICKET: {self._ticket.title}
{self._ticket.description}

ACCEPTANCE: {self._story.acceptance_criteria or 'N/A'}

FILES ALREADY READ:
{file_blocks or 'None'}

Implement now. Return JSON with files array (full content per file)."""

        messages = [
            {"role": "system", "content": FILE_CHANGE_PROMPT},
            {"role": "user", "content": user},
        ]
        raw = await chat_completion(
            self.llm_config, self.api_key, messages, max_tokens=8192, json_mode=True
        )
        try:
            parsed = extract_json(raw)
        except ValueError:
            return None

        files = parsed.get("files") or []
        staged = []
        for f in files:
            if not f.get("path") or f.get("content") is None:
                continue
            path = resolve_paths([f["path"]], self.tool_state.tree_paths)[0]
            staged.append(
                {
                    "path": path,
                    "content": f["content"],
                    "commit_message": parsed.get("commit_message", f"autopm: {self._ticket.title}"),
                }
            )
        issues = validate_staged_writes(
            staged, self._ticket, self._story, self.tool_state.tree_paths, self.existing_by_path
        )
        if issues:
            await self.agent.add_log(
                self.run_id, "warning", "quality", f"Fallback failed: {issues[0][:200]}"
            )
            return None
        self.tool_state.staged_writes = staged
        return staged

    def _parse_step(self, raw: str) -> tuple[str, dict, str]:
        try:
            data = extract_json(raw)
        except ValueError:
            return "", {}, ""

        action = (
            data.get("action")
            or data.get("tool")
            or data.get("name")
            or ""
        ).strip().lower().replace("-", "_")
        action = ACTION_ALIASES.get(action, action)
        args = data.get("args") or data.get("arguments") or data.get("parameters") or {}
        if not isinstance(args, dict):
            args = {}
        thought = data.get("thought") or data.get("reasoning") or data.get("analysis") or ""
        return action, args, str(thought)[:500]

    def _phase_hint(self, step: int) -> str | None:
        if self.tool_state.staged_writes:
            return None
        if step == 4 and not self.tool_state.files_read:
            return "Hint: call search_files or read_file before writing."
        if step >= 5 and self.tool_state.files_read and not self.tool_state.staged_writes:
            return (
                "Hint: you have read files. NEXT action MUST be write_file with the "
                "COMPLETE updated file content, then finish."
            )
        if step >= 10 and not self.tool_state.staged_writes:
            return "URGENT: call write_file now with full file body, then finish."
        return None

    def _track_action(self, action: str) -> None:
        self._recent_actions.append(action)
        if len(self._recent_actions) > 8:
            self._recent_actions.pop(0)

    def _is_stuck(self) -> bool:
        if len(self._recent_actions) < 4:
            return False
        last4 = self._recent_actions[-4:]
        return len(set(last4)) == 1 and last4[0] in ("list_tree", "search_files", "think", "read_file")

    async def _observation(
        self, tool: str, content: str, *, blocked: bool = False
    ) -> None:
        self.store.append(
            AgentEvent(
                event_type="observation",
                source="environment",
                content=content,
                metadata={"tool": tool, "blocked": blocked},
            )
        )
        await persist_event(self.agent, self.run_id, self.store.events[-1])

    async def _cancelled(self) -> bool:
        from sqlalchemy import select

        from modules.agent.models import AgentRun

        result = await self.db.execute(select(AgentRun).where(AgentRun.id == self.run_id))
        run = result.scalar_one_or_none()
        return run is not None and run.status == "cancelled"

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.models import AgentMemory, AgentRun


class AgentMemoryStore:
    def __init__(self, db: AsyncSession, run_id: uuid.UUID):
        self.db = db
        self.run_id = run_id

    async def set(self, key: str, content: str) -> None:
        result = await self.db.execute(
            select(AgentMemory).where(
                AgentMemory.run_id == self.run_id,
                AgentMemory.memory_key == key,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.content = content
        else:
            self.db.add(AgentMemory(run_id=self.run_id, memory_key=key, content=content))
        await self.db.commit()

    async def get(self, key: str) -> str | None:
        result = await self.db.execute(
            select(AgentMemory).where(
                AgentMemory.run_id == self.run_id,
                AgentMemory.memory_key == key,
            )
        )
        row = result.scalar_one_or_none()
        return row.content if row else None

    async def append(self, key: str, line: str) -> None:
        existing = await self.get(key) or ""
        await self.set(key, f"{existing}\n{line}".strip())

    async def load_all(self) -> dict[str, str]:
        result = await self.db.execute(
            select(AgentMemory).where(AgentMemory.run_id == self.run_id)
        )
        return {m.memory_key: m.content for m in result.scalars().all()}

    async def save_conversation(self, run: AgentRun, messages: list[dict]) -> None:
        run.conversation_memory = messages[-30:]
        await self.db.commit()

    async def remember_json(self, key: str, data: dict | list) -> None:
        await self.set(key, json.dumps(data, indent=2))

    async def get_json(self, key: str) -> dict | list | None:
        raw = await self.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def remember_decision(self, decision: str) -> None:
        await self.append("decisions", f"- {decision}")

    async def remember_files_touched(self, paths: list[str]) -> None:
        existing = await self.get("files_touched") or ""
        known = {p.strip() for p in existing.split("\n") if p.strip()}
        known.update(paths)
        await self.set("files_touched", "\n".join(sorted(known)))

    async def remember_exploration(self, ticket_id: uuid.UUID, exploration: dict) -> None:
        """OpenHands explore step: reasoning, paths, approach, risks."""
        await self.remember_json(f"exploration_{ticket_id}", exploration)
        reasoning = exploration.get("reasoning") or exploration.get("analysis") or ""
        approach = exploration.get("approach") or ""
        if reasoning:
            await self.remember_decision(f"Explore ({ticket_id}): {reasoning[:400]}")
        if approach:
            await self.append("exploration_notes", f"[{ticket_id}] {approach[:500]}")

    async def remember_thought(self, thought: str) -> None:
        if thought.strip():
            await self.append("thoughts", f"- {thought.strip()[:400]}")


async def load_prior_story_learnings(
    db: AsyncSession,
    story_id: uuid.UUID,
    *,
    exclude_run_id: uuid.UUID | None = None,
    max_runs: int = 3,
) -> str:
    """Cross-run memory: learnings from previous completed story agent runs."""
    query = (
        select(AgentRun)
        .where(
            AgentRun.story_id == story_id,
            AgentRun.run_type == "story",
            AgentRun.status == "completed",
        )
        .order_by(AgentRun.completed_at.desc())
        .limit(max_runs)
    )
    result = await db.execute(query)
    runs = list(result.scalars().all())
    if exclude_run_id:
        runs = [r for r in runs if r.id != exclude_run_id]

    if not runs:
        return ""

    lines: list[str] = []
    for run in runs:
        mem_result = await db.execute(
            select(AgentMemory).where(AgentMemory.run_id == run.id)
        )
        entries = {m.memory_key: m.content for m in mem_result.scalars().all()}
        summary_parts = []
        if run.pr_url:
            summary_parts.append(f"PR: {run.pr_url}")
        if entries.get("execution_plan"):
            summary_parts.append(f"Plan: {entries['execution_plan'][:400]}")
        if entries.get("completed_tickets"):
            summary_parts.append(entries["completed_tickets"][:500])
        if entries.get("decisions"):
            summary_parts.append(entries["decisions"][:400])
        if entries.get("files_touched"):
            summary_parts.append(f"Files: {entries['files_touched'][:300]}")
        if entries.get("exploration_notes"):
            summary_parts.append(f"Exploration: {entries['exploration_notes'][:300]}")
        if entries.get("thoughts"):
            summary_parts.append(f"Reasoning: {entries['thoughts'][:300]}")
        if summary_parts:
            lines.append(f"Run {run.completed_at}:\n" + "\n".join(summary_parts))

    return "\n\n".join(lines)

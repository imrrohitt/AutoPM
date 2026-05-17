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
        run.conversation_memory = messages[-20:]
        await self.db.commit()

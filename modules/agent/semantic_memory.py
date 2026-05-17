"""Project-level semantic memory (pgvector + fastembed): long-term + short-term."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from modules.agent.embeddings import embed_text
from modules.agent.models import ProjectSemanticMemory

logger = logging.getLogger(__name__)

LONG_TERM = "long_term"
SHORT_TERM = "short_term"


@dataclass
class MemoryHit:
    content: str
    memory_type: str
    memory_tier: str
    score: float


class SemanticMemoryStore:
    """Store and recall embeddings scoped by project (and optionally story/run)."""

    def __init__(self, db: AsyncSession, project_id: uuid.UUID):
        self.db = db
        self.project_id = project_id
        self._enabled = get_settings().SEMANTIC_MEMORY_ENABLED

    async def _vector_available(self) -> bool:
        if not self._enabled:
            return False
        try:
            result = await self.db.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            return result.scalar() is not None
        except Exception:
            return False

    async def remember(
        self,
        content: str,
        memory_type: str,
        *,
        tier: str = LONG_TERM,
        story_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        if not content.strip():
            return
        if not await self._vector_available():
            return
        try:
            vector = embed_text(content)
            row = ProjectSemanticMemory(
                project_id=self.project_id,
                story_id=story_id,
                run_id=run_id if tier == SHORT_TERM else None,
                memory_tier=tier,
                memory_type=memory_type,
                content=content.strip()[:12000],
                embedding=vector,
                meta=meta,
            )
            self.db.add(row)
            await self.db.commit()
        except Exception:
            logger.exception("semantic memory store failed type=%s", memory_type)
            await self.db.rollback()

    async def remember_long_term(
        self,
        content: str,
        memory_type: str,
        *,
        story_id: uuid.UUID | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        await self.remember(
            content, memory_type, tier=LONG_TERM, story_id=story_id, meta=meta
        )

    async def remember_short_term(
        self,
        content: str,
        memory_type: str,
        *,
        story_id: uuid.UUID | None = None,
        run_id: uuid.UUID,
        meta: dict[str, Any] | None = None,
    ) -> None:
        await self.remember(
            content,
            memory_type,
            tier=SHORT_TERM,
            story_id=story_id,
            run_id=run_id,
            meta=meta,
        )

    async def recall(
        self,
        query: str,
        *,
        limit: int = 8,
        story_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        tiers: tuple[str, ...] = (LONG_TERM, SHORT_TERM),
    ) -> list[MemoryHit]:
        if not query.strip() or not await self._vector_available():
            return []
        try:
            query_vec = embed_text(query)
            vec_literal = "[" + ",".join(f"{x:.8f}" for x in query_vec) + "]"

            tier_placeholders = ", ".join(f":tier_{i}" for i in range(len(tiers)))
            tier_filter = f"AND memory_tier IN ({tier_placeholders})"
            params: dict[str, Any] = {
                "project_id": str(self.project_id),
                "vec": vec_literal,
                "limit": limit,
            }
            for i, tier in enumerate(tiers):
                params[f"tier_{i}"] = tier

            story_clause = ""
            if story_id:
                story_clause = "AND (story_id IS NULL OR story_id = :story_id)"
                params["story_id"] = str(story_id)

            run_clause = ""
            if run_id and SHORT_TERM in tiers:
                run_clause = (
                    "AND (memory_tier = 'long_term' OR run_id = :run_id OR run_id IS NULL)"
                )
                params["run_id"] = str(run_id)

            sql = text(
                f"""
                SELECT content, memory_type, memory_tier,
                       1 - (embedding <=> CAST(:vec AS vector)) AS score
                FROM project_semantic_memory
                WHERE project_id = CAST(:project_id AS uuid)
                  {tier_filter}
                  {story_clause}
                  {run_clause}
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :limit
                """
            )
            result = await self.db.execute(sql, params)
            return [
                MemoryHit(
                    content=row[0],
                    memory_type=row[1],
                    memory_tier=row[2],
                    score=float(row[3]),
                )
                for row in result.fetchall()
            ]
        except Exception:
            logger.exception("semantic memory recall failed")
            return []

    @staticmethod
    def format_hits(hits: list[MemoryHit], *, header: str = "Semantic memory") -> str:
        if not hits:
            return ""
        lines = [f"## {header}"]
        for h in hits:
            lines.append(
                f"- [{h.memory_tier}/{h.memory_type} score={h.score:.2f}] {h.content[:600]}"
            )
        return "\n".join(lines)

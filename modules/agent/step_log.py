"""Persist every agent step to agent_logs (OpenHands event → DB)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from modules.agent.events import AgentEvent
from modules.agent.service import AgentService


def event_to_log_fields(event: AgentEvent) -> tuple[str, str, str, dict[str, Any]]:
    """Map AgentEvent → (level, step, message, metadata) for AgentLog."""
    meta: dict[str, Any] = {
        "event_type": event.event_type,
        "event_id": event.id,
        "source": event.source,
        **event.metadata,
    }

    if event.event_type == "action":
        tool = str(event.metadata.get("tool", "action"))
        args = event.metadata.get("args") or {}
        path = args.get("path", "") if isinstance(args, dict) else ""
        thought = (event.metadata.get("thought") or "").strip()
        msg = thought or f"Calling {tool}"
        if path:
            msg = f"{msg} → {path}"
        return "info", f"tool:{tool}", msg[:2000], meta

    if event.event_type == "observation":
        tool = str(event.metadata.get("tool", "observation"))
        if event.metadata.get("blocked"):
            return (
                "warning",
                f"blocked:{tool}",
                event.content[:2000],
                meta,
            )
        if tool == "stuck":
            return "warning", "stuck", event.content[:2000], meta
        if tool == "error":
            return "warning", "parse_error", event.content[:2000], meta
        if tool == "finish" and "rejected" in event.content.lower():
            return "warning", "finish", event.content[:2000], meta
        if "Staged write" in event.content or "SUCCESS" in event.content:
            return "success", f"observe:{tool}", event.content[:2000], meta
        preview = event.content[:500].replace("\n", " ")
        if len(event.content) > 500:
            preview += "…"
        meta["content_length"] = len(event.content)
        return "info", f"observe:{tool}", preview, meta

    if event.event_type == "condensation":
        forgotten = event.metadata.get("forgotten_count", 0)
        preview = event.content[:300].replace("\n", " ")
        return (
            "info",
            "memory",
            f"Condensed {forgotten} events: {preview}",
            meta,
        )

    if event.event_type == "message":
        if event.source == "user" and event.content.startswith("Hint:"):
            return "info", "hint", event.content[:2000], meta
        if event.source == "user":
            return "info", "task", event.content[:500] + ("…" if len(event.content) > 500 else ""), meta
        return "info", "thinking", event.content[:2000], meta

    if event.event_type == "system":
        return "info", "system", "Agent context loaded", meta

    return "info", event.event_type, event.content[:2000], meta


async def persist_event(
    agent: AgentService,
    run_id: uuid.UUID,
    event: AgentEvent,
    *,
    step_override: str | None = None,
    message_override: str | None = None,
    level_override: str | None = None,
) -> None:
    level, step, message, metadata = event_to_log_fields(event)
    if step_override:
        step = step_override
    if message_override:
        message = message_override
    if level_override:
        level = level_override
    await agent.add_log(run_id, level, step, message, metadata)

"""OpenHands-style event log: append-only history → LLM messages."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AgentEvent:
    """Single event in the agent conversation (maps to OpenHands Event types)."""

    event_type: str  # system | message | action | observation | condensation
    source: str  # user | agent | environment
    content: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_llm_message(self) -> dict[str, str] | None:
        if self.event_type == "system":
            return {"role": "system", "content": self.content}
        if self.event_type == "message":
            role = "assistant" if self.source == "agent" else "user"
            return {"role": role, "content": self.content}
        if self.event_type == "action":
            tool = self.metadata.get("tool", "unknown")
            args = json.dumps(self.metadata.get("args", {}), indent=2)[:1500]
            thought = self.metadata.get("thought", "")
            body = f"ACTION {tool}({args})"
            if thought:
                body = f"{thought}\n\n{body}"
            return {"role": "assistant", "content": body}
        if self.event_type == "observation":
            tool = self.metadata.get("tool", "unknown")
            return {
                "role": "user",
                "content": f"OBSERVATION [{tool}]:\n{self.content[:12000]}",
            }
        if self.event_type == "condensation":
            return {
                "role": "system",
                "content": f"CONDENSED HISTORY:\n{self.content}",
            }
        return None


class EventStore:
    """In-memory event log with persistence via AgentLog."""

    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    def append(self, event: AgentEvent) -> AgentEvent:
        self.events.append(event)
        return event

    def to_messages(self) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for event in self.events:
            msg = event.to_llm_message()
            if msg:
                messages.append(msg)
        return messages

    def log_step_for_ui(self, event: AgentEvent) -> tuple[str, str, str]:
        """Map event to (level, step, message) for AgentLog."""
        if event.event_type == "action":
            tool = event.metadata.get("tool", "action")
            return "info", f"tool:{tool}", event.metadata.get("thought") or f"Calling {tool}"
        if event.event_type == "observation":
            tool = event.metadata.get("tool", "observation")
            preview = event.content[:200].replace("\n", " ")
            return "info", f"observe:{tool}", preview
        if event.event_type == "condensation":
            return "info", "memory", "Condensed conversation history"
        if event.event_type == "message" and event.source == "agent":
            return "info", "thinking", event.content[:500]
        return "info", event.event_type, event.content[:500]

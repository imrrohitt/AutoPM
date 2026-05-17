"""OpenHands-style rolling condenser: keep head + tail, summarize middle."""

from __future__ import annotations

from modules.agent.events import AgentEvent, EventStore
from modules.llm.client import chat_completion

CONDENSE_PROMPT = """Summarize this agent work log for continuity. Preserve:
- User goals and acceptance criteria
- Files read, modified, or staged
- Tool actions taken and key observations
- Decisions, errors, and what remains

Respond in plain text under 600 words. No JSON."""


async def rolling_condense(
    llm_config,
    api_key: str | None,
    store: EventStore,
    *,
    max_events: int = 24,
    keep_first: int = 4,
    keep_last: int = 8,
) -> bool:
    """
    OpenHands RollingCondenser pattern.
    Returns True if condensation was applied.
    """
    events = store.events
    if len(events) <= max_events:
        return False

    head = events[:keep_first]
    tail = events[-keep_last:]
    middle = events[keep_first:-keep_last]
    if not middle:
        return False

    transcript = "\n\n".join(
        f"[{e.event_type}/{e.source}] {e.content[:800]}"
        for e in middle
    )
    summary_messages = [
        {"role": "system", "content": CONDENSE_PROMPT},
        {"role": "user", "content": transcript},
    ]
    summary = await chat_completion(
        llm_config, api_key, summary_messages, max_tokens=2048, json_mode=False
    )

    condensation = AgentEvent(
        event_type="condensation",
        source="environment",
        content=summary.strip(),
        metadata={"forgotten_count": len(middle)},
    )
    store.events = head + [condensation] + tail
    return True


async def condense_conversation(
    llm_config,
    api_key: str | None,
    messages: list[dict[str, str]],
    *,
    keep_recent: int = 4,
    trigger_at: int = 10,
) -> tuple[list[dict[str, str]], str | None]:
    """Legacy message-list condenser (kept for compatibility)."""
    if len(messages) <= trigger_at:
        return messages, None

    system_msgs = [m for m in messages if m["role"] == "system"]
    non_system = [m for m in messages if m["role"] != "system"]
    if len(non_system) <= keep_recent + 2:
        return messages, None

    to_summarize = non_system[:-keep_recent]
    recent = non_system[-keep_recent:]

    transcript = "\n\n".join(
        f"{m['role'].upper()}: {m['content'][:2000]}" for m in to_summarize
    )
    summary_messages = [
        {"role": "system", "content": CONDENSE_PROMPT},
        {"role": "user", "content": transcript},
    ]
    summary = await chat_completion(
        llm_config, api_key, summary_messages, max_tokens=2048, json_mode=False
    )

    condensed: list[dict[str, str]] = []
    condensed.extend(system_msgs[:1])
    condensed.append(
        {
            "role": "system",
            "content": f"CONDENSED PRIOR CONTEXT:\n{summary.strip()}",
        }
    )
    condensed.extend(recent)
    return condensed, summary.strip()

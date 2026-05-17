"""OpenHands-style security validation before tool execution."""

from __future__ import annotations

from dataclasses import dataclass

from modules.agent.quality import validate_change_set, validate_file_change
from modules.stories.models import Story
from modules.tickets.models import Ticket


@dataclass
class SecurityResult:
    allowed: bool
    risk: str  # low | medium | high
    reason: str = ""


def analyze_action(
    action: str,
    args: dict,
    *,
    ticket: Ticket,
    story: Story,
    tree_paths: list[str],
    existing_by_path: dict[str, str | None],
) -> SecurityResult:
    """Evaluate proposed tool action before execution."""
    if action in ("read_file", "list_tree", "search_files", "think"):
        return SecurityResult(allowed=True, risk="low")

    if action == "finish":
        return SecurityResult(allowed=True, risk="low")

    if action == "write_file":
        path = args.get("path", "")
        content = args.get("content", "")
        if not path:
            return SecurityResult(allowed=False, risk="high", reason="write_file missing path")
        issues = validate_file_change(
            path,
            content,
            ticket,
            story,
            tree_paths,
            existing_content=existing_by_path.get(path),
        )
        if issues:
            return SecurityResult(
                allowed=False,
                risk="high",
                reason="; ".join(issues[:5]),
            )
        return SecurityResult(allowed=True, risk="low")

    return SecurityResult(allowed=False, risk="high", reason=f"Unknown action: {action}")


def validate_staged_writes(
    staged: list[dict],
    ticket: Ticket,
    story: Story,
    tree_paths: list[str],
    existing_by_path: dict[str, str | None],
) -> list[str]:
    return validate_change_set(staged, ticket, story, tree_paths, existing_by_path)

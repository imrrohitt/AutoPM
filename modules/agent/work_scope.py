"""Story-driven work scope — no hardcoded CSS/docs kinds; follows story + project intelligence."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from modules.stories.models import Story
from modules.tickets.models import Ticket

_PATH_IN_TEXT = re.compile(
    r"(?:^|[\s`'\"(])([\w][\w./-]*\.\w{1,10})(?:[\s`'\",)]|$)",
    re.MULTILINE,
)
_TOKEN = re.compile(r"[a-z0-9][a-z0-9_./-]*", re.IGNORECASE)

_PROJECT_WIDE_KEYWORDS = (
    "rename",
    "rebrand",
    "whole project",
    "entire project",
    "all files",
    "across the project",
    "project-wide",
    "refactor project",
    "every file",
)


def _is_project_wide_task(text: str) -> bool:
    lower = text.lower()
    if not any(k in lower for k in _PROJECT_WIDE_KEYWORDS):
        return False
    return (
        "rename" in lower
        or "rebrand" in lower
        or "whole" in lower
        or "entire" in lower
        or "all files" in lower
        or "every file" in lower
    )


@dataclass
class WorkScope:
    """What the agent may change, derived from story/ticket text and repo tree."""

    hint: str
    focus_paths: list[str] = field(default_factory=list)
    focus_tokens: set[str] = field(default_factory=set)
    restrict_to_story_paths: bool = False
    project_wide: bool = False

    def is_path_allowed(self, path: str, tree_paths: list[str]) -> bool:
        path_lower = path.strip().lstrip("/").lower()
        if not path_lower:
            return False

        tree_lower = {p.lower() for p in tree_paths}
        if path_lower not in tree_lower and tree_paths:
            # allow if basename matches a tree entry
            base = path_lower.split("/")[-1]
            if base not in {p.split("/")[-1] for p in tree_lower}:
                return False

        if self.project_wide:
            return True

        if self.restrict_to_story_paths and self.focus_paths:
            focus_lower = {p.lower() for p in self.focus_paths}
            if path_lower in focus_lower:
                return True
            base = path_lower.split("/")[-1]
            if base in {p.split("/")[-1] for p in focus_lower}:
                return True
            # Same extension as a story-mentioned file (e.g. story names one .css file)
            for fp in focus_lower:
                if "." in fp:
                    ext = "." + fp.rsplit(".", 1)[-1]
                    if path_lower.endswith(ext):
                        return True
            return False

        if self.focus_tokens:
            return any(t in path_lower for t in self.focus_tokens if len(t) > 2)
        return True


def task_text(ticket: Ticket, story: Story) -> str:
    return "\n".join(
        [
            story.title,
            story.description or "",
            story.acceptance_criteria or "",
            ticket.title,
            ticket.description or "",
        ]
    )


def _extract_tokens(text: str) -> set[str]:
    lower = text.lower()
    return {t for t in _TOKEN.findall(lower) if len(t) > 2}


def _resolve_mentions(raw_paths: list[str], tree_paths: list[str]) -> list[str]:
    tree_set = set(tree_paths)
    tree_by_base: dict[str, list[str]] = {}
    for p in tree_paths:
        tree_by_base.setdefault(p.split("/")[-1].lower(), []).append(p)

    resolved: list[str] = []
    seen: set[str] = set()
    for raw in raw_paths:
        p = raw.strip().lstrip("/")
        if not p:
            continue
        if p in tree_set and p not in seen:
            seen.add(p)
            resolved.append(p)
            continue
        base = p.split("/")[-1].lower()
        candidates = tree_by_base.get(base, [])
        if not candidates:
            continue
        candidates.sort(key=lambda x: (x.count("/"), len(x)))
        best = candidates[0]
        if base == "readme.md":
            root = next((c for c in candidates if c.lower() == "readme.md"), None)
            if root:
                best = root
        if best not in seen:
            seen.add(best)
            resolved.append(best)
    return resolved


def _paths_mentioned_in_text(text: str, tree_paths: list[str]) -> list[str]:
    mentions: list[str] = []
    for match in _PATH_IN_TEXT.finditer(text):
        mentions.append(match.group(1))
    # Also pick basename tokens that exist in tree (e.g. "index.css" without extension in prose)
    tokens = _extract_tokens(text)
    tree_by_base = {p.split("/")[-1].lower(): p for p in tree_paths}
    for t in tokens:
        if t in tree_by_base and tree_by_base[t] not in mentions:
            mentions.append(tree_by_base[t])
    return _resolve_mentions(mentions, tree_paths)


def build_work_scope(
    story: Story,
    ticket: Ticket,
    tree_paths: list[str],
    *,
    project_intelligence: str = "",
) -> WorkScope:
    """
    Build scope from story/ticket wording and project intelligence (OpenHands-style).
    No fixed CSS/docs categories — the story defines the work.
    """
    full_text = task_text(ticket, story)
    focus_paths = _paths_mentioned_in_text(full_text, tree_paths)
    focus_tokens = _extract_tokens(full_text)

    lines = [
        "SCOPE — follow the story and acceptance criteria (not generic file-type rules):",
        f"Story: {story.title}",
    ]
    if story.description:
        lines.append(f"Description: {story.description.strip()}")
    if story.acceptance_criteria:
        lines.append(f"Acceptance criteria: {story.acceptance_criteria.strip()}")
    lines.append(f"Ticket: {ticket.title}")
    if ticket.description:
        lines.append(f"Ticket detail: {ticket.description.strip()}")

    if focus_paths:
        lines.append(
            "Paths explicitly referenced in the story/ticket (prefer these): "
            + ", ".join(focus_paths[:20])
        )
    elif focus_tokens:
        lines.append(
            "Keywords from the story (prefer paths containing these): "
            + ", ".join(sorted(focus_tokens)[:25])
        )

    if project_intelligence:
        lines.append(
            "Use PROJECT INTELLIGENCE for repository layout, entrypoints, and conventions."
        )

    project_wide = _is_project_wide_task(full_text)
    if project_wide:
        lines.append(
            "PROJECT-WIDE TASK: you may edit any repo file needed (list_tree first). "
            "Use read_file → write_file per file — there is no bulk-rename tool."
        )
    else:
        lines.append(
            "Only change files required to satisfy the story. "
            "Never paste ticket/story text as file content."
        )

    restrict = len(focus_paths) > 0 and not project_wide
    return WorkScope(
        hint="\n".join(lines),
        focus_paths=focus_paths,
        focus_tokens=focus_tokens,
        restrict_to_story_paths=restrict,
        project_wide=project_wide,
    )

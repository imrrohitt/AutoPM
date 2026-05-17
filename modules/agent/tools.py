"""OpenHands-style tools (action → observation) via GitHub API."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from modules.agent.context import fetch_files, score_paths_by_keywords
from modules.agent.quality import resolve_paths
from modules.github.git_client import GitHubClient
from modules.stories.models import Story
from modules.tickets.models import Ticket

from modules.agent.prompts import SMALL_MODEL_TOOL_PROMPT

TOOL_INSTRUCTIONS = SMALL_MODEL_TOOL_PROMPT + """

You work in a reasoning-action loop. Each step respond with ONLY valid JSON:

{
  "thought": "brief reasoning for this step",
  "action": "<tool_name>",
  "args": { }
}

Available tools:
- read_file: {"path": "repo/path"} — read file content from branch
- list_tree: {"prefix": ""} — list file paths (optional prefix filter)
- search_files: {"query": "keywords"} — find relevant paths in repo tree
- write_file: {"path": "...", "content": "FULL file body", "commit_message": "..."} — stage a file change (validated before commit)
- think: {"note": "..."} — record reasoning only, no side effect
- finish: {"summary": "...", "verification": "how acceptance criteria are met"} — done with ticket

Rules:
- Always read_file before write_file on existing paths
- Use exact paths from list_tree/search_files
- write_file content must be complete final file, not a description of changes
- Call finish when done; do not stop after only planning"""


@dataclass
class ToolState:
    git: GitHubClient
    owner: str
    repo: str
    branch: str
    base_branch: str
    tree_paths: list[str]
    story: Story
    ticket: Ticket
    staged_writes: list[dict] = field(default_factory=list)
    files_read: set[str] = field(default_factory=set)


async def execute_tool(state: ToolState, action: str, args: dict) -> str:
    if action == "think":
        return args.get("note", "Noted.")

    if action == "list_tree":
        prefix = (args.get("prefix") or "").strip()
        paths = state.tree_paths
        if prefix:
            paths = [p for p in paths if p.startswith(prefix)]
        return "\n".join(paths[:200]) or "(empty)"

    if action == "search_files":
        query = args.get("query") or state.ticket.title
        scored = score_paths_by_keywords(state.tree_paths, state.ticket, state.story, limit=30)
        tokens = [t for t in query.lower().split() if len(t) > 2]
        extra = [p for p in state.tree_paths if any(t in p.lower() for t in tokens)]
        combined = list(dict.fromkeys(scored + extra))[:25]
        return json.dumps({"paths": combined})

    if action == "read_file":
        path = args.get("path", "")
        if not path:
            return "Error: path required"
        resolved = resolve_paths([path], state.tree_paths)
        path = resolved[0] if resolved else path
        files = await fetch_files(
            state.git,
            state.owner,
            state.repo,
            state.branch,
            [path],
            fallback_ref=state.base_branch,
        )
        if not files:
            return f"Error: could not read {path}"
        state.files_read.add(path)
        return files[0].content[:14000]

    if action == "write_file":
        path = args.get("path", "")
        content = args.get("content", "")
        commit_message = args.get("commit_message", f"autopm: {state.ticket.title}")
        if not path or content is None:
            return "Error: path and content required"
        resolved = resolve_paths([path], state.tree_paths)
        path = resolved[0] if resolved else path
        state.staged_writes.append(
            {"path": path, "content": content, "commit_message": commit_message}
        )
        return (
            f"Staged write to {path} ({len(content)} chars). "
            "SUCCESS — your NEXT action MUST be finish with summary and verification. "
            "If quality passed, the run may auto-complete."
        )

    if action == "finish":
        summary = args.get("summary", "Done")
        verification = args.get("verification", "")
        return json.dumps(
            {
                "status": "finished",
                "summary": summary,
                "verification": verification,
                "staged_files": [w["path"] for w in state.staged_writes],
            }
        )

    return f"Error: unknown action '{action}'. Use read_file, list_tree, search_files, write_file, think, or finish."

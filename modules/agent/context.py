"""Codebase context retrieval inspired by OpenHands (relevant files, not random samples)."""

import re
import uuid
from dataclasses import dataclass

from modules.agent.parsing import extract_json
from modules.agent.quality import resolve_paths
from modules.github.git_client import GitHubClient
from modules.llm.client import chat_completion
from modules.stories.models import Story
from modules.tickets.models import Ticket

CODE_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json", ".yaml", ".yml", ".toml", ".rs", ".go")
AGENT_DOC_PATHS = ("AGENTS.md", "agents.md", "CONTRIBUTING.md", "README.md", ".cursorrules")

EXPLORE_PROMPT = """You are an expert software engineer exploring a repository before making changes.
Respond with ONLY compact valid JSON. No markdown. Keep every string under 120 characters.

Schema:
{
  "reasoning": "one sentence",
  "relevant_paths": ["up to 8 paths from the tree"],
  "approach": "short numbered steps in one string",
  "dependencies": ["max 3 paths"],
  "risks": ["max 2 short items"]
}

Rules:
- Pick paths that exist in the provided file tree only
- Prefer files directly related to the ticket
- Be brief — truncated JSON breaks the pipeline"""


@dataclass
class FileContext:
    path: str
    content: str


def score_paths_by_keywords(
    tree_paths: list[str],
    ticket: Ticket,
    story: Story,
    *,
    limit: int = 40,
) -> list[str]:
    """Heuristic ranking before LLM selection."""
    text = " ".join(
        [
            ticket.title,
            ticket.description or "",
            story.title,
            story.description or "",
            story.acceptance_criteria or "",
        ]
    ).lower()
    tokens = {t for t in re.split(r"[^a-z0-9]+", text) if len(t) > 2}

    scored: list[tuple[int, str]] = []
    for path in tree_paths:
        path_lower = path.lower()
        score = sum(2 if t in path_lower else 0 for t in tokens)
        if path_lower.endswith(CODE_EXTENSIONS):
            score += 1
        if any(doc.lower() in path_lower for doc in ("readme", "agent", "contribut")):
            score += 3
        if score > 0:
            scored.append((score, path))

    scored.sort(key=lambda x: (-x[0], x[1]))
    top = [p for _, p in scored[:limit]]
    if not top:
        top = [p for p in tree_paths if p.lower().endswith(CODE_EXTENSIONS)][:limit]
    return top


async def fetch_agent_docs(
    git: GitHubClient,
    owner: str,
    repo: str,
    branch: str,
    *,
    fallback_ref: str | None = None,
) -> list[FileContext]:
    """Load project docs; try feature branch first, then base branch (new branches may be empty)."""
    docs: list[FileContext] = []
    refs = [branch]
    if fallback_ref and fallback_ref != branch:
        refs.append(fallback_ref)
    for name in AGENT_DOC_PATHS:
        content = None
        for ref in refs:
            content = await git.get_file_content(owner, repo, name, ref)
            if content:
                break
        if content:
            docs.append(FileContext(path=name, content=content[:6000]))
    return docs


async def fetch_files(
    git: GitHubClient,
    owner: str,
    repo: str,
    branch: str,
    paths: list[str],
    *,
    fallback_ref: str | None = None,
    max_per_file: int = 12_000,
    max_files: int = 12,
) -> list[FileContext]:
    files: list[FileContext] = []
    seen: set[str] = set()
    refs = [branch]
    if fallback_ref and fallback_ref != branch:
        refs.append(fallback_ref)
    for path in paths:
        if path in seen or len(files) >= max_files:
            continue
        seen.add(path)
        content = None
        for ref in refs:
            content = await git.get_file_content(owner, repo, path, ref)
            if content:
                break
        if content:
            files.append(FileContext(path=path, content=content[:max_per_file]))
    return files


async def explore_ticket_context(
    llm_config,
    api_key: str | None,
    *,
    project_name: str,
    project_goals: str | None,
    tech_stack: str | None,
    story: Story,
    ticket: Ticket,
    tree_paths: list[str],
    prior_work: str,
    codebase_summary: str,
) -> dict:
    """LLM selects relevant files and plans approach (OpenHands-style exploration step)."""
    candidates = score_paths_by_keywords(tree_paths, ticket, story, limit=60)
    tree_sample = "\n".join(tree_paths[:150])
    candidate_list = "\n".join(f"- {p}" for p in candidates[:50])

    user_prompt = f"""PROJECT: {project_name}
GOALS: {project_goals or 'N/A'}
TECH STACK: {tech_stack or 'N/A'}

STORY: {story.title}
DESCRIPTION: {story.description or ''}
ACCEPTANCE: {story.acceptance_criteria or 'N/A'}

TICKET: {ticket.title} ({ticket.type}, {ticket.priority})
{ticket.description}

PRIOR WORK ON THIS STORY:
{prior_work or 'None'}

CODEBASE INDEX:
{codebase_summary[:3000]}

CANDIDATE PATHS (ranked by relevance):
{candidate_list}

FULL TREE (truncated):
{tree_sample}

Select files to read and outline your implementation approach."""

    messages = [
        {"role": "system", "content": EXPLORE_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    raw = await chat_completion(llm_config, api_key, messages, max_tokens=2048, json_mode=True)
    try:
        parsed = extract_json(raw)
    except ValueError:
        raw = await chat_completion(
            llm_config,
            api_key,
            messages
            + [
                {
                    "role": "user",
                    "content": (
                        "Reply again with ONLY minimal JSON. "
                        'Example: {"reasoning":"...","relevant_paths":["README.md"],'
                        '"approach":"1. edit file","dependencies":[],"risks":[]}'
                    ),
                }
            ],
            max_tokens=1024,
            json_mode=True,
        )
        try:
            parsed = extract_json(raw)
        except ValueError:
            fallback_paths = candidates[:8] or score_paths_by_keywords(
                tree_paths, ticket, story, limit=8
            )
            parsed = {
                "reasoning": "Fallback: using keyword-matched paths (LLM response was truncated)",
                "relevant_paths": fallback_paths,
                "approach": "1. Read relevant files 2. Apply ticket changes",
                "dependencies": [],
                "risks": [],
            }
    parsed["relevant_paths"] = resolve_paths(parsed.get("relevant_paths") or [], tree_paths)
    if "readme" in (ticket.description or "").lower() or "readme" in ticket.title.lower():
        for candidate in ("README.md", "readme.md", "Readme.md"):
            if candidate in tree_paths and candidate not in parsed["relevant_paths"]:
                parsed["relevant_paths"].insert(0, candidate)
                break
    return parsed


def format_files_for_prompt(files: list[FileContext]) -> str:
    if not files:
        return "No file contents loaded."
    parts = []
    for f in files:
        parts.append(f"### {f.path}\n```\n{f.content}\n```")
    return "\n\n".join(parts)

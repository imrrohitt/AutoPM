"""OpenHands-style project intelligence: structured repo understanding for every run."""

from __future__ import annotations

import re
from collections import Counter

from modules.projects.models import Project

_CODE_EXT = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".css",
    ".scss",
    ".html",
    ".vue",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
}
_FRAMEWORK_HINTS = {
    "next": ("next.config", "app/", "pages/"),
    "react": ("vite.config", "src/App", ".jsx", ".tsx"),
    "fastapi": ("fastapi", "uvicorn", "main.py"),
    "django": ("manage.py", "settings.py"),
    "celery": ("celery", "tasks.py"),
}


def build_project_intelligence(
    project: Project,
    tree_paths: list[str],
    *,
    agent_instructions: str = "",
    max_paths: int = 80,
) -> str:
    """
    Build a compact repo intelligence brief (OpenHands microagent / repo skill).
    Always injected into agent context before planning and implementation.
    """
    if not tree_paths:
        return f"Project {project.name}: empty or unreadable repository tree."

    ext_counts: Counter[str] = Counter()
    top_dirs: Counter[str] = Counter()
    entrypoints: list[str] = []
    config_files: list[str] = []
    style_paths: list[str] = []
    doc_paths: list[str] = []

    for path in tree_paths:
        parts = path.split("/")
        if len(parts) > 1:
            top_dirs[parts[0]] += 1
        lower = path.lower()
        ext = ""
        if "." in path.split("/")[-1]:
            ext = "." + path.split("/")[-1].rsplit(".", 1)[-1]
            if ext in _CODE_EXT:
                ext_counts[ext] += 1

        base = path.split("/")[-1].lower()
        if base in (
            "package.json",
            "pyproject.toml",
            "requirements.txt",
            "dockerfile",
            "makefile",
            "cargo.toml",
            "go.mod",
        ):
            config_files.append(path)
        if lower.endswith((".css", ".scss", ".sass", ".less")):
            style_paths.append(path)
        if lower.endswith(".md") or "readme" in lower:
            doc_paths.append(path)
        if re.match(r"^(main|index|app)\.(py|ts|tsx|js|jsx)$", base):
            entrypoints.append(path)

    frameworks: list[str] = []
    tree_blob = "\n".join(tree_paths[:300]).lower()
    for name, hints in _FRAMEWORK_HINTS.items():
        if any(h.lower() in tree_blob for h in hints):
            frameworks.append(name)

    lines = [
        f"# Project intelligence: {project.name}",
        "",
        "## Goals",
        (project.goals or "Not specified").strip()[:1500],
        "",
        "## Tech stack (declared)",
        (project.tech_stack or "Not specified").strip()[:800],
        "",
        "## Repository shape",
        f"- Files indexed: {len(tree_paths)}",
        f"- Top-level dirs: {', '.join(d for d, _ in top_dirs.most_common(12)) or 'flat root'}",
        f"- Languages/extensions: {', '.join(f'{e}({c})' for e, c in ext_counts.most_common(8)) or 'unknown'}",
    ]
    if frameworks:
        lines.append(f"- Detected stacks: {', '.join(frameworks)}")
    if entrypoints:
        lines.append(f"- Likely entrypoints: {', '.join(entrypoints[:6])}")
    if config_files:
        lines.append(f"- Config: {', '.join(config_files[:8])}")
    if style_paths:
        lines.append(f"- Stylesheets: {', '.join(style_paths[:10])}")
    if doc_paths:
        lines.append(f"- Docs: {', '.join(doc_paths[:8])}")

    lines.extend(
        [
            "",
            "## Key paths (sample)",
            "\n".join(f"- {p}" for p in tree_paths[:max_paths]),
        ]
    )
    if len(tree_paths) > max_paths:
        lines.append(f"- … and {len(tree_paths) - max_paths} more")

    if agent_instructions:
        lines.extend(
            [
                "",
                "## Repository instructions (AGENTS.md / README)",
                agent_instructions[:3500],
            ]
        )

    lines.extend(
        [
            "",
            "## Agent discipline (OpenHands)",
            "- Explore → read → implement → verify before finish",
            "- Never echo ticket text as file content",
            "- Use exact paths from the tree above",
        ]
    )
    return "\n".join(lines)

"""OpenHands-style task scoping: infer work type and restrict which files may change."""

from __future__ import annotations

import re

from modules.stories.models import Story
from modules.tickets.models import Ticket

TaskKind = str  # css | docs | code | general

STYLE_EXTENSIONS = (".css", ".scss", ".sass", ".less", ".module.css")
STYLE_PATH_HINTS = (
    "style",
    "styles",
    "stylesheet",
    "globals",
    "homepage",
    "home",
    "theme",
    "tailwind",
    "app.css",
    "index.css",
    "layout.css",
)
CODE_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt")
DOC_EXTENSIONS = (".md", ".mdx", ".rst", ".txt")


def task_text(ticket: Ticket, story: Story) -> str:
    return " ".join(
        [
            ticket.title,
            ticket.description or "",
            story.title,
            story.description or "",
            story.acceptance_criteria or "",
        ]
    ).lower()


def infer_task_kind(ticket: Ticket, story: Story) -> TaskKind:
    text = task_text(ticket, story)

    css_signals = (
        "css",
        "stylesheet",
        "styling",
        "style change",
        "homepage",
        "landing page",
        "layout",
        "color",
        "colour",
        "theme",
        "tailwind",
        "visual",
        "ui polish",
        "font",
        "spacing",
        "margin",
        "padding",
        "background",
    )
    doc_signals = (
        "readme",
        "documentation",
        "docs ",
        "changelog",
        "contributing",
        "agents.md",
    )

    has_css = any(s in text for s in css_signals)
    has_docs = any(s in text for s in doc_signals)

    if has_css and not (has_docs and "css" not in text and "style" not in text):
        return "css"
    if has_docs:
        return "docs"
    return "code"


def is_path_in_scope(path: str, kind: TaskKind, tree_paths: list[str]) -> bool:
    """Whether this path may be written for the inferred task kind."""
    path_lower = path.lower().strip().lstrip("/")
    if not path_lower:
        return False

    if kind == "css":
        if path_lower.endswith(STYLE_EXTENSIONS):
            return True
        if any(hint in path_lower for hint in STYLE_PATH_HINTS):
            return True
        # Homepage markup that carries styles (rare)
        if path_lower.endswith((".html", ".htm")) and any(
            x in path_lower for x in ("index", "home", "landing", "page")
        ):
            return True
        return False

    if kind == "docs":
        if path_lower.endswith(DOC_EXTENSIONS):
            return True
        if path_lower.endswith("agents.md") or path_lower.endswith("contributing.md"):
            return True
        return False

    # code / general — allow typical source files present in tree
    if path_lower in {p.lower() for p in tree_paths}:
        return True
    if path_lower.endswith(CODE_EXTENSIONS + STYLE_EXTENSIONS + DOC_EXTENSIONS):
        return True
    return bool(tree_paths)


def scope_hint_for_kind(kind: TaskKind) -> str:
    if kind == "css":
        return (
            "SCOPE (CSS/styling task): ONLY edit stylesheet files (.css, .scss, etc.) "
            "or style modules whose paths contain style/globals/theme/homepage. "
            "Do NOT modify .js, .ts, .tsx, .jsx, or .md files. "
            "Read the homepage/component CSS first, then change colors/layout/spacing in place."
        )
    if kind == "docs":
        return (
            "SCOPE (documentation task): ONLY edit markdown/doc files (.md, .mdx, etc.). "
            "Do NOT modify source code files unless the ticket explicitly requires it."
        )
    return (
        "SCOPE: Change only files directly required for this ticket. "
        "Do not edit unrelated modules."
    )


def looks_like_markdown_in_code_file(path: str, content: str) -> bool:
    """Detect README/markdown pasted into a code file (common small-model failure)."""
    if not any(path.lower().endswith(ext) for ext in CODE_EXTENSIONS):
        return False

    stripped = content.strip()
    if not stripped:
        return False

    score = 0
    if re.match(r"^#\s+\S", stripped):
        score += 2
    if re.search(r"^##\s+\S", content, re.MULTILINE):
        score += 2
    if re.search(r"^###\s+\S", content, re.MULTILINE):
        score += 1
    if "|" in content and re.search(r"^\|.+\|", content, re.MULTILINE):
        score += 1
    if re.search(r"^-\s+\*\*", content, re.MULTILINE):
        score += 1
    doc_section_headers = (
        "overview",
        "requirements",
        "features",
        "setup",
        "usage",
        "getting started",
        "installation",
    )
    lower = content.lower()
    if sum(1 for h in doc_section_headers if h in lower) >= 2:
        score += 2
    if "production-oriented" in lower and "browser-only" in lower:
        score += 3

    return score >= 3


def looks_like_code_in_doc_file(path: str, content: str) -> bool:
    if not path.lower().endswith(DOC_EXTENSIONS):
        return False
    stripped = content.strip()
    if re.match(r"^(import|export|const|function|class)\s", stripped):
        return True
    if stripped.startswith(("def ", "async def ", "package ")):
        return True
    return False

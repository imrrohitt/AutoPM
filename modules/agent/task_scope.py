"""Content-shape validators (markdown-in-code, etc.). Scope lives in work_scope.py."""

from __future__ import annotations

import re

CODE_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt")
DOC_EXTENSIONS = (".md", ".mdx", ".rst", ".txt")


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

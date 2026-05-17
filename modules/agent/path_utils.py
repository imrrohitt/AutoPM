"""Normalize LLM file paths to repo-relative paths (fixes absolute/local paths)."""

from __future__ import annotations

import re

_WINDOWS_ABS = re.compile(r"^[A-Za-z]:[\\/]")


def normalize_repo_path(raw: str, tree_paths: list[str]) -> str:
    """
    Convert absolute or messy paths to a repo-relative path from tree_paths.
    e.g. /Users/.../BrowserLLM/src/README.md → src/README.md
    """
    if not raw or not str(raw).strip():
        return ""

    path = str(raw).strip().replace("\\", "/")
    # Strip quotes/backticks the model sometimes adds
    path = path.strip("`'\"")

    tree_set = set(tree_paths)
    if path in tree_set:
        return path

    rel = path.lstrip("/")
    if rel in tree_set:
        return rel

    # Absolute Unix or Windows path — find longest suffix that exists in the tree
    is_abs = path.startswith("/") or bool(_WINDOWS_ABS.match(path))
    if is_abs or path.count("/") > 4:
        segments = [s for s in path.split("/") if s]
        for start in range(len(segments)):
            candidate = "/".join(segments[start:])
            if candidate in tree_set:
                return candidate
        # Match by suffix (e.g. .../src/README.md when tree has src/README.md)
        for t in sorted(tree_paths, key=lambda x: (-len(x), x)):
            if path.endswith(t) or path.endswith("/" + t):
                return t

    # Bare filename only
    base = rel.split("/")[-1]
    if base and base in {p.split("/")[-1] for p in tree_paths}:
        candidates = [p for p in tree_paths if p == base or p.endswith(f"/{base}")]
        if candidates:
            candidates.sort(key=lambda p: (p.count("/"), len(p)))
            return candidates[0]

    return rel

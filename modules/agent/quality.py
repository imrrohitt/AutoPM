"""Quality gates for agent file changes (reject placeholders and bad paths)."""

import re
from difflib import SequenceMatcher

from modules.stories.models import Story
from modules.tickets.models import Ticket

MIN_README_LINES = 12
MIN_README_CHARS = 400
MIN_CODE_CHARS = 80
MIN_GENERIC_DOC_CHARS = 200


def resolve_paths(requested: list[str], tree_paths: list[str]) -> list[str]:
    """Map LLM paths to real repo paths (e.g. README.md not src/README.md)."""
    tree_set = set(tree_paths)
    resolved: list[str] = []
    seen: set[str] = set()

    for raw in requested:
        path = raw.strip().lstrip("/")
        if not path:
            continue
        if path in tree_set and path not in seen:
            seen.add(path)
            resolved.append(path)
            continue

        basename = path.split("/")[-1]
        candidates = [t for t in tree_paths if t == basename or t.endswith(f"/{basename}")]
        if not candidates:
            if path not in seen:
                seen.add(path)
                resolved.append(path)
            continue

        # Prefer repo root (e.g. README.md over src/README.md)
        candidates.sort(key=lambda p: (p.count("/"), len(p), p))
        best = candidates[0]
        if basename.lower() == "readme.md":
            root_readme = next((c for c in candidates if c.lower() == "readme.md"), None)
            if root_readme:
                best = root_readme
        if best not in seen:
            seen.add(best)
            resolved.append(best)

    return resolved


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def is_echo_content(content: str, ticket: Ticket, story: Story) -> bool:
    """Detect when the model echoed the task instead of implementing."""
    stripped = content.strip()
    if not stripped:
        return True

    check_strings = [
        ticket.title,
        ticket.description or "",
        story.title,
        story.description or "",
        story.acceptance_criteria or "",
    ]
    normalized_content = _normalize(stripped)

    for text in check_strings:
        if len(text) < 12:
            continue
        norm = _normalize(text)
        if norm in normalized_content and len(stripped) < len(text) * 2:
            return True
        if _similarity(stripped, text) > 0.72:
            return True

    placeholder_patterns = [
        r"^update the .+ file",
        r"^make it (nice|better|more)",
        r"^implement:",
        r"^fix the .+ file",
    ]
    first_line = stripped.split("\n")[0].strip().lower()
    for pattern in placeholder_patterns:
        if re.match(pattern, first_line) and len(stripped) < 300:
            return True

    non_empty_lines = [ln for ln in stripped.splitlines() if ln.strip()]
    if len(non_empty_lines) <= 1 and len(stripped) < 250:
        return True

    return False


def validate_markdown_quality(path: str, content: str) -> list[str]:
    issues: list[str] = []
    lines = [ln for ln in content.splitlines() if ln.strip()]

    if len(lines) < MIN_README_LINES:
        issues.append(f"{path}: README/docs need at least {MIN_README_LINES} non-empty lines")
    if len(content.strip()) < MIN_README_CHARS:
        issues.append(f"{path}: content too short ({len(content)} chars, need {MIN_README_CHARS}+)")
    if not re.search(r"^#\s+\S", content, re.MULTILINE):
        issues.append(f"{path}: markdown must include a top-level `# Title` heading")
    if not re.search(r"^##\s+\S", content, re.MULTILINE):
        issues.append(f"{path}: include at least one `##` section (Overview, Setup, Usage, etc.)")

    return issues


def validate_file_change(
    path: str,
    content: str,
    ticket: Ticket,
    story: Story,
    tree_paths: list[str],
    *,
    existing_content: str | None = None,
) -> list[str]:
    """Return human-readable quality issues; empty list means OK."""
    issues: list[str] = []
    tree_set = set(tree_paths)

    if is_echo_content(content, ticket, story):
        issues.append(
            f"{path}: content looks like a copy of the task description, not real implementation"
        )

    basename = path.split("/")[-1].lower()
    if basename in tree_set and path != basename:
        issues.append(f"{path}: use existing repo path `{basename}` instead of nested wrong path")

    if path.endswith(".md"):
        issues.extend(validate_markdown_quality(path, content))
    elif any(path.endswith(ext) for ext in (".py", ".ts", ".tsx", ".js", ".jsx")):
        if len(content.strip()) < MIN_CODE_CHARS:
            issues.append(f"{path}: code file too short to be a real implementation")
    elif len(content.strip()) < MIN_GENERIC_DOC_CHARS:
        issues.append(f"{path}: file content too short")

    if existing_content and _normalize(existing_content) == _normalize(content):
        issues.append(f"{path}: no meaningful change from existing file")

    return issues


def validate_patch(
    filename: str,
    patch: str | None,
    ticket: Ticket,
    story: Story,
) -> list[str]:
    """Validate PR patch content before merge."""
    if not patch:
        return []
    added_lines = [
        line[1:]
        for line in patch.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    if not added_lines:
        return [f"{filename}: no added content in patch"]
    content = "\n".join(added_lines)
    return validate_file_change(filename, content, ticket, story, tree_paths=[])


def validate_change_set(
    files: list[dict],
    ticket: Ticket,
    story: Story,
    tree_paths: list[str],
    existing_by_path: dict[str, str | None],
) -> list[str]:
    all_issues: list[str] = []
    if not files:
        all_issues.append("No files produced — agent must change or create at least one file")
        return all_issues

    for fc in files:
        path = fc.get("path", "")
        content = fc.get("content", "")
        if not path:
            all_issues.append("File entry missing path")
            continue
        all_issues.extend(
            validate_file_change(
                path,
                content,
                ticket,
                story,
                tree_paths,
                existing_content=existing_by_path.get(path),
            )
        )
    return all_issues

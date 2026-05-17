"""Load agent knowledge skills from modules/agent/skills/*.md."""

from __future__ import annotations

import re
from pathlib import Path

from dataclasses import dataclass

_SKILLS_DIR = Path(__file__).parent / "skills"


@dataclass
class LoadedSkill:
    name: str
    triggers: list[str]
    content: str
    always: bool = False


def _parse_skill_file(path: Path) -> tuple[str, list[str], bool, str]:
    text = path.read_text(encoding="utf-8")
    name = path.stem
    triggers: list[str] = []
    always = path.name.startswith("_always_") or path.name.startswith("always_")

    body_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("# Skill:"):
            name = line.split(":", 1)[1].strip().lower().replace(" ", "_")
        elif line.startswith("triggers:"):
            triggers = [t.strip() for t in line.split(":", 1)[1].split(",") if t.strip()]
        elif line.startswith("always:"):
            always = line.split(":", 1)[1].strip().lower() in ("true", "yes", "1")
        elif line.strip() == "---":
            continue
        else:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()
    if not body:
        body = text.strip()
    return name, triggers, always, body


def load_skills_from_md() -> tuple[list[LoadedSkill], str]:
    """
    Returns (triggered knowledge skills, always-on markdown block for system prompt).
    """
    if not _SKILLS_DIR.is_dir():
        return [], ""

    triggered: list[LoadedSkill] = []
    always_blocks: list[str] = []

    for path in sorted(_SKILLS_DIR.glob("*.md")):
        name, triggers, always, body = _parse_skill_file(path)
        if always:
            always_blocks.append(f"### {name}\n{body}")
        elif triggers:
            triggered.append(
                LoadedSkill(name=name, triggers=triggers, content=body, always=False)
            )

    always_text = ""
    if always_blocks:
        always_text = "## Agent skills (always active)\n\n" + "\n\n".join(always_blocks)

    return triggered, always_text

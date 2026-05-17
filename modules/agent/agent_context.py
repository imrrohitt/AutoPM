"""OpenHands AgentContext: repo skills + knowledge skills → system prompt."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from modules.projects.models import Project
from modules.stories.models import Story
from modules.tickets.models import Ticket

_AUTOPM_AGENTS = (Path(__file__).parent / "AGENTS.md").read_text(encoding="utf-8")


@dataclass
class RepoSkill:
    """Always-on project context (OpenHands repo skill)."""

    name: str
    content: str


@dataclass
class KnowledgeSkill:
    """Trigger-activated domain knowledge (OpenHands knowledge skill)."""

    name: str
    triggers: list[str]
    content: str


@dataclass
class AgentContext:
    """Container for skills and prompts applied to every LLM query."""

    repo_skills: list[RepoSkill] = field(default_factory=list)
    knowledge_skills: list[KnowledgeSkill] = field(default_factory=list)
    system_suffix: str = ""

    def build_system_prompt(self, tool_instructions: str) -> str:
        parts = [_AUTOPM_AGENTS, "", "---", "", tool_instructions, ""]
        if self.repo_skills:
            parts.append("## Repository context (always active)")
            for skill in self.repo_skills:
                parts.append(f"### {skill.name}\n{skill.content}")
        if self.system_suffix:
            parts.append(self.system_suffix)
        return "\n".join(parts)

    def active_knowledge(self, text: str) -> str:
        """Return knowledge blocks whose triggers match the user text."""
        lower = text.lower()
        blocks: list[str] = []
        for skill in self.knowledge_skills:
            if any(t.lower() in lower for t in skill.triggers):
                blocks.append(f"### {skill.name}\n{skill.content}")
        if not blocks:
            return ""
        return "## Activated knowledge\n" + "\n\n".join(blocks)


def build_story_context(
    project: Project,
    story: Story,
    ticket: Ticket,
    *,
    agent_instructions: str = "",
    execution_plan: str = "",
    prior_learnings: str = "",
    codebase_summary: str = "",
    project_intelligence: str = "",
    exploration_block: str = "",
    task_kind: str = "code",
) -> AgentContext:
    repo_content = f"""PROJECT: {project.name}
GOALS: {project.goals or 'N/A'}
TECH STACK: {project.tech_stack or 'N/A'}

STORY: {story.title}
DESCRIPTION: {story.description or ''}
ACCEPTANCE CRITERIA: {story.acceptance_criteria or 'N/A'}

TICKET: {ticket.title} ({ticket.type}, {ticket.priority})
{ticket.description}
"""
    if execution_plan:
        repo_content += f"\nEXECUTION PLAN:\n{execution_plan[:4000]}\n"
    if prior_learnings:
        repo_content += f"\nPRIOR RUNS:\n{prior_learnings[:3000]}\n"
    if codebase_summary:
        repo_content += f"\nCODEBASE INDEX:\n{codebase_summary[:4000]}\n"
    if project_intelligence:
        repo_content += f"\nPROJECT INTELLIGENCE:\n{project_intelligence[:5000]}\n"
    elif agent_instructions:
        repo_content += f"\nREPO DOCS:\n{agent_instructions[:4000]}\n"
    if exploration_block:
        repo_content += f"\nEXPLORATION (read these before editing):\n{exploration_block[:12000]}\n"

    ctx = AgentContext(
        repo_skills=[RepoSkill(name="story_and_project", content=repo_content)],
        knowledge_skills=[
            KnowledgeSkill(
                name="css_and_styling_tasks",
                triggers=[
                    "css",
                    "stylesheet",
                    "styling",
                    "homepage",
                    "layout",
                    "color",
                    "theme",
                    "tailwind",
                    "visual",
                    "style",
                ],
                content=(
                    "CSS/styling task: ONLY edit .css/.scss files (or paths with style/globals/homepage). "
                    "Never write README markdown into .js/.ts files. "
                    "Read the existing stylesheet, then change selectors/properties in place. "
                    "Do not replace unrelated source files."
                ),
            ),
            KnowledgeSkill(
                name="documentation_tasks",
                triggers=["readme", "documentation", "docs", ".md"],
                content=(
                    "For documentation: read the existing file first, preserve accurate "
                    "technical facts, add # title and ## sections, minimum 15 lines of "
                    "real content. Never paste the ticket text as the file body."
                ),
            ),
            KnowledgeSkill(
                name="quality_gate",
                triggers=["implement", "fix", "update", "create"],
                content=(
                    "Before finish: verify acceptance criteria, ensure file paths exist "
                    "in the tree, match the task type (CSS→stylesheets only), "
                    "and write complete file bodies — never markdown inside code files."
                ),
            ),
            KnowledgeSkill(
                name="openhands_loop",
                triggers=["think", "read", "write", "search", "finish"],
                content=(
                    "OpenHands loop: each step emit thought → action → read observation. "
                    "Use think to plan; do not repeat list_tree/search after files are loaded. "
                    "After write_file succeeds, call finish with verification vs acceptance criteria."
                ),
            ),
        ],
    )
    if task_kind == "css":
        ctx.system_suffix = (
            "TASK TYPE: CSS/styling. Allowed writes: stylesheets only. "
            "Forbidden: .js, .ts, .tsx, .jsx, .md unless ticket explicitly says otherwise."
        )
    elif task_kind == "docs":
        ctx.system_suffix = "TASK TYPE: documentation. Allowed writes: .md and doc files only."
    return ctx

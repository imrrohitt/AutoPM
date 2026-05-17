"""Story-level execution planning (OpenHands-style task decomposition)."""

import json

from modules.agent.parsing import extract_json
from modules.llm.client import chat_completion
from modules.stories.models import Story
from modules.tickets.models import Ticket

PLAN_PROMPT = """You are a tech lead planning how an AI coding agent should complete a story.
Respond with ONLY valid JSON (no markdown fences).

Schema:
{
  "summary": "one paragraph plan",
  "ticket_order": ["ticket titles in recommended execution order"],
  "architecture_notes": "how this fits the repo",
  "testing_strategy": "what to verify",
  "constraints": ["things the agent must not do — include: never echo task text as file content"]
}"""


async def create_story_plan(
    llm_config,
    api_key: str | None,
    *,
    project_name: str,
    project_goals: str | None,
    tech_stack: str | None,
    story: Story,
    tickets: list[Ticket],
    codebase_summary: str,
    prior_learnings: str,
) -> dict:
    ticket_block = "\n".join(
        f"- [{t.type}] {t.title} (priority={t.priority}): {t.description[:300]}"
        for t in tickets
    )
    user_prompt = f"""PROJECT: {project_name}
GOALS: {project_goals or 'N/A'}
TECH: {tech_stack or 'N/A'}

STORY: {story.title}
{story.description or ''}

ACCEPTANCE CRITERIA:
{story.acceptance_criteria or 'N/A'}

TICKETS:
{ticket_block}

CODEBASE:
{codebase_summary[:4000]}

PRIOR RUNS ON THIS STORY:
{prior_learnings or 'None — first run'}

Create an execution plan for the coding agent."""

    messages = [
        {"role": "system", "content": PLAN_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    raw = await chat_completion(llm_config, api_key, messages, max_tokens=4096, json_mode=True)
    return extract_json(raw)


def order_tickets_by_plan(tickets: list[Ticket], plan: dict) -> list[Ticket]:
    order = plan.get("ticket_order") or []
    if not order:
        return tickets
    title_to_ticket = {t.title: t for t in tickets}
    ordered: list[Ticket] = []
    for title in order:
        if title in title_to_ticket:
            ordered.append(title_to_ticket.pop(title))
    ordered.extend(title_to_ticket.values())
    return ordered


def plan_to_memory_text(plan: dict) -> str:
    return json.dumps(plan, indent=2)

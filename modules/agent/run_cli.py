"""Run one agent job in an isolated process (used by gevent Celery workers)."""

import asyncio
import sys
import uuid

import core.models_registry  # noqa: F401 — register SQLAlchemy mappers
from modules.agent.tasks import _mark_run_failed, _run_agent_async


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "usage: python -m modules.agent.run_cli <run_id> [--mark-failed <message>]",
            file=sys.stderr,
        )
        return 2
    run_id = uuid.UUID(sys.argv[1])
    if len(sys.argv) >= 3 and sys.argv[2] == "--mark-failed":
        message = sys.argv[3] if len(sys.argv) > 3 else "Unknown error"
        asyncio.run(_mark_run_failed(run_id, message))
        return 0
    asyncio.run(_run_agent_async(run_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

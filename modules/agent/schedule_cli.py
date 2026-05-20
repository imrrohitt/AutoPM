"""Poll due story agent schedules in an isolated process (gevent Celery workers)."""

import asyncio
import sys

import core.models_registry  # noqa: F401


def main() -> int:
    from modules.agent.schedule_tasks import _process_due_schedules_async

    triggered = asyncio.run(_process_due_schedules_async())
    print(triggered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

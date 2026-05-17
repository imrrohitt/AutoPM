#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ ! -x .venv/bin/celery ]; then
  echo "Missing .venv — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

# Agent queue: prefork (asyncio + asyncpg in-process).
# Default queue: gevent greenlets for lightweight I/O tasks.
# Override single-pool mode: CELERY_POOL=gevent|prefork with CELERY_QUEUES=agent,default
QUEUES="${CELERY_QUEUES:-agent,default}"
CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-10}"
SINGLE_POOL="${CELERY_POOL:-}"

echo "Stopping any existing AutoPM Celery workers..."
pkill -9 -f "modules.agent.celery_app worker" 2>/dev/null || true
sleep 2

CELERY=(.venv/bin/celery -A modules.agent.celery_app worker --loglevel=info)

cleanup() {
  jobs -p 2>/dev/null | xargs kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if [ -n "${SINGLE_POOL}" ]; then
  echo "Starting Celery (single pool=${SINGLE_POOL}, queues=${QUEUES})"
  unset AUTOPM_CELERY_GEVENT
  [ "${SINGLE_POOL}" = "gevent" ] && export AUTOPM_CELERY_GEVENT=1
  exec "${CELERY[@]}" --pool="${SINGLE_POOL}" --concurrency="${CONCURRENCY}" \
    --queues="${QUEUES}" -n "agent@%h"
fi

# Dual workers: agent → prefork, default → gevent (recommended).
has_agent=false
has_default=false
IFS=',' read -ra PARTS <<< "${QUEUES}"
for q in "${PARTS[@]}"; do
  q="${q// /}"
  [ "$q" = "agent" ] && has_agent=true
  [ "$q" = "default" ] && has_default=true
done

if $has_agent; then
  echo "Starting agent worker (prefork, queue=agent, concurrency=2)"
  unset AUTOPM_CELERY_GEVENT
  "${CELERY[@]}" --pool=prefork --concurrency=2 --queues=agent \
    -n "agent-prefork@%h" &
fi

if $has_default; then
  echo "Starting I/O worker (gevent greenlets, queue=default, concurrency=${CONCURRENCY})"
  export AUTOPM_CELERY_GEVENT=1
  export GEVENT_RESOLVER=block
  "${CELERY[@]}" --pool=gevent --concurrency="${CONCURRENCY}" --queues=default \
    -n "agent-gevent@%h" &
fi

if ! $has_agent && ! $has_default; then
  echo "No recognized queues in CELERY_QUEUES=${QUEUES}"
  exit 1
fi

wait

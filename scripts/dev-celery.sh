#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ ! -x .venv/bin/celery ]; then
  echo "Missing .venv — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

# gevent pool: greenlets in one process (not prefork). Override via .env or env.
CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-10}"
QUEUES="${CELERY_QUEUES:-agent,default}"

echo "Starting Celery (gevent pool, concurrency=${CONCURRENCY}, queues=${QUEUES})"

export AUTOPM_CELERY_GEVENT=1

exec .venv/bin/celery -A modules.agent.celery_app worker \
  --pool=gevent \
  --concurrency="${CONCURRENCY}" \
  --queues="${QUEUES}" \
  --loglevel=info

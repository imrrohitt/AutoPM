#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
celery -A modules.agent.celery_app worker --loglevel=info

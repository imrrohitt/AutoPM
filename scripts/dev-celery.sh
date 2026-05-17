#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../backend"
source .venv/bin/activate
celery -A modules.agent.celery_app worker --loglevel=info

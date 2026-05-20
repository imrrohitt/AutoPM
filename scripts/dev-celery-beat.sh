#!/usr/bin/env bash
# Beat is included in dev-celery.sh — this wrapper keeps old docs/commands working.
exec "$(cd "$(dirname "$0")" && pwd)/dev-celery.sh" "$@"

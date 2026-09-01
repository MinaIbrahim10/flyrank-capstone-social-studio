#!/usr/bin/env bash

set -euo pipefail

ROOT="$(
    cd "$(dirname "$0")/.."
    pwd
)"

cd "$ROOT"

if [ ! -x .venv/bin/python ]; then
    ./scripts/setup.sh
fi

mkdir -p data

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

export DATABASE_URL="${DEMO_DATABASE_URL:-sqlite:///./data/demo.db}"
export PUBLISHER_OVERRIDE="mock_x"
export SCHEDULER_POLL_SECONDS="${SCHEDULER_POLL_SECONDS:-1}"
export APP_HOST="${APP_HOST:-127.0.0.1}"
export APP_PORT="${APP_PORT:-8000}"

# Running a script from scripts/ normally puts only scripts/
# on sys.path. Add the repository root explicitly so imports
# such as `from app.db import Database` work in a fresh clone.
if [ -n "${PYTHONPATH:-}" ]; then
    export PYTHONPATH="$ROOT:$PYTHONPATH"
else
    export PYTHONPATH="$ROOT"
fi

.venv/bin/python \
    scripts/seed_demo.py

.venv/bin/python \
    -m app.worker &

WORKER_PID=$!

cleanup() {
    if kill -0 \
        "$WORKER_PID" \
        >/dev/null 2>&1
    then
        kill \
            "$WORKER_PID" \
            >/dev/null 2>&1 \
            || true

        wait \
            "$WORKER_PID" \
            2>/dev/null \
            || true
    fi
}

trap cleanup EXIT INT TERM

echo
echo "SOCIAL MEDIA STUDIO DEMO: READY"
echo "API: http://${APP_HOST}:${APP_PORT}"
echo "Docs: http://${APP_HOST}:${APP_PORT}/docs"
echo "Publishing target: Mock X"
echo

.venv/bin/uvicorn \
    app.main:app \
    --host "$APP_HOST" \
    --port "$APP_PORT"

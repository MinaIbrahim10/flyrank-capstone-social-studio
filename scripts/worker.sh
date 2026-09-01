#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
    echo "Run ./scripts/setup.sh first."
    exit 1
fi

mkdir -p data

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

exec .venv/bin/python \
    -m app.worker

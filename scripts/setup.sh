#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3.13}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Python 3.13 is required."
    exit 1
fi

if [ ! -d .venv ]; then
    "$PYTHON" -m venv .venv
fi

.venv/bin/python \
    -m pip install \
    --upgrade pip

.venv/bin/python \
    -m pip install \
    -r requirements.txt

mkdir -p data

echo "SETUP: PASS"

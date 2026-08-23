#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then
  echo "Create .env from env.example (do not commit secrets)."
fi
export DEMO_MODE="${DEMO_MODE:-0}"
exec python3 -m uvicorn main:app --host 127.0.0.1 --port "${PORT:-8000}" --reload

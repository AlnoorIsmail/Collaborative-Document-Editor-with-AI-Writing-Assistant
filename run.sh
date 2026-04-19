#!/usr/bin/env bash

set -euo pipefail

command="${1:-dev}"

case "$command" in
  install)
    python -m pip install -r requirements.txt
    (
      cd app/frontend
      npm ci
    )
    ;;
  backend)
    uvicorn app.backend.main:app --reload
    ;;
  frontend)
    (
      cd app/frontend
      npm run dev
    )
    ;;
  dev)
    backend_pid=""
    frontend_pid=""

    cleanup() {
      if [[ -n "${backend_pid}" ]]; then
        kill "${backend_pid}" 2>/dev/null || true
      fi
      if [[ -n "${frontend_pid}" ]]; then
        kill "${frontend_pid}" 2>/dev/null || true
      fi
    }

    trap cleanup EXIT INT TERM

    uvicorn app.backend.main:app --reload &
    backend_pid=$!

    (
      cd app/frontend
      npm run dev
    ) &
    frontend_pid=$!

    wait "${backend_pid}" "${frontend_pid}"
    ;;
  tests)
    pytest app/backend/tests -q
    ;;
  *)
    echo "Usage: ./run.sh [install|dev|backend|frontend|tests]"
    exit 1
    ;;
esac

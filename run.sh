#!/usr/bin/env bash

set -euo pipefail

command="${1:-dev}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_bin="${script_dir}/.venv/bin"

if [[ -x "${venv_bin}/python" ]]; then
  PYTHON_BIN="${venv_bin}/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  echo "Python 3 is required but was not found on PATH."
  exit 1
fi

if [[ -x "${venv_bin}/uvicorn" ]]; then
  UVICORN_BIN="${venv_bin}/uvicorn"
else
  UVICORN_BIN="uvicorn"
fi

if [[ -x "${venv_bin}/pytest" ]]; then
  PYTEST_BIN="${venv_bin}/pytest"
else
  PYTEST_BIN="pytest"
fi

case "$command" in
  install)
    "${PYTHON_BIN}" -m pip install -r requirements.txt
    (
      cd app/frontend
      npm ci
    )
    ;;
  backend)
    "${UVICORN_BIN}" app.backend.main:app --reload
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

    "${UVICORN_BIN}" app.backend.main:app --reload &
    backend_pid=$!

    (
      cd app/frontend
      npm run dev
    ) &
    frontend_pid=$!

    wait "${backend_pid}" "${frontend_pid}"
    ;;
  tests)
    "${PYTEST_BIN}" app/backend/tests -q
    ;;
  *)
    echo "Usage: ./run.sh [install|dev|backend|frontend|tests]"
    exit 1
    ;;
esac

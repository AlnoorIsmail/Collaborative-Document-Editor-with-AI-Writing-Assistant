#!/usr/bin/env bash

set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_python="${root_dir}/.venv/bin/python"
frontend_dir="${root_dir}/app/frontend"

ensure_venv() {
  if [[ ! -x "${venv_python}" ]]; then
    echo "Project virtualenv is missing. Run 'bash run.sh install' first."
    exit 1
  fi
}

command="${1:-dev}"

case "$command" in
  install)
    if [[ ! -x "${venv_python}" ]]; then
      python3 -m venv "${root_dir}/.venv"
    fi

    "${venv_python}" -m pip install -r "${root_dir}/requirements.txt"
    (
      cd "${frontend_dir}"
      npm ci
    )
    ;;
  backend)
    ensure_venv
    "${venv_python}" -m uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000
    ;;
  frontend)
    (
      cd "${frontend_dir}"
      npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
    )
    ;;
  dev)
    ensure_venv
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

    "${venv_python}" -m uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000 &
    backend_pid=$!

    (
      cd "${frontend_dir}"
      npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
    ) &
    frontend_pid=$!

    wait "${backend_pid}" "${frontend_pid}"
    ;;
  tests)
    ensure_venv
    "${venv_python}" -m pytest app/backend/tests -q
    ;;
  *)
    echo "Usage: ./run.sh [install|dev|backend|frontend|tests]"
    exit 1
    ;;
esac

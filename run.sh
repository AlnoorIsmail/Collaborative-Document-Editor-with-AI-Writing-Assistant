#!/usr/bin/env bash

set -euo pipefail

command="${1:-backend}"

case "$command" in
  install)
    python -m pip install -r requirements.txt
    ;;
  backend)
    uvicorn app.backend.main:app --reload
    ;;
  tests)
    pytest app/backend/tests -q
    ;;
  *)
    echo "Usage: ./run.sh [install|backend|tests]"
    exit 1
    ;;
esac

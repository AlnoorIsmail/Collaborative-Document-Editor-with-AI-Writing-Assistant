#!/usr/bin/env bash

set -euo pipefail

COMMAND="${1:-run}"

case "$COMMAND" in
  setup)
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    ;;
  run)
    uvicorn app.backend.main:app --reload
    ;;
  test)
    pytest app/backend/tests -q
    ;;
  *)
    echo "Usage: ./run.sh [setup|run|test]"
    exit 1
    ;;
esac

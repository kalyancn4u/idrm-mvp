#!/usr/bin/env bash
# Run BOTH apps in one shell. Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."

GREEN=$'\033[32m'; CYAN=$'\033[36m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'

API_PORT="${API_PORT:-8000}"
DASH_PORT="${DASH_PORT:-5000}"

cleanup() {
  echo
  echo -e "${YELLOW}Shutting down…${RESET}"
  [[ -n "${API_PID:-}"  ]] && kill "$API_PID"  2>/dev/null || true
  [[ -n "${DASH_PID:-}" ]] && kill "$DASH_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

echo -e "${CYAN}▶ API       http://127.0.0.1:${API_PORT}/docs${RESET}"
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT" --reload &
API_PID=$!

echo -e "${CYAN}▶ DASHBOARD http://127.0.0.1:${DASH_PORT}/dashboard/auth/login${RESET}"
FLASK_APP=dashboard:create_dashboard FLASK_DEBUG=1 \
  .venv/bin/flask run --host 0.0.0.0 --port "$DASH_PORT" &
DASH_PID=$!

echo
echo -e "${GREEN}Both apps running. Ctrl+C to stop.${RESET}"
wait


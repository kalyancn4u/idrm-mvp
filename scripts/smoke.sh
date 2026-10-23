#!/usr/bin/env bash
# Smoke test — curls both apps.
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
DASH_URL="${DASH_URL:-http://127.0.0.1:5000}"

PASS=0; FAIL=0
GREEN=$'\033[32m'; RED=$'\033[31m'; CYAN=$'\033[36m'; RESET=$'\033[0m'

check() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    echo -e "  ${GREEN}✔${RESET} $label ($actual)"; PASS=$((PASS+1))
  else
    echo -e "  ${RED}✖${RESET} $label (expected $expected, got $actual)"; FAIL=$((FAIL+1))
  fi
}

echo -e "${CYAN}FastAPI (public) → $API_URL${RESET}"
check "GET /api/v1/health"          200 "$(curl -s -o /dev/null -w '%{http_code}' "$API_URL/api/v1/health")"
check "GET /docs"                   200 "$(curl -s -o /dev/null -w '%{http_code}' "$API_URL/docs")"
check "GET /api/v1/users/me (anon)" 401 "$(curl -s -o /dev/null -w '%{http_code}' "$API_URL/api/v1/users/me")"

echo
echo -e "${CYAN}Flask dashboard → $DASH_URL${RESET}"
check "GET /dashboard/login"        200 "$(curl -s -o /dev/null -w '%{http_code}' "$DASH_URL/dashboard/login")"
check "GET /dashboard/ (anon)"      302 "$(curl -s -o /dev/null -w '%{http_code}' "$DASH_URL/dashboard/")"

echo
echo -e "${CYAN}Result: ${GREEN}${PASS} passed${RESET}, ${RED}${FAIL} failed${RESET}"
[[ "$FAIL" -eq 0 ]] || exit 1


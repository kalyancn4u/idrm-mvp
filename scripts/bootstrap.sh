#!/usr/bin/env bash
# IDRM MVP — one-shot bootstrap
set -euo pipefail

BOLD=$'\033[1m'; GREEN=$'\033[32m'; CYAN=$'\033[36m'; RED=$'\033[31m'; RESET=$'\033[0m'

step() { echo -e "${CYAN}▶ $*${RESET}"; }
ok()   { echo -e "${GREEN}✔ $*${RESET}"; }
die()  { echo -e "${RED}✖ $*${RESET}" >&2; exit 1; }

cd "$(dirname "$0")/.."

step "Checking prerequisites"
command -v python3 >/dev/null || die "python3 is required"
command -v docker  >/dev/null || echo "  (docker not found — assuming external PostGIS)"

step "Creating .env"
make env

step "Creating virtualenv and installing dependencies"
make install

step "Generating RS256 JWT keypair"
make keys

step "Starting PostGIS + MinIO + Redis"
if command -v docker >/dev/null 2>&1; then
  make infra-up || echo "  (docker compose failed — assuming external services)"
fi

step "Creating the database"
make db-create

step "Applying migrations"
make migrate

step "Seeding data"
make seed

echo
ok "Bootstrap complete."
echo
echo -e "${BOLD}Next:${RESET}"
echo "    make run"
echo "    API       → http://127.0.0.1:8000/docs"
echo "    Dashboard → http://127.0.0.1:5000/dashboard/auth/login"
echo
echo -e "${BOLD}Demo logins${RESET}"
echo "    admin@idrm.local       / Admin#2026"
echo "    coord.hyd@idrm.local   / IDRMseed#2026"


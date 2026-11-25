# =============================================================================
#  IDRM MVP — Integrated Disaster Response Management
#  make help  to list every target
# =============================================================================
SHELL          := /bin/bash
.DEFAULT_GOAL  := help

PYTHON         ?= python3
VENV           := .venv
VENV_BIN       := $(VENV)/bin
PY             := $(VENV_BIN)/python
PIP            := $(VENV_BIN)/pip
UVICORN        := $(VENV_BIN)/uvicorn
FLASK          := $(VENV_BIN)/flask
ALEMBIC        := $(VENV_BIN)/alembic
PYTEST         := $(VENV_BIN)/pytest
GUNICORN       := $(VENV_BIN)/gunicorn

PGHOST         ?= 127.0.0.1
PGPORT         ?= 5432
PGUSER         ?= idrm_user
PGPASSWORD     ?= idrm_pass
PGDATABASE     ?= idrm_db
# Role used to create the app role and database.  With docker-compose the
# container's superuser IS $(PGUSER) (there is no "postgres" role), so that
# is the default.  For a native install:  make db-create PGMAINT=postgres PGMAINTPASSWORD=...
PGMAINT        ?= $(PGUSER)
PGMAINTPASSWORD ?= $(PGPASSWORD)
export PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE

DATABASE_URL        ?= postgresql+asyncpg://$(PGUSER):$(PGPASSWORD)@$(PGHOST):$(PGPORT)/$(PGDATABASE)
DATABASE_URL_SYNC   ?= postgresql+psycopg2://$(PGUSER):$(PGPASSWORD)@$(PGHOST):$(PGPORT)/$(PGDATABASE)
export DATABASE_URL DATABASE_URL_SYNC

PSQL           := PGPASSWORD=$(PGPASSWORD) psql -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) -d $(PGDATABASE) -v ON_ERROR_STOP=1
PSQL_MAINT     := PGPASSWORD=$(PGMAINTPASSWORD) psql -h $(PGHOST) -p $(PGPORT) -U $(PGMAINT) -v ON_ERROR_STOP=1

# Tests run against their OWN database so they never write into dev data.
TEST_PGDATABASE        ?= idrm_test
TEST_DATABASE_URL      ?= postgresql+asyncpg://$(PGUSER):$(PGPASSWORD)@$(PGHOST):$(PGPORT)/$(TEST_PGDATABASE)
TEST_DATABASE_URL_SYNC ?= postgresql+psycopg2://$(PGUSER):$(PGPASSWORD)@$(PGHOST):$(PGPORT)/$(TEST_PGDATABASE)
TEST_ENV       := DATABASE_URL=$(TEST_DATABASE_URL) DATABASE_URL_SYNC=$(TEST_DATABASE_URL_SYNC)

# Minimum line coverage. The CI workflow uses the same number.
COV_MIN        ?= 60

API_PORT       ?= 8000
DASH_PORT      ?= 5000

help:  ## Show every target
	@echo -e "IDRM MVP — make targets"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---- Setup -------------------------------------------------------------------
setup: venv install env keys infra-up db-create migrate seed  ## One-shot bring-up
	@echo "✔ setup complete. Run: make run"

venv:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@$(PIP) install --quiet --upgrade pip setuptools wheel

install: venv
	@$(PIP) install --quiet -r requirements.txt

env:
	@test -f .env || (cp .env.example .env && echo "✔ .env created")

keys:
	@$(PY) scripts/generate_keys.py

# ---- Infrastructure ----------------------------------------------------------
infra-up:
	@docker compose up -d postgres minio redis
	@echo -n "  waiting for postgres"; \
	  for i in $$(seq 1 30); do PGPASSWORD=$(PGPASSWORD) pg_isready -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) -q && break; echo -n "."; sleep 1; done; echo " ok"

infra-down:
	@docker compose down

db-create:
	@$(PSQL_MAINT) -d postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='$(PGUSER)'" | grep -q 1 || \
	  $(PSQL_MAINT) -d postgres -c "CREATE ROLE $(PGUSER) LOGIN PASSWORD '$(PGPASSWORD)';"
	@$(PSQL_MAINT) -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='$(PGDATABASE)'" | grep -q 1 || \
	  $(PSQL_MAINT) -d postgres -c "CREATE DATABASE $(PGDATABASE) OWNER $(PGUSER);"
	@$(PSQL_MAINT) -d $(PGDATABASE) -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# ---- Schema + data -----------------------------------------------------------
migrate:
	@$(ALEMBIC) upgrade head

revision:
	@test -n "$(m)" || (echo "usage: make revision m='message'"; exit 1)
	@$(ALEMBIC) revision --autogenerate -m "$(m)"

seed:  ## Demo data (users with a public password) — development only
	@$(PY) -m scripts.seed

seed-reference:  ## Regions only — safe for production
	@$(PY) -m scripts.seed --reference-only

db-reset:
	@echo "DESTRUCTIVE — this drops every IDRM table"
	@read -p "Type 'yes' to continue: " c; [ "$$c" = "yes" ] || exit 1
	@$(PSQL) -q -f sql/99_reset.sql
	@$(MAKE) migrate seed

psql:
	@$(PSQL)

dump:
	@mkdir -p backups && PGPASSWORD=$(PGPASSWORD) pg_dump -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) \
	  --no-owner --clean --if-exists $(PGDATABASE) > backups/idrm_$$(date +%Y%m%d_%H%M%S).sql

# ---- Run ---------------------------------------------------------------------
run:  ## Run BOTH apps
	@bash scripts/run_all.sh

run-api:
	@$(UVICORN) app.main:app --host 0.0.0.0 --port $(API_PORT) --reload

run-dashboard:
	@FLASK_APP=dashboard:create_dashboard FLASK_DEBUG=1 $(FLASK) run --host 0.0.0.0 --port $(DASH_PORT)

serve:
	@$(GUNICORN) -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 "app.main:app" & \
	 $(GUNICORN) -w 4 -b 0.0.0.0:5000 "dashboard:create_dashboard()" & wait

routes:
	@echo "--- FastAPI ---"
	@$(PY) -c "from app.main import app; [print(f'  {sorted(r.methods)} {r.path}') for r in app.routes if hasattr(r,'methods')]"
	@echo "--- Flask ---"
	@$(PY) -c "from dashboard import create_dashboard; d=create_dashboard(); [print(f'  {sorted(r.methods)} {r.rule}') for r in d.url_map.iter_rules() if r.endpoint != 'static']"

# ---- Quality -----------------------------------------------------------------
test-db:  ## Create, migrate and seed the test database ($(TEST_PGDATABASE))
	@$(PSQL_MAINT) -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='$(TEST_PGDATABASE)'" | grep -q 1 || \
	  $(PSQL_MAINT) -d postgres -c "CREATE DATABASE $(TEST_PGDATABASE) OWNER $(PGUSER);"
	@$(PSQL_MAINT) -d $(TEST_PGDATABASE) -c "CREATE EXTENSION IF NOT EXISTS postgis;"
	@$(TEST_ENV) $(ALEMBIC) upgrade head
	@$(TEST_ENV) $(PY) -m scripts.seed

test:  ## Full suite (run `make test-db` once first for the database tests)
	@$(TEST_ENV) $(PYTEST) -q

test-api:
	@$(TEST_ENV) $(PYTEST) -q tests/unit tests/api

test-dashboard:
	@$(TEST_ENV) $(PYTEST) -q tests/dashboard

test-no-redis:
	@$(TEST_ENV) REDIS_URL="" $(PYTEST) -q -m "not requires_redis"

test-cov:
	@$(TEST_ENV) $(PYTEST) -q --cov=app --cov=dashboard --cov=shared --cov-report=term-missing --cov-fail-under=$(COV_MIN)

lint:
	@$(VENV_BIN)/ruff check app dashboard shared tests scripts
	@$(PY) scripts/lint_boundaries.py
	@$(PY) scripts/lint_docs.py

fmt:
	@$(VENV_BIN)/ruff check --fix app dashboard shared tests scripts
	@$(VENV_BIN)/ruff format app dashboard shared tests scripts

qa: lint test-cov

smoke:
	@bash scripts/smoke.sh

# ---- Housekeeping ------------------------------------------------------------
stats:
	@$(PSQL) -c "SELECT relname AS table, n_live_tup AS rows FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 20;"

docs:
	@ls -1 docs/*.md | sed 's/^/  /'

clean:
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .ruff_cache htmlcov .coverage 2>/dev/null || true

nuke: clean
	@rm -rf $(VENV)
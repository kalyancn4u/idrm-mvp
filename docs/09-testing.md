# Testing Guide

## Running tests

```bash
make test              # Full suite
make test-api          # FastAPI only
make test-dashboard    # Flask only
make test-no-redis     # Prove it works without Redis
make test-cov          # Coverage report
```

Directly:

```bash
.venv/bin/pytest -q
.venv/bin/pytest -v tests/unit/test_lifecycle.py
.venv/bin/pytest -k "rbac"
.venv/bin/pytest -m "not requires_redis"
```

## Test layout

| Path | Coverage |
|---|---|
| `tests/unit/` | Pure logic — no DB |
| `tests/api/` | FastAPI contracts |
| `tests/dashboard/` | Flask routes + RBAC |
| `tests/integration/` | DB-backed end-to-end |

## Fixtures

From `tests/conftest.py`:

```python
@pytest.fixture()
async def client():
    """An httpx ASGI client bound to the FastAPI app."""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.fixture()
def dash_app():
    from dashboard import create_dashboard
    app = create_dashboard()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app

@pytest.fixture()
def dash_client(dash_app):
    return dash_app.test_client()
```

## Writing a test

### Pure logic (fastest)

```python
def test_legal_transitions():
    assert can_transition("approve", S.created)
    assert next_status("approve") == S.approved
```

### API contract

```python
@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/api/v1/users/me")
    assert r.status_code == 401
```

### Dashboard RBAC

```python
def test_dashboard_redirects_anonymous(dash_client):
    r = dash_client.get("/dashboard/")
    assert r.status_code == 302
```

### Integration (DB-backed)

```python
@pytest.mark.pg
@pytest.mark.asyncio
async def test_auto_approval_creates_decision(client):
    r = await client.post("/api/v1/incidents", json={...})
    assert r.status_code == 201
    body = r.json()
    assert body.get("auto_approved") in (True, False)
```

## Markers

| Marker | Meaning |
|---|---|
| `pg` | Requires a real PostgreSQL + PostGIS instance |
| `requires_redis` | Requires Redis |
| `slow` | Takes more than a second |

Skip them with `-m "not pg and not requires_redis"`.

## What's well covered

- ✅ The incident state machine
- ✅ Password hashing + JWT round-trip
- ✅ Token type confusion is rejected
- ✅ Jitter spreads token expiries
- ✅ Dashboard RBAC gate
- ✅ Anonymous requests are rejected

## What's thin

- ⚠️ Full lifecycle with DB writes
- ⚠️ Auto-approval with real caps
- ⚠️ Dashboard template rendering
- ⚠️ Concurrency

## CI sketch

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:16-3.4
        env:
          POSTGRES_USER: idrm_user
          POSTGRES_PASSWORD: idrm_pass
          POSTGRES_DB: idrm_db
        ports: ['5432:5432']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: make install
      - run: make lint
      - run: make test
      - run: make test-no-redis
```

## Debugging

```bash
.venv/bin/pytest tests/api/test_auth.py::test_me_requires_auth -vv
.venv/bin/pytest --pdb
.venv/bin/pytest -s
```

| Symptom | Cause |
|---|---|
| `no such table` | `db.create_all()` didn't run — check fixtures |
| `RuntimeError: working outside app context` | Wrap in `with app.app_context():` |
| 403 where 200 expected | Wrong role in the test |
| `fn_severity_points does not exist` | On SQLite; mark `@pytest.mark.pg` |

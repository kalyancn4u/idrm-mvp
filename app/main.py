"""
IDRM MVP — FastAPI assembly.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.dependencies import client_ip
from app.core.exceptions import register_exception_handlers
from shared.config import get_settings
from shared.logging import client_ip_ctx, configure_logging, request_id_ctx

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info("IDRM API starting (env=%s)", settings.app_env)

    from shared.db import async_engine

    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        log.info("Database connection OK")
    except Exception as exc:  # pragma: no cover
        log.error("Database unreachable: %s", exc)

    yield

    from shared.db import async_engine as engine

    await engine.dispose()
    log.info("IDRM API stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    settings.require_safe_for_production()

    app = FastAPI(
        title="IDRM — Integrated Disaster Response Management",
        description="Map-driven platform connecting people with providers.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.middleware("http")
    async def _request_context(request: Request, call_next):
        """
        Give every request an id and remember who sent it.

        Both values are stored in context variables, which is where the JSON
        log formatter and `shared.audit` look them up. Without this, every
        log line has request id "-" and every audit row has no IP address.
        """
        request_id = (request.headers.get("X-Request-ID") or uuid.uuid4().hex)[:64]
        rid_token = request_id_ctx.set(request_id)
        ip_token = client_ip_ctx.set(client_ip(request))
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(rid_token)
            client_ip_ctx.reset(ip_token)
        response.headers["X-Request-ID"] = request_id
        return response

    # ---- routers ----------------------------------------------------------
    API = "/api/v1"
    from app.modules.administration.router import router as admin_router
    from app.modules.audit.router import router as audit_router
    from app.modules.comms.router import router as comms_router
    from app.modules.dispatch.router import router as dispatch_router
    from app.modules.files.router import router as files_router
    from app.modules.ics.router import router as ics_router
    from app.modules.incidents.router import router as incidents_router
    from app.modules.logistics.router import router as logistics_router
    from app.modules.organizations.router import router as orgs_router
    from app.modules.personnel.router import router as personnel_router
    from app.modules.policies.router import router as policies_router
    from app.modules.scheduling.router import router as scheduling_router
    from app.modules.users.router import router as users_router

    app.include_router(users_router,     prefix=f"{API}", tags=["users"])
    app.include_router(incidents_router, prefix=f"{API}", tags=["incidents"])
    app.include_router(dispatch_router,  prefix=f"{API}", tags=["dispatch"])
    app.include_router(personnel_router, prefix=f"{API}", tags=["personnel"])
    app.include_router(orgs_router,      prefix=f"{API}", tags=["organizations"])
    app.include_router(scheduling_router,prefix=f"{API}", tags=["scheduling"])
    app.include_router(logistics_router, prefix=f"{API}", tags=["logistics"])
    app.include_router(ics_router,       prefix=f"{API}", tags=["ics"])
    app.include_router(comms_router,     prefix=f"{API}", tags=["comms"])
    app.include_router(policies_router,  prefix=f"{API}", tags=["policies"])
    app.include_router(files_router,     prefix=f"{API}/files", tags=["files"])
    app.include_router(audit_router,     prefix=f"{API}/audit-logs", tags=["audit"])
    app.include_router(admin_router,     prefix=f"{API}", tags=["system"])

    # ---- static (for the docs preview; the main UI is Flask) --------------
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/health", include_in_schema=False)
    async def _health():
        return {"status": "ok"}

    return app


app = create_app()


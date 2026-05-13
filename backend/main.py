"""
LoanLens AI — FastAPI Backend Entry Point using Prisma ORM.
"""

import asyncio
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import db, ensure_runtime_schema_compatibility, verify_database_connection
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# Import all routes
from routes.health import router as health_router
from routes.auth import router as auth_router
from routes.cases import router as cases_router
from routes.documents import router as documents_router
from routes.analysis import router as analysis_router
from routes.ask import router as ask_router
from services.job_queue_service import start_analysis_job_worker, stop_analysis_job_worker

settings = get_settings()


def allows_degraded_startup() -> bool:
    """Only local development may continue without a database connection."""
    return settings.APP_ENV == "development"


def startup_policy() -> str:
    """Describe whether the current environment requires a live database at boot."""
    return "development-degraded-ok" if allows_degraded_startup() else "strict-db-required"


def initialize_app_state(app: FastAPI) -> None:
    app.state.db_startup_error = None
    app.state.job_worker_started = False
    app.state.app_env = settings.APP_ENV
    app.state.startup_policy = startup_policy()


async def startup_app(app: FastAPI) -> None:
    """Connect Prisma client and start background workers."""
    try:
        await asyncio.wait_for(
            db.connect(),
            timeout=settings.DATABASE_CONNECT_TIMEOUT_SECONDS,
        )
        await verify_database_connection(db)
        missing_columns = await ensure_runtime_schema_compatibility(db, settings)
        if missing_columns:
            logger.warning(
                "Applied compatibility columns for legacy analysis tables: %s",
                ", ".join(missing_columns),
            )
        app.state.db_startup_error = None
    except Exception as exc:
        app.state.db_startup_error = str(exc) or exc.__class__.__name__
        if not allows_degraded_startup():
            logger.exception(
                "Database connection failed during startup; refusing boot in env=%s with policy=%s",
                settings.APP_ENV,
                startup_policy(),
            )
            raise
        logger.exception("Database connection failed during startup; continuing in degraded development mode")
    else:
        await start_analysis_job_worker()
        app.state.job_worker_started = True

    db_status = "connected" if db.is_connected() and app.state.db_startup_error is None else "disconnected"
    startup_status = "ready" if db_status == "connected" else "degraded"
    print(
        f"[startup] LoanLens AI API started with Prisma - "
        f"status={startup_status} db={db_status} pid={os.getpid()} "
        f"reload={os.getenv('BACKEND_RELOAD_MODE', 'unknown')} "
        f"port={os.getenv('BACKEND_PORT', 'unknown')} "
        f"env={settings.APP_ENV} policy={startup_policy()}"
    )


async def shutdown_app(app: FastAPI) -> None:
    """Stop background workers and disconnect Prisma."""
    if app.state.job_worker_started:
        await stop_analysis_job_worker()
        app.state.job_worker_started = False
    if db.is_connected():
        await db.disconnect()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_app(app)
    try:
        yield
    finally:
        await shutdown_app(app)

# Ensure Windows console encoding won't crash on unicode output.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = FastAPI(
    title="LoanLens AI API",
    description="AI-powered loan document analysis API for fintech.",
    version="0.1.0",
    lifespan=lifespan,
)
initialize_app_state(app)

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

logger = logging.getLogger("loanlens")
logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}')

@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Method={request.method} Path={request.url.path} Status={response.status_code} Duration={process_time:.3f}s RequestID={request_id}")
    response.headers["X-Request-ID"] = request_id
    return response

origins = [settings.FRONTEND_URL]
if settings.APP_ENV != "production":
    origins.extend([
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router)

app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(cases_router, prefix=settings.API_V1_PREFIX)
app.include_router(documents_router, prefix=settings.API_V1_PREFIX)
app.include_router(analysis_router, prefix=settings.API_V1_PREFIX)
app.include_router(ask_router, prefix=settings.API_V1_PREFIX)

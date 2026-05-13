"""
Health check route.
"""

from fastapi import APIRouter, HTTPException, Request

from core.database import DatabaseUnavailableError, db, verify_database_connection

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(request: Request):
    """Health check endpoint for monitoring and load balancers."""
    startup_error = getattr(request.app.state, "db_startup_error", None)
    app_env = getattr(request.app.state, "app_env", "unknown")
    startup_policy = getattr(request.app.state, "startup_policy", "strict-db-required")
    db_connected = db.is_connected()
    if db_connected:
        try:
            await verify_database_connection(db)
        except DatabaseUnavailableError as exc:
            db_connected = False
            startup_error = str(exc)

    return {
        "status": "ok" if db_connected else "degraded",
        "service": "LoanLens AI API",
        "version": "0.1.0",
        "environment": app_env,
        "startup_policy": startup_policy,
        "ready": db_connected,
        "database": "connected" if db_connected else "disconnected",
        "startup_error": startup_error if startup_error else None,
    }


@router.get("/health/live")
async def live_check(request: Request):
    """Liveness probe for process-level health checks."""
    return {
        "status": "alive",
        "service": "LoanLens AI API",
        "version": "0.1.0",
        "environment": getattr(request.app.state, "app_env", "unknown"),
        "startup_policy": getattr(request.app.state, "startup_policy", "strict-db-required"),
    }


@router.get("/health/ready")
async def readiness_check(request: Request):
    """Readiness probe for deployments and local dependency checks."""
    app_env = getattr(request.app.state, "app_env", "unknown")
    startup_policy = getattr(request.app.state, "startup_policy", "strict-db-required")
    if not db.is_connected():
        detail = "Database not connected"
        if startup_policy == "development-degraded-ok":
            detail = "Database not connected; running in degraded development mode"
        raise HTTPException(status_code=503, detail=detail)

    try:
        await verify_database_connection(db)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "status": "ready",
        "service": "LoanLens AI API",
        "version": "0.1.0",
        "environment": app_env,
        "startup_policy": startup_policy,
        "ready": True,
        "database": "connected",
        "startup_error": None,
    }

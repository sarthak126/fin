from types import SimpleNamespace
from unittest.mock import AsyncMock

import main as main_module
from routes import health as health_routes


async def test_health_check_reports_service_status(async_client, monkeypatch):
    monkeypatch.setattr(health_routes, "db", SimpleNamespace(is_connected=lambda: True))
    monkeypatch.setattr(health_routes, "verify_database_connection", AsyncMock())
    main_module.app.state.app_env = "development"
    main_module.app.state.startup_policy = "development-degraded-ok"

    response = await async_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "LoanLens AI API",
        "version": "0.1.0",
        "environment": "development",
        "startup_policy": "development-degraded-ok",
        "ready": True,
        "database": "connected",
        "startup_error": None,
    }


async def test_health_check_reports_degraded_development_mode(async_client, monkeypatch):
    monkeypatch.setattr(health_routes, "db", SimpleNamespace(is_connected=lambda: False))
    main_module.app.state.app_env = "development"
    main_module.app.state.startup_policy = "development-degraded-ok"
    main_module.app.state.db_startup_error = "connection timeout"

    response = await async_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "service": "LoanLens AI API",
        "version": "0.1.0",
        "environment": "development",
        "startup_policy": "development-degraded-ok",
        "ready": False,
        "database": "disconnected",
        "startup_error": "connection timeout",
    }


async def test_health_check_reports_unavailable_when_probe_fails(async_client, monkeypatch):
    monkeypatch.setattr(health_routes, "db", SimpleNamespace(is_connected=lambda: True))
    monkeypatch.setattr(
        health_routes,
        "verify_database_connection",
        AsyncMock(side_effect=health_routes.DatabaseUnavailableError("Database connection is unavailable")),
    )
    main_module.app.state.app_env = "development"
    main_module.app.state.startup_policy = "development-degraded-ok"
    main_module.app.state.db_startup_error = None

    response = await async_client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["ready"] is False
    assert response.json()["startup_error"] == "Database connection is unavailable"


async def test_ready_check_returns_503_when_probe_fails(async_client, monkeypatch):
    monkeypatch.setattr(health_routes, "db", SimpleNamespace(is_connected=lambda: True))
    monkeypatch.setattr(
        health_routes,
        "verify_database_connection",
        AsyncMock(side_effect=health_routes.DatabaseUnavailableError("Database connection is unavailable")),
    )

    response = await async_client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database connection is unavailable"}


async def test_ready_check_returns_503_when_database_is_disconnected(async_client, monkeypatch):
    monkeypatch.setattr(health_routes, "db", SimpleNamespace(is_connected=lambda: False))
    main_module.app.state.app_env = "development"
    main_module.app.state.startup_policy = "development-degraded-ok"

    response = await async_client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Database not connected; running in degraded development mode",
    }


async def test_ready_check_reports_connected_database(async_client, monkeypatch):
    monkeypatch.setattr(health_routes, "db", SimpleNamespace(is_connected=lambda: True))
    monkeypatch.setattr(health_routes, "verify_database_connection", AsyncMock())
    main_module.app.state.app_env = "development"
    main_module.app.state.startup_policy = "development-degraded-ok"

    response = await async_client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "LoanLens AI API",
        "version": "0.1.0",
        "environment": "development",
        "startup_policy": "development-degraded-ok",
        "ready": True,
        "database": "connected",
        "startup_error": None,
    }


async def test_live_check_reports_process_health(async_client):
    main_module.app.state.app_env = "staging"
    main_module.app.state.startup_policy = "strict-db-required"

    response = await async_client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "alive",
        "service": "LoanLens AI API",
        "version": "0.1.0",
        "environment": "staging",
        "startup_policy": "strict-db-required",
    }


def test_only_development_allows_degraded_startup(monkeypatch):
    monkeypatch.setattr(main_module.settings, "APP_ENV", "development")
    assert main_module.allows_degraded_startup() is True
    assert main_module.startup_policy() == "development-degraded-ok"

    monkeypatch.setattr(main_module.settings, "APP_ENV", "staging")
    assert main_module.allows_degraded_startup() is False
    assert main_module.startup_policy() == "strict-db-required"

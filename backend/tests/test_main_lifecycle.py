import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import main as main_module


@pytest.mark.asyncio
async def test_startup_app_starts_worker_after_successful_db_connect(monkeypatch):
    app = SimpleNamespace(state=SimpleNamespace(db_startup_error="old", job_worker_started=False))
    connect_mock = AsyncMock(return_value=None)
    start_worker_mock = AsyncMock(return_value=None)
    compat_mock = AsyncMock(return_value=[])
    probe_mock = AsyncMock(return_value=None)
    fake_db = SimpleNamespace(connect=connect_mock, disconnect=AsyncMock(), is_connected=lambda: True)

    monkeypatch.setattr(main_module, "db", fake_db)
    monkeypatch.setattr(main_module, "start_analysis_job_worker", start_worker_mock)
    monkeypatch.setattr(main_module, "verify_database_connection", probe_mock)
    monkeypatch.setattr(main_module, "ensure_runtime_schema_compatibility", compat_mock)

    await main_module.startup_app(app)

    connect_mock.assert_awaited_once()
    probe_mock.assert_awaited_once_with(fake_db)
    compat_mock.assert_awaited_once_with(fake_db, main_module.settings)
    start_worker_mock.assert_awaited_once()
    assert app.state.db_startup_error is None
    assert app.state.job_worker_started is True


@pytest.mark.asyncio
async def test_startup_app_raises_in_strict_mode_when_db_connect_fails(monkeypatch):
    app = SimpleNamespace(state=SimpleNamespace(db_startup_error=None, job_worker_started=False))
    connect_mock = AsyncMock(side_effect=RuntimeError("db unavailable"))
    fake_db = SimpleNamespace(connect=connect_mock, disconnect=AsyncMock(), is_connected=lambda: False)

    monkeypatch.setattr(main_module.settings, "APP_ENV", "staging")
    monkeypatch.setattr(main_module, "db", fake_db)

    with pytest.raises(RuntimeError, match="db unavailable"):
        await main_module.startup_app(app)

    assert app.state.db_startup_error == "db unavailable"
    assert app.state.job_worker_started is False


@pytest.mark.asyncio
async def test_startup_app_records_error_type_when_db_connect_timeout_has_no_message(monkeypatch):
    app = SimpleNamespace(state=SimpleNamespace(db_startup_error=None, job_worker_started=False))
    connect_mock = AsyncMock(side_effect=asyncio.TimeoutError())
    fake_db = SimpleNamespace(connect=connect_mock, disconnect=AsyncMock(), is_connected=lambda: True)

    monkeypatch.setattr(main_module.settings, "APP_ENV", "development")
    monkeypatch.setattr(main_module, "db", fake_db)

    await main_module.startup_app(app)

    assert app.state.db_startup_error == "TimeoutError"
    assert app.state.job_worker_started is False


@pytest.mark.asyncio
async def test_shutdown_app_stops_worker_and_disconnects(monkeypatch):
    app = SimpleNamespace(state=SimpleNamespace(job_worker_started=True))
    stop_worker_mock = AsyncMock(return_value=None)
    disconnect_mock = AsyncMock(return_value=None)
    fake_db = SimpleNamespace(connect=AsyncMock(), disconnect=disconnect_mock, is_connected=lambda: True)

    monkeypatch.setattr(main_module, "stop_analysis_job_worker", stop_worker_mock)
    monkeypatch.setattr(main_module, "db", fake_db)

    await main_module.shutdown_app(app)

    stop_worker_mock.assert_awaited_once()
    disconnect_mock.assert_awaited_once()
    assert app.state.job_worker_started is False

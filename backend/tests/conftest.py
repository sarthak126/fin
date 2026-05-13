from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_PROVIDER", "postgresql")
os.environ.setdefault("DATABASE_URL", "postgresql://loanlens:loanlens@localhost:5432/loanlens_test")
os.environ.setdefault("DIRECT_URL", "postgresql://loanlens:loanlens@localhost:5432/loanlens_test")
os.environ.setdefault("PRISMA_SCHEMA_PATH", "./schema.prisma")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

import main as main_module
from core.database import get_db
from core.security import AuthenticatedContext, get_auth_context


@pytest.fixture(autouse=True)
def reset_test_state():
    original_state = {
        "db_startup_error": getattr(main_module.app.state, "db_startup_error", None),
        "job_worker_started": getattr(main_module.app.state, "job_worker_started", False),
        "app_env": getattr(main_module.app.state, "app_env", "development"),
        "startup_policy": getattr(main_module.app.state, "startup_policy", "development-degraded-ok"),
    }
    limiter_storage = getattr(getattr(main_module.app.state, "limiter", None), "_storage", None)
    if limiter_storage and hasattr(limiter_storage, "reset"):
        limiter_storage.reset()

    yield

    main_module.app.dependency_overrides.clear()
    for key, value in original_state.items():
        setattr(main_module.app.state, key, value)
    if limiter_storage and hasattr(limiter_storage, "reset"):
        limiter_storage.reset()


@pytest.fixture
def fake_db():
    return SimpleNamespace(
        case=SimpleNamespace(
            create=AsyncMock(),
            find_many=AsyncMock(),
            find_first=AsyncMock(),
            update=AsyncMock(),
        ),
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock()),
        auditlog=SimpleNamespace(create=AsyncMock()),
        caseanalysis=SimpleNamespace(
            create=AsyncMock(),
            find_first=AsyncMock(),
            find_many=AsyncMock(),
            update=AsyncMock(),
        ),
    )


@pytest.fixture
def auth_context() -> AuthenticatedContext:
    return AuthenticatedContext(
        user_id="user_test_123",
        org_id="org_test_456",
        email="analyst@example.com",
        name="Test Analyst",
        role="analyst",
        token_payload={"sub": "user_test_123", "org_id": "org_test_456"},
    )


@pytest_asyncio.fixture
async def async_client(fake_db, auth_context: AuthenticatedContext):
    async def override_get_db():
        yield fake_db

    async def override_get_auth_context():
        return auth_context

    main_module.app.dependency_overrides.clear()
    main_module.app.dependency_overrides[get_db] = override_get_db
    main_module.app.dependency_overrides[get_auth_context] = override_get_auth_context

    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client

    main_module.app.dependency_overrides.clear()

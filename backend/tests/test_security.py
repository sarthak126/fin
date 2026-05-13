from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import httpx
import pytest

from core import security
from models import UserRole


@pytest.mark.asyncio
async def test_sync_auth_context_creates_personal_workspace_when_org_claim_missing():
    fake_db = SimpleNamespace(
        organization=SimpleNamespace(
            find_unique=AsyncMock(return_value=None),
            create=AsyncMock(),
        ),
        user=SimpleNamespace(
            find_unique=AsyncMock(side_effect=[None, None]),
            create=AsyncMock(),
            update=AsyncMock(),
        ),
    )
    token_payload = {
        "sub": "user_test_123",
        "email": "analyst@example.com",
        "name": "Test Analyst",
    }

    context = await security.sync_auth_context(db=fake_db, token_payload=token_payload)

    assert context.user_id == "user_test_123"
    assert context.org_id == "personal_user_test_123"
    fake_db.organization.create.assert_awaited_once_with(
        data={
            "id": "personal_user_test_123",
            "name": "Test Analyst's Workspace",
        }
    )
    fake_db.user.create.assert_awaited_once_with(
        data={
            "id": "user_test_123",
            "email": "analyst@example.com",
            "name": "Test Analyst",
            "org_id": "personal_user_test_123",
        }
    )


@pytest.mark.asyncio
async def test_sync_auth_context_returns_service_unavailable_when_database_is_down_in_production(monkeypatch):
    monkeypatch.setattr(security.settings, "APP_ENV", "production")
    fake_db = SimpleNamespace(
        organization=SimpleNamespace(
            find_unique=AsyncMock(side_effect=httpx.ConnectError("query engine unavailable")),
        ),
        user=SimpleNamespace(),
    )
    token_payload = {
        "sub": "user_test_123",
        "email": "analyst@example.com",
        "name": "Test Analyst",
    }

    with pytest.raises(security.AuthConfigurationException) as error:
        await security.sync_auth_context(db=fake_db, token_payload=token_payload)

    assert error.value.status_code == 503
    assert "database connection is unavailable" in error.value.detail


@pytest.mark.asyncio
async def test_sync_auth_context_uses_claims_in_degraded_development_mode(monkeypatch):
    monkeypatch.setattr(security.settings, "APP_ENV", "development")
    fake_db = SimpleNamespace(
        organization=SimpleNamespace(
            find_unique=AsyncMock(side_effect=httpx.ConnectError("query engine unavailable")),
        ),
        user=SimpleNamespace(),
    )
    token_payload = {
        "sub": "user_test_123",
        "email": "analyst@example.com",
        "name": "Test Analyst",
    }

    context = await security.sync_auth_context(db=fake_db, token_payload=token_payload)

    assert context.user_id == "user_test_123"
    assert context.org_id == "personal_user_test_123"
    assert context.email == "analyst@example.com"
    assert context.name == "Test Analyst"
    assert context.role == UserRole.ADMIN.value


@pytest.mark.asyncio
async def test_get_auth_context_uses_claims_in_degraded_development_mode(monkeypatch):
    monkeypatch.setattr(security.settings, "APP_ENV", "development")
    fake_db = SimpleNamespace(
        organization=SimpleNamespace(
            find_unique=AsyncMock(side_effect=httpx.ConnectError("query engine unavailable")),
        ),
        user=SimpleNamespace(),
    )
    token_payload = {
        "sub": "user_test_123",
        "email": "analyst@example.com",
        "name": "Test Analyst",
    }

    context = await security.get_auth_context(db=fake_db, token_payload=token_payload)

    assert context.user_id == "user_test_123"
    assert context.org_id == "personal_user_test_123"
    assert context.role == UserRole.ADMIN.value


@pytest.mark.asyncio
async def test_get_auth_context_accepts_existing_personal_workspace_without_org_claim():
    fake_db = SimpleNamespace(
        organization=SimpleNamespace(
            find_unique=AsyncMock(
                return_value=SimpleNamespace(id="personal_user_test_123", name="Personal Workspace")
            )
        ),
        user=SimpleNamespace(
            find_unique=AsyncMock(
                return_value=SimpleNamespace(
                    id="user_test_123",
                    email="analyst@example.com",
                    name="Test Analyst",
                    org_id="personal_user_test_123",
                )
            )
        ),
    )
    token_payload = {
        "sub": "user_test_123",
        "email": "analyst@example.com",
        "name": "Test Analyst",
    }

    context = await security.get_auth_context(db=fake_db, token_payload=token_payload)

    assert context.user_id == "user_test_123"
    assert context.org_id == "personal_user_test_123"


def test_extract_org_id_still_prefers_explicit_clerk_organization_claims():
    assert security._extract_org_id({"org_id": "org_direct_123"}, "user_test_123") == "org_direct_123"
    assert security._extract_org_id({"o": {"id": "org_nested_456"}}, "user_test_123") == "org_nested_456"
    assert security._extract_org_id({}, "user_test_123") == "personal_user_test_123"


@pytest.mark.asyncio
async def test_verify_token_allows_small_clerk_clock_skew(monkeypatch):
    request = SimpleNamespace(headers={"Authorization": "Bearer clerk.jwt"})
    decode_mock = Mock(
        return_value={
            "sub": "user_test_123",
            "azp": "http://localhost:3000",
        }
    )

    monkeypatch.setattr(security.settings, "CLERK_JWT_LEEWAY_SECONDS", 60)
    monkeypatch.setattr(security.jwt, "get_unverified_header", Mock(return_value={"kid": "key_123"}))
    monkeypatch.setattr(security, "_get_rsa_key", Mock(return_value={"kty": "RSA", "kid": "key_123", "use": "sig", "n": "n", "e": "e"}))
    monkeypatch.setattr(security.RSAAlgorithm, "from_jwk", Mock(return_value="public-key"))
    monkeypatch.setattr(security.jwt, "decode", decode_mock)

    payload = await security.verify_token(request)

    assert payload["sub"] == "user_test_123"
    decode_mock.assert_called_once()
    assert decode_mock.call_args.kwargs["leeway"] == 60


@pytest.mark.asyncio
async def test_verify_token_allows_local_bypass_only_when_development_flag_is_enabled(monkeypatch):
    request = SimpleNamespace(headers={"Authorization": "Bearer codex-e2e-auth-bypass"})

    monkeypatch.setattr(security.settings, "APP_ENV", "development")
    monkeypatch.setattr(security.settings, "CODEX_E2E_AUTH_BYPASS", True)

    payload = await security.verify_token(request)

    assert payload["sub"] == "codex_e2e_user"
    assert payload["org_id"] == "codex_e2e_org"


@pytest.mark.asyncio
async def test_verify_token_rejects_local_bypass_in_production(monkeypatch):
    request = SimpleNamespace(headers={"Authorization": "Bearer codex-e2e-auth-bypass"})

    monkeypatch.setattr(security.settings, "APP_ENV", "production")
    monkeypatch.setattr(security.settings, "CODEX_E2E_AUTH_BYPASS", True)

    with pytest.raises(security.UnauthorizedException) as error:
        await security.verify_token(request)

    assert error.value.status_code == 401


def test_require_mutation_role_allows_admin_and_analyst():
    for role in (UserRole.ADMIN.value, UserRole.ANALYST.value):
        context = security.AuthenticatedContext(
            user_id="user_test_123",
            org_id="org_test_456",
            email="analyst@example.com",
            name="Test Analyst",
            role=role,
            token_payload={},
        )

        security.require_mutation_role(context)


def test_require_mutation_role_rejects_viewer():
    context = security.AuthenticatedContext(
        user_id="user_test_123",
        org_id="org_test_456",
        email="viewer@example.com",
        name="Test Viewer",
        role=UserRole.VIEWER.value,
        token_payload={},
    )

    with pytest.raises(security.ForbiddenException) as error:
        security.require_mutation_role(context)

    assert error.value.status_code == 403
    assert error.value.detail == "This action requires an admin or analyst role"

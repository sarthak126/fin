from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import production_readiness_service as readiness


def _settings(**overrides):
    data = {
        "APP_ENV": "production",
        "SECRET_KEY": "x" * 40,
        "FRONTEND_URL": "https://app.loanlens.ai",
        "DATABASE_PROVIDER": "postgresql",
        "DATABASE_URL": "postgresql://loanlens:secret@db.example.com:5432/loanlens",
        "DIRECT_URL": "postgresql://loanlens:secret@db.example.com:5432/loanlens",
        "PRISMA_AUTO_GENERATE_CLIENT": False,
        "PRISMA_SCHEMA_PATH": "./schema.prisma",
        "CLERK_SECRET_KEY": "sk_live_" + ("x" * 32),
        "CLERK_JWKS_URL": "https://api.clerk.com/v1/jwks",
        "CLERK_JWT_ISSUER": "https://trusted.clerk.accounts",
        "CLERK_JWT_AUDIENCE": "loanlens-api",
        "GOOGLE_API_KEY": "google-api-key",
        "OCR_PROVIDER_MODE": "hybrid",
        "GOOGLE_DOCUMENT_AI_PROJECT_ID": "loanlens-prod",
        "GOOGLE_DOCUMENT_AI_LOCATION": "us",
        "GOOGLE_DOCUMENT_AI_PROCESSOR_ID": "processor-123",
        "AWS_ACCESS_KEY_ID": "access-key",
        "AWS_SECRET_ACCESS_KEY": "secret-key",
        "AWS_REGION": "us-east-1",
        "S3_BUCKET_NAME": "loanlens-prod-documents",
        "AWS_S3_ENDPOINT_URL": "",
        "AWS_KMS_KEY_ID": "alias/loanlens-prod",
        "RETENTION_CASE_DAYS": 180,
        "RETENTION_DOCUMENT_DAYS": 180,
        "RETENTION_AUDIT_LOG_DAYS": 365,
        "RETENTION_BATCH_SIZE": 100,
        "ANALYSIS_JOBS_PATH": "./analysis_jobs",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _current_prisma_status():
    return SimpleNamespace(
        is_current=True,
        describe_mismatch=lambda: "client mismatch",
    )


def test_static_readiness_passes_for_hardened_config(monkeypatch):
    monkeypatch.setattr(readiness, "inspect_prisma_client_status", lambda settings: _current_prisma_status())

    checks = readiness.build_static_readiness_checks(_settings())

    assert not any(check.failed for check in checks)
    assert any(check.name == "analysis_job_queue" and check.status == readiness.READINESS_WARN for check in checks)


def test_static_readiness_fails_for_unsafe_production_config(monkeypatch):
    monkeypatch.setattr(readiness, "inspect_prisma_client_status", lambda settings: _current_prisma_status())

    checks = readiness.build_static_readiness_checks(
        _settings(
            APP_ENV="development",
            SECRET_KEY="your-secret-key-change-this",
            FRONTEND_URL="http://localhost:3000",
            DATABASE_PROVIDER="sqlite",
            DATABASE_URL="file:./dev.db",
            DIRECT_URL="",
            PRISMA_AUTO_GENERATE_CLIENT=True,
            CLERK_SECRET_KEY="",
            CLERK_JWT_ISSUER="",
            CLERK_JWT_AUDIENCE="",
            GOOGLE_API_KEY="",
            GOOGLE_DOCUMENT_AI_PROJECT_ID="",
            AWS_ACCESS_KEY_ID="",
            AWS_KMS_KEY_ID="",
            RETENTION_DOCUMENT_DAYS=0,
        )
    )

    failed_names = {check.name for check in checks if check.failed}
    assert {
        "app_env",
        "secret_key",
        "frontend_url",
        "database_provider",
        "database_url",
        "direct_url",
        "prisma_auto_generate",
        "clerk_secret",
        "clerk_jwt_issuer",
        "clerk_jwt_audience",
        "google_api_key",
        "document_ai_config",
        "s3_config",
        "kms_config",
        "retention_document_days",
    }.issubset(failed_names)


@pytest.mark.asyncio
async def test_live_readiness_checks_schema_audit_table_and_audit_write(monkeypatch):
    fake_db = SimpleNamespace(
        auditlog=SimpleNamespace(
            create=AsyncMock(return_value=SimpleNamespace(id="readiness_123")),
            delete=AsyncMock(),
        )
    )
    monkeypatch.setattr(readiness, "ensure_runtime_schema_compatibility", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        readiness,
        "get_table_columns",
        AsyncMock(return_value=set(readiness.REQUIRED_AUDIT_LOG_COLUMNS)),
    )

    checks = await readiness.build_live_readiness_checks(fake_db, _settings())

    assert [check.status for check in checks] == [
        readiness.READINESS_PASS,
        readiness.READINESS_PASS,
        readiness.READINESS_PASS,
    ]
    fake_db.auditlog.create.assert_awaited_once()
    fake_db.auditlog.delete.assert_awaited_once_with(where={"id": "readiness_123"})


@pytest.mark.asyncio
async def test_live_readiness_fails_when_audit_log_table_is_missing_columns(monkeypatch):
    fake_db = SimpleNamespace(
        auditlog=SimpleNamespace(create=AsyncMock(), delete=AsyncMock())
    )
    monkeypatch.setattr(readiness, "ensure_runtime_schema_compatibility", AsyncMock(return_value=[]))
    monkeypatch.setattr(readiness, "get_table_columns", AsyncMock(return_value={"id", "action"}))

    checks = await readiness.build_live_readiness_checks(fake_db, _settings())

    audit_check = next(check for check in checks if check.name == "audit_log_table")
    assert audit_check.status == readiness.READINESS_FAIL
    assert "created_at" in audit_check.metadata["missing"]


@pytest.mark.asyncio
async def test_readiness_report_fails_when_live_db_requested_without_db(monkeypatch):
    monkeypatch.setattr(readiness, "inspect_prisma_client_status", lambda settings: _current_prisma_status())

    report = await readiness.build_readiness_report(
        settings=_settings(),
        db=None,
        include_live_db=True,
    )

    assert report.ok is False
    assert report.exit_code() == 1
    assert any(check.name == "database_connection" for check in report.checks)

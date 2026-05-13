from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core import database


def _settings(**overrides):
    data = {
        "APP_ENV": "development",
        "DATABASE_PROVIDER": "postgresql",
        "DATABASE_URL": "postgresql://loanlens:loanlens@localhost:5432/loanlens",
        "PRISMA_SCHEMA_PATH": "./schema.prisma",
        "PRISMA_AUTO_GENERATE_CLIENT": True,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_resolve_prisma_schema_path_uses_canonical_schema_by_default():
    settings = _settings()

    resolved = database.resolve_prisma_schema_path(settings)

    assert resolved == (database.BACKEND_ROOT / "schema.prisma").resolve()


def test_resolve_prisma_schema_path_keeps_explicit_custom_path():
    custom_schema = "./custom/schema.prisma"
    settings = _settings(PRISMA_SCHEMA_PATH=custom_schema)

    resolved = database.resolve_prisma_schema_path(settings)

    assert resolved == (database.BACKEND_ROOT / custom_schema).resolve()


def test_ensure_prisma_client_ready_rejects_sqlite_runtime_config():
    with pytest.raises(database.PrismaClientGenerationError, match="requires PostgreSQL"):
        database.ensure_prisma_client_ready(
            _settings(
                DATABASE_PROVIDER="sqlite",
                DATABASE_URL="file:./legacy.db",
            )
        )


def test_ensure_prisma_client_ready_regenerates_mismatch_in_development(monkeypatch):
    stale = database.PrismaClientStatus(
        expected_schema_path=Path("expected.prisma"),
        expected_provider="postgresql",
        generated_schema_path=Path("packaged.prisma"),
        generated_source_schema_path=Path("source.prisma"),
        generated_provider="sqlite",
        schema_matches=False,
        provider_matches=False,
    )
    fresh = database.PrismaClientStatus(
        expected_schema_path=Path("expected.prisma"),
        expected_provider="postgresql",
        generated_schema_path=Path("packaged.prisma"),
        generated_source_schema_path=Path("source.prisma"),
        generated_provider="postgresql",
        schema_matches=True,
        provider_matches=True,
    )
    statuses = [stale, fresh]
    fake_module = SimpleNamespace(Prisma=object)
    generate_calls: list[Path] = []

    monkeypatch.setattr(database, "inspect_prisma_client_status", lambda settings=None: statuses.pop(0))
    monkeypatch.setattr(database, "_run_prisma_generate", lambda schema_path: generate_calls.append(schema_path))
    monkeypatch.setattr(database, "_reload_prisma_modules", lambda: fake_module)

    prisma_class = database.ensure_prisma_client_ready(
        _settings(
            APP_ENV="development",
            DATABASE_PROVIDER="postgresql",
            DATABASE_URL="postgresql://loanlens:loanlens@localhost:5432/loanlens",
            PRISMA_AUTO_GENERATE_CLIENT=True,
        )
    )

    assert prisma_class is object
    assert generate_calls == [Path("expected.prisma")]


def test_ensure_prisma_client_ready_raises_in_strict_env(monkeypatch):
    stale = database.PrismaClientStatus(
        expected_schema_path=Path("expected.prisma"),
        expected_provider="postgresql",
        generated_schema_path=Path("packaged.prisma"),
        generated_source_schema_path=Path("source.prisma"),
        generated_provider="sqlite",
        schema_matches=False,
        provider_matches=False,
    )
    monkeypatch.setattr(database, "inspect_prisma_client_status", lambda settings=None: stale)

    with pytest.raises(database.PrismaClientGenerationError, match="Generated Prisma client is stale"):
        database.ensure_prisma_client_ready(
            _settings(
                APP_ENV="production",
                DATABASE_PROVIDER="postgresql",
                DATABASE_URL="postgresql://loanlens:loanlens@localhost:5432/loanlens",
                PRISMA_AUTO_GENERATE_CLIENT=False,
            )
        )


@pytest.mark.asyncio
async def test_ensure_runtime_schema_compatibility_adds_missing_analysis_columns_in_development():
    fake_db = SimpleNamespace(
        query_raw=AsyncMock(
            side_effect=[
                [
                {"column_name": "id"},
                {"column_name": "document_id"},
                {"column_name": "risk_score"},
                {"column_name": "confidence"},
                {"column_name": "recommendation"},
                {"column_name": "extracted_fields"},
                {"column_name": "risk_alerts"},
                {"column_name": "summary"},
                {"column_name": "processing_time_seconds"},
                {"column_name": "model_used"},
                {"column_name": "raw_response"},
                {"column_name": "created_at"},
                ],
                [
                    {"column_name": "id"},
                    {"column_name": "case_id"},
                    {"column_name": "case_status"},
                    {"column_name": "risk_score"},
                    {"column_name": "confidence"},
                    {"column_name": "recommendation"},
                    {"column_name": "decision_status"},
                    {"column_name": "decision_recommendation"},
                    {"column_name": "decision_reason"},
                    {"column_name": "extraction_confidence"},
                    {"column_name": "risk_confidence"},
                    {"column_name": "data_completeness"},
                    {"column_name": "required_followups_json"},
                    {"column_name": "analysis_limitations_json"},
                    {"column_name": "extracted_fields"},
                    {"column_name": "risk_alerts"},
                    {"column_name": "summary"},
                    {"column_name": "processing_time_seconds"},
                    {"column_name": "model_used"},
                    {"column_name": "raw_response"},
                    {"column_name": "created_at"},
                ],
            ]
        ),
        execute_raw=AsyncMock(return_value=None),
    )

    missing = await database.ensure_runtime_schema_compatibility(
        fake_db,
        _settings(APP_ENV="development"),
    )

    assert missing == [
        "decision_status",
        "decision_recommendation",
        "decision_reason",
        "extraction_confidence",
        "risk_confidence",
        "data_completeness",
        "required_followups_json",
        "analysis_limitations_json",
        "is_final",
    ]
    assert fake_db.execute_raw.await_count == len(missing)


@pytest.mark.asyncio
async def test_ensure_runtime_schema_compatibility_raises_in_strict_env():
    fake_db = SimpleNamespace(
        query_raw=AsyncMock(side_effect=[[{"column_name": "id"}], [{"column_name": "id"}]]),
        execute_raw=AsyncMock(return_value=None),
    )

    with pytest.raises(database.PrismaClientGenerationError, match="missing required analyses columns"):
        await database.ensure_runtime_schema_compatibility(
            fake_db,
            _settings(APP_ENV="production"),
        )

    fake_db.execute_raw.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_runtime_schema_compatibility_raises_for_missing_case_analysis_columns_in_strict_env():
    fake_db = SimpleNamespace(
        query_raw=AsyncMock(
            side_effect=[
                [
                    {"column_name": "id"},
                    {"column_name": "document_id"},
                    {"column_name": "risk_score"},
                    {"column_name": "confidence"},
                    {"column_name": "recommendation"},
                    {"column_name": "decision_status"},
                    {"column_name": "decision_recommendation"},
                    {"column_name": "decision_reason"},
                    {"column_name": "extraction_confidence"},
                    {"column_name": "risk_confidence"},
                    {"column_name": "data_completeness"},
                    {"column_name": "required_followups_json"},
                    {"column_name": "analysis_limitations_json"},
                    {"column_name": "extracted_fields"},
                    {"column_name": "risk_alerts"},
                    {"column_name": "summary"},
                    {"column_name": "processing_time_seconds"},
                    {"column_name": "model_used"},
                    {"column_name": "raw_response"},
                    {"column_name": "created_at"},
                ],
                [
                    {"column_name": "id"},
                    {"column_name": "case_id"},
                    {"column_name": "case_status"},
                    {"column_name": "risk_score"},
                    {"column_name": "confidence"},
                    {"column_name": "recommendation"},
                    {"column_name": "decision_status"},
                    {"column_name": "decision_recommendation"},
                    {"column_name": "decision_reason"},
                    {"column_name": "extraction_confidence"},
                    {"column_name": "risk_confidence"},
                    {"column_name": "data_completeness"},
                    {"column_name": "required_followups_json"},
                    {"column_name": "analysis_limitations_json"},
                    {"column_name": "extracted_fields"},
                    {"column_name": "risk_alerts"},
                    {"column_name": "summary"},
                    {"column_name": "processing_time_seconds"},
                    {"column_name": "model_used"},
                    {"column_name": "raw_response"},
                    {"column_name": "created_at"},
                ],
            ]
        ),
        execute_raw=AsyncMock(return_value=None),
    )

    with pytest.raises(database.PrismaClientGenerationError, match="missing required case_analyses columns"):
        await database.ensure_runtime_schema_compatibility(
            fake_db,
            _settings(APP_ENV="production"),
        )

    fake_db.execute_raw.assert_not_awaited()

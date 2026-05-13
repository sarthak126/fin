"""
Database and Prisma client setup.

This module guards backend startup against a stale generated Prisma client.
The Python client bundles a packaged schema and active provider at generation
time, so we validate that against the runtime-selected schema before creating
the shared client instance.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
from prisma.errors import ClientNotConnectedError, HTTPClientClosedError

from core.config import Settings, get_settings


logger = logging.getLogger("loanlens.database")

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PRISMA_SCHEMA = Path("./schema.prisma")
GENERATED_PRISMA_MODULES = (
    "prisma.enums",
    "prisma.fields",
    "prisma.metadata",
    "prisma.types",
    "prisma.models",
    "prisma.partials",
    "prisma.bases",
    "prisma.actions",
    "prisma.client",
    "prisma",
)

LEGACY_ANALYSIS_COMPAT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("decision_status", "TEXT"),
    ("decision_recommendation", "TEXT"),
    ("decision_reason", "TEXT"),
    ("extraction_confidence", "DOUBLE PRECISION"),
    ("risk_confidence", "DOUBLE PRECISION"),
    ("data_completeness", "DOUBLE PRECISION"),
    ("required_followups_json", "TEXT"),
    ("analysis_limitations_json", "TEXT"),
)
LEGACY_CASE_ANALYSIS_COMPAT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("is_final", "BOOLEAN NOT NULL DEFAULT FALSE"),
)


class PrismaClientGenerationError(RuntimeError):
    """Raised when the generated Prisma client does not match runtime config."""


class DatabaseUnavailableError(RuntimeError):
    """Raised when the Prisma query engine or database cannot be reached."""


@dataclass(frozen=True)
class PrismaClientStatus:
    expected_schema_path: Path
    expected_provider: str
    generated_schema_path: Path
    generated_source_schema_path: Path
    generated_provider: str
    schema_matches: bool
    provider_matches: bool

    @property
    def is_current(self) -> bool:
        return self.schema_matches and self.provider_matches

    def describe_mismatch(self) -> str:
        reasons: list[str] = []
        if not self.provider_matches:
            reasons.append(
                f"provider mismatch (expected {self.expected_provider}, generated {self.generated_provider})"
            )
        if not self.schema_matches:
            reasons.append("schema mismatch")

        reason_text = ", ".join(reasons) or "unknown mismatch"
        return (
            f"Generated Prisma client is stale: {reason_text}. "
            f"Runtime expects schema {self.expected_schema_path}, "
            f"but the packaged client was generated from {self.generated_source_schema_path} "
            f"and currently bundles {self.generated_schema_path}. "
            f"Run `{sys.executable} -m prisma generate --schema {self.expected_schema_path}`."
        )


def _normalize_provider(provider: str | None) -> str:
    normalized = (provider or "").strip().lower()
    if normalized == "postgres":
        return "postgresql"
    return normalized


def _provider_from_database_url(database_url: str | None) -> str:
    url = (database_url or "").strip().lower()
    if url.startswith(("postgresql://", "postgres://")):
        return "postgresql"
    if url.startswith(("file:", "sqlite:", "sqlite://")):
        return "sqlite"
    return ""


def resolve_prisma_schema_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    candidate = Path((settings.PRISMA_SCHEMA_PATH or "").strip() or DEFAULT_PRISMA_SCHEMA)

    if not candidate.is_absolute():
        candidate = (BACKEND_ROOT / candidate).resolve()

    return candidate


def _validate_postgresql_runtime_config(settings: Settings) -> None:
    configured_provider = _normalize_provider(settings.DATABASE_PROVIDER)
    if configured_provider and configured_provider != "postgresql":
        raise PrismaClientGenerationError(
            "LoanLens now requires PostgreSQL. Set DATABASE_PROVIDER=postgresql."
        )

    url_provider = _provider_from_database_url(settings.DATABASE_URL)
    if url_provider == "sqlite":
        raise PrismaClientGenerationError(
            "LoanLens no longer supports SQLite DATABASE_URL values. "
            "Set DATABASE_URL to a PostgreSQL connection string."
        )


def _read_schema_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()


def _extract_provider(schema_text: str) -> str:
    match = re.search(
        r"datasource\s+\w+\s*\{.*?provider\s*=\s*\"([^\"]+)\"",
        schema_text,
        flags=re.DOTALL,
    )
    if not match:
        raise PrismaClientGenerationError("Unable to determine datasource provider from Prisma schema.")
    return _normalize_provider(match.group(1))


def _import_prisma_client_module() -> ModuleType:
    return importlib.import_module("prisma.client")


def inspect_prisma_client_status(settings: Settings | None = None) -> PrismaClientStatus:
    settings = settings or get_settings()
    expected_schema_path = resolve_prisma_schema_path(settings)
    if not expected_schema_path.exists():
        raise PrismaClientGenerationError(
            f"Configured Prisma schema does not exist: {expected_schema_path}"
        )

    client_module = _import_prisma_client_module()
    generated_schema_path = Path(client_module.PACKAGED_SCHEMA_PATH).resolve()
    generated_source_schema_path = Path(client_module.SCHEMA_PATH).resolve()

    expected_schema_text = _read_schema_text(expected_schema_path)
    generated_schema_text = _read_schema_text(generated_schema_path)

    expected_provider = _extract_provider(expected_schema_text)
    generated_provider = _extract_provider(generated_schema_text)

    return PrismaClientStatus(
        expected_schema_path=expected_schema_path,
        expected_provider=expected_provider,
        generated_schema_path=generated_schema_path,
        generated_source_schema_path=generated_source_schema_path,
        generated_provider=generated_provider,
        schema_matches=expected_schema_text == generated_schema_text,
        provider_matches=expected_provider == generated_provider,
    )


def _run_prisma_generate(expected_schema_path: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "prisma",
        "generate",
        "--schema",
        str(expected_schema_path),
    ]
    result = subprocess.run(
        command,
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout or "").strip()
        raise PrismaClientGenerationError(
            f"Failed to regenerate Prisma client for {expected_schema_path}: {output}"
        )


def _reload_prisma_modules() -> ModuleType:
    reloaded_client: ModuleType | None = None
    importlib.invalidate_caches()

    for module_name in GENERATED_PRISMA_MODULES:
        module = sys.modules.get(module_name)
        if module is None:
            module = importlib.import_module(module_name)
        else:
            module = importlib.reload(module)

        if module_name == "prisma.client":
            reloaded_client = module

    if reloaded_client is None:
        reloaded_client = _import_prisma_client_module()

    return reloaded_client


def _should_auto_regenerate(settings: Settings) -> bool:
    return settings.APP_ENV == "development" and settings.PRISMA_AUTO_GENERATE_CLIENT


def ensure_prisma_client_ready(settings: Settings | None = None) -> type[Any]:
    settings = settings or get_settings()
    _validate_postgresql_runtime_config(settings)
    status = inspect_prisma_client_status(settings)
    if status.is_current:
        return _import_prisma_client_module().Prisma

    if _should_auto_regenerate(settings):
        logger.warning(
            "Detected stale Prisma client at startup; regenerating for schema=%s provider=%s",
            status.expected_schema_path,
            status.expected_provider,
        )
        _run_prisma_generate(status.expected_schema_path)
        client_module = _reload_prisma_modules()
        refreshed = inspect_prisma_client_status(settings)
        if refreshed.is_current:
            logger.info(
                "Prisma client regenerated successfully for schema=%s provider=%s",
                refreshed.expected_schema_path,
                refreshed.expected_provider,
            )
            return client_module.Prisma
        raise PrismaClientGenerationError(refreshed.describe_mismatch())

    raise PrismaClientGenerationError(status.describe_mismatch())


Prisma = ensure_prisma_client_ready()
db = Prisma()


def is_database_unavailable_error(exc: BaseException) -> bool:
    """Return True for low-level Prisma connectivity failures."""
    return isinstance(
        exc,
        (
            asyncio.TimeoutError,
            ClientNotConnectedError,
            HTTPClientClosedError,
            httpx.HTTPError,
            OSError,
        ),
    )


async def verify_database_connection(db_client: Any, *, timeout_seconds: float = 3.0) -> None:
    """Run a cheap query so health checks do not trust stale client state."""
    try:
        await asyncio.wait_for(db_client.query_raw("SELECT 1"), timeout=timeout_seconds)
    except Exception as exc:
        if is_database_unavailable_error(exc):
            raise DatabaseUnavailableError("Database connection is unavailable") from exc
        raise


async def get_db():
    """
    Dependency to provide the Prisma client to API routes.
    """
    yield db


async def get_table_columns(db_client: Any, table_name: str, schema_name: str = "public") -> set[str]:
    """Return the currently available columns for a table."""
    rows = await db_client.query_raw(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
        """,
        schema_name,
        table_name,
    )
    return {str(row["column_name"]) for row in rows}


async def ensure_runtime_schema_compatibility(
    db_client: Any,
    settings: Settings | None = None,
) -> list[str]:
    """
    Backfill additive columns required by the current Prisma schema.

    Older development databases may still have legacy `analyses` or
    `case_analyses` layouts. Prisma selects all modeled fields, so missing
    nullable/defaulted columns can break otherwise simple read and write paths.
    """
    settings = settings or get_settings()
    existing_columns = await get_table_columns(db_client, "analyses")
    missing_columns = [
        column_name
        for column_name, _column_type in LEGACY_ANALYSIS_COMPAT_COLUMNS
        if column_name not in existing_columns
    ]

    if missing_columns and settings.APP_ENV != "development":
        raise PrismaClientGenerationError(
            "Database schema is missing required analyses columns: "
            f"{', '.join(missing_columns)}. Run the pending database migration."
        )

    for column_name, column_type in LEGACY_ANALYSIS_COMPAT_COLUMNS:
        if column_name in existing_columns:
            continue
        await db_client.execute_raw(
            f'ALTER TABLE "analyses" ADD COLUMN IF NOT EXISTS "{column_name}" {column_type}'
        )

    existing_case_analysis_columns = await get_table_columns(db_client, "case_analyses")
    missing_case_analysis_columns = [
        column_name
        for column_name, _column_type in LEGACY_CASE_ANALYSIS_COMPAT_COLUMNS
        if column_name not in existing_case_analysis_columns
    ]

    if missing_case_analysis_columns and settings.APP_ENV != "development":
        raise PrismaClientGenerationError(
            "Database schema is missing required case_analyses columns: "
            f"{', '.join(missing_case_analysis_columns)}. Run the pending database migration."
        )

    for column_name, column_type in LEGACY_CASE_ANALYSIS_COMPAT_COLUMNS:
        if column_name in existing_case_analysis_columns:
            continue
        await db_client.execute_raw(
            f'ALTER TABLE "case_analyses" ADD COLUMN IF NOT EXISTS "{column_name}" {column_type}'
        )

    return missing_columns + missing_case_analysis_columns

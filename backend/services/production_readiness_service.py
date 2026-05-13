"""
Production readiness checks for deployment gates.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import httpx

from core.config import Settings, get_settings
from core.database import (
    PrismaClientGenerationError,
    ensure_runtime_schema_compatibility,
    get_table_columns,
    inspect_prisma_client_status,
)
from services.storage_service import (
    delete_password,
    download_file,
    get_boto3_clients,
    retrieve_password,
    store_password,
    upload_file,
)

READINESS_PASS = "pass"
READINESS_WARN = "warn"
READINESS_FAIL = "fail"

REQUIRED_AUDIT_LOG_COLUMNS = {
    "id",
    "user_id",
    "action",
    "resource_type",
    "resource_id",
    "metadata_json",
    "ip_address",
    "created_at",
}


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return self.status == READINESS_FAIL

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReadinessReport:
    checks: list[ReadinessCheck]

    @property
    def ok(self) -> bool:
        return not any(check.failed for check in self.checks)

    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def model_dump(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "summary": {
                "passed": sum(1 for check in self.checks if check.status == READINESS_PASS),
                "warnings": sum(1 for check in self.checks if check.status == READINESS_WARN),
                "failed": sum(1 for check in self.checks if check.status == READINESS_FAIL),
            },
            "checks": [check.model_dump() for check in self.checks],
        }


def _value(settings: Any, name: str, default: Any = "") -> Any:
    return getattr(settings, name, default)


def _is_blank(value: Any) -> bool:
    return not str(value or "").strip()


def _is_placeholder(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {
        "",
        "changeme",
        "change-me",
        "replace_me",
        "replace-me",
        "your-secret-key-change-this",
        "sk_test_replace_me",
        "pk_test_replace_me",
    }


def _is_postgres_url(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized.startswith(("postgresql://", "postgres://"))


def _is_local_url(value: Any) -> bool:
    parsed = urlparse(str(value or ""))
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local")


def _fail(name: str, detail: str, **metadata: Any) -> ReadinessCheck:
    return ReadinessCheck(name=name, status=READINESS_FAIL, detail=detail, metadata=metadata)


def _warn(name: str, detail: str, **metadata: Any) -> ReadinessCheck:
    return ReadinessCheck(name=name, status=READINESS_WARN, detail=detail, metadata=metadata)


def _pass(name: str, detail: str, **metadata: Any) -> ReadinessCheck:
    return ReadinessCheck(name=name, status=READINESS_PASS, detail=detail, metadata=metadata)


def _check_secret_key(settings: Any) -> ReadinessCheck:
    secret = str(_value(settings, "SECRET_KEY", "") or "")
    if _is_placeholder(secret) or len(secret) < 32:
        return _fail(
            "secret_key",
            "SECRET_KEY must be a non-placeholder value with at least 32 characters.",
            configured_length=len(secret),
        )
    return _pass("secret_key", "SECRET_KEY is present and non-placeholder.")


def _check_frontend_url(settings: Any, *, require_production_env: bool) -> ReadinessCheck:
    frontend_url = str(_value(settings, "FRONTEND_URL", "") or "").strip()
    parsed = urlparse(frontend_url)
    if not parsed.scheme or not parsed.netloc:
        return _fail("frontend_url", "FRONTEND_URL must be an absolute URL.", value=frontend_url)
    if require_production_env and parsed.scheme != "https":
        return _fail("frontend_url", "FRONTEND_URL must use HTTPS in production.", value=frontend_url)
    if require_production_env and _is_local_url(frontend_url):
        return _fail("frontend_url", "FRONTEND_URL cannot point at localhost in production.", value=frontend_url)
    return _pass("frontend_url", "FRONTEND_URL is production-safe.", value=frontend_url)


def _check_database_config(settings: Any) -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []
    provider = str(_value(settings, "DATABASE_PROVIDER", "") or "").strip().lower()
    if provider != "postgresql":
        checks.append(_fail("database_provider", "DATABASE_PROVIDER must be postgresql.", value=provider))
    else:
        checks.append(_pass("database_provider", "DATABASE_PROVIDER is postgresql."))

    database_url = _value(settings, "DATABASE_URL", "")
    if not _is_postgres_url(database_url):
        checks.append(_fail("database_url", "DATABASE_URL must be a PostgreSQL URL."))
    else:
        checks.append(_pass("database_url", "DATABASE_URL uses PostgreSQL."))

    direct_url = _value(settings, "DIRECT_URL", "")
    if not _is_postgres_url(direct_url):
        checks.append(_fail("direct_url", "DIRECT_URL must be a direct PostgreSQL URL."))
    else:
        checks.append(_pass("direct_url", "DIRECT_URL uses PostgreSQL."))

    if bool(_value(settings, "PRISMA_AUTO_GENERATE_CLIENT", False)):
        checks.append(_fail("prisma_auto_generate", "PRISMA_AUTO_GENERATE_CLIENT must be false in production."))
    else:
        checks.append(_pass("prisma_auto_generate", "Prisma auto-generation is disabled."))

    return checks


def _check_clerk_config(settings: Any) -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []
    if _is_placeholder(_value(settings, "CLERK_SECRET_KEY", "")):
        checks.append(_fail("clerk_secret", "CLERK_SECRET_KEY must be configured."))
    else:
        checks.append(_pass("clerk_secret", "CLERK_SECRET_KEY is configured."))

    jwks_url = str(_value(settings, "CLERK_JWKS_URL", "") or "").strip()
    if not jwks_url.startswith("https://"):
        checks.append(_fail("clerk_jwks_url", "CLERK_JWKS_URL must be an HTTPS Clerk JWKS URL.", value=jwks_url))
    else:
        checks.append(_pass("clerk_jwks_url", "CLERK_JWKS_URL is HTTPS.", value=jwks_url))

    if _is_blank(_value(settings, "CLERK_JWT_ISSUER", "")):
        checks.append(_fail("clerk_jwt_issuer", "CLERK_JWT_ISSUER must be configured in production."))
    else:
        checks.append(_pass("clerk_jwt_issuer", "CLERK_JWT_ISSUER is configured."))

    if _is_blank(_value(settings, "CLERK_JWT_AUDIENCE", "")):
        checks.append(_fail("clerk_jwt_audience", "CLERK_JWT_AUDIENCE must be configured in production."))
    else:
        checks.append(_pass("clerk_jwt_audience", "CLERK_JWT_AUDIENCE is configured."))

    return checks


def _check_ai_config(settings: Any) -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []
    if _is_placeholder(_value(settings, "GOOGLE_API_KEY", "")):
        checks.append(_fail("google_api_key", "GOOGLE_API_KEY must be configured for analysis and Ask AI."))
    else:
        checks.append(_pass("google_api_key", "GOOGLE_API_KEY is configured."))

    ocr_mode = str(_value(settings, "OCR_PROVIDER_MODE", "hybrid") or "hybrid").strip().lower()
    if ocr_mode not in {"hybrid", "document_ai", "tesseract"}:
        checks.append(_fail("ocr_provider_mode", "OCR_PROVIDER_MODE must be hybrid, document_ai, or tesseract.", value=ocr_mode))
    else:
        checks.append(_pass("ocr_provider_mode", "OCR_PROVIDER_MODE is supported.", value=ocr_mode))

    if ocr_mode in {"hybrid", "document_ai"}:
        missing = [
            name
            for name in (
                "GOOGLE_DOCUMENT_AI_PROJECT_ID",
                "GOOGLE_DOCUMENT_AI_LOCATION",
                "GOOGLE_DOCUMENT_AI_PROCESSOR_ID",
            )
            if _is_blank(_value(settings, name, ""))
        ]
        if missing:
            checks.append(
                _fail(
                    "document_ai_config",
                    "Google Document AI OCR settings must be configured for production OCR.",
                    missing=missing,
                )
            )
        else:
            checks.append(_pass("document_ai_config", "Google Document AI OCR settings are configured."))

    return checks


def _check_storage_config(settings: Any) -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []
    missing = [
        name
        for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "S3_BUCKET_NAME")
        if _is_blank(_value(settings, name, ""))
    ]
    if missing:
        checks.append(_fail("s3_config", "Remote S3 storage must be configured in production.", missing=missing))
    else:
        checks.append(_pass("s3_config", "Remote S3 storage settings are configured."))

    if _is_blank(_value(settings, "AWS_KMS_KEY_ID", "")):
        checks.append(_fail("kms_config", "AWS_KMS_KEY_ID must be configured for production storage encryption."))
    else:
        checks.append(_pass("kms_config", "AWS_KMS_KEY_ID is configured."))

    endpoint = str(_value(settings, "AWS_S3_ENDPOINT_URL", "") or "").strip()
    if endpoint and _is_local_url(endpoint):
        checks.append(_fail("s3_endpoint", "AWS_S3_ENDPOINT_URL cannot point at a local endpoint in production.", value=endpoint))
    elif endpoint:
        checks.append(_warn("s3_endpoint", "Custom S3 endpoint configured; verify this is intentional.", value=endpoint))
    else:
        checks.append(_pass("s3_endpoint", "Using default AWS S3 endpoint."))

    return checks


def _check_retention_config(settings: Any) -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []
    for name in ("RETENTION_CASE_DAYS", "RETENTION_DOCUMENT_DAYS", "RETENTION_AUDIT_LOG_DAYS"):
        value = int(_value(settings, name, 0) or 0)
        if value <= 0:
            checks.append(_fail(name.lower(), f"{name} must be greater than zero in production.", value=value))
        else:
            checks.append(_pass(name.lower(), f"{name} is enabled.", value=value))

    batch_size = int(_value(settings, "RETENTION_BATCH_SIZE", 0) or 0)
    if batch_size <= 0:
        checks.append(_fail("retention_batch_size", "RETENTION_BATCH_SIZE must be greater than zero.", value=batch_size))
    else:
        checks.append(_pass("retention_batch_size", "RETENTION_BATCH_SIZE is valid.", value=batch_size))

    return checks


def _check_prisma_client(settings: Any) -> ReadinessCheck:
    try:
        status = inspect_prisma_client_status(settings)
    except Exception as exc:
        return _fail("prisma_client", f"Unable to inspect generated Prisma client: {exc}")
    if not status.is_current:
        return _fail("prisma_client", status.describe_mismatch())
    return _pass("prisma_client", "Generated Prisma client matches the runtime schema/provider.")


def build_static_readiness_checks(
    settings: Settings,
    *,
    require_production_env: bool = True,
) -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []

    app_env = str(_value(settings, "APP_ENV", "") or "").strip().lower()
    if require_production_env and app_env != "production":
        checks.append(_fail("app_env", "APP_ENV must be production for this gate.", value=app_env))
    elif app_env == "production":
        checks.append(_pass("app_env", "APP_ENV is production.", value=app_env))
    else:
        checks.append(_warn("app_env", "APP_ENV is not production; running a non-production readiness check.", value=app_env))

    checks.append(_check_secret_key(settings))
    checks.append(_check_frontend_url(settings, require_production_env=require_production_env))
    checks.extend(_check_database_config(settings))
    checks.extend(_check_clerk_config(settings))
    checks.extend(_check_ai_config(settings))
    checks.extend(_check_storage_config(settings))
    checks.extend(_check_retention_config(settings))
    checks.append(_check_prisma_client(settings))

    jobs_path = str(_value(settings, "ANALYSIS_JOBS_PATH", "") or "").strip()
    checks.append(
        _warn(
            "analysis_job_queue",
            "Analysis jobs still use filesystem manifests; production must provide persistent single-writer storage or replace this queue.",
            path=jobs_path,
        )
    )
    return checks


async def check_database_schema(db: Any, settings: Settings) -> ReadinessCheck:
    try:
        await ensure_runtime_schema_compatibility(db, settings)
    except PrismaClientGenerationError as exc:
        return _fail("database_schema", str(exc))
    except Exception as exc:
        return _fail("database_schema", f"Unable to verify database schema: {exc}")
    return _pass("database_schema", "Database schema compatibility checks passed.")


async def check_audit_log_table(db: Any) -> ReadinessCheck:
    try:
        columns = await get_table_columns(db, "audit_logs")
    except Exception as exc:
        return _fail("audit_log_table", f"Unable to inspect audit_logs table: {exc}")

    missing = sorted(REQUIRED_AUDIT_LOG_COLUMNS - columns)
    if missing:
        return _fail("audit_log_table", "audit_logs table is missing required columns.", missing=missing)
    return _pass("audit_log_table", "audit_logs table has required columns.")


async def check_audit_write(db: Any) -> ReadinessCheck:
    audit_id = f"readiness_{uuid.uuid4().hex}"
    try:
        record = await db.auditlog.create(
            data={
                "id": audit_id,
                "user_id": None,
                "action": "readiness.audit_write",
                "resource_type": "readiness",
                "resource_id": audit_id,
                "metadata_json": json.dumps({"source": "production_readiness"}),
                "ip_address": None,
            }
        )
        await db.auditlog.delete(where={"id": getattr(record, "id", audit_id)})
    except Exception as exc:
        return _fail("audit_write", f"Unable to write/delete an audit log readiness row: {exc}")
    return _pass("audit_write", "Audit log write/delete round-trip passed.")


async def check_clerk_jwks(settings: Settings) -> ReadinessCheck:
    jwks_url = str(_value(settings, "CLERK_JWKS_URL", "") or "").strip()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                jwks_url,
                headers={"Authorization": f"Bearer {_value(settings, 'CLERK_SECRET_KEY', '')}"},
            )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return _fail("clerk_jwks_live", f"Unable to fetch Clerk JWKS: {exc}")

    if not payload.get("keys"):
        return _fail("clerk_jwks_live", "Clerk JWKS response did not include signing keys.")
    return _pass("clerk_jwks_live", "Clerk JWKS endpoint returned signing keys.")


async def check_storage_roundtrip() -> ReadinessCheck:
    s3, kms = get_boto3_clients()
    if not s3:
        return _fail("storage_roundtrip", "Remote S3 client is not configured.")

    key = f"readiness/{uuid.uuid4().hex}.pdf"
    password = "readiness-secret"
    sample_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    try:
        file_url = await upload_file(key, sample_pdf, "application/pdf")
        downloaded = await download_file(file_url)
        if downloaded != sample_pdf:
            return _fail("storage_roundtrip", "Downloaded readiness object did not match uploaded bytes.")

        await store_password(key, password)
        stored_password = await retrieve_password(key)
        if stored_password != password:
            return _fail("storage_roundtrip", "Password sidecar did not round-trip through storage.")

        settings = get_settings()
        bucket_name = settings.S3_BUCKET_NAME
        file_head = await asyncio.to_thread(s3.head_object, Bucket=bucket_name, Key=key)
        password_head = await asyncio.to_thread(s3.head_object, Bucket=bucket_name, Key=f"{key}.pwd")
        expected_sse = "aws:kms" if settings.AWS_KMS_KEY_ID else "AES256"
        for head in (file_head, password_head):
            actual_sse = head.get("ServerSideEncryption")
            if actual_sse != expected_sse:
                return _fail(
                    "storage_roundtrip",
                    "S3 object encryption did not match the expected mode.",
                    expected=expected_sse,
                    actual=actual_sse,
                )
        return _pass(
            "storage_roundtrip",
            "S3 upload/download/password round-trip passed.",
            server_side_encryption=expected_sse,
        )
    except Exception as exc:
        return _fail("storage_roundtrip", f"Unable to verify S3 storage round-trip: {exc}")
    finally:
        try:
            await delete_password(key)
        finally:
            try:
                await asyncio.to_thread(s3.delete_object, Bucket=get_settings().S3_BUCKET_NAME, Key=key)
            except Exception:
                pass


async def build_live_readiness_checks(
    db: Any,
    settings: Settings,
    *,
    include_storage: bool = False,
    include_clerk: bool = False,
    storage_checker: Callable[[], Awaitable[ReadinessCheck]] = check_storage_roundtrip,
    clerk_checker: Callable[[Settings], Awaitable[ReadinessCheck]] = check_clerk_jwks,
) -> list[ReadinessCheck]:
    checks = [
        await check_database_schema(db, settings),
        await check_audit_log_table(db),
        await check_audit_write(db),
    ]

    if include_storage:
        checks.append(await storage_checker())
    if include_clerk:
        checks.append(await clerk_checker(settings))

    return checks


async def build_readiness_report(
    *,
    settings: Settings,
    db: Any | None = None,
    include_live_db: bool = True,
    include_storage: bool = False,
    include_clerk: bool = False,
    require_production_env: bool = True,
) -> ReadinessReport:
    checks = build_static_readiness_checks(
        settings,
        require_production_env=require_production_env,
    )
    if include_live_db:
        if db is None:
            checks.append(_fail("database_connection", "Live database checks require a connected Prisma client."))
        else:
            checks.extend(
                await build_live_readiness_checks(
                    db,
                    settings,
                    include_storage=include_storage,
                    include_clerk=include_clerk,
                )
            )
    return ReadinessReport(checks=checks)

"""
Smoke-test a production-like backend stack against live Postgres and S3/KMS.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.config import get_settings
from services.storage_service import (
    delete_password,
    download_file,
    get_boto3_clients,
    retrieve_password,
    store_password,
    upload_file,
)

settings = get_settings()


async def wait_for_backend(base_url: str, timeout_seconds: int = 120) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_error = "backend did not respond"

    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.monotonic() < deadline:
            try:
                live = await client.get(f"{base_url}/health/live")
                ready = await client.get(f"{base_url}/health/ready")
                if live.status_code == 200 and ready.status_code == 200:
                    return {
                        "live": live.json(),
                        "ready": ready.json(),
                    }
                last_error = f"live={live.status_code} ready={ready.status_code}"
            except Exception as exc:  # pragma: no cover - exercised in live rehearsal
                last_error = str(exc)

            await asyncio.sleep(2)

    raise RuntimeError(f"Timed out waiting for backend readiness: {last_error}")


async def verify_storage_roundtrip() -> dict[str, object]:
    s3, kms = get_boto3_clients()
    if not s3:
        raise RuntimeError("Remote S3 storage is not configured for rehearsal")

    kms_identifiers: set[str] = set()
    if settings.AWS_KMS_KEY_ID and kms:
        metadata = await asyncio.to_thread(kms.describe_key, KeyId=settings.AWS_KMS_KEY_ID)
        key_metadata = metadata["KeyMetadata"]
        kms_identifiers.update(
            {
                settings.AWS_KMS_KEY_ID,
                key_metadata.get("KeyId", ""),
                key_metadata.get("Arn", ""),
            }
        )

    key = f"rehearsal/{uuid.uuid4()}.pdf"
    password = "rehearsal-secret-pass"
    sample_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    file_url = await upload_file(key, sample_pdf, "application/pdf")
    expected_sse = "aws:kms" if settings.AWS_KMS_KEY_ID else "AES256"

    try:
        if not file_url.startswith("s3://"):
            raise RuntimeError(f"Expected S3 storage during rehearsal, got {file_url}")

        downloaded = await download_file(file_url)
        if downloaded != sample_pdf:
            raise RuntimeError("Downloaded rehearsal object does not match uploaded bytes")

        await store_password(key, password)
        retrieved_password = await retrieve_password(key)
        if retrieved_password != password:
            raise RuntimeError("Stored password did not round-trip through remote storage")

        file_head = await asyncio.to_thread(
            s3.head_object,
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
        )
        pwd_head = await asyncio.to_thread(
            s3.head_object,
            Bucket=settings.S3_BUCKET_NAME,
            Key=f"{key}.pwd",
        )

        for head in (file_head, pwd_head):
            if head.get("ServerSideEncryption") != expected_sse:
                raise RuntimeError(
                    f"Expected {expected_sse} remote encryption, got {head.get('ServerSideEncryption')}"
                )

            if expected_sse == "aws:kms":
                kms_value = head.get("SSEKMSKeyId", "")
                if kms_identifiers and not any(identifier and identifier in kms_value for identifier in kms_identifiers):
                    raise RuntimeError(
                        f"Expected KMS key {settings.AWS_KMS_KEY_ID}, got {kms_value}"
                    )

        return {
            "file_url": file_url,
            "server_side_encryption": expected_sse,
            "bucket": settings.S3_BUCKET_NAME,
        }
    finally:
        await delete_password(key)
        await asyncio.to_thread(s3.delete_object, Bucket=settings.S3_BUCKET_NAME, Key=key)


async def main() -> None:
    backend_url = os.getenv("REHEARSAL_BACKEND_URL", "http://localhost:8000")
    health = await wait_for_backend(backend_url)
    storage = await verify_storage_roundtrip()
    print(json.dumps({"backend": health, "storage": storage}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

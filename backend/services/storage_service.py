"""
Storage service for document blobs and PDF passwords.

- S3 mode: stores objects in S3 and enables KMS-backed server-side encryption
  when the KMS client is available.
- Local mode: encrypts every blob at rest with AES-GCM and derives the local
  encryption key from LOCAL_STORAGE_ENCRYPTION_KEY or SECRET_KEY.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from core.config import get_settings

settings = get_settings()

_LOCAL_ENCRYPTION_MAGIC = b"LOANLENS_ENC_V1"
_LOCAL_NONCE_SIZE = 12
_LOCAL_MAX_ENCRYPTION_LAYERS = 3
_FILE_PURPOSE = "file"
_PASSWORD_PURPOSE = "password"
_ARTIFACT_PURPOSE = "artifact"


def _local_upload_dir() -> Path:
    return (Path(__file__).resolve().parent / ".." / "uploads").resolve()


def _set_local_permissions(path: Path, mode: int) -> None:
    if os.name != "nt":
        os.chmod(path, mode)


def _ensure_local_parent(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _set_local_permissions(path, 0o700)


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    _ensure_local_parent(path.parent)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_bytes(content)
    _set_local_permissions(tmp_path, 0o600)
    tmp_path.replace(path)
    _set_local_permissions(path, 0o600)


def _local_encryption_seed() -> bytes:
    seed = settings.LOCAL_STORAGE_ENCRYPTION_KEY or settings.SECRET_KEY
    if not seed:
        raise RuntimeError("Local storage encryption key is not configured")
    return seed.encode("utf-8")


def _derive_local_key(purpose: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"loanlens-local-storage-v1",
        info=f"loanlens-local-{purpose}".encode("utf-8"),
    ).derive(_local_encryption_seed())


def _encrypt_local_blob(plaintext: bytes, purpose: str) -> bytes:
    nonce = os.urandom(_LOCAL_NONCE_SIZE)
    ciphertext = AESGCM(_derive_local_key(purpose)).encrypt(
        nonce,
        plaintext,
        purpose.encode("utf-8"),
    )
    return _LOCAL_ENCRYPTION_MAGIC + nonce + ciphertext


def _decrypt_local_blob(blob: bytes, purpose: str) -> bytes:
    if len(blob) < len(_LOCAL_ENCRYPTION_MAGIC) + _LOCAL_NONCE_SIZE:
        raise ValueError("Encrypted local blob is truncated")

    nonce_start = len(_LOCAL_ENCRYPTION_MAGIC)
    nonce_end = nonce_start + _LOCAL_NONCE_SIZE
    nonce = blob[nonce_start:nonce_end]
    ciphertext = blob[nonce_end:]
    return AESGCM(_derive_local_key(purpose)).decrypt(
        nonce,
        ciphertext,
        purpose.encode("utf-8"),
    )


def _unwrap_local_blob(blob: bytes, purpose: str) -> tuple[bytes, int]:
    current = blob
    layers = 0

    while current.startswith(_LOCAL_ENCRYPTION_MAGIC):
        layers += 1
        if layers > _LOCAL_MAX_ENCRYPTION_LAYERS:
            raise ValueError("Encrypted local blob exceeds supported nesting depth")
        current = _decrypt_local_blob(current, purpose)

    return current, layers


def _read_local_blob(path: Path, purpose: str, migrate_legacy: bool = False) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(_LOCAL_ENCRYPTION_MAGIC):
        plaintext, layers = _unwrap_local_blob(raw, purpose)
        if layers > 1:
            # Normalize legacy nested blobs back to a single encrypted layer.
            _atomic_write_bytes(path, _encrypt_local_blob(plaintext, purpose))
        return plaintext

    if migrate_legacy:
        _atomic_write_bytes(path, _encrypt_local_blob(raw, purpose))

    return raw


def _write_local_blob(path: Path, plaintext: bytes, purpose: str) -> None:
    _atomic_write_bytes(path, _encrypt_local_blob(plaintext, purpose))


def storage_key_from_file_url(file_url: str | None) -> str:
    """Convert a persisted file URL back into the storage key used by helpers."""
    if not file_url:
        return ""

    if file_url.startswith("s3://"):
        parts = file_url.replace("s3://", "", 1).split("/", 1)
        return parts[1] if len(parts) == 2 else ""

    file_path = Path(file_url).resolve()
    try:
        return file_path.relative_to(_local_upload_dir()).as_posix()
    except ValueError:
        return file_path.name


def extraction_artifact_key_for_file(file_url: str | None) -> str:
    """Return the storage key for a normalized extraction sidecar."""
    key = storage_key_from_file_url(file_url)
    if not key:
        return ""
    return f"{key}.extraction.json"


def _remote_storage_enabled() -> bool:
    return bool(
        settings.AWS_ACCESS_KEY_ID
        and settings.AWS_SECRET_ACCESS_KEY
        and settings.S3_BUCKET_NAME
    )


def _s3_client_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {}
    if settings.AWS_S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.AWS_S3_ENDPOINT_URL
    if settings.AWS_S3_FORCE_PATH_STYLE:
        kwargs["config"] = BotoConfig(s3={"addressing_style": "path"})
    return kwargs


def _kms_client_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {}
    endpoint_url = settings.AWS_KMS_ENDPOINT_URL or settings.AWS_S3_ENDPOINT_URL
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return kwargs


def _remote_encryption_kwargs() -> dict[str, str]:
    if settings.AWS_KMS_KEY_ID:
        return {
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": settings.AWS_KMS_KEY_ID,
        }
    return {"ServerSideEncryption": "AES256"}


def get_boto3_clients():
    """Returns S3 and optional KMS clients when remote storage is configured."""
    if not _remote_storage_enabled():
        return None, None

    session = boto3.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    s3_client = session.client("s3", **_s3_client_kwargs())

    kms_client = None
    if settings.AWS_KMS_KEY_ID or settings.AWS_KMS_ENDPOINT_URL:
        kms_client = session.client("kms", **_kms_client_kwargs())

    return s3_client, kms_client


async def upload_file(key: str, file_content: bytes, content_type: str) -> str:
    """Upload a document to S3 or encrypted local fallback storage."""
    s3, _ = get_boto3_clients()

    if s3:
        def _upload():
            put_object_kwargs = {
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": key,
                "Body": file_content,
                "ContentType": content_type,
            }
            put_object_kwargs.update(_remote_encryption_kwargs())
            s3.put_object(**put_object_kwargs)

        await asyncio.to_thread(_upload)
        return f"s3://{settings.S3_BUCKET_NAME}/{key}"

    file_path = (_local_upload_dir() / key).resolve()
    await asyncio.to_thread(_write_local_blob, file_path, file_content, _FILE_PURPOSE)
    return str(file_path)


async def download_file(file_url: str) -> bytes:
    """Download a document from S3 or decrypt the local blob."""
    if file_url.startswith("s3://"):
        s3, _ = get_boto3_clients()
        if not s3:
            raise RuntimeError("S3 client not configured but s3:// URL found")

        parts = file_url.replace("s3://", "", 1).split("/", 1)
        bucket, key = parts[0], parts[1]

        def _download():
            response = s3.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()

        return await asyncio.to_thread(_download)

    file_path = Path(file_url).resolve()
    return await asyncio.to_thread(_read_local_blob, file_path, _FILE_PURPOSE, True)


async def store_password(key: str, password: str):
    """Store a PDF password using encrypted storage."""
    s3, _ = get_boto3_clients()
    if s3:
        def _encrypt_and_upload():
            put_object_kwargs = {
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": key + ".pwd",
                "Body": password.encode("utf-8"),
            }
            put_object_kwargs.update(_remote_encryption_kwargs())
            s3.put_object(**put_object_kwargs)

        await asyncio.to_thread(_encrypt_and_upload)
        return

    file_path = (_local_upload_dir() / f"{key}.pwd").resolve()
    await asyncio.to_thread(
        _write_local_blob,
        file_path,
        password.encode("utf-8"),
        _PASSWORD_PURPOSE,
    )


async def retrieve_password(key: str) -> str:
    """Retrieve a stored PDF password."""
    s3, _ = get_boto3_clients()
    if s3:
        def _download_and_decrypt():
            try:
                response = s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=key + ".pwd")
                return response["Body"].read().decode("utf-8")
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "NoSuchKey":
                    return ""
                raise exc

        return await asyncio.to_thread(_download_and_decrypt)

    file_path = (_local_upload_dir() / f"{key}.pwd").resolve()
    if not file_path.exists():
        return ""

    password_bytes = await asyncio.to_thread(_read_local_blob, file_path, _PASSWORD_PURPOSE, True)
    return password_bytes.decode("utf-8")


async def retrieve_password_for_file(file_url: str | None) -> str:
    """Retrieve the stored password associated with a persisted file URL."""
    key = storage_key_from_file_url(file_url)
    if not key:
        return ""
    return await retrieve_password(key)


async def delete_password(key: str) -> None:
    """Delete a stored password after analysis no longer needs it."""
    s3, _ = get_boto3_clients()
    if s3:
        def _delete():
            try:
                s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key + ".pwd")
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "NoSuchKey":
                    raise exc

        await asyncio.to_thread(_delete)
        return

    file_path = (_local_upload_dir() / f"{key}.pwd").resolve()
    if file_path.exists():
        await asyncio.to_thread(file_path.unlink)


async def delete_password_for_file(file_url: str | None) -> None:
    """Delete the password associated with a persisted file URL."""
    key = storage_key_from_file_url(file_url)
    if key:
        await delete_password(key)


def _bucket_and_key_from_s3_url(file_url: str) -> tuple[str, str]:
    parts = file_url.replace("s3://", "", 1).split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise RuntimeError("Invalid S3 file URL")
    return parts[0], parts[1]


async def delete_storage_key(key: str, *, bucket: str | None = None) -> None:
    """Delete a storage object from S3 or encrypted local fallback storage."""
    normalized_key = (key or "").strip().lstrip("/\\")
    if not normalized_key:
        return

    s3, _ = get_boto3_clients()
    if s3:
        def _delete():
            try:
                s3.delete_object(Bucket=bucket or settings.S3_BUCKET_NAME, Key=normalized_key)
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "NoSuchKey":
                    raise exc

        await asyncio.to_thread(_delete)
        return

    file_path = (_local_upload_dir() / normalized_key).resolve()
    try:
        file_path.relative_to(_local_upload_dir())
    except ValueError:
        raise RuntimeError("Refusing to delete a file outside the local upload directory")

    if file_path.exists():
        await asyncio.to_thread(file_path.unlink)


async def delete_file(file_url: str | None) -> None:
    """Delete a persisted document blob from S3 or local storage."""
    if not file_url:
        return

    if file_url.startswith("s3://"):
        bucket, key = _bucket_and_key_from_s3_url(file_url)
        await delete_storage_key(key, bucket=bucket)
        return

    await delete_storage_key(storage_key_from_file_url(file_url))


async def delete_extraction_artifact(key: str) -> None:
    """Delete a normalized extraction sidecar if one exists."""
    await delete_storage_key(key)


async def delete_extraction_artifact_for_file(file_url: str | None) -> None:
    """Delete the normalized extraction sidecar associated with a file URL."""
    key = extraction_artifact_key_for_file(file_url)
    if key:
        await delete_extraction_artifact(key)


async def save_extraction_artifact(key: str, payload: dict) -> str:
    """Persist a normalized extraction sidecar beside the source file."""
    encoded = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    s3, _ = get_boto3_clients()
    if s3:
        def _upload():
            put_object_kwargs = {
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": key,
                "Body": encoded,
                "ContentType": "application/json",
            }
            put_object_kwargs.update(_remote_encryption_kwargs())
            s3.put_object(**put_object_kwargs)

        await asyncio.to_thread(_upload)
        return f"s3://{settings.S3_BUCKET_NAME}/{key}"

    file_path = (_local_upload_dir() / key).resolve()
    await asyncio.to_thread(_write_local_blob, file_path, encoded, _ARTIFACT_PURPOSE)
    return str(file_path)


async def load_extraction_artifact(key: str) -> dict | None:
    """Load a normalized extraction sidecar if one exists."""
    s3, _ = get_boto3_clients()
    if s3:
        def _download():
            try:
                response = s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
                return response["Body"].read()
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "NoSuchKey":
                    return None
                raise exc

        raw = await asyncio.to_thread(_download)
        if raw is None:
            return None
        return json.loads(raw.decode("utf-8"))

    file_path = (_local_upload_dir() / key).resolve()
    if not file_path.exists():
        return None

    raw = await asyncio.to_thread(_read_local_blob, file_path, _ARTIFACT_PURPOSE, False)
    return json.loads(raw.decode("utf-8"))


async def save_extraction_artifact_for_file(file_url: str | None, payload: dict) -> str:
    key = extraction_artifact_key_for_file(file_url)
    if not key:
        raise RuntimeError("Cannot persist extraction artifact without a storage key")
    return await save_extraction_artifact(key, payload)


async def load_extraction_artifact_for_file(file_url: str | None) -> dict | None:
    key = extraction_artifact_key_for_file(file_url)
    if not key:
        return None
    return await load_extraction_artifact(key)

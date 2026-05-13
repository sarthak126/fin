from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from services import storage_service


def test_get_boto3_clients_uses_configured_endpoints(monkeypatch):
    session_calls: list[dict[str, object]] = []
    client_calls: list[tuple[str, dict[str, object]]] = []

    class FakeSession:
        def client(self, service_name: str, **kwargs):
            client_calls.append((service_name, kwargs))
            return SimpleNamespace(service_name=service_name, kwargs=kwargs)

    def fake_session(**kwargs):
        session_calls.append(kwargs)
        return FakeSession()

    monkeypatch.setattr(storage_service.boto3, "Session", fake_session)
    monkeypatch.setattr(storage_service.settings, "AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setattr(storage_service.settings, "AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setattr(storage_service.settings, "AWS_REGION", "us-east-1")
    monkeypatch.setattr(storage_service.settings, "S3_BUCKET_NAME", "loanlens-rehearsal")
    monkeypatch.setattr(storage_service.settings, "AWS_S3_ENDPOINT_URL", "http://localstack:4566")
    monkeypatch.setattr(storage_service.settings, "AWS_KMS_ENDPOINT_URL", "http://localstack:4566")
    monkeypatch.setattr(storage_service.settings, "AWS_KMS_KEY_ID", "alias/loanlens-rehearsal")
    monkeypatch.setattr(storage_service.settings, "AWS_S3_FORCE_PATH_STYLE", True)

    s3, kms = storage_service.get_boto3_clients()

    assert session_calls == [
        {
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "region_name": "us-east-1",
        }
    ]
    assert s3.service_name == "s3"
    assert kms.service_name == "kms"
    assert client_calls[0][0] == "s3"
    assert client_calls[0][1]["endpoint_url"] == "http://localstack:4566"
    assert client_calls[0][1]["config"].s3["addressing_style"] == "path"
    assert client_calls[1] == ("kms", {"endpoint_url": "http://localstack:4566"})


@pytest.mark.asyncio
async def test_upload_file_uses_configured_kms_headers(monkeypatch):
    captured: dict[str, object] = {}

    class FakeS3:
        def put_object(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(storage_service, "get_boto3_clients", lambda: (FakeS3(), SimpleNamespace()))
    monkeypatch.setattr(storage_service.settings, "S3_BUCKET_NAME", "loanlens-rehearsal")
    monkeypatch.setattr(storage_service.settings, "AWS_KMS_KEY_ID", "alias/loanlens-rehearsal")

    file_url = await storage_service.upload_file("docs/sample.pdf", b"pdf", "application/pdf")

    assert file_url == "s3://loanlens-rehearsal/docs/sample.pdf"
    assert captured["Bucket"] == "loanlens-rehearsal"
    assert captured["Key"] == "docs/sample.pdf"
    assert captured["ServerSideEncryption"] == "aws:kms"
    assert captured["SSEKMSKeyId"] == "alias/loanlens-rehearsal"


@pytest.mark.asyncio
async def test_delete_file_removes_remote_s3_object(monkeypatch):
    deleted: list[tuple[str, str]] = []

    class FakeS3:
        def delete_object(self, *, Bucket: str, Key: str):
            deleted.append((Bucket, Key))

    monkeypatch.setattr(storage_service, "get_boto3_clients", lambda: (FakeS3(), None))

    await storage_service.delete_file("s3://loanlens-rehearsal/docs/sample.pdf")

    assert deleted == [("loanlens-rehearsal", "docs/sample.pdf")]


@pytest.mark.asyncio
async def test_password_roundtrip_uses_remote_s3_without_kms_client(monkeypatch):
    stored_objects: dict[str, bytes] = {}
    deleted_keys: list[str] = []

    class FakeBody:
        def __init__(self, data: bytes):
            self._data = data

        def read(self) -> bytes:
            return self._data

    class FakeS3:
        def put_object(self, **kwargs):
            stored_objects[kwargs["Key"]] = kwargs["Body"]
            assert kwargs["ServerSideEncryption"] == "AES256"

        def get_object(self, *, Bucket: str, Key: str):
            return {"Body": FakeBody(stored_objects[Key])}

        def delete_object(self, *, Bucket: str, Key: str):
            deleted_keys.append(Key)
            stored_objects.pop(Key, None)

    monkeypatch.setattr(storage_service, "get_boto3_clients", lambda: (FakeS3(), None))
    monkeypatch.setattr(storage_service.settings, "S3_BUCKET_NAME", "loanlens-rehearsal")
    monkeypatch.setattr(storage_service.settings, "AWS_KMS_KEY_ID", "")

    await storage_service.store_password("docs/sample.pdf", "super-secret")
    retrieved = await storage_service.retrieve_password("docs/sample.pdf")
    await storage_service.delete_password("docs/sample.pdf")

    assert retrieved == "super-secret"
    assert deleted_keys == ["docs/sample.pdf.pwd"]


@pytest.mark.asyncio
async def test_extraction_artifact_roundtrip_uses_remote_storage(monkeypatch):
    stored_objects: dict[str, bytes] = {}

    class FakeBody:
        def __init__(self, data: bytes):
            self._data = data

        def read(self) -> bytes:
            return self._data

    class FakeS3:
        def put_object(self, **kwargs):
            stored_objects[kwargs["Key"]] = kwargs["Body"]
            assert kwargs["ContentType"] == "application/json"

        def get_object(self, *, Bucket: str, Key: str):
            return {"Body": FakeBody(stored_objects[Key])}

    monkeypatch.setattr(storage_service, "get_boto3_clients", lambda: (FakeS3(), None))
    monkeypatch.setattr(storage_service.settings, "S3_BUCKET_NAME", "loanlens-rehearsal")
    monkeypatch.setattr(storage_service.settings, "AWS_KMS_KEY_ID", "")

    payload = {
        "file_type": "application/pdf",
        "total_pages": 2,
        "pages": [{"page_num": 1, "text": "hello"}],
    }

    artifact_url = await storage_service.save_extraction_artifact("docs/sample.pdf.extraction.json", payload)
    roundtrip = await storage_service.load_extraction_artifact("docs/sample.pdf.extraction.json")

    assert artifact_url == "s3://loanlens-rehearsal/docs/sample.pdf.extraction.json"
    assert roundtrip == payload


@pytest.mark.asyncio
async def test_local_file_roundtrip_encrypts_at_rest(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(storage_service, "get_boto3_clients", lambda: (None, None))
    monkeypatch.setattr(storage_service, "_local_upload_dir", lambda: tmp_path)

    file_url = await storage_service.upload_file("docs/sample.pdf", b"%PDF-1.7\nhello", "application/pdf")
    stored_path = Path(file_url)

    stored_bytes = stored_path.read_bytes()
    assert stored_bytes.startswith(storage_service._LOCAL_ENCRYPTION_MAGIC)

    downloaded = await storage_service.download_file(file_url)
    assert downloaded == b"%PDF-1.7\nhello"


@pytest.mark.asyncio
async def test_local_delete_helpers_remove_file_password_and_artifact(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(storage_service, "get_boto3_clients", lambda: (None, None))
    monkeypatch.setattr(storage_service, "_local_upload_dir", lambda: tmp_path)

    file_url = await storage_service.upload_file("docs/sample.pdf", b"%PDF-1.7\nhello", "application/pdf")
    await storage_service.store_password("docs/sample.pdf", "secret")
    await storage_service.save_extraction_artifact("docs/sample.pdf.extraction.json", {"pages": []})

    await storage_service.delete_password_for_file(file_url)
    await storage_service.delete_extraction_artifact_for_file(file_url)
    await storage_service.delete_file(file_url)

    assert not (tmp_path / "docs" / "sample.pdf").exists()
    assert not (tmp_path / "docs" / "sample.pdf.pwd").exists()
    assert not (tmp_path / "docs" / "sample.pdf.extraction.json").exists()


@pytest.mark.asyncio
async def test_download_file_unwraps_and_normalizes_nested_local_encryption(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(storage_service, "get_boto3_clients", lambda: (None, None))
    monkeypatch.setattr(storage_service, "_local_upload_dir", lambda: tmp_path)

    file_path = tmp_path / "docs" / "sample.pdf"
    plaintext = b"%PDF-1.7\nnested"
    nested_blob = storage_service._encrypt_local_blob(
        storage_service._encrypt_local_blob(plaintext, storage_service._FILE_PURPOSE),
        storage_service._FILE_PURPOSE,
    )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(nested_blob)

    downloaded = await storage_service.download_file(str(file_path))
    assert downloaded == plaintext

    normalized = file_path.read_bytes()
    assert normalized.startswith(storage_service._LOCAL_ENCRYPTION_MAGIC)
    once_unwrapped, layers = storage_service._unwrap_local_blob(normalized, storage_service._FILE_PURPOSE)
    assert once_unwrapped == plaintext
    assert layers == 1

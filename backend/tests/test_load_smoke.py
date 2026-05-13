from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import main as main_module
from routes import documents as document_routes


def _make_document():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id="doc_load_123",
        filename="load-test.pdf",
        original_filename="load-test.pdf",
        file_url="s3://loanlens/documents/load-test.pdf",
        file_type="application/pdf",
        document_type="bank_statement",
        status="analyzed",
        file_size_bytes=128,
        created_at=now,
        updated_at=now,
        user_id="user_test_123",
        org_id="org_test_456",
        analyses=[],
    )


@pytest.mark.load
async def test_live_endpoint_handles_concurrent_burst(async_client):
    main_module.app.state.app_env = "staging"
    main_module.app.state.startup_policy = "strict-db-required"

    async def hit_live():
        response = await async_client.get("/health/live")
        assert response.status_code == 200
        return response.headers["x-request-id"]

    request_ids = await asyncio.gather(*(hit_live() for _ in range(40)))

    assert len(request_ids) == 40
    assert len(set(request_ids)) == 40


@pytest.mark.load
async def test_list_documents_handles_authenticated_burst(async_client, fake_db, auth_context, monkeypatch):
    observed_calls: list[dict[str, object]] = []

    async def fake_get_documents(**kwargs):
        observed_calls.append(kwargs)
        await asyncio.sleep(0.01)
        return [_make_document()]

    monkeypatch.setattr(document_routes, "get_documents", fake_get_documents)

    responses = await asyncio.gather(
        *(async_client.get("/api/v1/documents?skip=0&limit=10") for _ in range(25))
    )

    assert all(response.status_code == 200 for response in responses)
    assert len(observed_calls) == 25
    assert all(call["db"] is fake_db for call in observed_calls)
    assert all(call["org_id"] == auth_context.org_id for call in observed_calls)
    assert all(call["skip"] == 0 for call in observed_calls)
    assert all(call["limit"] == 10 for call in observed_calls)
    assert all("x-request-id" in response.headers for response in responses)

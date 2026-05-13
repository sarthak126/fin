from __future__ import annotations

from types import SimpleNamespace

from services import vector_service


def test_retrieve_relevant_chunks_falls_back_to_lexical_search_when_query_embedding_fails(monkeypatch):
    class FakeCollection:
        def count(self):
            return 2

        def query(self, **kwargs):
            raise AssertionError("vector query should not run when query embedding fails")

        def get(self, include):
            return {
                "documents": [
                    "Average balance remained above 48,000 with recurring salary credits.",
                    "Penalty clauses and bounce charges were not present in this period.",
                ],
                "metadatas": [
                    {"section_title": "Account Summary", "page_num": 2},
                    {"section_title": "Charges", "page_num": 4},
                ],
            }

    fake_client = SimpleNamespace(get_collection=lambda name: FakeCollection())

    monkeypatch.setattr(vector_service, "_get_chroma_client", lambda: fake_client)
    monkeypatch.setattr(
        vector_service,
        "_generate_query_embedding",
        lambda query: (_ for _ in ()).throw(RuntimeError("503 UNAVAILABLE")),
    )

    chunks = vector_service.retrieve_relevant_chunks(
        document_id="doc_test_123",
        query="What is the average balance?",
        top_k=2,
    )

    assert chunks
    assert chunks[0]["section_title"] == "Account Summary"
    assert "Average balance" in chunks[0]["text"]

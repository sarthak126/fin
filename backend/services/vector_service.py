"""
Vector Service — ChromaDB vector storage with Gemini embeddings.

Pipeline step: Upload → Extraction → Chunking → [THIS] → Gemini → Insights

Each document gets its own ChromaDB collection for isolation.
Uses Gemini text-embedding-004 for generating embeddings.
"""

import os
import re
import time
from google import genai
import chromadb
from chromadb.config import Settings as ChromaSettings
from core.config import get_settings


# ────────────────────────────────────────
# Singleton ChromaDB client
# ────────────────────────────────────────

_chroma_client: chromadb.ClientAPI | None = None

_TRANSIENT_EMBEDDING_ERROR_MARKERS = (
    "RESOURCE_EXHAUSTED",
    "UNAVAILABLE",
    "DEADLINE_EXCEEDED",
    "INTERNAL",
    "429",
    "500",
    "503",
)
_LEXICAL_STOPWORDS = {
    "about",
    "after",
    "and",
    "are",
    "can",
    "did",
    "does",
    "for",
    "from",
    "have",
    "how",
    "into",
    "loan",
    "show",
    "that",
    "the",
    "this",
    "there",
    "were",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "your",
}


def _get_chroma_client() -> chromadb.ClientAPI:
    """Get or create the persistent ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        settings = get_settings()
        persist_dir = os.path.abspath(settings.CHROMA_DB_PATH)
        os.makedirs(persist_dir, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


def _get_collection_name(document_id: str) -> str:
    """Generate a valid ChromaDB collection name for a document."""
    # ChromaDB requires 3-63 chars, alphanumeric + underscores/hyphens
    safe_id = document_id.replace("-", "_")[:50]
    return f"doc_{safe_id}"


def _is_transient_embedding_error(error: Exception) -> bool:
    message = str(error).upper()
    return any(marker in message for marker in _TRANSIENT_EMBEDDING_ERROR_MARKERS)


def _retry_delay_seconds(error: Exception, attempt: int) -> float:
    match = re.search(r"retry in ([0-9.]+)s", str(error), flags=re.IGNORECASE)
    if match:
        try:
            return min(float(match.group(1)), 8.0)
        except ValueError:
            pass
    return min(2.0 * (attempt + 1), 8.0)


def _embed_content_with_retry(
    client: genai.Client,
    *,
    model: str,
    contents: str,
    retries: int = 2,
):
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return client.models.embed_content(
                model=model,
                contents=contents,
            )
        except Exception as error:
            last_error = error
            if attempt == retries or not _is_transient_embedding_error(error):
                raise
            delay_seconds = _retry_delay_seconds(error, attempt)
            print(
                "[warn] Gemini embedding request failed with a transient provider error; "
                f"retrying in {delay_seconds:.1f}s ({error})"
            )
            time.sleep(delay_seconds)

    raise RuntimeError(f"Gemini embedding request failed after retries: {last_error}")


def _query_keywords(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", query.lower())
        if token not in _LEXICAL_STOPWORDS
    }


def _lexical_score_chunk(query: str, chunk: dict) -> float:
    keywords = _query_keywords(query)
    if not keywords:
        return 0.0

    section_title = str(chunk.get("section_title", "")).lower()
    text = str(chunk.get("text", "")).lower()
    combined = f"{section_title} {text}"

    score = 0.0
    for keyword in keywords:
        if keyword in section_title:
            score += 3.0
        elif keyword in combined:
            score += 1.0

    if query.lower() in combined:
        score += 2.0

    return score


def _lexical_retrieve_relevant_chunks(
    collection,
    *,
    query: str,
    top_k: int,
) -> list[dict]:
    try:
        results = collection.get(include=["documents", "metadatas"])
    except Exception as error:
        print(f"[warn] Lexical chunk fallback failed to read collection: {error}")
        return []

    documents = results.get("documents") or []
    metadatas = results.get("metadatas") or []
    chunks: list[dict] = []

    for index, doc_text in enumerate(documents):
        meta = metadatas[index] if index < len(metadatas) else {}
        chunk = {
            "text": doc_text,
            "section_title": meta.get("section_title", ""),
            "page_num": meta.get("page_num", 0),
        }
        score = _lexical_score_chunk(query, chunk)
        if score > 0:
            chunk["score"] = score
            chunks.append(chunk)

    chunks.sort(key=lambda chunk: chunk.get("score", 0), reverse=True)
    return chunks[:top_k]


# ────────────────────────────────────────
# Embedding via Gemini
# ────────────────────────────────────────

def _generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using Gemini text-embedding-004."""
    settings = get_settings()
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    embeddings: list[list[float]] = []

    for text in texts:
        response = _embed_content_with_retry(
            client,
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents=text,
        )
        embeddings.append(response.embeddings[0].values)

    return embeddings


def _generate_query_embedding(query: str) -> list[float]:
    """Generate a single embedding for a search query."""
    settings = get_settings()
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    response = _embed_content_with_retry(
        client,
        model=settings.GEMINI_EMBEDDING_MODEL,
        contents=query,
    )
    return response.embeddings[0].values


# ────────────────────────────────────────
# Public API
# ────────────────────────────────────────

def store_document_chunks(document_id: str, chunks: list) -> int:
    """
    Embed and store document chunks in ChromaDB.
    
    Returns the number of chunks stored.
    """
    if not chunks:
        return 0

    client = _get_chroma_client()
    collection_name = _get_collection_name(document_id)

    # Delete existing collection if re-analyzing
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    collection = client.create_collection(
        name=collection_name,
        metadata={"document_id": document_id},
    )

    # Prepare data
    texts = [chunk.text for chunk in chunks]
    ids = [f"{document_id}_chunk_{chunk.chunk_index}" for chunk in chunks]
    metadatas = [
        {
            "chunk_index": chunk.chunk_index,
            "page_num": chunk.page_num or 0,
            "section_title": chunk.section_title,
            "document_id": document_id,
        }
        for chunk in chunks
    ]

    # Generate embeddings
    embeddings = _generate_embeddings(texts)

    # Store in ChromaDB
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )

    return len(chunks)


def retrieve_relevant_chunks(
    document_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Retrieve the most relevant chunks for a query from a document's vector collection.
    
    Returns list of { text, section_title, page_num, score }.
    """
    client = _get_chroma_client()
    collection_name = _get_collection_name(document_id)

    try:
        collection = client.get_collection(collection_name)
    except Exception:
        return []

    try:
        query_embedding = _generate_query_embedding(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as error:
        print(
            "[warn] Vector query failed; falling back to lexical chunk retrieval "
            f"for document {document_id}: {error}"
        )
        return _lexical_retrieve_relevant_chunks(
            collection,
            query=query,
            top_k=top_k,
        )

    chunks = []
    if results and results["documents"]:
        for i, doc_text in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            chunks.append({
                "text": doc_text,
                "section_title": meta.get("section_title", ""),
                "page_num": meta.get("page_num", 0),
                "score": 1 - distance,  # convert distance to similarity score
            })

    return chunks


def get_all_chunks(document_id: str) -> list[dict]:
    """Get all stored chunks for a document (for full-context analysis)."""
    client = _get_chroma_client()
    collection_name = _get_collection_name(document_id)

    try:
        collection = client.get_collection(collection_name)
    except Exception:
        return []

    results = collection.get(include=["documents", "metadatas"])

    chunks = []
    if results and results["documents"]:
        for i, doc_text in enumerate(results["documents"]):
            meta = results["metadatas"][i] if results["metadatas"] else {}
            chunks.append({
                "text": doc_text,
                "section_title": meta.get("section_title", ""),
                "page_num": meta.get("page_num", 0),
            })

    return chunks


def delete_document_vectors(document_id: str) -> bool:
    """Delete all vectors for a document."""
    client = _get_chroma_client()
    collection_name = _get_collection_name(document_id)
    try:
        client.delete_collection(collection_name)
        return True
    except Exception:
        return False

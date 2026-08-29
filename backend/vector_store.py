"""
vector_store.py

Wraps Qdrant with per-tenant collection isolation. Per the plan:
"No shared collections" — each tenant gets their own Qdrant
collection, named deterministically from their tenant_id, so there
is no way to accidentally query across tenants.
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from config import settings
from embeddings import embed_text

client = QdrantClient(url=settings.QDRANT_URL)

EMBEDDING_DIM = 384  # matches all-MiniLM-L6-v2's output size


def _collection_name(tenant_id: str) -> str:
    return f"tenant_{tenant_id}"


def ensure_tenant_collection(tenant_id: str):
    """Creates this tenant's isolated collection if it doesn't exist yet."""
    name = _collection_name(tenant_id)
    existing = [c.name for c in client.get_collections().collections]
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )


def upsert_chunks(tenant_id: str, chunks: list[dict]):
    """
    Stores document chunks in the tenant's collection.
    Each chunk dict: {"id": str, "text": str, "metadata": dict}
    """
    ensure_tenant_collection(tenant_id)
    name = _collection_name(tenant_id)

    points = [
        PointStruct(
            id=chunk["id"],
            vector=embed_text(chunk["text"]),
            payload={"text": chunk["text"], **chunk.get("metadata", {})},
        )
        for chunk in chunks
    ]
    client.upsert(collection_name=name, points=points)


def search(tenant_id: str, query: str, top_k: int = 4) -> list[dict]:
    """
    Retrieves the most relevant chunks for a query, scoped to ONE
    tenant's collection only. This is the actual isolation guarantee —
    it is structurally impossible for this query to touch another
    tenant's data, since it never even opens their collection.
    """
    name = _collection_name(tenant_id)
    existing = [c.name for c in client.get_collections().collections]
    if name not in existing:
        return []  # tenant has no ingested data yet

    query_vector = embed_text(query)
    results = client.query_points(
        collection_name=name,
        query=query_vector,
        limit=top_k,
    ).points

    return [{"text": r.payload.get("text", ""), "score": r.score} for r in results]


def delete_points(tenant_id: str, point_ids: list[str]):
    """
    Removes specific chunks from a tenant's Qdrant collection — used
    when a business deletes an outdated knowledge source, so old
    content (e.g. old hours, an old address) stops being retrievable,
    not just hidden in Postgres.
    """
    if not point_ids:
        return
    name = _collection_name(tenant_id)
    existing = [c.name for c in client.get_collections().collections]
    if name not in existing:
        return  # nothing to delete
    client.delete(collection_name=name, points_selector=point_ids)


"""Retrieval: find the help center chunks most similar to a question."""

from app import config
from app.embeddings import embed_texts, get_chroma_client

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        _collection = get_chroma_client().get_collection(config.COLLECTION_NAME)
    return _collection


def retrieve(question: str, top_k: int = config.TOP_K) -> list[dict]:
    """Return the top_k chunks as dicts: text, source, score (cosine similarity, higher = closer)."""
    [query_vector], _ = embed_texts([question])
    result = _get_collection().query(query_embeddings=[query_vector], n_results=top_k)
    return [
        {"text": text, "source": meta["source"], "score": round(1 - distance, 3)}
        for text, meta, distance in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]

"""Embeddings and vector store access, shared by ingest.py and retriever.py.

We compute embeddings ourselves with OpenAI instead of letting Chroma use a
hidden default model, so the embedding model is explicit and swappable.
"""

import chromadb
import openai
from chromadb.config import Settings

from app import config

_openai = openai.OpenAI()


def embed_texts(texts: list[str]) -> tuple[list[list[float]], int]:
    """Return one vector per text, plus the number of tokens billed."""
    response = _openai.embeddings.create(model=config.EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data], response.usage.prompt_tokens


def get_chroma_client() -> chromadb.ClientAPI:
    """Local, file-based Chroma database in ./chroma_db (telemetry off)."""
    return chromadb.PersistentClient(
        path=str(config.CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

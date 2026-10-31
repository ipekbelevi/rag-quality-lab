"""Ingestion: read help center docs, split them into chunks, embed, store in Chroma.

Run once (and again after any doc or CHUNK_SIZE change):
    .venv/bin/python -m app.ingest

The collection is rebuilt from scratch on every run, so the result is repeatable.
"""

from app import config
from app.embeddings import embed_texts, get_chroma_client


def chunk_document(text: str, chunk_size: int) -> list[str]:
    """Split one markdown doc into chunks of at most chunk_size characters.

    Strategy: keep paragraphs whole, glue each heading to the paragraph after it,
    and prefix every chunk with the document title so it makes sense on its own.
    """
    lines = text.strip().split("\n", 1)
    title = lines[0].lstrip("# ").strip()
    body = lines[1] if len(lines) > 1 else ""

    # Paragraphs, with headings merged into the paragraph that follows them
    paragraphs, pending_heading = [], ""
    for block in (b.strip() for b in body.split("\n\n")):
        if not block:
            continue
        if block.startswith("#") and "\n" not in block:
            pending_heading += block + "\n"
            continue
        paragraphs.append(pending_heading + block)
        pending_heading = ""

    # Greedily pack paragraphs into chunks; hard-split paragraphs that are too long
    chunks, current = [], ""
    for paragraph in paragraphs:
        pieces = _split_long(paragraph, chunk_size) if len(paragraph) > chunk_size else [paragraph]
        for piece in pieces:
            if current and len(current) + 2 + len(piece) > chunk_size:
                chunks.append(current)
                current = piece
            else:
                current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)

    return [f"# {title}\n{chunk}" for chunk in chunks]


def _split_long(text: str, chunk_size: int) -> list[str]:
    """Split an oversized paragraph on word boundaries."""
    pieces, current = [], ""
    for word in text.split(" "):
        if current and len(current) + 1 + len(word) > chunk_size:
            pieces.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        pieces.append(current)
    return pieces


def ingest() -> None:
    doc_paths = sorted(config.DOCS_DIR.glob("*.md"))
    ids, chunks, metadatas = [], [], []
    for path in doc_paths:
        for i, chunk in enumerate(chunk_document(path.read_text(encoding="utf-8"), config.CHUNK_SIZE)):
            ids.append(f"{path.stem}#{i}")
            chunks.append(chunk)
            metadatas.append({"source": path.name, "chunk_index": i})

    vectors, tokens = embed_texts(chunks)

    client = get_chroma_client()
    if config.COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(config.COLLECTION_NAME)
    collection = client.create_collection(
        name=config.COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,  # we always pass our own vectors
    )
    collection.add(ids=ids, documents=chunks, embeddings=vectors, metadatas=metadatas)

    sizes = [len(c) for c in chunks]
    print(f"Docs: {len(doc_paths)} | chunks: {len(chunks)} | CHUNK_SIZE={config.CHUNK_SIZE}")
    print(f"Chunk length (chars): min={min(sizes)} avg={sum(sizes) // len(sizes)} max={max(sizes)}")
    print(f"Embedding tokens: {tokens}")


if __name__ == "__main__":
    ingest()

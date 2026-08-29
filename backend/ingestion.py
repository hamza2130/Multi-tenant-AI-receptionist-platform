"""
ingestion.py

The training pipeline: takes raw text (from an uploaded doc, a
pasted FAQ, or a scraped URL), cleans it, splits it into small
chunks, and stores those chunks in the tenant's vector collection.

This is what lets a business "train" their receptionist just by
uploading their existing content — no manual FAQ writing required.
"""

import re
import uuid
from sqlalchemy.orm import Session
from models import KnowledgeSource, Document
import vector_store


def clean_text(text: str) -> str:
    """
    Basic cleanup: collapse repeated whitespace WITHIN a line, and
    normalize multiple blank lines down to exactly one paragraph
    break — but never destroy paragraph breaks entirely. Previously
    this collapsed \\n\\n into a single space, which silently
    defeated chunk_text()'s paragraph-boundary splitting (it had
    nothing left to split on), causing every knowledge base entry to
    fall back to naive 500-character slicing regardless of sentence
    or paragraph boundaries.
    """
    text = re.sub(r"[ \t]+", " ", text)        # collapse horizontal whitespace only
    text = re.sub(r"\n{3,}", "\n\n", text)      # normalize 3+ blank lines to exactly one paragraph break
    return text.strip()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Splits text into chunks, respecting paragraph boundaries first.
    A paragraph that fits within chunk_size stays as one clean,
    complete chunk. Only a paragraph longer than chunk_size gets
    further sub-split (sliding window, same as before).
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks = []
    for para in paragraphs:
        if len(para) <= chunk_size:
            chunks.append(para)
        else:
            start = 0
            while start < len(para):
                end = start + chunk_size
                sub_chunk = para[start:end].strip()
                if sub_chunk:
                    chunks.append(sub_chunk)
                start = end - overlap

    return chunks



def ingest_text(db: Session, tenant_id: str, source_type: str, raw_text: str) -> str:
    """
    Full pipeline for one piece of content: creates a KnowledgeSource
    record, chunks the text, stores chunks in Postgres (for reference)
    AND in Qdrant (for retrieval), scoped to this tenant only.

    Returns the created KnowledgeSource id.
    """
    source = KnowledgeSource(tenant_id=tenant_id, type=source_type, status="processing")
    db.add(source)
    db.flush()  # get source.id without committing yet

    cleaned = clean_text(raw_text)
    text_chunks = chunk_text(cleaned)

    qdrant_chunks = []
    for chunk in text_chunks:
        doc_id = str(uuid.uuid4())
        db.add(Document(
            id=doc_id,
            source_id=source.id,
            tenant_id=tenant_id,
            chunk_text=chunk,
        ))
        qdrant_chunks.append({"id": doc_id, "text": chunk, "metadata": {"source_id": source.id}})

    vector_store.upsert_chunks(tenant_id, qdrant_chunks)

    source.status = "ready"
    db.commit()

    return source.id

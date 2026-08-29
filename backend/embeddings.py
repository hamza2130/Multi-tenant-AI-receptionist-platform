"""
embeddings.py

Converts text into embeddings (lists of numbers representing meaning)
using a local, free, open-source model — no API key or per-call cost.

This is what powers RAG: both the tenant's documents AND the caller's
questions get embedded with this same model, so we can mathematically
compare "how similar in meaning" they are.
"""

from sentence_transformers import SentenceTransformer
from config import settings

# Loaded once at import time — the model itself runs locally on CPU,
# no network call needed per embedding.
_model = SentenceTransformer(settings.EMBEDDING_MODEL)


def embed_text(text: str) -> list[float]:
    """Embeds a single piece of text. Returns a vector (list of floats)."""
    return _model.encode(text, normalize_embeddings=True).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embeds many texts at once — much faster than calling embed_text in a loop."""
    return _model.encode(texts, normalize_embeddings=True).tolist()

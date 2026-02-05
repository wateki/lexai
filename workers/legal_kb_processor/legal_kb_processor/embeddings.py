"""
Optional embedding generation for pgvector (quick lookups only; primary retrieval is PageIndex).
"""
import logging
from typing import Any

from openai import OpenAI

from .config import EMBEDDING_DIM, EMBEDDING_MODEL, OPENAI_API_KEY

logger = logging.getLogger(__name__)


def generate_embedding(text: str, max_chars: int = 8000) -> list[float] | None:
    """
    Generate a single embedding vector for text (truncated to max_chars).
    Returns None if API key missing or error; dimension must match EMBEDDING_DIM (1536).
    """
    if not OPENAI_API_KEY or not text:
        return None
    truncated = text[:max_chars].strip()
    if not truncated:
        return None
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        r = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=truncated,
            dimensions=EMBEDDING_DIM,
        )
        vec = r.data[0].embedding
        if len(vec) != EMBEDDING_DIM:
            logger.warning("Embedding dimension %s != %s", len(vec), EMBEDDING_DIM)
        return vec
    except Exception as e:
        logger.warning("Embedding generation failed: %s", e)
        return None

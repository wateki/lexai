"""Configuration from environment for the full Docling + PageIndex pipeline."""
import os
from pathlib import Path

# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

# Storage & pipeline
LEGAL_KB_BUCKET = "legal-kb"
PIPELINE_NAME = "docling_pageindex"

# OpenAI (LLM metadata extraction, PageIndex summaries, embeddings)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
LLM_MODEL = os.environ.get("LEGAL_KB_LLM_MODEL", "gpt-4o-mini").strip()
EMBEDDING_MODEL = os.environ.get("LEGAL_KB_EMBEDDING_MODEL", "text-embedding-3-small").strip()
EMBEDDING_DIM = 1536  # match legal_knowledge_base.ai_embedding

# PageIndex
PAGEINDEX_ADD_NODE_SUMMARY = os.environ.get("PAGEINDEX_ADD_NODE_SUMMARY", "no").strip().lower() == "yes"

# LLM metadata extraction: max chars of markdown to send (to stay within context)
MAX_MARKDOWN_FOR_EXTRACTION = int(os.environ.get("LEGAL_KB_MAX_MARKDOWN_EXTRACTION", "120000"))

# Optional: vector fallback (pgvector quick lookups, not primary retrieval)
ENABLE_VECTOR_FALLBACK = os.environ.get("LEGAL_KB_ENABLE_VECTOR_FALLBACK", "no").strip().lower() == "yes"
MAX_TEXT_FOR_EMBEDDING = int(os.environ.get("LEGAL_KB_MAX_EMBEDDING_TEXT", "8000"))

# Optional: Graphiti (topic-case graph; requires FalkorDB or Neo4j)
ENABLE_GRAPHITI = os.environ.get("LEGAL_KB_ENABLE_GRAPHITI", "no").strip().lower() == "yes"
GRAPHITI_PROVIDER = os.environ.get("LEGAL_KB_GRAPHITI_PROVIDER", "falkordb").strip().lower()
GRAPHITI_FALKORDB_HOST = os.environ.get("LEGAL_KB_GRAPHITI_FALKORDB_HOST", "localhost").strip()
GRAPHITI_FALKORDB_PORT = int(os.environ.get("LEGAL_KB_GRAPHITI_FALKORDB_PORT", "6379"))
GRAPHITI_NEO4J_URI = os.environ.get("LEGAL_KB_GRAPHITI_NEO4J_URI", "").strip()
GRAPHITI_NEO4J_USER = os.environ.get("LEGAL_KB_GRAPHITI_NEO4J_USER", "").strip()
GRAPHITI_NEO4J_PASSWORD = os.environ.get("LEGAL_KB_GRAPHITI_NEO4J_PASSWORD", "").strip()
GRAPHITI_DATABASE = os.environ.get("LEGAL_KB_GRAPHITI_DATABASE", "lex_nexus_graph").strip()

# PageIndex: local repo only (no PyPI package); docling, eyecite, graphiti are pip-installed
REPO_ROOT = Path(__file__).resolve().parents[2]
PAGEINDEX_ROOT = REPO_ROOT / "pageIndex" / "PageIndex"

# Logging
LOG_LEVEL = os.environ.get("LEGAL_KB_LOG_LEVEL", "INFO").strip().upper()

# Retries
DOCLING_MAX_RETRIES = int(os.environ.get("LEGAL_KB_DOCLING_MAX_RETRIES", "2"))
LLM_MAX_RETRIES = int(os.environ.get("LEGAL_KB_LLM_MAX_RETRIES", "3"))

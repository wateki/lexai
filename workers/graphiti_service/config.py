"""Configuration for Lex Nexus Graphiti API service. Uses same env as legal_kb_processor."""
import os

ENABLE_GRAPHITI = os.environ.get("LEGAL_KB_ENABLE_GRAPHITI", "no").strip().lower() == "yes"
GRAPHITI_PROVIDER = os.environ.get("LEGAL_KB_GRAPHITI_PROVIDER", "falkordb").strip().lower()
GRAPHITI_FALKORDB_HOST = os.environ.get("LEGAL_KB_GRAPHITI_FALKORDB_HOST", "localhost").strip()
GRAPHITI_FALKORDB_PORT = int(os.environ.get("LEGAL_KB_GRAPHITI_FALKORDB_PORT", "6379"))
GRAPHITI_NEO4J_URI = os.environ.get("LEGAL_KB_GRAPHITI_NEO4J_URI", "").strip()
GRAPHITI_NEO4J_USER = os.environ.get("LEGAL_KB_GRAPHITI_NEO4J_USER", "").strip()
GRAPHITI_NEO4J_PASSWORD = os.environ.get("LEGAL_KB_GRAPHITI_NEO4J_PASSWORD", "").strip()
GRAPHITI_DATABASE = os.environ.get("LEGAL_KB_GRAPHITI_DATABASE", "lex_nexus_graph").strip()

# Optional: bind host/port for this API
GRAPHITI_SERVICE_HOST = os.environ.get("GRAPHITI_SERVICE_HOST", "0.0.0.0").strip()
GRAPHITI_SERVICE_PORT = int(os.environ.get("GRAPHITI_SERVICE_PORT", "8765"))

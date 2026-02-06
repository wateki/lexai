"""
Optional Graphiti client for adding Legal KB entries as episodes (topic-case graph).
Requires ENABLE_GRAPHITI and FalkorDB or Neo4j configuration.
Uses pip-installed graphiti-core (e.g. pip install graphiti-core[falkordb]).

For add_episode/search API details and local codebase reference, see:
  docs/GRAPHITI_CONSUMPTION.md (and graphiti/examples/quickstart/quickstart_falkordb.py).
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from .config import (
    ENABLE_GRAPHITI,
    GRAPHITI_DATABASE,
    GRAPHITI_FALKORDB_HOST,
    GRAPHITI_FALKORDB_PORT,
    GRAPHITI_NEO4J_PASSWORD,
    GRAPHITI_NEO4J_URI,
    GRAPHITI_NEO4J_USER,
    GRAPHITI_PROVIDER,
)

logger = logging.getLogger(__name__)
_graphiti_client: Any = None


def get_graphiti_client():
    """Lazy-init Graphiti client (FalkorDB or Neo4j). Returns None if disabled or misconfigured."""
    global _graphiti_client
    if not ENABLE_GRAPHITI:
        return None
    if _graphiti_client is not None:
        return _graphiti_client
    try:
        from graphiti_core import Graphiti
        if GRAPHITI_PROVIDER == "falkordb":
            from graphiti_core.driver.falkordb_driver import FalkorDriver
            driver = FalkorDriver(
                host=GRAPHITI_FALKORDB_HOST,
                port=GRAPHITI_FALKORDB_PORT,
                database=GRAPHITI_DATABASE or "lex_nexus_graph",
            )
        elif GRAPHITI_PROVIDER == "neo4j" and GRAPHITI_NEO4J_URI:
            from graphiti_core.driver.neo4j_driver import Neo4jDriver
            driver = Neo4jDriver(
                uri=GRAPHITI_NEO4J_URI,
                user=GRAPHITI_NEO4J_USER,
                password=GRAPHITI_NEO4J_PASSWORD,
                database=GRAPHITI_DATABASE or "neo4j",
            )
        else:
            logger.warning("Graphiti enabled but provider/Neo4j config missing")
            return None
        _graphiti_client = Graphiti(graph_driver=driver)
        return _graphiti_client
    except Exception as e:
        logger.warning("Graphiti client init failed: %s", e)
        return None


def add_episode_sync(
    entry_id: str,
    document_type: str,
    jurisdiction: str,
    summary: str | None = None,
    case_name: str | None = None,
    citations: list[str] | None = None,
    decision_date: str | None = None,
) -> bool:
    """
    Add a Legal KB entry as a Graphiti episode (sync wrapper around async add_episode).
    Returns True if episode was added, False if Graphiti disabled or failed.
    """
    client = get_graphiti_client()
    if client is None:
        return False
    episode_body = (
        f"Legal document entry_id={entry_id} document_type={document_type} jurisdiction={jurisdiction}. "
        + (f"Case: {case_name}. " if case_name else "")
        + (f"Summary: {summary[:500]} " if summary else "")
        + (f"Citations: {', '.join((citations or [])[:20])} " if citations else "")
    )
    ref_time = datetime.now(timezone.utc)
    if decision_date:
        try:
            ref_time = datetime.fromisoformat(decision_date.replace("Z", "+00:00"))
        except Exception:
            pass
    try:
        asyncio.run(
            client.add_episode(
                name=f"legal_kb_entry_{entry_id}",
                episode_body=episode_body,
                source_description="Legal KB",
                reference_time=ref_time,
                group_id=GRAPHITI_DATABASE or None,
            )
        )
        return True
    except Exception as e:
        logger.warning("Graphiti add_episode failed: %s", e)
        return False

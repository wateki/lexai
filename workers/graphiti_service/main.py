"""
Lex Nexus Graphiti API service (Phase 3).
Exposes REST: POST /search, POST /episodes, GET /health.
Uses same env as legal_kb_processor (LEGAL_KB_GRAPHITI_*).
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config import (
    ENABLE_GRAPHITI,
    GRAPHITI_DATABASE,
    GRAPHITI_FALKORDB_HOST,
    GRAPHITI_FALKORDB_PORT,
    GRAPHITI_NEO4J_PASSWORD,
    GRAPHITI_NEO4J_URI,
    GRAPHITI_NEO4J_USER,
    GRAPHITI_PROVIDER,
    GRAPHITI_SERVICE_HOST,
    GRAPHITI_SERVICE_PORT,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_graphiti = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graphiti
    g = get_graphiti()
    if g:
        try:
            await g.build_indices_and_constraints()
            logger.info("Graphiti indices built")
        except Exception as e:
            logger.warning("build_indices_and_constraints failed: %s", e)
    yield
    if _graphiti:
        try:
            await _graphiti.close()
        except Exception:
            pass


def get_graphiti():
    """Lazy-init Graphiti. Returns None if disabled or misconfigured."""
    global _graphiti
    if not ENABLE_GRAPHITI:
        return None
    if _graphiti is not None:
        return _graphiti
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
        _graphiti = Graphiti(graph_driver=driver)
        return _graphiti
    except Exception as e:
        logger.warning("Graphiti init failed: %s", e)
        return None


app = FastAPI(title="Lex Nexus Graphiti API", version="0.1.0", lifespan=lifespan)


# --- DTOs ---

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    group_ids: list[str] | None = Field(None, description="Graph partition(s), e.g. ['lex_nexus_graph']")
    num_results: int = Field(default=10, ge=1, le=100)


class FactResult(BaseModel):
    uuid: str
    fact: str
    valid_at: str | None
    invalid_at: str | None
    created_at: str | None
    source_node_uuid: str | None = None


class SearchResponse(BaseModel):
    facts: list[FactResult]


class AddEpisodeRequest(BaseModel):
    name: str = Field(..., min_length=1)
    episode_body: str = Field(..., min_length=1)
    source_description: str = Field(default="Lex Nexus")
    reference_time: str | None = Field(None, description="ISO datetime; default now UTC")
    group_id: str | None = Field(None, description="Partition; default GRAPHITI_DATABASE")


class AddEpisodeResponse(BaseModel):
    success: bool
    message: str
    episode_uuid: str | None = None


# --- Routes ---

@app.get("/health")
async def health():
    g = get_graphiti()
    return {
        "status": "ok",
        "graphiti_configured": ENABLE_GRAPHITI and g is not None,
    }


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    g = get_graphiti()
    if g is None:
        raise HTTPException(status_code=503, detail="Graphiti not configured or unavailable")
    group_ids = req.group_ids if req.group_ids else [GRAPHITI_DATABASE or "lex_nexus_graph"]
    try:
        edges = await g.search(
            query=req.query,
            group_ids=group_ids,
            num_results=req.num_results,
        )
        facts = []
        for e in edges:
            facts.append(FactResult(
                uuid=e.uuid,
                fact=e.fact or "",
                valid_at=e.valid_at.isoformat() if e.valid_at else None,
                invalid_at=e.invalid_at.isoformat() if e.invalid_at else None,
                created_at=e.created_at.isoformat() if getattr(e, "created_at", None) else None,
                source_node_uuid=getattr(e, "source_node_uuid", None),
            ))
        return SearchResponse(facts=facts)
    except Exception as e:
        logger.exception("Search failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/episodes", response_model=AddEpisodeResponse)
async def add_episode(req: AddEpisodeRequest):
    g = get_graphiti()
    if g is None:
        raise HTTPException(status_code=503, detail="Graphiti not configured or unavailable")
    ref_time = datetime.now(timezone.utc)
    if req.reference_time:
        try:
            ref_time = datetime.fromisoformat(req.reference_time.replace("Z", "+00:00"))
        except ValueError:
            pass
    group_id = req.group_id or GRAPHITI_DATABASE or None
    try:
        from graphiti_core.nodes import EpisodeType
        result = await g.add_episode(
            name=req.name,
            episode_body=req.episode_body,
            source_description=req.source_description,
            reference_time=ref_time,
            source=EpisodeType.text,
            group_id=group_id,
        )
        episode_uuid = result.episode.uuid if result and getattr(result, "episode", None) else None
        return AddEpisodeResponse(success=True, message="Episode added", episode_uuid=episode_uuid)
    except Exception as e:
        logger.exception("Add episode failed")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=GRAPHITI_SERVICE_HOST,
        port=GRAPHITI_SERVICE_PORT,
        reload=False,
    )

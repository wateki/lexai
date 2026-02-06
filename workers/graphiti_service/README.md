# Lex Nexus Graphiti API Service (Phase 3)

REST API for the Graphiti topic–case graph: **search** and **add episode**. Used by the Next.js app for RAG context, case sync, and graph queries.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | `{ status, graphiti_configured }` |
| POST | `/search` | Body: `{ query, group_ids?, num_results? }` → `{ facts: [{ uuid, fact, valid_at, invalid_at, ... }] }` |
| POST | `/episodes` | Body: `{ name, episode_body, source_description?, reference_time?, group_id? }` → `{ success, message, episode_uuid? }` |

## Configuration

Same env as the Legal KB worker (see `../legal_kb_processor/README.md`):

- `LEGAL_KB_ENABLE_GRAPHITI=yes` — enable Graphiti
- `LEGAL_KB_GRAPHITI_PROVIDER=falkordb` (or `neo4j`)
- `LEGAL_KB_GRAPHITI_FALKORDB_HOST`, `LEGAL_KB_GRAPHITI_FALKORDB_PORT` (default 6379)
- `LEGAL_KB_GRAPHITI_DATABASE=lex_nexus_graph` (group_id / partition)
- Optional: `GRAPHITI_SERVICE_HOST=0.0.0.0`, `GRAPHITI_SERVICE_PORT=8765`

## Run

```bash
# From repo root or workers/graphiti_service
pip install -r requirements.txt
# Set env (e.g. LEGAL_KB_ENABLE_GRAPHITI=yes, FalkorDB host/port)
python main.py
# Or: uvicorn main:app --host 0.0.0.0 --port 8765
```

Next.js should set `GRAPHITI_SERVICE_URL=http://localhost:8765` (or the deployed URL) to call this service.

## Docker: FalkorDB only

To run only FalkorDB (this service runs on the host or in another container):

```bash
docker run -p 6379:6379 falkordb/falkordb:latest
```

See also `graphiti/mcp_server/docker/docker-compose-falkordb.yml` for FalkorDB + optional MCP server.

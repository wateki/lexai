# Consuming Graphiti (Local Codebase Reference)

This doc summarizes how to use **Graphiti** from the `graphiti/` repo in this workspace for Phase 3 (topic–case graph, RAG context, agent memory). The worker and any Graphiti service should align with this API.

---

## 1. Repo layout (relevant parts)

| Path | Purpose |
|------|--------|
| `graphiti/graphiti_core/` | Core library: `Graphiti`, drivers, search, nodes, edges |
| `graphiti/graphiti_core/graphiti.py` | Main class: `add_episode`, `search`, `search_` |
| `graphiti/graphiti_core/driver/falkordb_driver.py` | FalkorDB driver |
| `graphiti/graphiti_core/driver/neo4j_driver.py` | Neo4j driver |
| `graphiti/graphiti_core/search/search.py` | Search implementation (hybrid, RRF, etc.) |
| `graphiti/server/graph_service/` | Optional HTTP API (ingest + retrieve) |
| `graphiti/examples/quickstart/quickstart_falkordb.py` | FalkorDB init, add_episode, search |

---

## 2. Initialization (FalkorDB)

From `graphiti/examples/quickstart/quickstart_falkordb.py`:

```python
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver

# Env: FALKORDB_HOST (default localhost), FALKORDB_PORT (default 6379), optional FALKORDB_USERNAME, FALKORDB_PASSWORD
falkor_driver = FalkorDriver(
    host=os.environ.get('FALKORDB_HOST', 'localhost'),
    port=int(os.environ.get('FALKORDB_PORT', '6379')),
    username=os.environ.get('FALKORDB_USERNAME'),
    password=os.environ.get('FALKORDB_PASSWORD'),
)
graphiti = Graphiti(graph_driver=falkor_driver)
# Optional: LLM/embedder for entity extraction (defaults used if not passed)
```

The worker uses the same pattern in `workers/legal_kb_processor/legal_kb_processor/graphiti_client.py` with `GRAPHITI_FALKORDB_HOST`, `GRAPHITI_FALKORDB_PORT`, `GRAPHITI_DATABASE` (as `group_id`).

---

## 3. Adding episodes

**Signature** (`graphiti_core/graphiti.py`):

```python
async def add_episode(
    self,
    name: str,
    episode_body: str,
    source_description: str,
    reference_time: datetime,
    source: EpisodeType = EpisodeType.message,
    group_id: str | None = None,
    uuid: str | None = None,
    ...
) -> AddEpisodeResults:
```

- **episode_body**: String content (or JSON string). Graphiti extracts entities and relationships from this text.
- **reference_time**: Used for temporal validity (`valid_at`).
- **group_id**: Partitions the graph (e.g. per org or database name). Worker uses `GRAPHITI_DATABASE` or default.

**Example (quickstart):**

```python
from graphiti_core.nodes import EpisodeType

await graphiti.add_episode(
    name='legal_kb_entry_abc-123',
    episode_body='Legal document entry_id=abc-123 document_type=case_law jurisdiction=Kenya. Case: Smith v Acme. Summary: ...',
    source_description='Legal KB',
    reference_time=datetime.now(timezone.utc),
    source=EpisodeType.text,  # or EpisodeType.message
    group_id='lex_nexus_graph',
)
```

The worker’s `add_episode_sync()` in `graphiti_client.py` builds a single string from entry metadata and calls this (with `asyncio.run`).

---

## 4. Search (hybrid: semantic + BM25)

**Signature** (`graphiti_core/graphiti.py`):

```python
async def search(
    self,
    query: str,
    center_node_uuid: str | None = None,
    group_ids: list[str] | None = None,
    num_results: int = DEFAULT_SEARCH_LIMIT,  # 10
    search_filter: SearchFilters | None = None,
) -> list[EntityEdge]:
```

- Returns **list of EntityEdge** (facts). Each edge has: `uuid`, `fact`, `valid_at`, `invalid_at`, `source_node_uuid`, etc.
- **group_ids**: Restrict search to one or more partitions (e.g. `['lex_nexus_graph']`).
- **center_node_uuid**: Rerank by graph distance to this node (e.g. a case or document node).

**Example (quickstart):**

```python
edges = await graphiti.search(
    'precedents for wrongful termination in Kenya',
    group_ids=['lex_nexus_graph'],
    num_results=10,
)
for e in edges:
    print(e.uuid, e.fact, e.valid_at)
```

**Advanced search** (nodes + edges + config): use `search_()` with a `SearchConfig` (see `graphiti_core/search/search_config_recipes.py`).

---

## 5. Server API (optional HTTP layer)

The repo’s **server** (`graphiti/server/graph_service/`) exposes:

| Method | Path | Purpose |
|--------|------|--------|
| POST | `/search` | Body: `{ "query", "group_ids", "max_facts" }` → `{ "facts": [ { "uuid", "fact", "valid_at", "invalid_at", ... } ] }` |
| POST | `/messages` | Add episodes (messages) for a `group_id` |
| POST | `/get-memory` | Memory over messages (builds query from message list) |

**Note:** The bundled server is wired for **Neo4j** (see `config.py`: `neo4j_uri`, `neo4j_user`, `neo4j_password`). For FalkorDB, either:
- Run a **separate** small FastAPI service that uses `FalkorDriver` + `Graphiti` and exposes the same `/search` and ingest semantics, or
- Use the **worker** for ingest (already does) and add a minimal **search service** (FalkorDB + `graphiti.search`) that Next.js can call.

---

## 6. Aligning the worker with the local codebase

The worker (`workers/legal_kb_processor/legal_kb_processor/graphiti_client.py`) uses the **pip-installed** `graphiti-core` and already matches this usage:

- `get_graphiti_client()` builds `Graphiti(graph_driver=FalkorDriver(...))` or Neo4j equivalent.
- `add_episode_sync()` calls `add_episode(name=..., episode_body=..., source_description=..., reference_time=..., group_id=...)`.

For **search**, the worker does not call Graphiti today. Any Graphiti **search** (e.g. for RAG context or graph query APIs) should:

1. Use the same driver/config as the worker (FalkorDB + `GRAPHITI_DATABASE` as `group_id`), and
2. Call `await graphiti.search(query, group_ids=[group_id], num_results=...)` and map `EntityEdge` to the shape your API expects (e.g. `{ uuid, fact, valid_at, invalid_at }`).

---

## 7. References

- **Local quickstart:** `graphiti/examples/quickstart/quickstart_falkordb.py`
- **Main class:** `graphiti/graphiti_core/graphiti.py` (`Graphiti`, `add_episode`, `search`, `search_`)
- **Server DTOs:** `graphiti/server/graph_service/dto/retrieve.py` (`SearchQuery`, `FactResult`, `SearchResults`)
- **Worker client:** `workers/legal_kb_processor/legal_kb_processor/graphiti_client.py`

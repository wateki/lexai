# Legal KB Processor Worker (V2 — Full Pipeline)

Background worker that processes `legal_kb_processing_jobs` with the **full Docling + PageIndex pipeline**: extraction, tree generation, LLM metadata, citation parsing, optional embedding, and optional Graphiti episode.

## Flow

1. Poll `legal_kb_processing_jobs` for `status = 'queued'` and `pipeline = 'docling_pageindex'`.
2. Download file from Supabase Storage to a temp path.
3. **Docling:** Convert document → markdown + structured JSON (with retries).
4. **PageIndex:** Build reasoning-ready tree from markdown (`md_to_tree`).
5. **LLM metadata extraction:** Title, summary, key_points, legal_principles, case/statute fields, practice_areas, keywords (merges with existing row; does not overwrite user-provided values).
6. **Citation parsing (eyecite):** Parse case and statute citations from markdown → `cited_cases`, `cited_statutes`.
7. **Optional embedding:** Generate `ai_embedding` for pgvector quick lookups (if `LEGAL_KB_ENABLE_VECTOR_FALLBACK=yes`).
8. **Optional Graphiti:** Add document as episode for topic-case graph (if `LEGAL_KB_ENABLE_GRAPHITI=yes`).
9. Final DB update and mark job `completed` or `failed`.

## Dependencies

- **docling**, **eyecite**, **graphiti-core:** Installed via pip (see `requirements.txt`). Use `graphiti-core[neo4j]` instead of `[falkordb]` if you use Neo4j.
- **PageIndex:** Used from local repo at `../pageIndex/PageIndex` (path added at runtime; no PyPI package).

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Service role key (Storage + DB) |
| `OPENAI_API_KEY` | Yes (for extraction) | LLM metadata extraction; PageIndex summaries; embeddings |
| `LEGAL_KB_LLM_MODEL` | No | Default `gpt-4o-mini` |
| `LEGAL_KB_EMBEDDING_MODEL` | No | Default `text-embedding-3-small` |
| `PAGEINDEX_ADD_NODE_SUMMARY` | No | `yes` to add node summaries (needs OPENAI_API_KEY) |
| `LEGAL_KB_MAX_MARKDOWN_EXTRACTION` | No | Max chars for LLM context (default 120000) |
| `LEGAL_KB_ENABLE_VECTOR_FALLBACK` | No | `yes` to populate `ai_embedding` |
| `LEGAL_KB_MAX_EMBEDDING_TEXT` | No | Max chars for embedding (default 8000) |
| `LEGAL_KB_ENABLE_GRAPHITI` | No | `yes` to add episodes to Graphiti |
| `LEGAL_KB_GRAPHITI_PROVIDER` | No | `falkordb` or `neo4j` |
| `LEGAL_KB_GRAPHITI_FALKORDB_HOST` | No | Default `localhost` |
| `LEGAL_KB_GRAPHITI_FALKORDB_PORT` | No | Default `6379` |
| `LEGAL_KB_GRAPHITI_NEO4J_URI` | No | Required for neo4j |
| `LEGAL_KB_LOG_LEVEL` | No | Default `INFO` |
| `LEGAL_KB_DOCLING_MAX_RETRIES` | No | Default 2 |
| `LEGAL_KB_LLM_MAX_RETRIES` | No | Default 3 |

## Setup

From repo root (so `pageIndex` path resolves for local PageIndex):

```bash
cd workers/legal_kb_processor
python -m venv .venv
.venv\Scripts\activate   # Windows
# .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
# Ensure ../../pageIndex/PageIndex exists for PageIndex
```

## Run

From repo root or from `workers/legal_kb_processor` (with `PYTHONPATH` including parent so `legal_kb_processor` is importable):

```bash
# Process one job and exit (good for cron)
python -m legal_kb_processor.main --once

# Poll every 60 seconds
python -m legal_kb_processor.main --interval 60
```

## Full pipeline scope

- Docling conversion (with retries).
- PageIndex tree generation (optional node summaries).
- LLM metadata extraction (title, summary, key_points, legal_principles, case/statute fields, practice_areas, keywords).
- Citation parsing via **eyecite** (local repo) → `cited_cases`, `cited_statutes`.
- Optional pgvector embedding for quick lookups.
- Optional Graphiti episode for topic-case graph.

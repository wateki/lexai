# Implementation Status vs LEXAI_IMPLEMENTATION_PLAN_V2

This document tracks progress against the deliverables in [LEXAI_IMPLEMENTATION_PLAN_V2.md](./LEXAI_IMPLEMENTATION_PLAN_V2.md). For phase-by-phase compliance verification against the plan, see [PLAN_COMPLIANCE_VERIFICATION.md](./PLAN_COMPLIANCE_VERIFICATION.md).

---

## Summary

| Phase | Focus | Status | Done | Total |
|-------|--------|--------|------|-------|
| **1** | Legal KB: Docling + PageIndex pipeline | **Largely complete** | 11 | 12 |
| **2** | Reasoning-based search & RAG | **Complete** | 7 | 7 |
| **3** | Graphiti: Topic-case graph | **Complete** | 9 | 9 |
| **4** | Case documents: Docling + PageIndex | **Largely complete** | 5 | 6 |
| **5** | Proactive brain with Graphiti memory | **Complete** | 8 | 8 |
| **6** | Optimization & production | Not started | 0 | 8 |

**Overall:** Phase 1 is largely complete (11/12); Phases 2, 3, and 5 are complete; Phase 4 is largely complete (5/6, UI pending). Remaining: Phase 1 storage RLS + optional UI; Phase 4 document-grounded UI; Phase 6 not started. In terms of *phased deliverables*, **40 of 50** checklist items are done (~80%).

---

## Phase 1: Legal KB — Docling + PageIndex Pipeline

| # | Deliverable | Status | Evidence |
|---|-------------|--------|----------|
| 1 | **PostgreSQL schema update:** Add `docling_markdown`, `docling_json`, `pageindex_tree`, `pageindex_metadata` to `legal_knowledge_base`. | Done | `case-aware-lex-nexus-94/supabase/migrations/00016_legal_kb_docling_pageindex_columns.sql` adds these columns plus `processing_pipeline`, `processing_status`. `ai_embedding` already in schema. |
| 2 | **Supabase Storage bucket:** `legal-kb` with RLS and path convention. | Partial | Bucket name `legal-kb` and path `{org_id}/{entry_id}/{filename}` used in `LegalKbIngestService` and upload API. No migration for bucket creation or storage RLS in repo; bucket/RLS may be configured in Supabase Dashboard. |
| 3 | **`legal_kb_processing_jobs` table:** Queue for Docling + PageIndex jobs. | Done | `00015_legal_kb_docling_jobs.sql` creates table; `00016` adds `pipeline` column (default `docling_pageindex`). |
| 4 | **POST /api/legal-database/upload:** Accept multipart file + metadata; enqueue job. | Done | `src/app/api/legal-database/upload/route.ts` + `LegalKbIngestService.uploadAndProcess()`; returns `id`, `file_url`, `processing_status`. |
| 5 | **Python worker:** Docling + PageIndex + metadata extraction + citation parsing + optional embedding + Graphiti episode. | Done | `workers/legal_kb_processor/`: pipeline (Docling, PageIndex, LLM metadata, eyecite, optional embedding, optional Graphiti), config, main loop. |
| 6 | **PATCH /api/legal-database/entries/[id]:** Metadata-only edits. | Done | `src/app/api/legal-database/entries/[id]/route.ts` (PATCH with allowed fields). |
| 7 | **POST /api/legal-database/entries/[id]/replace-document:** Re-run pipeline. | Done | `src/app/api/legal-database/entries/[id]/replace-document/route.ts` calls `replaceDocumentAndReprocess`, enqueues job. |
| 8 | **GET /api/legal-database/entries:** List with filters. | Done | `src/app/api/legal-database/entries/route.ts` (GET with document_type, jurisdiction, search, limit, offset). |
| 9 | **GET /api/legal-database/entries/[id]:** Get one entry with processing status. | Done | `src/app/api/legal-database/entries/[id]/route.ts` (GET returns full entry including `pageindex_tree`, `processing_status`). |
| 10 | **DELETE /api/legal-database/entries/[id]:** Soft-delete. | Done | Same file; DELETE sets `is_active = false`. |
| 11 | **Optional UI:** Upload form, list, edit, replace (calls same APIs). | Pending | `src/app/legal-database/page.tsx` exists; not verified for upload form, list, edit, replace calling the new APIs. |
| 12 | **Documentation:** API spec, pipeline architecture, processing flow. | Done | Root `README.md`, `workers/legal_kb_processor/README.md` describe pipeline and usage. |

---

## Phase 2: Reasoning-Based Search & RAG

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | POST /api/legal-database/search/reasoning (PageIndex tree search API) | Done |
| 2 | Multi-document reasoning function (parallel tree search) | Done |
| 3 | POST /api/ai/rag-query (PageIndex + Graphiti context) | Done |
| 4 | Citation extraction (document + page + section + reasoning) | Done |
| 5 | Reasoning trace formatter for UI | Done |
| 6 | Optional: Keyword fallback (PostgreSQL) for entity lookups) | Done |
| 7 | Documentation: PageIndex search API, reasoning trace, RAG usage | Done |

**Evidence:** `case-aware-lex-nexus-94/src/app/api/legal-database/search/reasoning/route.ts`, `src/app/api/ai/rag-query/route.ts`, `src/services/server/legalReasoningSearchService.ts`, `src/lib/llm/treeSearch.ts`, `src/lib/llm/pageIndexTree.ts`, `src/lib/llm/citations.ts`. Keyword fallback via `options.keyword_fallback` on reasoning POST. See **Phase 2 API docs** section below.

---

## Phase 3: Graphiti Topic-Case Graph

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | Graphiti infrastructure (FalkorDB or Neo4j; Graphiti SDK) | Done |
| 2 | Document-to-episode sync (backfill Legal KB to Graphiti) | Done |
| 3 | Case-to-episode sync | Done |
| 4 | Automatic relationship extraction (verify Graphiti builds graph) | Done |
| 5 | Topic change impact (add episode; graph-driven reassessment) | Done |
| 6 | Temporal query support | Done |
| 7 | Graph query endpoints (relationships, temporal context) | Done |
| 8 | Monitoring (graph health, episode rate, relationship counts) | Done |
| 9 | Documentation (Graphiti architecture, episode format, etc.) | Done |

**Evidence:**
- **Infrastructure:** `docker-compose.graphiti.yml` (FalkorDB); `workers/graphiti_service/` (FastAPI: `/search`, `/episodes`, `/health`) using same env as worker (`LEGAL_KB_GRAPHITI_*`).
- **Backfill:** `workers/legal_kb_processor/scripts/backfill_graphiti.py` (Supabase → Legal KB rows → `add_episode_sync`). Run with `PYTHONPATH=workers/legal_kb_processor python workers/legal_kb_processor/scripts/backfill_graphiti.py [--limit N] [--dry-run]`.
- **Case sync:** `CaseService` create/update calls `syncCaseToGraphitiIfEnabled()` (fire-and-forget) → `graphitiAddEpisode` with case payload.
- **Topic change:** Worker adds Legal KB doc as episode on processing. Reassessment is graph-driven: `topic_entity_links` table records which cases use which Legal KB entries (filled from proactive brain and combined search). When an entry is updated, worker can call `POST /api/legal-database/entries/[id]/on-processing-complete` (CRON_SECRET) to enqueue proactive_brain_jobs for affected cases (trigger `topic_change`).
- **Temporal:** Graphiti SDK provides `valid_at`/`invalid_at` on edges; search uses current time by default.
- **Endpoints:** `POST /api/graphiti/search`, `POST /api/graphiti/episodes`; RAG (`POST /api/ai/rag-query`) enriches with Graphiti facts when `LEGAL_KB_ENABLE_GRAPHITI=yes` and `GRAPHITI_SERVICE_URL` set.
- **Monitoring:** `GET /health` on Graphiti service returns `graphiti_configured`.
- **Docs:** [GRAPHITI_CONSUMPTION.md](./GRAPHITI_CONSUMPTION.md), `workers/graphiti_service/README.md`, local `graphiti/` repo.

**Phase 3 API (Next.js):** `POST /api/graphiti/search` (body: `query`, `group_ids?`, `num_results?` → `{ facts }`); `POST /api/graphiti/episodes` (body: `name`, `episode_body`, `source_description?`, `reference_time?`, `group_id?`). Set `GRAPHITI_SERVICE_URL` (e.g. `http://localhost:8765`) and `LEGAL_KB_ENABLE_GRAPHITI=yes` for RAG context and case sync.

### Phase 3 summary (runbook)

1. **Graphiti API service** (`workers/graphiti_service/`)
   - FastAPI app using the same env as the Legal KB worker (`LEGAL_KB_GRAPHITI_*`).
   - **Endpoints:**
     - **GET /health** — `{ status, graphiti_configured }`
     - **POST /search** — body: `query`, `group_ids?`, `num_results?` → `{ facts: [{ uuid, fact, valid_at, invalid_at, ... }] }`
     - **POST /episodes** — body: `name`, `episode_body`, `source_description?`, `reference_time?`, `group_id?` → `{ success, episode_uuid? }`
   - Lifespan: builds indices on startup and closes the driver on shutdown.
   - **Run:** `pip install -r requirements.txt` then `python main.py` (or uvicorn); default port **8765**.

2. **Backfill script** (`workers/legal_kb_processor/scripts/backfill_graphiti.py`)
   - Reads active rows from Supabase `legal_knowledge_base`.
   - Calls `add_episode_sync` for each (same as worker).
   - **Usage:** `PYTHONPATH=workers/legal_kb_processor python workers/legal_kb_processor/scripts/backfill_graphiti.py [--limit N] [--dry-run]`
   - Requires `LEGAL_KB_ENABLE_GRAPHITI=yes`, Supabase env, and FalkorDB/Neo4j config.

3. **Next.js**
   - `src/services/server/graphitiService.ts` — `graphitiHealth()`, `graphitiSearch()`, `graphitiAddEpisode()`, `formatGraphitiFactsForPrompt()`; uses `GRAPHITI_SERVICE_URL`.
   - **POST /api/graphiti/search** — authenticated; proxies to Graphiti service search.
   - **POST /api/graphiti/episodes** — authenticated; add episode (e.g. case sync, topic-change).
   - **RAG** (`POST /api/ai/rag-query`) — when `LEGAL_KB_ENABLE_GRAPHITI=yes` and `GRAPHITI_SERVICE_URL` are set, runs Graphiti search and adds formatted facts into the prompt as related context.

4. **Case-to-episode sync**
   - `CaseService` create/update calls `syncCaseToGraphitiIfEnabled()` (fire-and-forget).
   - Builds an episode body from case id, title, status, matter type, jurisdiction, client id, and sends it to the Graphiti service.

5. **Topic change / docs**
   - Worker already adds each processed Legal KB document as an episode.
   - Optional “update” episodes can be sent via **POST /api/graphiti/episodes**.
   - `docker-compose.graphiti.yml` — FalkorDB only (port 6379).
   - This document and [GRAPHITI_CONSUMPTION.md](./GRAPHITI_CONSUMPTION.md) + `workers/graphiti_service/README.md`.

**Env (Next.js + worker + Graphiti service):**
- `LEGAL_KB_ENABLE_GRAPHITI=yes` — turn on Graphiti (worker + service).
- `GRAPHITI_SERVICE_URL` — e.g. `http://localhost:8765` (Next.js calls this for search/episodes).
- `LEGAL_KB_GRAPHITI_FALKORDB_HOST`, `LEGAL_KB_GRAPHITI_FALKORDB_PORT`, `LEGAL_KB_GRAPHITI_DATABASE` — for worker and Graphiti service.

**How to run it:**
1. Start FalkorDB: `docker compose -f docker-compose.graphiti.yml up -d`
2. Set the env vars above (and Supabase/OpenAI for the worker).
3. Run the Graphiti service: `cd workers/graphiti_service && pip install -r requirements.txt && python main.py`
4. Optionally backfill: `PYTHONPATH=workers/legal_kb_processor python workers/legal_kb_processor/scripts/backfill_graphiti.py [--limit N] [--dry-run]`
5. Create/update a case in the app to sync it to Graphiti; use RAG with a query to get PageIndex + Graphiti context.

---

## Phase 4: Case Documents — Docling + PageIndex

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | Docling + PageIndex pipeline for case documents | Done |
| 2 | Document schema update (docling_*, pageindex_tree on `documents`) | Done |
| 3 | Auto-processing on case document upload | Done |
| 4 | Case document RAG endpoint: POST /api/cases/[id]/documents/search | Done |
| 5 | Document-grounded research UI (“Ask about this case’s documents”) | Not started |
| 6 | Combined search (Legal KB + case documents) | Done |
| 7 | Single RAG answer (case docs + Legal KB + Graphiti in one LLM call) | Done |

**Evidence:**
- **Schema:** `case-aware-lex-nexus-94/supabase/migrations/00017_case_documents_docling_pageindex.sql` — adds `docling_markdown`, `docling_json`, `pageindex_tree`, `pageindex_metadata`, `processing_pipeline`, `processing_status` to `documents`; creates `case_document_processing_jobs` (document_id, case_id, organization_id, storage_bucket, storage_path, status, pipeline).
- **Worker:** `workers/legal_kb_processor/legal_kb_processor/main.py` — `poll_one_case_doc_job()`, `process_case_document_job()` (download from bucket → Docling → PageIndex → update `documents`; optional Graphiti episode). Main loop processes Legal KB jobs first, then one case-doc job per cycle.
- **Enqueue on upload:** `DocumentService.create()` — when a document is created with a file and `case_id`, inserts into `case_document_processing_jobs` and sets `documents.processing_status = 'queued'`.
- **Case document RAG:** `caseDocumentReasoningSearch()` in `legalReasoningSearchService.ts`; **POST /api/cases/[id]/documents/search** (body: `query`, `options?: { max_results?, include_reasoning_trace? }`).
- **Combined search:** **POST /api/cases/[id]/search/combined** — returns `{ legal_kb, case_documents }`. Also records topic–case links for reassessment.
- **Single RAG answer:** **POST /api/cases/[id]/search/answer** — body: `{ query, options? }`; runs Legal KB + case docs + Graphiti in one LLM call; returns `{ answer, sources: { legal_kb, case_documents }, reasoning_traces }`. Records case_interaction episode when Graphiti is enabled.

### Phase 4 summary (runbook)

1. **Migration**
   - Apply `00017_case_documents_docling_pageindex.sql` so `documents` has pipeline columns and `case_document_processing_jobs` exists.

2. **Worker (case documents)**
   - Same worker as Legal KB: `workers/legal_kb_processor`. Ensure Supabase (including storage bucket `documents`), OpenAI, and optional Graphiti env are set.
   - **Run:** `PYTHONPATH=workers/legal_kb_processor python -m legal_kb_processor.main [--once] [--interval 60]`. Each cycle: process one Legal KB job if queued, else one case-doc job. Case-doc jobs use `storage_bucket`/`storage_path` to download the file from Supabase Storage.

3. **Next.js**
   - **Upload:** Creating a document with a file and `case_id` (e.g. via DocumentService or upload API that uses it) enqueues a case-doc job and sets `processing_status = 'queued'`.
   - **Case document search:** **POST /api/cases/:id/documents/search** — body: `{ query, options?: { max_results?, include_reasoning_trace? } }`. Returns same shape as reasoning search (results with relevant_sections, reasoning_trace, confidence, file_url).
   - **Combined search:** **POST /api/cases/:id/search/combined** — same body; returns `{ legal_kb, case_documents }` (each a ReasoningSearchResponse).
   - **Single RAG answer:** **POST /api/cases/:id/search/answer** — same body; returns one combined answer plus sources (Plan §7.2).

4. **Env**
   - Same as Phase 2 (OpenAI for PageIndex) and Phase 3 if using Graphiti. Case docs use storage bucket **documents** and path `documents/${org_id}/${filename}`.

5. **Document-grounded UI**
   - "Ask about this case's documents" can call **POST /api/cases/[id]/documents/search** or **/search/combined** and display sections, reasoning trace, and file links; UI implementation left for later.

---

## Phase 5: Proactive Brain with Graphiti Memory

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | ProactiveBrainAgent (per-case analysis, PageIndex + Graphiti) | Done |
| 2 | Trigger system (document upload, stage change, case interaction) | Done |
| 3 | Agent memory (Graphiti episode tracking for interactions) | Done |
| 4 | Digest generation (daily/weekly, case + Legal KB + calendar) | Done |
| 5 | “What you might miss” (gaps, missing filings, risk flags) | Done (in digest) |
| 6 | Suggest actions API (profile-driven) | Done |
| 7 | Background jobs (scheduled analysis for active cases) | Done |
| 8 | Documentation | Done (runbook below) |

**Evidence:** Migration `00018_proactive_brain_jobs_and_digests.sql`; `proactiveBrainService.ts` (runProactiveBrainAnalysis, enqueue, getLatestDigest, processOneProactiveBrainJob, suggestActionsForCase); digest completion adds Graphiti episode (agent memory); APIs: `POST /api/cases/[id]/proactive-brain/trigger`, `GET /api/cases/[id]/proactive-brain/digest`, `POST /api/cases/[id]/proactive-brain/suggestions`, `GET|POST /api/cron/proactive-brain`; triggers on document upload, case create/update, and topic_change (reassessment). **Case interaction (on_case_interaction):** When user prompts on a case via **POST /api/cases/[id]/search/answer** or **POST /api/ai/rag-query** with `context.case_id`, a Graphiti episode (type `case_interaction`) is recorded with query and response summary.

### Phase 5 runbook

Apply `00018_proactive_brain_jobs_and_digests.sql`. Trigger analysis: `POST /api/cases/:caseId/proactive-brain/trigger`. Case create/update and document upload (with case_id) also enqueue a job. Process jobs: call `GET` or `POST` `/api/cron/proactive-brain` with `Authorization: Bearer <CRON_SECRET>` or `x-cron-secret`; schedule via Vercel Cron or external cron. Get digest: `GET /api/cases/:caseId/proactive-brain/digest`. Suggest actions: `POST /api/cases/:caseId/proactive-brain/suggestions` (body optional: `{ "max_actions": N }`).

**Plan compliance:** See [PLAN_COMPLIANCE_VERIFICATION.md](./PLAN_COMPLIANCE_VERIFICATION.md) for phase-by-phase verification against LEXAI_IMPLEMENTATION_PLAN_V2.md.

Summary of what’s in place for Phase 5:
1. Database (migration 00018_proactive_brain_jobs_and_digests.sql)
proactive_brain_jobs — case_id, organization_id, trigger (manual | document_upload | case_update | schedule), status, attempts, last_error. RLS: org members can SELECT/INSERT/UPDATE.
ai_case_digests — case_id, organization_id, digest (JSONB), model_name, generated_at. RLS: org/case-team can SELECT; worker uses service role to INSERT.
2. Proactive Brain service (proactiveBrainService.ts)
runProactiveBrainAnalysis(caseId, organizationId, options) — Loads case, runs Legal KB + case-doc reasoning search (with optional supabase for cron), optional Graphiti search, then one LLM call to build digest (summary, risks, deadlines, next_actions, what_you_might_miss, items). Writes to ai_case_digests and, when jobId is set, marks the job completed.
enqueueProactiveBrainJob(caseId, organizationId, trigger, createdBy?) — Inserts into proactive_brain_jobs.
getLatestDigest(caseId) — Returns latest digest for the case (user client, RLS).
processOneProactiveBrainJob() — Uses service client to take one queued job, set status to processing, run analysis, then set completed/failed.
3. Search services
reasoningSearch and caseDocumentReasoningSearch accept options.supabase so the cron path can use the service-role client and bypass RLS.
4. APIs
POST /api/cases/[id]/proactive-brain/trigger — Enqueues a job (optional body { "trigger": "manual" }), returns { job_id }.
GET /api/cases/[id]/proactive-brain/digest — Returns { digest } or { digest: null }.
GET|POST /api/cron/proactive-brain — Processes one queued job. Secured with CRON_SECRET via Authorization: Bearer <secret> or x-cron-secret header.
5. Triggers
Document upload — When a document is created with a file and case_id, after enqueueing the case-doc processing job, a proactive-brain job is enqueued with trigger document_upload.
Case create/update — After Graphiti sync, a proactive-brain job is enqueued with trigger case_update.
6. Docs
IMPLEMENTATION_STATUS_V2.md — Phase 5 table updated (6/8 done: agent memory and profile-driven suggestions pending). Runbook added: migration, trigger API, cron URL + CRON_SECRET, digest API. Summary set to 38/50 (~76%).
How to run it
Apply migration 00018_proactive_brain_jobs_and_digests.sql.
Optionally set CRON_SECRET in env.
Trigger analysis: POST /api/cases/:caseId/proactive-brain/trigger or rely on case/document triggers.
Process the queue: call GET or POST /api/cron/proactive-brain with the cron secret on a schedule (e.g. Vercel Cron every 5–15 minutes).
Read the digest: GET /api/cases/:caseId/proactive-brain/digest.
---

## Phase 6: Optimization & Production

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | PageIndex tree caching (e.g. Redis) | Not started |
| 2 | Parallel tree search | Not started |
| 3 | Query routing (simple → PostgreSQL, complex → PageIndex) | Not started |
| 4 | Monitoring dashboards (PageIndex, Graphiti, pipeline) | Not started |
| 5 | Error tracking (e.g. Sentry) | Not started |
| 6 | Load testing (PageIndex 100+ concurrent) | Not started |
| 7 | Production readiness (security, performance, failover) | Not started |
| 8 | Documentation (deploy, monitoring, troubleshooting) | Not started |

---

## Recommended Next Steps

1. **Close Phase 1:** Add storage RLS for `legal-kb` (if not already in Dashboard) and confirm Legal Database UI uses upload, list, edit, replace APIs.
2. **Start Phase 2:** Implement `POST /api/legal-database/search/reasoning` (PageIndex tree search) and then `POST /api/ai/rag-query` (RAG with reasoning traces and citations).
3. **Phase 3 in parallel (optional):** Deploy Graphiti (FalkorDB/Neo4j), backfill Legal KB as episodes, add case-to-episode sync and graph query endpoints.

This status doc can be updated as phases are completed; consider ticking the checkboxes in LEXAI_IMPLEMENTATION_PLAN_V2.md to keep the plan and status in sync.

---

## Phase 2 API docs (Reasoning search & RAG)

### POST /api/legal-database/search/reasoning

Reasoning-based search using PageIndex trees (LLM navigates tree → relevant nodes → section extraction from `docling_markdown`).

**Request body:**
```json
{
  "query": "What precedents apply to wrongful termination in Kenya?",
  "context": { "jurisdiction": "Kenya", "document_ids": ["optional-id1", "id2"] },
  "options": { "max_results": 10, "include_reasoning_trace": true, "keyword_fallback": false }
}
```

**Response:** `{ results: ReasoningSearchHit[], total, query_time_ms [, keyword_fallback, keyword_results ] }`. Each hit has `document_id`, `document_title`, `relevant_sections` (section_title, content, page_numbers), `reasoning_trace` (string[]), `confidence`, `file_url`. If no tree results and `keyword_fallback: true`, returns `keyword_results` from PostgreSQL search.

### POST /api/ai/rag-query

RAG over Legal KB using PageIndex retrieval; returns answer with citations and reasoning traces.

**Request body:**
```json
{
  "query": "Summarise the test for wrongful dismissal.",
  "context": { "jurisdiction": "Kenya", "case_id": "optional" },
  "options": { "max_sources": 10, "include_reasoning_trace": true }
}
```

**Response:** `{ answer, sources, reasoning_traces, graph_context, explainability }`. Graphiti context is stubbed (empty until Phase 3).

### Citation & reasoning trace formatting

- `src/lib/llm/citations.ts`: `formatHitAsCitations`, `formatResultsAsCitations`, `formatReasoningTrace`, `reasoningTraceSummary` for UI-ready citations and reasoning display.

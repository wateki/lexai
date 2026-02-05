# LexAI Implementation Plan & Guide

This document is a **detailed, robust implementation plan** to deliver the LexAI vision (one-stop shop, second brain, living Legal KB, topic–case index, proactive analysis). It is grounded in the **current state** of the platform and assumes **we do not yet have a populated Legal KB** — we **build it** primarily by **API upload** of actual documents (PDFs, etc.), and keep it **living and continuously updated**.

**Core Strategy:** **Accuracy-first** approach using **Docling + PageIndex** for reasoning-based retrieval (98.7% accuracy) with **Graphiti** for relationship tracking, prioritizing legal precision over speed.

**Strategy reference:** [LEXAI_STRATEGY_VISION.md](./LEXAI_STRATEGY_VISION.md)  
**Architecture reference:** [Legal_kb.md](./Legal_kb.md)  
**Graphiti Integration Analysis:** [GRAPHITI_INTEGRATION_ANALYSIS.md](./GRAPHITI_INTEGRATION_ANALYSIS.md)

---

## 1. Current State Summary

### 1.1 What Exists (case-aware-lex-nexus-94)

| Area | Status | Notes |
|------|--------|--------|
| **Schema** | ✅ | `legal_knowledge_base` table with document_type, jurisdiction, case_name, case_citation, court_name, statute_name, title, summary, full_text, key_points, legal_principles, practice_areas, keywords, file_url, ai_embedding (VECTOR 1536), usage_count, last_used_at, is_active, created_by, etc. |
| **Legal KB data** | ⚠️ | Table exists; seed has a few sample rows (case law + statutes). **No real, firm-populated Legal KB** — we need to build it via **document upload** and keep it living. |
| **Search** | ✅ | `search_legal_knowledge_secure(query, org_id, limit)` — keyword/ILIKE on title, summary, keywords; org-scoped; updates usage_count/last_used_at. |
| **Vector search (Legal KB)** | ✅ | `search_legal_knowledge_vector(embedding, org_id, limit, filters)` in DB; **requires rows to have ai_embedding populated** (currently none). |
| **document_chunks** | ✅ | Table + RLS + `search_document_chunks_vector` for case documents; **no pipeline yet** to chunk/embed case docs. |
| **API** | ✅ | `GET /api/legal-database/search?q=...` calls secure search; Legal Database page uses it. No upload or CRUD API for Legal KB entries. |
| **Cases, clients, documents, team, calendar** | ✅ | Full CRUD, lifecycle, RLS. Case documents: upload to Supabase Storage, link to case; no chunking/embedding pipeline yet. |
| **Topic–case index** | ❌ | Not implemented. |
| **Proactive / digest / insights pipelines** | ❌ | Mock or stubbed; no background jobs. |

### 1.2 Gaps to Address

1. **Legal KB is empty in practice** — Build it by **API upload** of actual documents (PDFs of judgments, statutes, regulations, articles); process and store in `legal_knowledge_base`; keep it **living** (add, update, replace via API).
2. **No upload or ingest flow** for Legal KB — Need: **upload API** (multipart file + metadata), storage bucket, processing pipeline (extract text, metadata), and APIs to create/update/replace entries. Any client (UI, script, integration, bulk ingest) uses the same API.
3. **No embeddings** for Legal KB rows — So vector search exists but returns nothing until we backfill; need an embedding pipeline for uploaded (and existing) KB documents.
4. **No topic–case graph/index** — So we cannot yet “reassess when topic X changes.”
5. **Case documents** not chunked/embedded — So RAG over case docs is not yet possible.
6. **Proactive brain** not implemented — No background analysis per case/stage or trigger-based reassessment.

---

## 2. Updated Architecture & Data Flows (Summary)

This section **summarises the updated architecture and flows** from `Legal_kb.md` so the implementation work in this document is aligned with the current design.

### 2.1 Layered System Architecture (Summary)

- **Client layer:** Web UI, mobile, API clients, and scripts all interact **only via APIs**.
- **API gateway & application layer:** Next.js API routes (or equivalent) handle auth, validation, rate limiting, and expose:
  - **Legal KB API service** (upload, replace, CRUD, search)
  - **Search service** (keyword + vector + filters)
  - **Analytics / insights services** (proactive brain, reporting).
- **Processing layer (event-driven):**
  - **Ingest pipeline:** validates requests, stores files to Supabase Storage, creates DB rows, enqueues processing jobs.
  - **Extraction pipeline (Docling):** converts documents to structured text, sections, tables, and pages.
  - **Metadata & citation pipeline:** LLM-driven metadata extraction and citation parsing on top of Docling output.
  - **Embedding & index pipeline:** generates embeddings, updates vector index, and maintains hybrid search readiness.
  - **Topic–case graph pipeline:** builds and updates `legal_topics` and `topic_entity_links` so we can answer “which cases/docs are affected when topic X changes?”.
- **Storage layer:**
  - **PostgreSQL + pgvector:** `legal_knowledge_base`, `legal_kb_processing_jobs`, topic–case graph tables, and embeddings.
  - **Supabase Storage:** canonical files under `legal-kb/{org_id}/{...}` with RLS.
- **Integration layer:**
  - **Cases / clients / documents services:** consume Legal KB via search and topic links.
  - **AI/RAG service:** uses hybrid retrieval over Legal KB (and case docs) for grounded answers.
  - **Proactive brain:** uses topic–case graph, Legal KB, and case context for digests and reassessments.

### 2.2 Core Pipelines & Flows (Aligned with Legal_kb.md)

- **Document ingestion pipeline (with Docling):**
  1. Client calls `POST /api/legal-database/upload` (multipart file + metadata).
  2. API validates, stores file in Supabase Storage, inserts `legal_knowledge_base` row with `status = 'pending'`, and enqueues a **Docling processing job** in `legal_kb_processing_jobs`.
  3. Worker downloads file, runs **Docling conversion** to get markdown + structured JSON (sections, tables, pages).
  4. Worker runs **LLM metadata extraction** (using Docling structure to improve prompts) and **citation parsing**.
  5. Worker computes **embeddings** (Docling HybridChunker + OpenAI `text-embedding-3-small`) and writes to `ai_embedding` (and any chunk tables we add).
  6. Worker updates processing status (`completed` / `failed`) and any diagnostic metadata; search endpoints see the new row immediately.
- **Embedding pipeline (batch / backfill):**
  - Periodically or on demand, identify rows with missing or outdated embeddings and run a batched embedding job to populate `ai_embedding` and refresh vector indices.
- **Topic change impact pipeline (topic–case graph):**
  1. When a Legal KB entry or topic is updated (e.g. replace-document), we create a **topic_change_event**.
  2. An impact worker queries `topic_entity_links` to find affected cases/documents and calculates impact priority.
  3. It queues **reassessment jobs** for high-priority entities and updates tags/metadata (e.g. “affected_by_change:topic_id”).
  4. Notifications and dashboards surface these impacts to users.
- **Backfill pipeline:**
  - For existing entries lacking `full_text`, metadata, or embeddings, run them through the **same Docling + LLM + embedding** pipeline and track progress.

### 2.3 Hybrid Search & RAG Flow

- **Hybrid search (Legal Database search API):**
  - Parse query + context (jurisdiction, case_id, filters).
  - Run **keyword search** (Postgres full-text) and **vector search** (pgvector) in parallel.
  - Fuse results (e.g. RRF) and then **re-rank with profile context** (case profile, jurisdiction, matter type, recency, usage).
- **RAG integration:**
  - AI/RAG service calls a retrieval function that embeds the query, runs hybrid search over Legal KB (and optionally case documents), and returns chunks + citations to the LLM for grounded answer generation.

This is the **canonical architecture and flow**; the phases below focus on **what we need to build next** to realise this end state.

---

## 3. Implementation Phases Overview

| Phase | Focus | Outcome |
|-------|--------|--------|
| **1** | **Legal KB: build via API upload** | **API upload** of actual documents (PDFs, etc.) → store → extract text & metadata → insert/update `legal_knowledge_base`. KB is **living** (add/update/replace via API). |
| **2** | Legal KB: taxonomy, search UX, admin | Jurisdiction/document_type/practice_areas consistent; filters in UI; optional bulk upload and CSV/API ingest. |
| **3** | Legal KB: embeddings & vector search | Pipeline to embed new/updated KB docs; backfill existing; keyword + vector hybrid search in API and UI. |
| **4** | Topic–case graph / impact index | Schema and jobs: link cases (and optionally docs) to topics; on topic change → query index → queue reassessment and re-tag. |
| **5** | Case documents: chunking, RAG | Chunk and embed case documents on upload; RAG API over Legal KB + case docs; citations. |
| **6** | Proactive brain & triggers | Per-case, per-stage analysis; triggers (new doc, stage change, topic change); digest and insights from real data. |

The following sections detail **Phase 1** (Legal KB via **API upload**) in full; Phases 2–6 are scoped with deliverables and dependencies so they can be implemented in order.

---

## 4. Phase 1: Legal KB — Build via API Upload (Detailed)

**Goal:** The Legal KB is **built and kept up to date through API upload** of actual documents (judgments, statutes, regulations, legal articles). There is no separate “UI-only” ingest path: **all population and updates go through the API**. Callers (web UI, scripts, integrations, bulk ingest) use the **upload API** to send files and metadata; the server stores the file, creates or updates a row in `legal_knowledge_base`, and runs extraction. Each upload results in a processed, searchable row with file storage, extracted or assigned metadata, and optional full-text for search.

### 3.1 Principles

- **Through API upload** — The Legal KB is populated and updated **through API upload** only. The primary endpoint is `POST /api/legal-database/upload` (plus replace, list, get, delete). Any client — web UI, script, external system, or bulk ingest — uses this same API; there is no alternate “direct” or UI-only upload path.
- **Living and continuously updated** — New API uploads add entries; replace-document API updates the same entry (re-process, update full_text and metadata); delete API sets `is_active = false` (or removes the row).
- **One document → one Legal KB row** (for typical case law/statute/article). Long documents can later get chunk-level indexing (Phase 3/5) if needed; for Phase 1, store `full_text` and optionally a short `summary` for search.

### 3.2 Storage

- **Supabase Storage:** Create a bucket for Legal KB source files (e.g. `legal-kb` or `legal_knowledge`).
  - **Path pattern:** `{organization_id}/{entry_id}/{filename}` or `{organization_id}/{year}/{month}/{entry_id}_{filename}` so that replacing a document can overwrite or add a new version.
  - **RLS:** Only org members can read; only admins (or designated “KB editors”) can upload/update/delete.
- **Table column:** `legal_knowledge_base.file_url` stores the Storage path (or public URL) to the uploaded file so users can open the original document.

### 3.3 Upload Flow (End-to-End) — API-driven, Docling Pipeline

1. **Client calls upload API:** `POST /api/legal-database/upload` with multipart/form-data: **file** (PDF, DOCX, or allowed types) + **metadata** (JSON or form fields). Client may be a web UI, a script, an integration, or a bulk-ingest job.
2. **Metadata (in request body or form):**
   - **Required:** `document_type` (e.g. case_law, statute, regulation, legal_article), `jurisdiction`.
   - **Optional but recommended:** `practice_areas[]`, `keywords[]`, `title` (can be omitted and filled from filename or extraction).
   - **Case law:** case_name, case_citation, court_name, decision_date.
   - **Statute/regulation:** statute_name, statute_number, enactment_date, effective_date.
   - If omitted, server can rely on **Docling-enhanced AI extraction** after text extraction (see below).
3. **Server (Next.js API route):** Accepts file + metadata; stores file in Supabase Storage bucket `legal-kb` with path `{organization_id}/{entry_id}/{filename}`; inserts a row in `legal_knowledge_base` (e.g. `title = filename`, `full_text = NULL`, `ai_processed = false`, `file_url` = Storage URL/path) and a `metadata.processing_status = 'pending'`. Returns `{ id, file_url, processing_status }` (e.g. `queued`).
4. **Job enqueue:** The API creates a row in `legal_kb_processing_jobs` (org_id, entry_id, storage_bucket, storage_path, status = `queued`). This is the hand-off to the **Python/Docling worker** described in `Legal_kb.md`.
5. **Python/Docling worker:** 
   - Downloads the file from Supabase Storage using `storage_bucket`/`storage_path`.
   - Runs **Docling conversion** → `DoclingDocument` (markdown full text + structured JSON: sections, tables, pages, metadata).
   - Runs **LLM metadata extraction** using Docling structure (sections, table summaries) for better prompts.
   - Runs **citation parsing** (e.g. `eyecite` on Docling markdown) and links citations.
   - Runs **embedding generation** from Docling chunks (HybridChunker → OpenAI `text-embedding-3-small`) and writes to `ai_embedding`.
   - Updates `legal_knowledge_base` row: `full_text`, `summary`, `key_points`, `legal_principles`, citations, `ai_embedding`, `ai_processed = true`, `metadata.processing_status = 'completed'`, plus diagnostic metadata (page count, table count, etc.).
   - Marks the job in `legal_kb_processing_jobs` as `completed` (or `failed` with `last_error` and retries).
6. **Completion:** Row is searchable via `search_legal_knowledge_secure` (keyword) **and** `search_legal_knowledge_vector` (vector). Client can poll `GET /api/legal-database/entries/[id]` for status (`pending` → `queued` → `processing` → `completed`/`failed`) or use webhooks if implemented.

### 3.4 Replace / Update Document (Living KB) — via API

- **Replace document:** Client calls `POST /api/legal-database/entries/[id]/replace-document` with a new file (e.g. amended statute, corrected judgment).
  - Server stores new file in Storage (new path or overwrite by policy); updates row: `file_url`, set `full_text = NULL`, `ai_processed = false`.
  - Server re-runs **text extraction** and **metadata extraction** (and later, in Phase 3, re-embed); then sets `ai_processed = true`, `updated_at = NOW()`.
- **Edit metadata only:** Client calls `PATCH /api/legal-database/entries/[id]` with title, jurisdiction, practice_areas, etc. Optionally mark “needs re-embed” for Phase 3.
- **Versioning (optional):** Keep a `version` or `document_version` column; or a separate `legal_kb_document_versions` table (file_url, uploaded_at, entry_id). For MVP, overwrite/replace via API is enough.

### 3.5 API Design (Phase 1) — Upload and Ingest Through API

All Legal KB population and updates are **through API**. Clients (web UI, scripts, integrations, bulk ingest) use these endpoints.

| Method | Endpoint | Purpose |
|--------|----------|--------|
| **POST** | `/api/legal-database/upload` | **Primary ingest.** Accept multipart/form-data: **file** (PDF, DOCX, etc.) + **metadata** (document_type, jurisdiction, title, practice_areas, keywords, case_name, case_citation, court_name, decision_date, statute_name, statute_number, etc.). Create Storage object, insert row in `legal_knowledge_base`, return `{ id, file_url, processing_status }`. Run extraction inline or enqueue job. |
| **PATCH** | `/api/legal-database/entries/[id]` | Update metadata only (title, jurisdiction, practice_areas, etc.). |
| **POST** | `/api/legal-database/entries/[id]/replace-document` | Replace file: accept new file in request body; update Storage and `file_url`; set row for re-processing (full_text = NULL, ai_processed = false); run or enqueue extraction. |
| **GET** | `/api/legal-database/entries` | List org’s Legal KB entries (query params: document_type, jurisdiction, search, limit, offset). |
| **GET** | `/api/legal-database/entries/[id]` | Get one entry (including processing_status, file_url). |
| **DELETE** | `/api/legal-database/entries/[id]` | Soft-delete: set `is_active = false` (or hard-delete + remove Storage object by policy). |

Existing **GET /api/legal-database/search?q=...** remains for search; it already uses `search_legal_knowledge_secure`.

### 3.6 Docling-based Extraction, Metadata, Citations, Embeddings

- **Docling conversion (text + structure):** The worker uses Docling to convert the stored file (PDF/DOCX, etc.) into a structured `DoclingDocument` with:
  - Markdown full text (`full_text` candidate) via `doc.export_to_markdown()`.
  - Rich structure via `doc.export_to_dict()` (sections, tables, pages, metadata).
  - Structure-aware chunks via `HybridChunker` for later embeddings.
- **LLM metadata extraction (enhanced by Docling):**
  - Prompts include Docling structure (section titles, table summaries, page count) to extract: title, summary, case_citation, court_name, decision_date, key_points, legal_principles, practice_areas, keywords, etc.
  - Results are written into `legal_knowledge_base` fields; optionally track which fields were AI-suggested vs. user-edited.
- **Citation parsing:**
  - Run `eyecite` (or equivalent) on Docling markdown to extract citations.
  - Use Docling’s section context (which section a citation appears in) to attach richer context; link citations to existing Legal KB entries where applicable.
- **Embedding generation (vector search readiness):**
  - Use Docling’s HybridChunker to create structure-aware chunks (sections, subsections, tables).
  - Generate embeddings for chunks and/or whole-document representations (e.g. OpenAI `text-embedding-3-small`) and store in `ai_embedding` (and optionally a dedicated `legal_kb_chunks` table if needed).
  - This makes the Legal KB immediately available to `search_legal_knowledge_vector` and RAG.
- **Idempotency:** Jobs can be retried safely; Docling conversion and metadata/citation/embedding steps overwrite computed fields while respecting any fields explicitly edited by users.

### 3.7 UI (Phase 1) — Optional; API is Primary

- **Upload is through API**; a UI is optional. If a UI is provided, it **calls the same upload and replace APIs** (e.g. `POST /api/legal-database/upload` with multipart from the browser).
- **Legal Database page (optional):** Keep existing search and results. Optionally add “Add to Legal KB” that posts file + metadata to the upload API and shows processing status (poll `GET /api/legal-database/entries/[id]`).
- **Manage Legal KB (optional):** List from `GET /api/legal-database/entries`; actions (Edit, Replace, Delete) call PATCH, POST replace-document, DELETE. Links to open `file_url` (original document).

### 3.8 Security & RLS

- **Storage bucket:** RLS so that only the organization’s members can read; only admins (or a “legal_kb_editor” role) can upload/update/delete.
- **Table:** Existing RLS on `legal_knowledge_base` (org-scoped); ensure INSERT/UPDATE/DELETE are restricted to admins or designated role so only authorised users can add/change Legal KB content.

### 3.9 Phase 1 Deliverables Checklist (Docling Pipeline)

- [ ] Supabase Storage bucket for Legal KB documents (`legal-kb`); RLS and path convention `{organization_id}/{entry_id}/{filename}`.
- [ ] `legal_kb_processing_jobs` table and migration to queue Docling jobs.
- [ ] **POST /api/legal-database/upload** — **primary ingest**: accept multipart file + metadata; create Storage object and DB row; enqueue Docling processing job. Document request/response and auth (e.g. Bearer token, org from session).
- [ ] Python/Docling worker service wired to `legal_kb_processing_jobs` (download → Docling → LLM metadata → citations → embeddings → DB updates).
- [ ] **PATCH /api/legal-database/entries/[id]** for metadata-only edits.
- [ ] **POST /api/legal-database/entries/[id]/replace-document** — accept new file; update Storage and `file_url`; enqueue re-processing job.
- [ ] **GET /api/legal-database/entries** (list with filters) and **GET /api/legal-database/entries/[id]** (include processing_status from metadata and optional job info).
- [ ] **DELETE** (soft or hard) for Legal KB entries.
- [ ] Optional UI that calls the above APIs (upload form, list, edit, replace) and surfaces Docling processing status.
- [ ] **Documentation:** API spec for upload, replace, list, get, delete; structure of `legal_kb_processing_jobs`; expected Docling worker behaviour; how the KB stays living (add/update/replace **via API** + Docling pipeline).

---

## 5. Phase 2: Legal KB — Taxonomy, Search UX, Admin

- **Taxonomy:** Standardise and constrain `document_type`, `jurisdiction`, `practice_areas` (e.g. dropdowns or tags from a controlled list) so filters and topic–case index (Phase 4) are consistent.
- **Search UX:** Filters (jurisdiction, document_type, practice_area) on Legal Database page; “Search in context of case” (prefill jurisdiction/matter from case).
- **Bulk / API ingest:** Optional CSV or API to bulk-create Legal KB entries (with file_url or file upload); same processing pipeline as single upload.
- **Deliverables:** Taxonomy config or table; filter UI; optional bulk ingest endpoint and template.

---

## 6. Phase 3: Legal KB — Embeddings & Vector Search

- **Embedding pipeline:** When a Legal KB row has `full_text` (and optionally summary, key_points), compute embedding (e.g. OpenAI `text-embedding-3-small`, 1536 dims) from a concatenated text, store in `ai_embedding`. Run on: new row after extraction; row after “replace document”; backfill for existing rows.
- **Keyword + vector:** API and UI can call both `search_legal_knowledge_secure` and `search_legal_knowledge_vector` (with query embedding); merge and rank (e.g. RRF or weighted combination).
- **Deliverables:** Embedding job or serverless function; backfill script; optional hybrid search API and UI.

---

## 7. Phase 4: Topic–Case Graph / Impact Index

- **Schema:** Table (or graph) linking **topics** (e.g. Legal KB entry id, or topic_id from a taxonomy) to **entities** (case_id, document_id, optional “situation” id). Optional weight. Updated when: case is created/updated (jurisdiction, matter_type); analysis links case to precedents/statutes; document is linked to case.
- **On topic change:** When a Legal KB entry (or topic) is updated/replaced, query index for affected case_ids (and doc ids); enqueue reassessment jobs; optionally re-tag “affected by [precedent/statute].”
- **Deliverables:** Migration for index table(s); jobs to maintain links (on case save, on KB entry save); job “on KB entry updated” → find affected → queue reassess; optional “affected cases” view in UI.

---

## 8. Phase 5: Case Documents — Chunking & RAG

- **On case document upload:** Extract text (OCR if needed), chunk, embed, insert into `document_chunks`. Link to case_id and document_id.
- **RAG API:** `POST /api/ai/rag-query`: query + context (case_id, source: legal_db | case_documents | both); embed query; call vector search Legal KB and/or document_chunks; LLM with retrieved chunks; return answer + citations.
- **Deliverables:** Chunking/embedding pipeline for case documents; RAG endpoint; UI for “Ask about this case” / “Research in context of case.”

---

## 9. Phase 6: Proactive Brain & Triggers

- **Per-case, per-stage analysis:** Background job (scheduled or event-driven) that, for each active case, builds profile, retrieves relevant Legal KB and similar cases, runs analysis, writes to `ai_insights` or digest.
- **Triggers:** New document on case → re-run analysis for that case. Case stage change → re-run. Topic (Legal KB) change → use topic–case index → queue affected cases for reassessment. Case interaction via prompting → update user/case context and refresh suggestions.
- **Deliverables:** Job definitions; trigger hooks (document upload, stage change, KB update); digest API using real cases + Legal KB + calendar; “What you might miss” and “Suggest actions” backed by real data.

---

## 10. Dependencies and Order

```
Phase 1 (Legal KB via upload) ← must complete first; no dependency on existing KB data.
    ↓
Phase 2 (Taxonomy, search UX) ← improves usability of KB built in Phase 1.
    ↓
Phase 3 (Embeddings) ← requires KB rows with full_text; enables vector search.
    ↓
Phase 4 (Topic–case index) ← requires Legal KB entries and cases; enables “reassess when topic changes.”
    ↓
Phase 5 (Case docs RAG) ← can start in parallel with Phase 4; depends on document_chunks pipeline.
    ↓
Phase 6 (Proactive brain) ← depends on Phase 1–4 (KB, index) and optionally Phase 5 (case docs).
```

---

## 11. Summary: Legal KB Built by API Upload

- **We do not have an existent Legal KB** in practice — we **build it** by **API upload** of actual documents (PDFs of case law, statutes, regulations, articles). All ingest is **through the API**; any client (UI, script, integration, bulk job) uses the same endpoints.
- **Flow:** Client calls **POST /api/legal-database/upload** (file + metadata) → server stores file in Supabase Storage → extract text → (optional) extract metadata with LLM/rules → insert row in `legal_knowledge_base` with `file_url`, `full_text`, metadata → searchable via existing keyword search; later embedded for vector search (Phase 3). Replace document via **POST /api/legal-database/entries/[id]/replace-document**.
- **Living and continuously updated:** New API uploads add entries; replace-document API re-runs extraction and updates the row; PATCH updates metadata; delete API soft-deletes. Optional versioning.
- **Phase 1** delivers the **API upload** pipeline, processing, and CRUD APIs so that the Legal KB is populated and maintained by **real documents via API**; Phases 2–6 then add taxonomy, vector search, topic–case index, case-doc RAG, and the proactive second brain on top of this living KB.

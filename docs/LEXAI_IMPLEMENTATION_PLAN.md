# LexAI Implementation Plan & Guide (v2.0 - Accuracy-First)

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
| **Vector search (Legal KB)** | ⚠️ | `search_legal_knowledge_vector(embedding, org_id, limit, filters)` in DB; **will be supplemental only** (not primary retrieval). |
| **document_chunks** | ✅ | Table + RLS; **will store PageIndex trees instead of vector chunks**. |
| **API** | ✅ | `GET /api/legal-database/search?q=...` calls secure search; Legal Database page uses it. No upload or CRUD API for Legal KB entries. |
| **Cases, clients, documents, team, calendar** | ✅ | Full CRUD, lifecycle, RLS. Case documents: upload to Supabase Storage, link to case; no processing pipeline yet. |
| **Topic–case index** | ❌ | Not implemented. **Will use Graphiti for this**. |
| **Proactive / digest / insights pipelines** | ❌ | Mock or stubbed; no background jobs. |
| **Docling** | ✅ | Available in codebase; superior document extraction (90%+ table accuracy). |
| **PageIndex** | ✅ | Available in codebase; reasoning-based retrieval (98.7% accuracy). |
| **Graphiti** | ✅ | Available in codebase; temporal knowledge graph for relationships. |

### 1.2 Gaps to Address (Updated Strategy)

1. **Legal KB is empty in practice** — Build it by **API upload** of actual documents (PDFs of judgments, statutes, regulations, articles); process with **Docling + PageIndex** pipeline.
2. **No upload or ingest flow** for Legal KB — Need: **upload API** (multipart file + metadata), storage bucket, **Docling + PageIndex processing pipeline**, and APIs to create/update/replace entries.
3. **No PageIndex trees** for Legal KB rows — Need pipeline to generate reasoning-ready tree structures from Docling output for all documents.
4. **No topic–case graph** — **Use Graphiti** for autonomous relationship tracking with temporal context.
5. **Case documents** not processed — Need **Docling + PageIndex** pipeline for all case documents (pleadings, contracts, etc.).
6. **Proactive brain** not implemented — Build on top of PageIndex retrieval + Graphiti graph.

---

## 2. Updated Architecture & Data Flows (Accuracy-First)

This section **summarises the accuracy-first architecture** using **Docling + PageIndex + Graphiti**.

### 2.1 Layered System Architecture

- **Client layer:** Web UI, mobile, API clients, and scripts all interact **only via APIs**.

- **API gateway & application layer:** Next.js API routes (or equivalent) handle auth, validation, rate limiting, and expose:
  - **Legal KB API service** (upload, replace, CRUD, search)
  - **Search service** (reasoning-based via PageIndex, with optional keyword fallback)
  - **Analytics / insights services** (proactive brain, reporting).

- **Processing layer (event-driven):**
  - **Ingest pipeline:** validates requests, stores files to Supabase Storage, creates DB rows, enqueues processing jobs.
  - **Extraction pipeline (Docling):** converts documents to structured text, sections, tables (90%+ accuracy), and pages.
  - **Tree generation pipeline (PageIndex):** builds hierarchical reasoning-ready tree structure from Docling output for all documents.
  - **Metadata & citation pipeline:** LLM-driven metadata extraction and citation parsing on top of Docling output.
  - **Optional embedding pipeline:** generates embeddings only for quick lookups (pgvector), not primary retrieval.
  - **Topic–case graph pipeline (Graphiti):** autonomous relationship tracking with temporal context.

- **Storage layer:**
  - **PostgreSQL:** `legal_knowledge_base`, `legal_kb_processing_jobs`, document metadata, **PageIndex trees (JSON)**, optional embeddings.
  - **Supabase Storage:** canonical files under `legal-kb/{org_id}/{...}` with RLS.
  - **Neo4j/FalkorDB (Graphiti):** temporal knowledge graph for topic-case relationships, agent memory, interaction history.

- **Retrieval layer (PRIMARY = PageIndex):**
  - **Primary: PageIndex reasoning-based retrieval** (98.7% accuracy) - all complex legal queries, multi-step reasoning.
  - **Supplemental: PostgreSQL keyword search** - simple entity lookups only (when speed > accuracy).
  - **Context: Graphiti graph queries** - relationship and temporal context enrichment.

- **Integration layer:**
  - **Cases / clients / documents services:** consume Legal KB via PageIndex search and Graphiti topic links.
  - **AI/RAG service:** uses **PageIndex reasoning retrieval** + **Graphiti context** for grounded answers.
  - **Proactive brain:** uses Graphiti temporal graph, PageIndex-retrieved Legal KB, and case context for digests and reassessments.

### 2.2 Core Pipelines & Flows (Docling + PageIndex + Graphiti)

#### **Document ingestion pipeline (Docling + PageIndex):**

1. Client calls `POST /api/legal-database/upload` (multipart file + metadata).
2. API validates, stores file in Supabase Storage, inserts `legal_knowledge_base` row with `status = 'pending'`, and enqueues a **Docling + PageIndex processing job** in `legal_kb_processing_jobs`.
3. Worker downloads file, runs **Docling conversion** to get markdown + structured JSON (sections, tables, pages, 90%+ table accuracy).
4. Worker runs **PageIndex tree generation** from Docling markdown → hierarchical tree structure (reasoning-ready).
5. Worker stores PageIndex tree JSON in PostgreSQL (new column: `pageindex_tree`).
6. Worker runs **LLM metadata extraction** (using Docling structure to improve prompts) and **citation parsing**.
7. Worker **optionally** generates embeddings for quick lookups (not primary retrieval).
8. Worker adds document to **Graphiti** as episode for relationship tracking.
9. Worker updates processing status (`completed` / `failed`) and any diagnostic metadata.

#### **PageIndex retrieval pipeline (Primary):**

- Query comes in → Load PageIndex tree from PostgreSQL → LLM navigates tree using reasoning → Returns relevant sections with reasoning trace + page numbers → LLM generates answer with citations.

#### **Graphiti relationship pipeline:**

- Documents, cases, interactions added as **episodes** → Graphiti autonomously extracts entities and relationships → Temporal graph updated → Used for topic-case queries, agent memory, impact analysis.

#### **Topic change impact pipeline (Graphiti-powered):**

1. When a Legal KB entry or topic is updated (e.g. replace-document), add update as **Graphiti episode**.
2. Graphiti automatically invalidates old relationships (temporal edge invalidation) and creates new ones.
3. Query Graphiti graph to find affected cases/documents (graph traversal).
4. It queues **reassessment jobs** for high-priority entities based on graph distance.
5. Notifications and dashboards surface these impacts to users.

#### **Backfill pipeline:**

- For existing entries lacking `pageindex_tree`, run them through the **same Docling + PageIndex** pipeline and track progress.

### 2.3 Reasoning-Based RAG Flow (PageIndex Primary)

#### **Search & Retrieval:**

- Parse query + context (jurisdiction, case_id, filters).
- **Primary retrieval: PageIndex tree search** (reasoning-based, 98.7% accuracy).
  - Load PageIndex trees for relevant documents.
  - LLM navigates trees using multi-step reasoning.
  - Returns: relevant sections + reasoning trace + page references.
- **Supplemental: Graphiti context enrichment**.
  - Query Graphiti for related entities (precedents, cases, clients).
  - Get temporal context (when relationships formed/changed).
  - Get agent memory (previous interactions).
- **Optional: PostgreSQL keyword** (only for simple entity lookups).

#### **RAG integration:**

- AI/RAG service calls PageIndex tree search → Gets sections with reasoning traces → Enriches with Graphiti context → LLM generates answer with citations (document + page + reasoning) → Returns explainable, court-ready answers.

This is the **canonical architecture and flow**; the phases below focus on **what we need to build next** to realise this end state.

---

## 3. Implementation Phases Overview (Updated)

| Phase | Focus | Outcome | Timeline |
|-------|--------|---------|----------|
| **1** | **Legal KB: Docling + PageIndex pipeline** | API upload → **Docling extraction** → **PageIndex tree generation** → store in PostgreSQL. Ready for reasoning-based queries. | Weeks 1-4 |
| **2** | **Reasoning-based search & RAG** | PageIndex tree search API; multi-document reasoning; citation extraction; RAG endpoint with explainability. | Weeks 5-6 |
| **3** | **Graphiti: Topic-case graph** | Deploy Graphiti (FalkorDB); sync documents as episodes; autonomous relationship tracking; temporal queries. | Weeks 7-10 |
| **4** | **Case documents: Docling + PageIndex** | Apply same pipeline to case documents; tree-based RAG over pleadings, contracts; document-grounded research. | Weeks 11-13 |
| **5** | **Proactive brain with Graphiti memory** | Per-case analysis using PageIndex + Graphiti; agent memory; triggers (new doc, stage change, topic change); digest generation. | Weeks 14-17 |
| **6** | **Optimization & production** | Cache PageIndex trees; parallel tree search; query routing; monitoring; optional pgvector for quick lookups. | Weeks 18-20 |

The following sections detail each phase with deliverables and implementation guidance.

---

## 4. Phase 1: Legal KB — Docling + PageIndex Pipeline (Weeks 1-4)

**Goal:** The Legal KB is **built via API upload** with **Docling extraction** followed by **PageIndex tree generation**, resulting in reasoning-ready, explainable documents stored in PostgreSQL. This is the foundation for all retrieval.

### 4.1 Principles (Updated)

- **Accuracy over speed** — Legal work demands 98.7% accuracy (PageIndex) over 70-80% (vector similarity). 2-5 second query time is acceptable.
- **Reasoning-based retrieval** — PageIndex navigates documents like human experts, not semantic similarity.
- **Explainability** — Every retrieval includes reasoning trace (court-admissible evidence).
- **Through API upload** — All ingest is via `POST /api/legal-database/upload` (web UI, scripts, bulk ingest use same API).
- **Living and continuously updated** — Replace-document API re-processes through Docling + PageIndex pipeline.
- **One document → one PageIndex tree** — Each uploaded document gets a tree structure for reasoning-based navigation.

### 4.2 Storage (Updated Schema)

**PostgreSQL columns (add to `legal_knowledge_base`):**
```sql
ALTER TABLE legal_knowledge_base 
  ADD COLUMN docling_markdown TEXT,                    -- Docling markdown output (clean, structured)
  ADD COLUMN docling_json JSONB,                       -- Docling structured metadata (sections, tables)
  ADD COLUMN pageindex_tree JSONB,                     -- PageIndex tree structure (PRIMARY for retrieval)
  ADD COLUMN pageindex_metadata JSONB,                 -- Tree stats (depth, node count, etc.)
  ADD COLUMN processing_pipeline VARCHAR(50) DEFAULT 'docling_pageindex',
  ADD COLUMN ai_embedding VECTOR(1536) DEFAULT NULL;   -- OPTIONAL (quick lookups only, not primary)
```

**Supabase Storage:** Bucket `legal-kb` with path `{organization_id}/{entry_id}/{filename}` + RLS.

### 4.3 Upload Flow (End-to-End) — Docling + PageIndex Pipeline

1. **Client calls upload API:** `POST /api/legal-database/upload` with multipart/form-data: **file** (PDF, DOCX, etc.) + **metadata** (JSON or form fields).

2. **Metadata (in request body or form):**
   - **Required:** `document_type`, `jurisdiction`.
   - **Optional:** `practice_areas[]`, `keywords[]`, `title`, case law fields, statute fields.
   - If omitted, Docling + LLM extraction fills them.

3. **Server (Next.js API route):** 
   - Accepts file + metadata.
   - Stores file in Supabase Storage `legal-kb/{organization_id}/{entry_id}/{filename}`.
   - Inserts row in `legal_knowledge_base` with `processing_status = 'pending'`.
   - Returns `{ id, file_url, processing_status: "queued" }`.

4. **Job enqueue:** Create row in `legal_kb_processing_jobs` (org_id, entry_id, storage_path, status = `queued`, pipeline = `docling_pageindex`).

5. **Python worker (Docling + PageIndex):**

   **Step 1: Docling extraction**
   ```python
   # Download file from Supabase Storage
   file_data = download_from_storage(storage_path)
   
   # Docling conversion (superior quality: 90%+ table accuracy)
   from docling.document_converter import DocumentConverter
   
   docling_result = converter.convert(file_path)
   doc = docling_result.document
   
   # Extract outputs
   markdown_text = doc.export_to_markdown()         # Clean, structured text
   structured_json = doc.export_to_dict()           # Sections, tables, hierarchy
   
   # Store Docling outputs in DB
   await db.update("legal_knowledge_base", entry_id, {
       "docling_markdown": markdown_text,
       "docling_json": structured_json,
       "processing_status": "docling_complete",
       "page_count": doc.metadata.page_count,
       "table_count": len(doc.tables)
   })
   ```

   **Step 2: PageIndex tree generation**
   ```python
   # Generate PageIndex tree from Docling markdown (reasoning-ready structure)
   from pageindex import generate_pageindex_tree
   
   pageindex_tree = await generate_pageindex_tree(
       content=markdown_text,
       # Optionally use Docling sections as structure hint
       structure_hint=extract_hierarchy(structured_json)
   )
   
   # Store PageIndex tree in DB (PRIMARY for retrieval)
   await db.update("legal_knowledge_base", entry_id, {
       "pageindex_tree": pageindex_tree,
       "pageindex_metadata": {
           "tree_depth": calculate_depth(pageindex_tree),
           "node_count": count_nodes(pageindex_tree),
           "generated_at": datetime.now()
       },
       "processing_status": "pageindex_complete"
   })
   ```

   **Step 3: LLM metadata extraction (using Docling structure)**
   ```python
   # Extract legal metadata (enhanced by Docling's clean structure)
   metadata = await extract_legal_metadata(
       markdown=markdown_text,
       sections=structured_json["sections"],
       tables=structured_json["tables"]
   )
   
   await db.update("legal_knowledge_base", entry_id, metadata)
   ```

   **Step 4: Citation parsing**
   ```python
   # Parse citations from Docling markdown (cleaner = better accuracy)
   from eyecite import get_citations
   
   citations = get_citations(markdown_text)
   await store_citations(entry_id, citations)
   ```

   **Step 5: OPTIONAL - Generate embeddings for quick lookups**
   ```python
   # Only if needed for simple entity lookups (NOT primary retrieval)
   if config.ENABLE_VECTOR_FALLBACK:
       embedding = await generate_embedding(markdown_text[:8000])
       await db.update("legal_knowledge_base", entry_id, {
           "ai_embedding": embedding
       })
   ```

   **Step 6: Add to Graphiti for relationship tracking**
   ```python
   # Graphiti episode for autonomous graph building
   await graphiti.add_episode(
       name=f"legal_kb_entry_{entry_id}",
       episode_body={
           "type": "legal_document",
           "entry_id": str(entry_id),
           "document_type": metadata["document_type"],
           "jurisdiction": metadata["jurisdiction"],
           "case_name": metadata.get("case_name"),
           "citations": [c.cite for c in citations],
           "summary": metadata["summary"],
           "ingested_at": datetime.now().isoformat()
       },
       reference_time=metadata.get("decision_date", datetime.now())
   )
   ```

   **Step 7: Finalize**
   ```python
   await db.update("legal_knowledge_base", entry_id, {
       "processing_status": "completed",
       "ai_processed": True,
       "completed_at": datetime.now()
   })
   
   await db.update("legal_kb_processing_jobs", job_id, {
       "status": "completed"
   })
   ```

6. **Completion:** Document is ready for **PageIndex reasoning-based queries** (primary) and optionally Graphiti graph queries (relationships) and PostgreSQL keyword (simple lookups).

### 4.4 Replace / Update Document (Living KB)

- **Replace document:** `POST /api/legal-database/entries/[id]/replace-document` → re-runs entire Docling + PageIndex pipeline → updates trees and metadata.
- **Edit metadata only:** `PATCH /api/legal-database/entries/[id]` → updates metadata fields only.

### 4.5 API Design (Phase 1)

All Legal KB population and updates are **through API**. Clients use these endpoints.

| Method | Endpoint | Purpose |
|--------|----------|--------|
| **POST** | `/api/legal-database/upload` | **Primary ingest.** Accept multipart file + metadata; enqueue Docling + PageIndex processing; return `{ id, file_url, processing_status }`. |
| **PATCH** | `/api/legal-database/entries/[id]` | Update metadata only. |
| **POST** | `/api/legal-database/entries/[id]/replace-document` | Replace file; re-run Docling + PageIndex pipeline. |
| **GET** | `/api/legal-database/entries` | List org's Legal KB entries (with filters). |
| **GET** | `/api/legal-database/entries/[id]` | Get one entry (including `pageindex_tree` and processing status). |
| **DELETE** | `/api/legal-database/entries/[id]` | Soft-delete: set `is_active = false`. |

### 4.6 Phase 1 Deliverables Checklist

- [ ] **PostgreSQL schema update:** Add `docling_markdown`, `docling_json`, `pageindex_tree`, `pageindex_metadata` columns to `legal_knowledge_base`.
- [ ] **Supabase Storage bucket:** `legal-kb` with RLS and path convention.
- [ ] **`legal_kb_processing_jobs` table:** Queue for Docling + PageIndex jobs.
- [ ] **POST /api/legal-database/upload:** Accept multipart file + metadata; enqueue job.
- [ ] **Python worker:** Docling conversion + PageIndex tree generation + metadata extraction + citation parsing + optional embedding + Graphiti episode.
- [ ] **PATCH /api/legal-database/entries/[id]:** Metadata-only edits.
- [ ] **POST /api/legal-database/entries/[id]/replace-document:** Re-run pipeline.
- [ ] **GET /api/legal-database/entries:** List with filters.
- [ ] **GET /api/legal-database/entries/[id]:** Get one entry with processing status.
- [ ] **DELETE /api/legal-database/entries/[id]:** Soft-delete.
- [ ] **Optional UI:** Upload form, list, edit, replace (calls same APIs).
- [ ] **Documentation:** API spec, Docling + PageIndex pipeline architecture, processing flow.

---

## 5. Phase 2: Reasoning-Based Search & RAG (Weeks 5-6)

**Goal:** Implement **PageIndex tree search** as primary retrieval method, delivering 98.7% accuracy with explainable reasoning traces.

### 5.1 PageIndex Tree Search API

**Endpoint:** `POST /api/legal-database/search/reasoning`

**Request:**
```json
{
  "query": "What precedents apply to wrongful termination in Kenya?",
  "context": {
    "jurisdiction": "Kenya",
    "case_id": "optional_case_id",
    "document_ids": ["id1", "id2"]  // optional: search specific docs
  },
  "options": {
    "max_results": 10,
    "include_reasoning_trace": true
  }
}
```

**Implementation:**
```python
async def pageindex_search(query: str, context: SearchContext):
    """
    Primary retrieval: PageIndex reasoning-based tree search
    """
    
    # 1. Filter documents by context
    filters = {
        "jurisdiction": context.jurisdiction,
        "is_active": True
    }
    
    if context.document_ids:
        filters["id"] = {"in": context.document_ids}
    
    documents = await db.fetch("""
        SELECT id, pageindex_tree, docling_markdown, title, file_url
        FROM legal_knowledge_base
        WHERE jurisdiction = $1 AND is_active = true
        ORDER BY usage_count DESC
        LIMIT 50
    """, context.jurisdiction)
    
    # 2. PageIndex tree search (reasoning-based)
    results = []
    for doc in documents:
        result = await pageindex_tree_search(
            tree=doc.pageindex_tree,
            query=query,
            full_text=doc.docling_markdown,  # For section extraction
            reasoning_mode=True
        )
        
        if result.relevance_score > 0.7:
            results.append({
                "document_id": doc.id,
                "document_title": doc.title,
                "relevant_sections": result.sections,
                "reasoning_trace": result.reasoning_trace,
                "confidence": result.relevance_score,
                "page_numbers": result.page_numbers,
                "file_url": doc.file_url
            })
    
    # 3. Sort by confidence
    results.sort(key=lambda x: x["confidence"], reverse=True)
    
    return results[:context.max_results]
```

**Response:**
```json
{
  "results": [
    {
      "document_id": "entry_123",
      "document_title": "Smith v. Acme Corp - Employment Case",
      "relevant_sections": [
        {
          "section_title": "Wrongful Termination Analysis",
          "content": "The court held that...",
          "page_numbers": [45, 46]
        }
      ],
      "reasoning_trace": [
        "Navigated: Document Root → Section 3: Employment Disputes",
        "Identified: Wrongful termination subsection (pages 45-47)",
        "Matched: Query intent with section content",
        "Confidence: 0.92"
      ],
      "confidence": 0.92,
      "file_url": "https://..."
    }
  ],
  "total": 5,
  "query_time_ms": 3200
}
```

### 5.2 Multi-Document Reasoning

```python
async def multi_document_reasoning(query: str, document_ids: List[str]):
    """
    Search across multiple documents with reasoning
    """
    
    documents = await db.fetch_by_ids(document_ids)
    
    # Parallel tree search
    tasks = [
        pageindex_tree_search(
            tree=doc.pageindex_tree,
            query=query,
            reasoning_mode=True
        )
        for doc in documents
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Combine and rank
    combined = []
    for doc, result in zip(documents, results):
        if result.relevance_score > 0.7:
            combined.append({
                "document_id": doc.id,
                "sections": result.sections,
                "reasoning": result.reasoning_trace,
                "confidence": result.relevance_score
            })
    
    return sorted(combined, key=lambda x: x["confidence"], reverse=True)
```

### 5.3 RAG Endpoint (PageIndex-Powered)

**Endpoint:** `POST /api/ai/rag-query`

```python
async def rag_query_with_pageindex(query: str, context: RAGContext):
    """
    RAG with PageIndex reasoning + Graphiti context
    """
    
    # 1. PageIndex retrieval (primary)
    pageindex_results = await pageindex_search(query, context)
    
    # 2. Graphiti context enrichment (supplemental)
    if context.case_id:
        graph_context = await graphiti.search(
            query=f"related entities for case {context.case_id}",
            num_results=10
        )
    else:
        graph_context = []
    
    # 3. LLM generation with rich context
    response = await llm.generate(
        prompt=f"""Answer the query using the following retrieved information:
        
        Retrieved Sections (with reasoning):
        {format_pageindex_results(pageindex_results)}
        
        Related Context:
        {format_graphiti_context(graph_context)}
        
        Query: {query}
        
        Provide a precise answer with citations including:
        - Document title
        - Page numbers
        - Section titles
        - Reasoning for relevance
        
        Answer:""",
        max_tokens=1000
    )
    
    return {
        "answer": response,
        "sources": pageindex_results,
        "reasoning_traces": [r["reasoning_trace"] for r in pageindex_results],
        "graph_context": graph_context,
        "explainability": "high"  # Court-ready reasoning
    }
```

### 5.4 Phase 2 Deliverables Checklist

- [ ] **POST /api/legal-database/search/reasoning:** PageIndex tree search API.
- [ ] **Multi-document reasoning function:** Parallel tree search across multiple documents.
- [ ] **POST /api/ai/rag-query:** RAG endpoint using PageIndex + Graphiti context.
- [ ] **Citation extraction:** Format citations with document + page + section + reasoning.
- [ ] **Reasoning trace formatter:** Human-readable reasoning traces for UI.
- [ ] **Optional: Keyword fallback:** Simple PostgreSQL keyword search for entity lookups.
- [ ] **Documentation:** PageIndex search API spec, reasoning trace format, RAG endpoint usage.

---

## 6. Phase 3: Graphiti Topic-Case Graph (Weeks 7-10)

**Goal:** Deploy **Graphiti** for autonomous relationship tracking with temporal context, replacing manual SQL topic-case graph.

### 6.1 Infrastructure Setup

**Week 7: Deploy Graphiti**

```bash
# Option 1: FalkorDB (Redis-based, lighter)
docker run -p 6379:6379 -it falkordb/falkordb:latest

# Option 2: Neo4j Community (if need more graph features)
docker run -p 7687:7687 -p 7474:7474 neo4j:latest

# Install Graphiti Python SDK
pip install graphiti-core[falkordb]  # or [neo4j]
```

**Initialize Graphiti:**
```python
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver

# Create driver
driver = FalkorDriver(
    host="localhost",
    port=6379,
    database="lex_nexus_graph"
)

# Initialize Graphiti
graphiti = Graphiti(graph_driver=driver)
```

### 6.2 Document-to-Episode Sync

**Week 8: Sync existing documents to Graphiti**

```python
async def backfill_documents_to_graphiti():
    """
    Sync existing Legal KB entries to Graphiti as episodes
    """
    
    documents = await db.fetch("SELECT * FROM legal_knowledge_base WHERE is_active = true")
    
    for doc in documents:
        await graphiti.add_episode(
            name=f"legal_kb_{doc['id']}",
            episode_body={
                "type": "legal_document",
                "document_id": str(doc["id"]),
                "document_type": doc["document_type"],
                "jurisdiction": doc["jurisdiction"],
                "case_name": doc.get("case_name"),
                "case_citation": doc.get("case_citation"),
                "court_name": doc.get("court_name"),
                "summary": doc["summary"],
                "legal_principles": doc.get("legal_principles", []),
                "practice_areas": doc.get("practice_areas", []),
                "citations": doc.get("citations", []),
                "created_at": doc["created_at"].isoformat()
            },
            source_description="Legal KB",
            reference_time=doc.get("decision_date") or doc["created_at"]
        )
        
        print(f"Synced document {doc['id']} to Graphiti")
```

**Graphiti automatically:**
- Extracts entities (Documents, Courts, Jurisdictions, Precedents)
- Creates relationships (Document cites Precedent, Document applies_in Jurisdiction)
- Tracks temporal context (when relationships formed)

### 6.3 Case-to-Episode Sync

**Week 8: Sync cases to Graphiti**

```python
async def sync_case_to_graphiti(case_id: str):
    """
    Add case as Graphiti episode for relationship tracking
    """
    
    case = await db.get_case(case_id)
    
    await graphiti.add_episode(
        name=f"case_{case_id}",
        episode_body={
            "type": "case",
            "case_id": str(case_id),
            "matter_type": case.matter_type,
            "jurisdiction": case.jurisdiction,
            "stage": case.stage,
            "client_id": str(case.client_id),
            "status": case.status,
            "created_at": case.created_at.isoformat()
        },
        source_description="Case management system",
        reference_time=case.created_at
    )
    
    # Graphiti automatically links:
    # - Case -> located_in -> Jurisdiction
    # - Case -> represents -> Client
    # - Case -> type_of -> Matter Type
```

### 6.4 Topic Change Impact (Graphiti-Powered)

**Week 9-10: Implement impact analysis**

```python
async def on_legal_kb_update(entry_id: str, changes: dict):
    """
    Handle Legal KB update with Graphiti impact analysis
    """
    
    # 1. Update PostgreSQL (operational data)
    await db.update("legal_knowledge_base", entry_id, changes)
    
    # 2. Add update as Graphiti episode
    await graphiti.add_episode(
        name=f"legal_kb_update_{entry_id}_{timestamp}",
        episode_body={
            "type": "legal_kb_update",
            "entry_id": str(entry_id),
            "changes": changes,
            "updated_at": datetime.now().isoformat()
        },
        reference_time=datetime.now()
    )
    
    # Graphiti automatically:
    # - Invalidates old relationships (temporal edge invalidation)
    # - Creates new relationships based on updated content
    # - Maintains historical graph (old relationships still queryable)
    
    # 3. Query affected entities
    affected = await graphiti.search(
        query=f"cases and documents affected by legal KB entry {entry_id} update",
        num_results=100
    )
    
    # 4. Group by priority (based on graph distance)
    high_priority = [e for e in affected if e.graph_distance <= 2]
    medium_priority = [e for e in affected if 2 < e.graph_distance <= 4]
    
    # 5. Queue reassessment
    for entity in high_priority:
        if entity.type == "Case":
            await queue_case_reassessment(entity.entity_id, priority="high")
    
    for entity in medium_priority:
        if entity.type == "Case":
            await queue_case_reassessment(entity.entity_id, priority="medium")
    
    return {
        "affected_count": len(affected),
        "high_priority_count": len(high_priority)
    }
```

### 6.5 Temporal Queries

**Query historical state:**
```python
# "Which precedents applied to this case on date X?"
historical_precedents = await graphiti.search(
    query=f"precedents for case {case_id}",
    # Point-in-time query (if Graphiti supports, else filter by temporal edges)
    timestamp=datetime(2024, 1, 1)
)
```

### 6.6 Phase 3 Deliverables Checklist

- [ ] **Graphiti infrastructure:** Deploy FalkorDB or Neo4j; configure Graphiti SDK.
- [ ] **Document-to-episode sync:** Backfill existing Legal KB entries to Graphiti.
- [ ] **Case-to-episode sync:** Sync cases to Graphiti for relationship tracking.
- [ ] **Automatic relationship extraction:** Verify Graphiti autonomously builds graph from episodes.
- [ ] **Topic change impact handler:** Detect updates, add episodes, query affected entities, queue reassessment.
- [ ] **Temporal query support:** Implement point-in-time or temporal edge filtering.
- [ ] **Graph query endpoints:** API to query Graphiti graph (relationships, temporal context).
- [ ] **Monitoring:** Graphiti graph health, episode ingestion rate, relationship counts.
- [ ] **Documentation:** Graphiti architecture, episode format, relationship types, temporal queries.

---

## 7. Phase 4: Case Documents — Docling + PageIndex (Weeks 11-13)

**Goal:** Apply the same **Docling + PageIndex** pipeline to **case documents** (pleadings, contracts, evidence, etc.) for document-grounded research.

### 7.1 Processing Pipeline (Same as Legal KB)

```python
async def process_case_document(document_id: str, case_id: str, file_path: str):
    """
    Apply Docling + PageIndex pipeline to case document
    """
    
    # 1. Docling extraction
    docling_result = await docling_convert(file_path)
    doc = docling_result.document
    
    # 2. PageIndex tree generation
    pageindex_tree = await generate_pageindex_tree(
        content=doc.export_to_markdown()
    )
    
    # 3. Store in PostgreSQL
    await db.update("documents", document_id, {
        "docling_markdown": doc.export_to_markdown(),
        "docling_json": doc.export_to_dict(),
        "pageindex_tree": pageindex_tree,
        "page_count": doc.metadata.page_count,
        "processing_status": "completed"
    })
    
    # 4. Add to Graphiti
    await graphiti.add_episode(
        name=f"case_document_{document_id}",
        episode_body={
            "type": "case_document",
            "document_id": str(document_id),
            "case_id": str(case_id),
            "document_type": document.type,
            "uploaded_at": document.uploaded_at.isoformat()
        },
        reference_time=document.uploaded_at
    )
```

### 7.2 Document-Grounded RAG

```python
async def case_document_rag(query: str, case_id: str):
    """
    RAG over case documents using PageIndex
    """
    
    # 1. Get case documents
    documents = await db.fetch("""
        SELECT id, pageindex_tree, docling_markdown, type, file_url
        FROM documents
        WHERE case_id = $1
        ORDER BY uploaded_at DESC
    """, case_id)
    
    # 2. PageIndex search across documents
    results = []
    for doc in documents:
        result = await pageindex_tree_search(
            tree=doc.pageindex_tree,
            query=query,
            full_text=doc.docling_markdown
        )
        
        if result.relevance_score > 0.7:
            results.append({
                "document_id": doc.id,
                "document_type": doc.type,
                "sections": result.sections,
                "reasoning": result.reasoning_trace,
                "file_url": doc.file_url
            })
    
    # 3. Get Legal KB context (precedents, statutes)
    legal_kb_context = await pageindex_search(
        query=query,
        context={"jurisdiction": case.jurisdiction}
    )
    
    # 4. Get Graphiti relationships
    graph_context = await graphiti.search(
        query=f"related precedents and entities for case {case_id}",
        num_results=10
    )
    
    # 5. LLM generation with combined context
    response = await llm.generate(
        prompt=f"""Answer the query using:
        
        Case Documents:
        {format_case_document_results(results)}
        
        Relevant Legal KB:
        {format_legal_kb_context(legal_kb_context)}
        
        Related Context:
        {format_graphiti_context(graph_context)}
        
        Query: {query}
        
        Answer:"""
    )
    
    return {
        "answer": response,
        "case_documents": results,
        "legal_kb": legal_kb_context,
        "graph_context": graph_context
    }
```

### 7.3 Phase 4 Deliverables Checklist

- [ ] **Docling + PageIndex pipeline for case documents:** Apply to all uploaded case docs.
- [ ] **Document schema update:** Add `docling_markdown`, `docling_json`, `pageindex_tree` to `documents` table.
- [ ] **Auto-processing on upload:** Trigger pipeline when case document uploaded.
- [ ] **Case document RAG endpoint:** `POST /api/cases/[id]/documents/search` using PageIndex.
- [ ] **Document-grounded research UI:** "Ask about this case's documents" feature.
- [ ] **Combined search:** Search across Legal KB + case documents simultaneously.
- [ ] **Documentation:** Case document processing pipeline, RAG endpoint usage.

---

## 8. Phase 5: Proactive Brain with Graphiti Memory (Weeks 14-17)

**Goal:** Build proactive, always-on brain using **PageIndex retrieval** + **Graphiti agent memory** for per-case analysis, triggers, and digests.

### 8.1 Per-Case Analysis Engine

```python
class ProactiveBrainAgent:
    def __init__(self):
        self.graphiti = Graphiti(...)
        self.db = PostgreSQLClient(...)
    
    async def analyze_case(self, case_id: str):
        """
        Per-case proactive analysis using PageIndex + Graphiti
        """
        
        # 1. Get operational data (PostgreSQL)
        case = await self.db.get_case(case_id)
        documents = await self.db.get_case_documents(case_id)
        
        # 2. Get temporal context (Graphiti)
        graph_context = await self.graphiti.search(
            query=f"complete context for case {case_id}",
            num_results=50
            # Returns:
            # - Related precedents (with temporal info)
            # - Similar cases
            # - Client history
            # - Previous interactions
            # - Agent memory
        )
        
        # 3. Retrieve relevant Legal KB (PageIndex)
        legal_kb_context = await pageindex_search(
            query=f"{case.matter_type} {case.jurisdiction}",
            context={"jurisdiction": case.jurisdiction}
        )
        
        # 4. Search case documents (PageIndex)
        case_doc_context = []
        for doc in documents:
            result = await pageindex_tree_search(
                tree=doc.pageindex_tree,
                query=f"key issues and strategies for {case.matter_type}"
            )
            case_doc_context.append(result)
        
        # 5. LLM analysis
        insights = await llm.generate(
            prompt=f"""Analyze case {case.name} ({case.stage}):
            
            Case Profile:
            - Matter: {case.matter_type}
            - Jurisdiction: {case.jurisdiction}
            - Stage: {case.stage}
            - Deadlines: {case.next_deadline}
            
            Related Precedents (PageIndex):
            {format_legal_kb_context(legal_kb_context)}
            
            Case Documents (PageIndex):
            {format_case_doc_context(case_doc_context)}
            
            Graph Context (Graphiti):
            {format_graphiti_context(graph_context)}
            
            Provide:
            1. Next steps for this stage
            2. Risks and gaps
            3. Relevant precedents to consider
            4. Missing documents or filings
            5. Suggestions based on similar cases
            
            Insights:"""
        )
        
        # 6. Store insights (PostgreSQL cache)
        await self.db.insert("ai_insights", {
            "case_id": case_id,
            "insights": insights,
            "generated_at": datetime.now()
        })
        
        # 7. Add analysis to Graphiti (agent memory)
        await self.graphiti.add_episode(
            name=f"case_analysis_{case_id}_{timestamp}",
            episode_body={
                "type": "proactive_analysis",
                "case_id": str(case_id),
                "stage": case.stage,
                "insights_summary": insights["summary"],
                "recommendations": insights["recommendations"],
                "analyzed_at": datetime.now().isoformat()
            }
        )
        
        return insights
```

### 8.2 Trigger System (Event-Driven)

```python
class TriggerSystem:
    async def on_document_upload(self, document_id: str, case_id: str):
        """
        Trigger: New document uploaded to case
        """
        # Add to Graphiti (automatic context update)
        await graphiti.add_episode(
            name=f"document_upload_{document_id}",
            episode_body={...}
        )
        
        # Re-analyze case with new context
        await proactive_brain.analyze_case(case_id)
    
    async def on_stage_change(self, case_id: str, new_stage: str):
        """
        Trigger: Case stage changed
        """
        await graphiti.add_episode(
            name=f"stage_change_{case_id}_{new_stage}",
            episode_body={
                "type": "stage_change",
                "case_id": str(case_id),
                "new_stage": new_stage,
                "changed_at": datetime.now().isoformat()
            }
        )
        
        # Re-analyze with stage-specific context
        await proactive_brain.analyze_case(case_id)
    
    async def on_case_interaction(self, case_id: str, user_query: str, response: str):
        """
        Trigger: User interacted with case via prompting
        """
        # Add interaction to Graphiti (agent memory)
        await graphiti.add_episode(
            name=f"case_interaction_{case_id}_{timestamp}",
            episode_body={
                "type": "case_interaction",
                "case_id": str(case_id),
                "user_query": user_query,
                "response_summary": response[:500],
                "interacted_at": datetime.now().isoformat()
            }
        )
        
        # Future queries automatically include this context
```

### 8.3 Digest Generation

```python
async def generate_daily_digest(user_id: str):
    """
    Daily digest using PageIndex + Graphiti
    """
    
    # Get user's active cases
    cases = await db.fetch_user_cases(user_id, status="active")
    
    digest_items = []
    
    for case in cases:
        # Get Graphiti context for case
        context = await graphiti.search(
            query=f"recent updates and changes for case {case.id}",
            num_results=10
        )
        
        # Check for Legal KB updates affecting this case
        affected_by = [
            e for e in context 
            if e.type == "legal_kb_update" and e.entity_id in case.precedent_ids
        ]
        
        if affected_by:
            digest_items.append({
                "case_id": case.id,
                "case_name": case.name,
                "alert": f"Precedent {affected_by[0].name} was updated - may affect this case",
                "priority": "high"
            })
        
        # Upcoming deadlines
        if case.next_deadline and (case.next_deadline - datetime.now()).days <= 7:
            digest_items.append({
                "case_id": case.id,
                "case_name": case.name,
                "alert": f"Deadline in {(case.next_deadline - datetime.now()).days} days",
                "priority": "high"
            })
    
    return {
        "user_id": user_id,
        "date": datetime.now().date(),
        "items": digest_items
    }
```

### 8.4 Phase 5 Deliverables Checklist

- [ ] **ProactiveBrainAgent class:** Per-case analysis using PageIndex + Graphiti.
- [ ] **Trigger system:** Handlers for document upload, stage change, case interaction.
- [ ] **Agent memory:** Graphiti episode tracking for all interactions.
- [ ] **Digest generation:** Daily/weekly digest API using real case + Legal KB + calendar data.
- [ ] **"What you might miss" feature:** Gap detection, missing filings, risk flags.
- [ ] **Suggest actions API:** Profile-driven suggestions for cases.
- [ ] **Background jobs:** Scheduled analysis for active cases.
- [ ] **Documentation:** Proactive brain architecture, trigger system, digest generation.

---

## 9. Phase 6: Optimization & Production (Weeks 18-20)

**Goal:** Optimize performance, add monitoring, and prepare for production.

### 9.1 Performance Optimizations

**Caching PageIndex Trees:**
```python
# Cache frequently accessed trees in Redis
import redis

redis_client = redis.Redis(host='localhost', port=6379)

async def get_pageindex_tree_cached(document_id: str):
    # Check cache
    cached = redis_client.get(f"tree:{document_id}")
    if cached:
        return json.loads(cached)
    
    # Load from DB
    tree = await db.fetch_one(
        "SELECT pageindex_tree FROM legal_knowledge_base WHERE id = $1",
        document_id
    )
    
    # Cache for 1 hour
    redis_client.setex(
        f"tree:{document_id}",
        3600,
        json.dumps(tree)
    )
    
    return tree
```

**Parallel Tree Search:**
```python
async def parallel_pageindex_search(query: str, document_ids: List[str]):
    # Search trees in parallel
    tasks = [
        pageindex_tree_search_cached(doc_id, query)
        for doc_id in document_ids
    ]
    
    results = await asyncio.gather(*tasks)
    return sorted(results, key=lambda x: x.confidence, reverse=True)
```

### 9.2 Query Routing (Optional)

```python
def route_query(query: str, context: QueryContext):
    """
    Route to appropriate retrieval system
    """
    
    # Simple entity lookup → PostgreSQL keyword (fast)
    if is_simple_entity_lookup(query):
        return "postgres_keyword"
    
    # Relationship query → Graphiti graph
    elif is_relationship_query(query):
        return "graphiti_graph"
    
    # Complex reasoning → PageIndex (default)
    else:
        return "pageindex_reasoning"
```

### 9.3 Monitoring & Observability

**Key Metrics:**
```python
# PageIndex metrics
PAGEINDEX_QUERY_DURATION = Histogram("pageindex_query_duration_seconds")
PAGEINDEX_ACCURACY = Gauge("pageindex_accuracy_score")

# Graphiti metrics
GRAPHITI_EPISODE_COUNT = Counter("graphiti_episodes_total")
GRAPHITI_QUERY_DURATION = Histogram("graphiti_query_duration_seconds")

# Processing metrics
DOCUMENT_PROCESSING_DURATION = Histogram("document_processing_duration_seconds")
PROCESSING_ERRORS = Counter("processing_errors_total")
```

### 9.4 Phase 6 Deliverables Checklist

- [ ] **PageIndex tree caching:** Redis cache for frequently accessed trees.
- [ ] **Parallel tree search:** Concurrent tree search across multiple documents.
- [ ] **Query routing (optional):** Route simple queries to PostgreSQL, complex to PageIndex.
- [ ] **Monitoring dashboards:** PageIndex query times, Graphiti graph size, processing pipeline health.
- [ ] **Error tracking:** Sentry integration for PageIndex and Graphiti errors.
- [ ] **Load testing:** Test PageIndex with 100+ concurrent queries.
- [ ] **Production readiness checklist:** Security audit, performance benchmarks, failover strategy.
- [ ] **Documentation:** Deployment guide, monitoring runbook, troubleshooting guide.

---

## 10. Dependencies and Order (Updated)

```
Phase 1 (Docling + PageIndex pipeline) ← MUST complete first; foundation for all retrieval.
    ↓
Phase 2 (PageIndex search & RAG) ← Core accuracy-first retrieval; requires Phase 1 trees.
    ↓
Phase 3 (Graphiti graph) ← Autonomous relationships; can start in parallel with Phase 2.
    ↓
Phase 4 (Case docs with PageIndex) ← Same pipeline for case documents; depends on Phase 1.
    ↓
Phase 5 (Proactive brain) ← Depends on Phase 1-4 (PageIndex + Graphiti + case docs).
    ↓
Phase 6 (Optimization) ← Performance tuning; depends on all prior phases.
```

**Critical path:** Phase 1 → Phase 2 → Phase 5  
**Parallel paths:** Phase 3 can overlap with Phase 2; Phase 4 can overlap with Phase 3.

---

## 11. Summary: Accuracy-First Legal KB with Docling + PageIndex + Graphiti

### **Core Approach**

- **We prioritize accuracy over speed** for legal work where mistakes = malpractice.
- **We build the Legal KB via API upload** with **Docling extraction** (90%+ table accuracy) followed by **PageIndex tree generation** (98.7% retrieval accuracy).
- **Primary retrieval: PageIndex reasoning-based tree search** (not vector similarity) with explainable reasoning traces (court-ready).
- **Relationship tracking: Graphiti temporal knowledge graph** (not manual SQL) with autonomous relationship extraction and agent memory.
- **Optional: pgvector for quick lookups** (simple entity lookups only, not primary retrieval).

### **Data Flow Summary**

```
Document Upload
    ↓
Docling Extraction (superior quality: 90%+ tables)
    ↓
PageIndex Tree Generation (reasoning-ready structure)
    ↓
Store in PostgreSQL (pageindex_tree JSON)
    ↓
Add to Graphiti (episode for relationships)
    ↓
Ready for:
    - PageIndex reasoning-based queries (primary: 98.7% accuracy)
    - Graphiti graph queries (relationships, temporal, memory)
    - Optional: PostgreSQL keyword (simple lookups only)
```

### **Why This Approach for Legal Work**

| Requirement | Solution | Benefit |
|-------------|----------|---------|
| **Accuracy (critical)** | PageIndex 98.7% | Malpractice prevention |
| **Explainability** | Reasoning traces | Court-admissible evidence |
| **Table preservation** | Docling 90%+ | Exhibits, regulations accurate |
| **Long documents** | PageIndex built for it | 100+ page contracts no problem |
| **Temporal tracking** | Graphiti bi-temporal | Compliance, audit trail |
| **Relationships** | Graphiti autonomous | 70% less manual graph code |
| **Agent memory** | Graphiti episodes | Context across sessions |
| **Living KB** | API replace-document | Re-process with Docling + PageIndex |

### **Trade-Offs Accepted**

- ✅ **Slower queries (2-5 sec vs 500ms)** → Acceptable for legal work's accuracy needs
- ✅ **Higher upfront cost (tree generation)** → One-time investment, permanent value
- ✅ **Additional infrastructure (Graphiti)** → Autonomous relationships worth the complexity

### **Success Metrics**

- **Accuracy:** >95% correct retrievals (measured against human lawyer judgment)
- **Explainability:** 100% of retrievals include reasoning traces
- **Processing:** <2 minutes per average document (Docling + PageIndex)
- **Query time:** <5 seconds for typical legal query
- **Relationships:** >90% of relevant relationships automatically extracted by Graphiti

---

**Phase 1** delivers the **Docling + PageIndex pipeline** and **API upload** so the Legal KB is populated with reasoning-ready documents via real PDFs; Phases 2–6 then add reasoning-based search, Graphiti relationships, case document processing, proactive brain, and production optimization on top of this accuracy-first foundation.

**Next steps:** Begin Phase 1 implementation (Weeks 1-4) with Docling + PageIndex pipeline for Legal KB.

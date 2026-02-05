# AI/RAG Strategy Comparison: Lex Nexus vs PageIndex

**Product vision:** LexAI is a **one-stop shop** and **second brain** for law firms — continuously updated, profile-aware (case type, client, documents), with research, suggestions, and “what you might miss.” See **[LEXAI_STRATEGY_VISION.md](./LEXAI_STRATEGY_VISION.md)** for the full strategy.

This document summarizes the **Lex Nexus** RAG strategy (vector-based, Legal DB–driven) and the **PageIndex** strategy (vectorless, reasoning-based), how each works in the codebase, and how they can be used together.

---

## 1. Lex Nexus RAG Strategy (Existing Docs)

**Sources:** `case-aware-lex-nexus-94/docs/RAG_ARCHITECTURE.md`, `AI_ARCHITECTURE_AND_FEATURES.md`

### 1.1 Approach

- **Primary source:** Legal Knowledge Base (`legal_knowledge_base`) + case documents (`documents` + `document_chunks`).
- **Retrieval:** Hybrid **vector (semantic)** + **keyword/full-text**; pgvector for embeddings; RRF or linear combination for fusion.
- **Chunking:** Fixed-size semantic chunks (512–1024 tokens, overlap); paragraph/section boundaries preserved; stored in `document_chunks` with `embedding`, `chunk_index`, metadata.
- **Generation:** Strict grounding and citations; system prompt instructs “answer only from provided chunks,” “cite source,” “say I don’t have enough information” when retrieval is insufficient.
- **APIs (planned):** `POST /api/ai/rag-query` (query, context.caseId, source: legal_db | case_documents | both); RPCs for vector search on Legal KB and document chunks.

### 1.2 Current State

- Legal KB search: **implemented** via `search_legal_knowledge_secure` (keyword/ILIKE); **pgvector and document_chunks** in migration `00014_pgvector_and_rag.sql` (checklist still has open items).
- Document “AI Analyze,” RAG query endpoint, embedding pipeline: **not yet implemented**.

---

## 2. PageIndex Strategy (Vectorless, Reasoning-Based)

**Sources:** `pageIndex/PageIndex/README.md`, `tutorials/tree-search/README.md`, `tutorials/doc-search/*.md`, and Python code in `pageindex/`.

### 2.1 Core Idea

- **No vector DB, no chunking.** Build a **hierarchical tree index** (like a “table of contents”) from each document, then use an **LLM to reason over the tree** (tree search) to pick relevant nodes/sections.
- **Retrieval = relevance via reasoning**, not similarity via embeddings. Aim: “similarity ≠ relevance”; professional/long documents need **reasoning** to find the right sections.
- **Two steps:**  
  1. **Tree generation:** Document → hierarchical tree (nodes with title, page range, optional summary, node_id).  
  2. **Retrieval:** Query + tree → LLM tree search → list of relevant `node_id`s → fetch those sections for the answer.

### 2.2 How the Code Works

#### Tree generation (this repo: open-source Python)

**PDF (`pageindex/page_index.py`):**

1. **Parse PDF** → list of pages with text and token counts (`get_page_tokens`).
2. **Detect TOC:** `find_toc_pages` uses an LLM to detect “is there a table of contents on this page?” over the first N pages (`toc_check_page_num`). If TOC exists, extract it and check if it has page numbers.
3. **Build structure:**
   - **If TOC with page numbers:** `process_toc_with_page_numbers` — transform TOC to JSON, map section titles to physical page indices, handle offset and missing pages.
   - **If TOC without page numbers:** `process_toc_no_page_numbers` — run document text in groups (by `max_tokens_per_node`), use LLM to “where does this section start?” and attach page indices.
   - **If no TOC:** `process_no_toc` — split document into token-sized groups, run `generate_toc_init` / `generate_toc_continue` (LLM) to infer hierarchical sections and their start pages.
4. **Verify/fix:** `verify_toc` (sample check “does this section title actually start on this page?”); if accuracy &lt; 1, `fix_incorrect_toc_with_retries` to correct bad page mappings.
5. **Large nodes:** If a section spans too many pages/tokens, recurse with `process_large_node_recursively` to subdivide and get a deeper tree.
6. **Optional:** Add `node_id`, node summaries (LLM), doc description (LLM), node text.
7. **Output:** JSON tree with `title`, `node_id`, `start_index`, `end_index` (pages), `summary`, optional `text`, nested `nodes`.

**Markdown (`pageindex/page_index_md.py`):**

1. **Parse headings** (`#`–`######`) to get nodes and levels; extract text between headings per node.
2. **Optional thinning:** Merge small nodes up to a token threshold.
3. **Build tree:** Assign `node_id`, optional summaries/description; output same shape as PDF (no page indices; uses line numbers internally).

**Entrypoint:** `run_pageindex.py` — CLI `--pdf_path` or `--md_path`; builds config (`config()` / `ConfigLoader`); calls `page_index_main()` (PDF) or `md_to_tree()` (MD); writes `*_structure.json` to `./results/`.

#### Retrieval (tree search)

- **Not implemented in this repo.** The open-source part only **builds** the tree.
- **Described in tutorials:**  
  - **Tree search:** Prompt = query + “Document tree structure: {PageIndex_Tree}” → LLM returns JSON `{ "thinking": "...", "node_list": [node_id1, node_id2, ...] }`. You then fetch content for those nodes (e.g. page ranges) and pass to the answer LLM.  
  - **Expert/preference:** Same prompt can include “Expert Knowledge of relevant sections: {Preference}” (e.g. “If query mentions X, prioritize section Y”) — no fine-tuning, just prompt injection.
- **Cloud/API:** PageIndex Cloud/Dashboard use “LLM tree search + value function-based MCTS”; retrieval API uses `doc_id` (from uploading the doc to their service) and returns relevant content. This repo only does **local tree generation**.

### 2.3 Multi-document search (PageIndex tutorials)

When you have **many documents**, each has a tree and a `doc_id`. You first **select which documents** are relevant, then run PageIndex retrieval on those:

- **By metadata:** Store (doc_id, metadata) in DB; “Query to SQL” with LLM → get doc_ids → retrieve via PageIndex API.
- **By description:** For each doc, generate a short description from its tree/summaries; LLM selects relevant doc_ids from “Query + list of (doc_id, doc_name, doc_description)”.
- **By semantics:** Classic vector search over **chunks** (or doc-level embeddings), get top-K chunks and their doc_ids; compute **DocScore** per document (e.g. normalized sum of chunk scores); take top docs and run PageIndex retrieval on their `doc_id`s.

So PageIndex can be **combined with** vector or keyword search for “which document?” and then use reasoning-based retrieval **inside** each chosen document.

---

## 3. Side-by-Side Comparison

| Aspect | Lex Nexus (RAG_ARCHITECTURE) | PageIndex (this repo + docs) |
|--------|-----------------------------|------------------------------|
| **Retrieval basis** | Vector similarity + keyword; hybrid fusion | LLM reasoning over tree (tree search); no vectors |
| **Index structure** | Flat or chunked: chunks with embeddings | Hierarchical tree: sections/nodes with title, page range, optional summary |
| **Chunking** | Fixed token size + overlap; paragraph-aware | No chunking; natural sections from TOC or LLM-inferred structure |
| **Explainability** | Citations to chunk/source | Traceable path: which nodes chosen + reasoning in prompt |
| **Legal KB** | Primary; org-scoped; keyword + (planned) vector | Not in PageIndex; could “select” Legal KB entries by metadata/description then treat each as a “document” with a tree |
| **Case documents** | document_chunks + embedding; case-scoped | Per-doc tree; multi-doc = doc selection (metadata/description/semantics) + tree search per doc |
| **Long docs** | Many chunks; context window limit | Tree keeps full structure; retrieval picks few nodes → less context, more targeted |
| **Implementation** | Supabase, pgvector, RPCs, API routes (partially done) | Python: tree generation only in repo; retrieval via prompts (tutorial) or PageIndex API |

---

## 4. How They Can Work Together

- **Lex Nexus Legal DB:** Stays the single source for legal knowledge; keyword (and later vector) search for “which precedent/statute.” No need to replace that with PageIndex for the Legal KB table itself.
- **Case documents (long PDFs):**  
  - **Option A (Lex Nexus native):** Chunk + embed → hybrid retrieval → grounded answer + citations (as in RAG_ARCHITECTURE).  
  - **Option B (PageIndex):** For selected case documents, build PageIndex trees (e.g. via `run_pageindex.py` or PageIndex API); store `doc_id` / tree or link to API. On query, use metadata/case_id (or description/semantic doc selection) to pick documents, then run tree search and pass retrieved sections to LLM for answer + citations.  
  - **Hybrid:** Use **document selection** with Lex Nexus (e.g. case_id, filters, or even vector search on doc metadata/summaries); then for each selected long doc, use **PageIndex** for reasoning-based retrieval inside the doc; merge and cite.
- **Expert knowledge / jurisdiction:** In Lex Nexus, filters (jurisdiction, matter_type) already narrow the Legal KB. In PageIndex, the same idea is “Expert Knowledge” in the tree-search prompt (e.g. “For Kenyan employment law, prefer sections on termination and remedies”).

---

## 5. Summary

- **Lex Nexus RAG:** Vector + keyword retrieval over Legal KB and case-document chunks; strict grounding and citations; implemented for Legal KB search; chunking/vector for documents still to be completed.
- **PageIndex (this repo):** Builds a **hierarchical tree** from PDF or Markdown (TOC detection or LLM-inferred sections); **retrieval** is LLM tree search (and optionally MCTS in their cloud). The code here only does **tree generation**; retrieval is described in MD tutorials and available via PageIndex API.
- **Together:** Use Lex Nexus for Legal DB and (when built) chunk-based RAG; use PageIndex for **reasoning-based retrieval inside long case documents** (and optionally for doc selection via metadata/description/semantics). Both strategies can feed the same “grounded answer + citations” layer.

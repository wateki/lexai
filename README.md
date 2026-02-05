# LexNexus

> Accuracy-first legal knowledge base and AI pipeline for law firms. A living Legal KB with reasoning-based retrieval (PageIndex), document conversion (Docling), and temporal relationship tracking (Graphiti).

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)

---

## Overview

LexNexus (LexAI) is designed as a one-stop shop and “second brain” for legal practice: a **living Legal KB** built from uploaded documents (judgments, statutes, regulations, articles), a **topic–case index** for how precedents and matters relate over time, and **proactive analysis** (relevant precedents, risks, next steps per case). **Accuracy and explainability** are prioritised over speed so that answers are grounded, defensible, and court-ready.

---

## Features

| Area | Description |
|------|-------------|
| **Living Legal KB** | Built from real documents uploaded by the firm, not a static snapshot. |
| **Accuracy-first retrieval** | Reasoning-based tree search (PageIndex) instead of vector similarity; high precision and interpretable paths. |
| **Explainability** | Retrievals include reasoning traces and citations (document, section, page) so lawyers can verify and cite. |
| **Topic–case relationships** | Graphiti maintains a temporal graph of entities and relationships; used for impact analysis and context. |
| **Proactive brain** | Surfaces relevant precedents, risks, and next steps per case using the KB and graph. |

---

## Tech Stack

| Component | Role |
|-----------|------|
| **Docling** | Document conversion (PDF, DOCX, etc.) to clean markdown and structured JSON; high fidelity for tables and sections. |
| **PageIndex** | Builds a hierarchical, reasoning-ready tree over document content. Retrieval = LLM-driven tree navigation (high accuracy, explainable), not vector search. |
| **Graphiti** | Temporal knowledge graph (FalkorDB or Neo4j). Documents/cases added as episodes; used for topic–case links and context, not primary retrieval. |
| **eyecite** | Legal citation parsing (case and statute citations) from extracted text. |
| **pgvector** | Optional; secondary quick lookups only, not the main source of legal answers. |
| **Supabase** | PostgreSQL (Legal KB, jobs, app data) and object storage for files. |

**Summary:** Primary retrieval = PageIndex (reasoning over trees). Context and relationships = Graphiti. Extraction = Docling. Vector search = optional fallback.

---

## Architecture

### Ingest Pipeline (document → Legal KB)

1. **Upload** — User or system uploads a file (e.g. PDF) and metadata (document type, jurisdiction, optional title, practice areas) via an upload API.
2. **Storage** — File is stored in object storage (e.g. Supabase Storage) under a stable path (e.g. `org_id/entry_id/filename`).
3. **Enqueue** — A row is created in the Legal KB table with status `pending`/`queued`, and a job is inserted into `legal_kb_processing_jobs`.
4. **Worker** (this repo) runs:
   - **Docling** — Convert file to markdown and structured JSON.
   - **PageIndex** — Build a reasoning-ready tree from the markdown (one tree per document).
   - **LLM metadata** — Extract title, summary, key points, legal principles, case/statute fields, practice areas, keywords (only filling fields the user did not set).
   - **eyecite** — Extract case and statute citations into `cited_cases` and `cited_statutes`.
   - **Optional** — Generate embedding (pgvector) and/or add document as a Graphiti episode.
5. **Write-back** — Worker updates the Legal KB row with markdown, tree, metadata, citations, status `completed` (or `failed`), and optionally embedding. Document is then queryable via PageIndex and, if enabled, Graphiti.

### Retrieval

- **Primary:** PageIndex tree search — load document tree, use an LLM to reason over the tree and select relevant sections; return sections with reasoning trace and page/section references.
- **Supplemental:** Keyword search (PostgreSQL) for simple lookups; optional vector search for filters.
- **Context:** Graphiti queried for related cases, topics, and temporal context to enrich answers.

### Data & Services

- **PostgreSQL (e.g. Supabase)** — Legal KB table (metadata, markdown, PageIndex tree JSON, optional embedding), jobs table, app data.
- **Object storage (e.g. Supabase Storage)** — Original/canonical files for the Legal KB.
- **Graph DB (FalkorDB or Neo4j)** — Graphiti’s temporal graph.
- **Worker** — Long-running or cron-triggered process that polls the jobs table and runs the pipeline.

---

## Project Structure

```
lex-nexus/
├── README.md           # This file
├── docs/               # Strategy, implementation plan, Legal KB schema, RAG & Graphiti analysis
└── workers/
    └── legal_kb_processor/   # Legal KB ingest worker (Docling → PageIndex → metadata → citations → optional embedding/Graphiti)
        ├── legal_kb_processor/
        ├── requirements.txt
        └── README.md
```

The web application (Next.js, Supabase auth, Legal KB upload/search UI) and the PageIndex package may live in other repos or folders; this repo holds the design (docs), implementation plan, and the worker that runs the accuracy-first ingest pipeline.

---

## Installation

**Prerequisites:** Python 3.10+, Supabase project, OpenAI API key. For PageIndex, a local PageIndex package is expected at a path the worker can resolve (e.g. sibling `pageIndex/PageIndex`).

From the repo root (so the worker’s PageIndex path resolves):

```bash
cd workers/legal_kb_processor
python -m venv .venv
```

**Windows:**

```bash
.venv\Scripts\activate
```

**Linux / macOS:**

```bash
source .venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
```

---

## Usage

Process one job and exit (e.g. for cron):

```bash
python -m legal_kb_processor.main --once
```

Poll for jobs every 60 seconds (default):

```bash
python -m legal_kb_processor.main --interval 60
```

The worker expects the application to have created Legal KB rows and enqueued jobs via the upload API and jobs table; it only processes jobs and updates the same database.

---

## Configuration

Set these in the environment (e.g. `.env` or shell) before running the worker.

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Service role key (storage + DB access) |
| `OPENAI_API_KEY` | Yes (for extraction) | LLM metadata extraction; PageIndex node summaries; embeddings if enabled |
| `LEGAL_KB_LLM_MODEL` | No | LLM for metadata extraction (default: `gpt-4o-mini`) |
| `LEGAL_KB_EMBEDDING_MODEL` | No | Embedding model (default: `text-embedding-3-small`) |
| `PAGEINDEX_ADD_NODE_SUMMARY` | No | Set to `yes` to add node summaries (uses OpenAI) |
| `LEGAL_KB_MAX_MARKDOWN_EXTRACTION` | No | Max characters sent to LLM for extraction (default: 120000) |
| `LEGAL_KB_ENABLE_VECTOR_FALLBACK` | No | Set to `yes` to populate `ai_embedding` for pgvector |
| `LEGAL_KB_MAX_EMBEDDING_TEXT` | No | Max characters used for embedding (default: 8000) |
| `LEGAL_KB_ENABLE_GRAPHITI` | No | Set to `yes` to add documents as Graphiti episodes |
| `LEGAL_KB_GRAPHITI_PROVIDER` | No | `falkordb` or `neo4j` |
| `LEGAL_KB_GRAPHITI_FALKORDB_HOST` | No | FalkorDB host (default: `localhost`) |
| `LEGAL_KB_GRAPHITI_FALKORDB_PORT` | No | FalkorDB port (default: `6379`) |
| `LEGAL_KB_GRAPHITI_NEO4J_URI` | No | Neo4j URI (required when provider is `neo4j`) |
| `LEGAL_KB_LOG_LEVEL` | No | Log level (default: `INFO`) |
| `LEGAL_KB_DOCLING_MAX_RETRIES` | No | Docling retries (default: 2) |
| `LEGAL_KB_LLM_MAX_RETRIES` | No | LLM extraction retries (default: 3) |

---

LexNexus is an accuracy-first Legal KB and AI pipeline: **Docling** for conversion, **PageIndex** for reasoning-based retrieval with explainability, and **Graphiti** for topic–case and temporal context. This repo contains the design (docs), implementation plan, and the worker that runs the full ingest pipeline; the rest of the stack is integrated via configuration and APIs.

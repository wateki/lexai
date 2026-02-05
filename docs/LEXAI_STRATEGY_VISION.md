# LexAI Strategy Vision: One-Stop Shop & Second Brain for Law Firms

This document sets the **product and technical strategy** for LexAI: a **one-stop shop** for all law/legal matters and a **second brain** for the firm — continuously updated, profile-aware, and proactive.

---

## 1. Vision

**LexAI is the single place where law firms manage and reason over everything legal.**

- **One-stop shop:** All law/legal-related matters in one platform — case files, precedents, statutes, regulations, internal documents, client history, deadlines, and research — with a **continuously updated** body of knowledge.
- **Second brain:** The system doesn’t just store and search; it **aids research**, **suggests actions** based on what’s happening, and **surfaces what the firm could miss** — deadlines, risks, relevant law, similar cases, gaps in filings or strategy — so nothing falls through the cracks.
- **Profile-aware intelligence:** Suggestions and research are driven by **profiling** of the case (type, stage, jurisdiction, matter), the **client** (type, industry, history, risk), and the **documents availed for the case** in the platform. Precedents and law are matched to this context so that advice is relevant, not generic.

---

## 2. Continuously Updated Knowledge Layer

For LexAI to act as a second brain, the following must be **living** and **kept current**:

| Layer | Content | How it stays updated |
|-------|---------|----------------------|
| **Legal knowledge** | Precedents, case law, statutes, regulations, practice-area notes | Regular ingest (manual, bulk, or API); usage and feedback; optional linking to official sources for currency. |
| **Case files** | Matters, status, stage, deadlines, team, value, key dates | Normal case lifecycle (create, update, close); calendar and timeline events; documents linked to cases. |
| **Case documents** | Pleadings, contracts, evidence, motions, discovery, correspondence | Upload/link to cases; optional OCR/extraction; indexing (chunks or tree) for retrieval. |
| **Client context** | Client type, industry, retainer, conflict status, risk, history of matters | Client and case data; risk assessment (existing RPC); historical matters and outcomes. |
| **Firm activity** | Who is on which case, workload, deadlines, recent activity | Team assignments, calendar, timeline, user activities. |

**Principle:** The second brain is only as good as what it knows. Prioritise **ingest pipelines**, **document processing**, and **linking** (case ↔ client ↔ documents ↔ legal KB) so that research and suggestions are grounded in up-to-date, firm-specific data.

---

## 3. Profiling Dimensions (What Drives Relevance)

Suggestions and research must be **contextual**. The following dimensions form the “profile” used for retrieval, ranking, and generation:

| Dimension | Source | Use |
|-----------|--------|-----|
| **Case type / matter type** | `cases.matter_type`, `case_category` | Filter Legal KB; find similar cases; suggest typical next steps and risks. |
| **Jurisdiction** | `cases.jurisdiction` | Restrict law and precedents to the right courts/regions. |
| **Case stage** | `cases.stage`, `status` | Stage-appropriate actions (e.g. discovery vs settlement); deadlines and checklist suggestions. |
| **Client type** | `clients.type` (e.g. individual, company, NGO) | Compliance, disclosure, and process suggestions. |
| **Client industry** | `clients.industry` | Sector-specific regulation and risk. |
| **Client history** | Past cases, outcomes, risk factors | “This client has had similar matters”; conflict and risk continuity. |
| **Documents in the case** | `documents` linked to case | Summaries, key claims, gaps (e.g. missing filings); “given what you’ve filed, consider …”. |
| **Lead/team** | `cases.lead_attorney_id`, `case_team_assignments` | Workload-aware suggestions; who might be missing something. |

**Principle:** Every AI feature (research, insights, digest, command bar, “what you might miss”) should **consume this profile** so that suggestions are tied to case type, client type, client history, and the actual documents and activity in the platform.

---

## 4. Core Capabilities (What the Second Brain Does)

### 4.1 Research

- **Legal research:** Query precedents, statutes, and practice materials — scoped by **jurisdiction**, **matter type**, and optionally **case** or **client**.
- **Case-linked research:** “Research in context of [Case X]” pre-fills jurisdiction/matter and (when implemented) can pull in case documents so that answers and citations are relevant to that matter.
- **Document-grounded research:** For a given case, combine Legal KB with **documents availed for the case** (pleadings, contracts) so that research can reference both “the law” and “what this case file says.”

*Technical:* Legal DB (keyword + optional vector) + case/document filters; optional RAG over case documents (chunks or PageIndex-style tree retrieval).

---

### 4.2 Suggestions Based on What Is Happening

- **Proactive suggestions:** Driven by **what’s happening now** — e.g. upcoming deadlines, cases in discovery, new documents uploaded, stage changes.
- **Sources:** Calendar, timeline, case stage, recent uploads, and open AI insights. Suggestions can be “next steps,” “consider this precedent,” “review this document,” “client risk updated.”

*Technical:* Digest/insights pipelines that run on case + calendar + timeline + Legal KB; optional background jobs or on-demand “refresh suggestions.”

---

### 4.3 What the Firm Could Miss

- **Gap and risk awareness:** Surfaces **what might be missed** — missed deadlines, typical filings not yet done for this stage, client risk flags, conflicting commitments, or precedents that could change strategy.
- **Checklists and playbooks:** By **case type** and **stage**, suggest standard steps (e.g. discovery checklist for employment matters in jurisdiction X) and compare against actual activity and documents.
- **Client and matter continuity:** “This client had a similar matter last year”; “this matter type often involves X — have you considered Y?”

*Technical:* Rules/playbooks (e.g. matter_type + stage → checklist); comparison of “expected” vs actual (timeline, documents); client history and risk (existing RPC + case list).

---

### 4.4 Action Suggestions from Case + Precedents + Client + Documents

- **Profile-driven actions:** For a given case, combine:
  - **Case profile:** type, stage, jurisdiction, deadlines, team.
  - **Client profile:** type, industry, history, risk.
  - **Case documents:** what’s already on the platform (summaries, key terms, gaps).
  - **Precedents / law:** relevant to jurisdiction and matter type.
- **Output:** Concrete suggestions — e.g. “Consider citing [precedent] given your pleading”; “Similar matters often file X by stage Y”; “Client risk suggests reinforcing Y in the retainer”; “Document A and B conflict on Z — consider reconciling.”

*Technical:* Single “suggest actions” flow (or per-surface: case detail, dashboard, digest) that:
  1. Builds profile (case, client, documents).
  2. Retrieves relevant Legal KB (and optionally similar cases).
  3. Optionally runs RAG over case documents.
  4. Generates actions with citations; writes to `ai_insights` or digest items.

---

### 4.5 Proactive, always-on brain: a step ahead

**Alongside user-initiated "suggest actions," the AI brain is a step ahead — analyzing and offering suggestions at every stage of the case lifecycle before the user catches up.**

- **Per case, at every stage:** For each case, at **every stage** of its lifecycle (intake, discovery, negotiation, litigation, settlement, closed), the system **already** runs analysis using:
  - **Current legal context** — law and precedents relevant to jurisdiction and matter type *as it stands now*.
  - **Similar and related contexts** — similar cases, same matter type, same jurisdiction, comparable outcomes.
  - **Case documents** — what's on the platform for this case (pleadings, contracts, evidence).
  - **Client and matter profile** — client type, history, risk; case stage and deadlines.
- **Vision into the case:** The brain has **ongoing vision** into the case: it is **already** analyzing and forming a view (suggestions, risks, next steps, relevant law) so that when the user opens the case or the digest, they see **prepared** suggestions and analysis — not only when they click "suggest actions" or ask a question.
- **User-initiated remains:** User-initiated "suggest actions" and research (e.g. command bar, "research in context of this case") stay in place; the proactive brain **complements** them by keeping the case view and suggestions current so the user is never starting from zero.

**Principle:** The second brain is **always on** for every case: at each lifecycle stage it is already one step ahead, offering suggestions and analysis given all legal context (current and similar) so the firm sees what matters *before* they have to ask.

*Technical:* Background or event-driven pipelines that, on case create/update, stage change, new document, or schedule (e.g. daily/weekly per active case), run profile + Legal KB + similar cases + document retrieval and write/refresh `ai_insights`, digest items, or a "case view" summary; UI surfaces these on case detail and dashboard so they appear without user initiation.

---

## 5. When the brain updates: triggers and context refresh

**The second brain stays current by updating knowledge and user context whenever something relevant changes — including new documents and case interaction via prompting.**

Whenever any of the following happens, the system **updates the knowledge and user context** so that analysis and suggestions reflect the latest state:

| Trigger | What updates |
|--------|----------------|
| **New documents added** (to a case) | Re-index documents (chunk or tree); refresh case document profile; re-run analysis for that case (relevant law, similar contexts, gaps, suggestions); update `ai_insights` and case-view summary so the brain's "vision" includes the new material. |
| **Case interaction via prompting** | When the user interacts with the case via chat/prompting (e.g. asks a question in context of the case, or provides new information in the conversation), treat that as new context: persist or summarize the interaction; update user context and, where appropriate, the case's working context; refresh suggestions so future analysis and answers take the new information into account. |
| **Case stage or status change** | Re-run stage-appropriate analysis (playbooks, next steps, risks for this stage); refresh suggestions and "what you might miss" for the new stage. |
| **Timeline or calendar events** | New deadline, hearing, or milestone → update "what's happening" and digest; optionally re-run suggestions for affected cases. |
| **Legal KB or precedent updates** | When a topic (precedent, statute, practice area) is updated: **query the topic–case graph/index** to get cases (and optionally documents/situations) linked to that topic → queue them for **reassessment**; apply **new tagging** where needed (e.g. “case affected by change in precedent X”); refresh suggestions so the brain and UI stay impact-aware. |

**Principle:** Once new documents are added or we get something from case interaction (e.g. prompting), we **update knowledge and user context** — so the brain's view of the case and the user's context are always in sync with the latest data and interaction.

*Technical:* Event handlers or jobs on document upload (and optionally on case chat/prompt ingestion); stage/status/timeline/calendar hooks; optional "context" store per case (or user) that includes last prompt summary or key facts from interaction; pipelines that re-index and re-run analysis and write to `ai_insights` / digest / case view.

---

## 6. Topic–case graph / impact index (living, continuously updated)

**It is critical to maintain a graph or index that tracks which cases (and documents, contracts, situations) are tied to which topics** — so that when topics change (e.g. precedent updated, statute amended), the system knows **what to reassess** and whether **new tagging** is needed. This index is **living** and **continuously updated**.

### 6.1 Why an index or graph

- **Topics** that can change: precedents, statutes, regulations, jurisdiction rules, matter-type playbooks, practice areas, legal issues (e.g. “termination”, “limitation period”).
- **Entities** that are affected: cases, case documents, contracts, situations (e.g. a clause type, a filing type).
- Without a **topic–entity index**, any change to a topic would require re-running analysis on *all* cases — expensive and slow. With the index, we **only reassess cases (and related documents/contracts/situations) that are linked to the changed topic**.
- When a precedent or statute changes, we need to know: *which cases, contracts, or situations are affected by this change?* The index answers that so we can trigger reassessment and, where needed, **re-tag** (e.g. “case affected by change in precedent X”, “contract clause type Y impacted by statute Z”).

### 6.2 What the index captures

| Concept | Description |
|--------|----------------|
| **Topics** | Precedents, statutes, practice areas, matter types, jurisdictions, legal issues — anything in the Legal KB or taxonomy that can *change* or *be updated*. |
| **Entities** | Cases, documents (pleadings, contracts), and optionally “situations” (e.g. clause types, filing types) that are **linked to** one or more topics. |
| **Links** | Case ↔ topic (e.g. case in jurisdiction X, matter type Y, cited precedent Z); document ↔ topic (e.g. contract touches statute S); optional **weight** or strength (e.g. how strongly a case depends on a precedent). |
| **Change events** | When a topic is updated (new precedent, statute amended, practice note changed), the index is queried to get **affected entities** → queue those for reassessment and optional re-tagging. |

### 6.3 Living, continuously updated

- **Index maintenance:** Whenever a case is created or updated (e.g. jurisdiction, matter_type, linked precedents), documents are linked to a case, or analysis runs and identifies relevant precedents/statutes, the **topic–case (and topic–document) links** are written or updated in the index.
- **When a topic changes:** Precedent added/updated, statute amended, Legal KB entry changed → update the topic’s “version” or “last_updated”; **query the index** for all cases (and optionally documents/situations) linked to that topic → **queue them for reassessment**; optionally **re-tag** (e.g. “affected by precedent X update”) so the brain and UI can surface “cases impacted by recent change in law.”
- **Weighting (optional):** Store a **weight** or relevance score (e.g. how central a precedent is to a case) so that when many cases are affected, we can **prioritise** reassessment (e.g. high-weight links first) or surface “highly affected” cases first.
- **Continuously updated:** The graph/index is updated on every relevant event — new case, new document, new link to precedent, topic change — so it always reflects **which cases are updated by which topics** and **which topics, when changed, should trigger reassessment of which cases**.

### 6.4 Re-tagging when affected

- When a **precedent**, **statute**, or other **topic** changes: after reassessment, the system may **re-tag** cases, documents, or situations (e.g. “case affected by change in precedent X”, “contract clause type Y impacted by statute Z”) so that:
  - The **living index** stays accurate (tags are part of the index or derived from it).
  - The **second brain** and UI can show “cases/contracts/situations affected by recent change” and prioritise suggestions accordingly.

**Principle:** Maintain a **living graph or index** of *topic ↔ case (and document/situation)* so that when topics are changed or updated, we know **what to reassess** and can apply **new tagging** where needed — keeping the system **continuously updated** and impact-aware.

*Technical:* Topic–entity index (e.g. table or graph: `topic_id`, `entity_type` (case | document | situation), `entity_id`, optional `weight`, `updated_at`); topic change events that query the index and enqueue reassessment jobs; optional tag store for “affected by precedent/statute X”; pipelines that update the index on case/document create/update and on analysis runs that link cases to precedents/statutes.

---

## 7. Documents Availed for the Case

- **Centrality of case documents:** Pleadings, contracts, evidence, and correspondence **uploaded or linked to the case** are first-class inputs to the second brain.
- **Use:** Research (“what does this contract say?”), summarisation, gap detection (“have you filed X?”), comparison with precedents (“your clause Y differs from common practice”), and action suggestions (“given document A, consider B”).
- **Indexing:** Documents must be **findable and citable** — either by chunking + embedding (vector/hybrid RAG) or by tree/structure (e.g. PageIndex) for long docs, so that suggestions and answers can point to specific sections or pages.

*Technical:* `documents` + optional `document_chunks` or tree store; ingestion pipeline (OCR/extract, chunk or tree, embed if vector); RAG or tree retrieval scoped by `case_id` and org.

---

## 8. How This Ties to the Current Architecture

| Building block | Role in “second brain” |
|-----------------|------------------------|
| **Legal KB** (`legal_knowledge_base`) | Continuously updated source of law and precedents; search (and later vector) scoped by jurisdiction/matter; feeds research, insights, and action suggestions. |
| **Cases** | Profile: matter_type, jurisdiction, stage, deadlines, team; link to clients and documents; trigger “what’s happening” and “what you might miss.” |
| **Clients** | Profile: type, industry, history, risk; client-level risk (existing RPC); continuity across matters. |
| **Documents** | Case documents as input to research and suggestions; indexing (chunk/tree) for retrieval and citation. |
| **Calendar / timeline** | “What’s happening”; deadlines and milestones; input to digest and proactive suggestions. |
| **AI insights** | Store for suggestions, risks, and “what you might miss” per case (or doc); written by pipelines and action-suggestion logic. |
| **RAG (vector + hybrid)** | Research and Q&A over Legal KB and case documents; strict grounding and citations. |
| **PageIndex (optional)** | Reasoning-based retrieval inside long case documents (e.g. long PDFs); can sit alongside vector RAG for doc-level selection. |
| **Topic–case graph / impact index** | Living index: which cases (and documents/situations) are linked to which topics (precedents, statutes, matter types, etc.); when a topic changes, query the index to determine **what to reassess** and apply **new tagging**; continuously updated on case/document/topic changes. |

---

## 9. Strategic Principles (Summary)

1. **One-stop shop:** All legal matter data (cases, clients, documents, precedents, activity) lives and is updated in the platform so the second brain has a single, current view.
2. **Continuously updated:** Legal KB and case documents are ingested and indexed so that research and suggestions reflect the latest the firm has.
3. **Profile-aware:** Every AI feature uses case type, jurisdiction, client type, client history, and case documents so that suggestions are relevant, not generic.
4. **Proactive second brain:** Research, suggestions, “what you might miss,” and action ideas are driven by profiling and by what’s happening (deadlines, stage, new docs), not only by ad-hoc queries.
5. **Always-on, a step ahead:** Alongside user-initiated "suggest actions," the brain is **already** analyzing at every lifecycle stage and offering suggestions and analysis (current legal context, similar cases, documents) so the user sees prepared insight when they open the case — before they ask.
6. **Update on triggers:** When new documents are added or case interaction happens via prompting (or stage/timeline/calendar changes), the system **updates knowledge and user context** so the brain's view and suggestions stay in sync with the latest data and interaction.
7. **Documents in the loop:** Case documents are first-class: indexed, summarised, and used for research, gap detection, and action suggestions alongside precedents and matter/client profile.
8. **Living topic–case index:** Maintain a **graph or index** of which cases (and documents/situations) are updated by which topics; when topics change, use it to know **what to reassess** and apply **new tagging** (e.g. case/contract affected by change in precedent); keep the index **continuously updated**.
9. **Incremental delivery:** Implement in layers — e.g. Legal DB search ✅; then profile-aware insights and digest; then document-backed RAG and “suggest actions”; then “what you might miss” and playbooks — so the firm gets value at each step.

---

## 10. Next Steps (High Level)

- **Implementation plan:** See **[LEXAI_IMPLEMENTATION_PLAN.md](./LEXAI_IMPLEMENTATION_PLAN.md)** for a detailed, phased implementation guide — including building the Legal KB via **document upload** (living, continuously updated), topic–case index, and proactive brain — grounded in current state.
- **Strategy:** Treat this doc as the north star for product and technical decisions; refine “what you might miss” and playbooks with real matter types and checklists.
- **Data:** Ensure case/client/document linking and ingest pipelines support “continuously updated” and profile dimensions; add or extend indexing (chunks/tree) for case documents; design and implement the **topic–case graph / impact index** (which cases/documents/situations are linked to which topics) and keep it living (updated on case/document/topic changes; topic change → query index → reassess affected entities and re-tag where needed).
- **AI features:** Implement profile-aware insights, digest, and command bar (Legal DB + case/client context); then document-backed RAG and “suggest actions”; then **proactive always-on analysis** (per case, per stage) and triggers (new docs, case interaction via prompting) to update knowledge and context; then gap/playbook features.
- **Retrieval:** Choose and implement RAG (vector/hybrid) and, if needed, PageIndex (or similar) for long docs, so that research and suggestions can cite both law and case documents.

---

*This vision document should be updated as the product and technical strategy evolve. It complements the more technical RAG and AI architecture docs in the codebase.*

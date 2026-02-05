# Implementation Plan Comparison: V1 vs V2

## Quick Summary

| Aspect | V1 (Original) | V2 (Accuracy-First) |
|--------|---------------|---------------------|
| **Primary Retrieval** | pgvector (similarity) | PageIndex (reasoning) |
| **Accuracy Target** | 70-80% (vector similarity) | 98.7% (reasoning-based) |
| **Topic-Case Graph** | Manual SQL tables | Graphiti (autonomous) |
| **Agent Memory** | Manual context assembly | Graphiti episodes |
| **Document Processing** | Docling → embeddings | Docling → PageIndex trees |
| **Query Speed** | 200-500ms | 2-5 seconds |
| **Explainability** | Low (black box vectors) | High (reasoning traces) |
| **Development Time** | 20 weeks | 20 weeks (same) |
| **Complexity** | Medium | Medium |
| **Cost** | $ (embeddings) | $$ (tree generation + Graphiti) |
| **Legal Fit** | ⚠️ Risky (accuracy concerns) | ✅✅ Optimal (accuracy + explainability) |

## Key Changes

### Architecture Changes

**V1:**
```
Document → Docling → Embeddings → pgvector
Query → Vector search (similarity) → Chunks
```

**V2:**
```
Document → Docling → PageIndex trees → PostgreSQL
Query → PageIndex reasoning → Sections (with reasoning trace)
         + Graphiti graph → Relationships + temporal context
```

### Phase Changes

| Phase | V1 Focus | V2 Focus | Change |
|-------|----------|----------|--------|
| **1** | Docling + embeddings | Docling + PageIndex trees | Replace embeddings with trees |
| **2** | Taxonomy + search UX | PageIndex search + RAG | Add reasoning-based retrieval |
| **3** | Embeddings pipeline | Graphiti graph setup | Replace embeddings with Graphiti |
| **4** | Manual topic-case SQL | (Merged into Phase 3) | Use Graphiti instead |
| **5** | Case docs chunking | Case docs PageIndex | Use PageIndex instead of chunks |
| **6** | Proactive brain | Proactive brain + Graphiti memory | Add agent memory |

## What to Use

**Use V1 if:**
- Speed is more important than accuracy
- Simple use case (not high-stakes legal work)
- Small team with limited infrastructure capacity

**Use V2 if:**
- Accuracy is critical (legal, medical, financial)
- Need explainability (court, compliance, audit)
- Want autonomous relationship tracking
- Building long-term AI agent with memory

**Recommendation for LexAI:** **V2** - Legal work demands accuracy and explainability.

## Migration Path

If you've already started implementing V1:
1. **Week 1-2:** Add PageIndex alongside existing vector RAG
2. **Week 3-4:** Run parallel (vector + PageIndex), compare accuracy
3. **Week 5:** Switch primary to PageIndex, keep vector as fallback
4. **Week 6+:** Add Graphiti for relationships

If starting fresh (your current state):
1. **Implement V2 directly** (no migration needed)
2. Start with Phase 1 (Docling + PageIndex)
3. Skip vector embeddings unless needed for quick lookups

## Bottom Line

**V2 is better for LexAI** because:
- ✅ Legal accuracy requirements (98.7% vs 70-80%)
- ✅ Explainability for court (reasoning traces)
- ✅ Long document handling (contracts, pleadings)
- ✅ Autonomous relationships (Graphiti saves dev time)
- ✅ Future-proof (agent memory, temporal queries)

The extra 2-3 seconds per query is **worth it** to avoid malpractice claims.

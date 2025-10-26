## Next 10 Interpreter + RAG Enhancements

This document lists the next 10 issues and a concrete, ordered task plan to implement them.

### Issues
- [x] Integrate the Semantic Interpreter into the RAG Flow (pre-generation)
- [x] Add Schema Awareness to the Interpreter (use tenant schema embeddings)
 - [x] Introduce a Schema Indexing Stage During Ingestion (per-tenant schema vectors)
 - [x] Link Intent Classification to the Generation Prompt (style routing)
 - [x] Implement Entity Consolidation Before Generation (merge same-entity chunks)
 - [x] Add Context Deduplication and Compression (token budget focus)
7. Create a Memory Buffer for Short-Term Recall (conversation-scoped)
8. Implement a Confidence Scoring Layer (pre-generation guard)
9. Add Schema Expansion Feedback Loop (self-improving schema map)
 - [x] Introduce Semantic Health Logging (observability)

---

### Step-by-Step Tasks

1) Interpreter in RAG flow
- Hook: RAGService.answer(), between reranking and prompt build
- Replace raw `\n\n`.join(contexts) with `interpreter.interpret(... )`
- Keep fallback to raw contexts if interpretation is empty

2) Schema-aware interpreter
- Query Qdrant for nearest schema fields for the query (per tenant)
- Pass field list to interpreter for relevance filtering
- Respect synonyms: map tenant-specific aliases → canonical labels

3) Schema indexing at ingestion
- In document_service: extract headers/keys per sheet/file
- Embed headers with OpenAI embeddings (1536-d) and upsert to Qdrant
- Tag collection/keyspace for fast schema lookup (`schema_fields`)

4) Intent-linked prompting
- Use `_classify_intent(query)` → set temperature and style flags
- Yes/No → strict short answers; Temporal → dates only; Causal → brief rationale
- Update prompt template to reflect selected style

5) Entity consolidation
- Identify entity keys (name/id) from metadata.row
- Merge multiple chunks for the same entity into one synthesized paragraph
- Prefer newest/most relevant facts by score and drop duplicates

6) Deduplication & compression
- Remove repeated sentences across interpreted contexts
- Keep first 1–2 sentences per paragraph for yes/no or temporal intents
- Cap final context to top-N most relevant interpreted facts

7) Memory buffer
- In conversation_service: store last 10 user queries and interpreted outputs
- On each new query: append memory buffer summary to interpreted context (cap length)
- Provide toggle to enable/disable memory use per tenant/channel

8) Confidence scoring
- Compute similarity between query and interpreted contexts:
  - Use CrossEncoder score if available; else cosine over embeddings
- If average confidence < threshold: return low-info response or trigger broader fallback retrieval

9) Schema expansion feedback
- Log (tenant_id, query, matched_fields, synonyms) per answer
- Periodically update synonyms map / re-embed schema labels
- Use logs to augment schema alias dictionary per tenant

10) Semantic health logging
- Structured logs per query:
  - intent, matched schema fields, interpreter applied?, confidence, answer type
- Emit metrics counters for applied/fallback and confidence buckets

---

### Acceptance Criteria
- Interpreted, concise, and relevant contexts feed generation by default
- Schema-aware filtering keeps only fields that matter to the question
- Same-entity chunks produce a single, coherent paragraph
- Conversation memory improves follow-ups without polluting prompts
- Confidence guard prevents speculative/hallucinated answers
- Observability shows per-query pipeline, coverage, and confidence



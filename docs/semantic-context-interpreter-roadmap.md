## Semantic Context Interpreter Roadmap

This document lists the new issues and a step-by-step plan to implement them in the RAG pipeline.

### Issues
1. Create the Semantic Context Interpreter: A service to transform raw contexts (CSV field:value, extracted text) into readable, human-language context using user query and tenant schema.
2. Integrate the Interpreter into the RAG Flow: Call it after reranking and before LLM prompt; replace raw concatenation with interpreted output.
3. Add Schema-Aware Context Filtering: Use schema embeddings to keep only fields relevant to the question; discard noisy fields.
4. Translate Structured Data into Natural Language: Map technical fields and codes into natural phrases; merge related fields.
5. Enhance the LLM Prompt: Instruct to interpret rather than quote; concise natural answers; include explicit reasoning examples.
6. Add Intent Classification / Answer Routing: Lightweight detector (factual/temporal/causal/descriptive) to adjust generation style.
7. Support Schema Expansion Across Tenants: Maintain per-tenant schema embeddings and synonym dictionaries; reuse for expansion and translation.
8. Implement Context Deduplication and Compression: Merge duplicates by entity and keep top facts to reduce token waste.
9. Adjust Conversation Service: Ensure only interpreted text enters the final LLM call; add trace logs.
10. Build Testing and Evaluation Routine: Binary/date/descriptive question tests to validate shorter, human-like outputs.
11. Add Fallback Behavior: If interpreter fails or no schema match, revert to raw context and log.

---

### Step-by-Step Tasks

 - [x] 1) Semantic Context Interpreter service
- Design interface: `interpret(query, contexts, tenant_id, schema_fields) -> List[str] | str`
- Implement rule-based core (no external calls):
  - Field selection heuristics (token overlap with query; embed proximity if available)
  - Field name normalization/synonyms; value decoding (Y/N, codes)
  - Structured sentence templates for common HR/CRM-style fields
- Optional: small LLM assist (config-gated) for paraphrasing

 - [x] 2) Integrate into RAG
- Hook after reranking; fetch schema fields (Qdrant + Redis cache)
- Replace raw `"\n\n".join(contexts)` with `interpreter_output`
- Preserve original contexts for fallback

 - [x] 3) Schema-aware filtering
- Use nearest-schema search (existing Qdrant) to pick relevant fields
- Config thresholds; keep top-K fields per chunk

 - [x] 4) NL translation of structured data
- Map technical keys to human phrases (e.g., `MaritalDesc -> marital status`)
- Expand boolean/coded values
- Merge related facts into single sentences

 - [x] 5) Prompt enhancement
- Update system prompt to: interpret, be concise, avoid raw labels
- Add few-shot snippets (e.g., marital status/date answer patterns)

 - [x] 6) Intent classification
- Add lightweight classifier (regex/keywords) with types: factual/temporal/causal/descriptive
- Route to style templates and prompt additives

 - [x] 7) Schema expansion across tenants
- Persist learned synonyms per tenant (Redis/DB)
- Feed into query expansion and interpreter key mapping

 - [x] 8) Deduplication & compression
- De-duplicate by entity key (e.g., name + employee id)
- Keep top-N relevant facts by score; compress long numeric lists

 - [x] 9) Conversation service wiring
- Ensure only interpreted text goes into final LLM prompt
- Add logs: `semantic_interpreter=applied|fallback`

 - [x] 10) Testing & evaluation
- Add tests: yes/no, date, descriptive across sample rows
- Snapshot before/after outputs; assert length and naturalness heuristics

 - [x] 11) Fallback behavior
- If interpreter empty or exception: use raw contexts; log `interpreter_fallback`

---

### Acceptance Criteria
- Interpreted contexts are shorter, human-readable, and field-labeled text no longer appears in the final prompt
- Schema filters remove irrelevant fields (race/zipcode/timestamps) for unrelated queries
- Binary/date/descriptive queries produce concise, natural answers consistently
- Fallback path works and logs are emitted

### Milestones
- M1: Interpreter core + RAG integration + prompt updates
- M2: Schema-aware filtering, NL translations, dedup/compression
- M3: Intent classifier + tenant synonym store + tests/evaluation


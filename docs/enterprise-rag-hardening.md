## Enterprise RAG Hardening: Issue List and Remediation Plan

This document lists 13 issues to bring `ai-core` to an enterprise-grade RAG, with concise fixes and an execution TODO checklist.

### Scope
- Backend: retrieval, embeddings, reranking, ingestion, Qdrant integration
- Non-goals: UI work (unless noted), long-running model training

---

### 1) Duplicate query expansion functions
- Problem: Two `expand_queries` variants; only the latter is active, risking silent overrides.
- Fix:
  - Consolidate into one schema-aware function: `expand_queries(query, schema_fields=None, tenant_id=None)`.
  - Add Redis cache `(tenant_id, query) -> [expansions]` with TTL.
- Acceptance:
  - Single definition; unit test verifies caching and schema inclusion.

### 2) Incorrect reranker flag wiring
- Problem: Reranker enablement is read/set from mixed keys, leading to inconsistent behavior.
- Fix:
  - Add a single `RERANK_ENABLED` (bool) in config.
  - `RAGService` uses only this flag to gate reranking; API toggle updates it.
- Acceptance:
  - Toggling on/off in `/reranker/toggle` deterministically enables/disables reranking.

### 3) Missing row metadata in Qdrant payloads
- Problem: Row `metadata` isn’t sent to Qdrant, so retrieved hits lack structured fields.
- Fix:
  - Include `metadata` when upserting chunks to Qdrant payload.
  - Backfill: when reading, prefer payload `metadata` if present.
- Acceptance:
  - Retrieved payload contains `metadata.row` for tabular rows.

### 4) CrossEncoder receives unstructured text
- Problem: Reranker sees raw text, not labeled fields.
- Fix:
  - When `metadata.row` exists, transform context to `"Field: Value | ..."` for CrossEncoder input; map back for final contexts.
- Acceptance:
  - Unit test: labeled context improves score for correct row vs. distractor.

### 5) Embedding model mismatch (OpenAI vs BGE)
- Problem: `BAAI/bge-large-en-v1.5` used in OpenAI embeddings path.
- Fix:
  - Split embedding backends: `embed_openai()` (1536-d), `embed_local_st()` (e.g., BGE 1024-d).
  - Enforce Qdrant dimension per backend or use separate collections.
- Acceptance:
  - No calls to OpenAI with HF model IDs; dims validated before Qdrant upsert.

### 6) Schema embeddings not queried during retrieval
- Problem: Schema vectors are stored but never searched.
- Fix:
  - During expansion, query `schema_fields` collection with query embedding to get nearest field names; merge into `schema_fields` list.
- Acceptance:
  - Logs show nearest fields used in expansions when Redis cache is empty.

### 7) Fusion not calibrated
- Problem: RRF uses fixed `k`; no weighting/normalization knobs.
- Fix:
  - Make `RRF_K`, `RRF_W_BM25`, `RRF_W_DENSE` configurable.
  - Optionally normalize dense/BM25 ranks by candidate count.
- Acceptance:
  - Config changes affect ranking deterministically.

### 8) Query expansion caching missing
- Problem: LLM expansions recomputed, adding latency/cost.
- Fix:
  - Cache `(tenant_id, query)` expansions in Redis with TTL.
- Acceptance:
  - Subsequent calls hit cache; no OpenAI request logged.

### 9) Schema embedding lifecycle incomplete
- Problem: Stale schema vectors after re-uploads.
- Fix:
  - Deterministic IDs per `(tenant_id, field_name)`. On ingestion, compute new set; delete any stale vectors not in new set.
- Acceptance:
  - After schema change, Qdrant shows only current fields for the tenant.

### 10) Tenant isolation in vector DB
- Problem: Risk of cross-tenant leakage.
- Fix:
  - Strict `tenant_id` filter on every query (already applied); consider per-tenant collections as an optional mode.
- Acceptance:
  - Queries without `tenant_id` return nothing; option to enable per-tenant collection naming.

### 11) Hybrid retrieval overhead
- Problem: Always runs both BM25 and dense.
- Fix:
  - Add `HYBRID_USE_BM25`, `HYBRID_USE_DENSE` flags; short-circuit when one is disabled or unavailable.
- Acceptance:
  - Disabling a retriever removes its calls from logs and reduces latency.

### 12) OCR and structural parsing missing
- Problem: Scanned PDFs/images produce empty/noisy chunks.
- Fix:
  - Optional OCR fallback via `pytesseract` + `pdfplumber`; config-gated `USE_OCR`.
- Acceptance:
  - Scanned PDF yields non-empty text when OCR is on; added dependency notes.

### 13) Semantic normalization not applied
- Problem: Variants like “Married/marital” embed differently.
- Fix:
  - Introduce lightweight normalizer (lowercase, punctuation trim, simple lemmatization/stemming optional) applied to all text before embedding/BM25.
- Acceptance:
  - Normalized text path covered by unit tests; BM25/embeddings use normalized strings.

---

## Execution TODOs

- [x] Consolidate `expand_queries` into one schema-aware function; add Redis caching
- [x] Add single `RERANK_ENABLED` flag; wire `RAGService` to use only this
- [x] Include `metadata` in Qdrant upserts for all chunks
- [x] Always pass labeled contexts to CrossEncoder when `metadata.row` exists
- [x] Split embedding backends (OpenAI vs local ST); validate Qdrant vector dims
- [x] Query `schema_fields` collection for nearest fields during expansion
- [x] Expose `RRF_K`, `RRF_W_BM25`, `RRF_W_DENSE` in config; apply in fusion
- [x] Add Redis cache for query expansions `(tenant, query)` with TTL
- [x] Implement schema upsert cleanup (delete stale field vectors)
- [x] Enforce tenant filters everywhere; optional per-tenant collections mode
- [x] Add `HYBRID_USE_BM25` and `HYBRID_USE_DENSE`; skip disabled retrievers
- [x] Integrate OCR fallback (pytesseract/pdfplumber) behind `USE_OCR`
- [x] Add normalization pipeline pre-embedding/BM25

## Rollout & Validation
- Config flags default to current behavior to allow gradual enablement.
- Add unit tests for expansions, fusion, normalization, and metadata propagation.
- Monitor latency and hit-rates post-deploy; tune `RRF` weights and `RRF_K`.



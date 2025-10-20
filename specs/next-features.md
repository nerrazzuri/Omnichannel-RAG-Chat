### Omnichannel RAG Chatbot – Next Feature Roadmap

#### Conversational intelligence
- Entity memory (people, topics, dates) across turns
- Temporal context (today/now/this month) with safe interpretation
- Follow-up coreference resolution (“his”, “that”, “next”, “continue”)
- Enhanced list follow-ups: arbitrary continue, from item X, insert-between

#### Universal tabular intelligence
- Column/Unit resolver: basic synonyms, fuzzy match, type inference (numeric/date/text) (completed; unit normalization pending)
- SQL aggregation v2: filters (eq, ne, gt, gte, lt, lte, contains), date ranges (year/between/quarter), group-by, distinct count, min/max, multi-column WHERE, sheet targeting (completed; top-k N/A for aggregation)
- Natural query parsing: “sales in Q1 2014 by region” → field, time window, group-by

#### Chat UX polish
- Markdown rendering (headings, tables, code), copy buttons, collapsible citations
- Inline source chips; click to preview chunk/document
- Message actions: edit & re-run, retry with expanded retrieval, follow-up suggestions

#### Upload and ingest UX
- Drag & drop + folder upload; parallel ingest; cancel/abort
- Live progress via SSE: extract → chunk → embed → upsert (per-file and overall)
- Ingest report: rows/documents added, sheets detected, columns mapped

#### Admin Knowledge UI
- Document list with status; reindex, delete, and “view chunks”
- Per-tenant KB selector; RBAC with JWT; audit log of changes

#### Retrieval/Indexing
- Chapter/title indexing surfaced in UI; “jump to chapter” controls
- Qdrant payload filters (tenant, chapter, sheet) and tuned HNSW params; quantization

#### Public fallback quality
- LLM public-knowledge fallback first with structured sources; Wikipedia only as last resort (completed)
- Tenant policy: enable/disable public fallback, max length, allowed domains

#### Platform readiness
- Replace dev SQLite shim with full Alembic migrations
- CI/CD: GitHub Actions for test/build backend, apply Terraform, deploy K8s to staging
- Observability: Prometheus/Grafana dashboards, request tracing, correlation IDs across services

#### Suggested next two to implement
- Universal tabular intelligence: column/unit resolver + advanced SQL aggregation
- Chat UX polish: Markdown rendering, citation chips, copy buttons; ingest progress via SSE



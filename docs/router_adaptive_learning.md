# Adaptive Router Learning (L.2)

This document describes how to train/update the per-tenant intent catalog used by the `HybridContextualRouter`. The router merges a default catalog with tenant-specific overrides stored as JSON.

## Overview
- Default intents: `lookup`, `summary`, `compare`, `aggregate`, `forecast`.
- Router signals: rule-based anchors, embedding similarity, conversational context, optional model.
- Adaptive learning mines common n-gram phrases from labeled queries and writes them into a per-tenant overrides file.

## Files and Paths
- Overrides directory: `data/intent_catalog/` (configurable via `INTENT_CATALOG_DIR`).
- Per-tenant file: `data/intent_catalog/<tenant_id>.json` mapping intent → list of phrases.
- Training job: `backend/src/ai_core/pipeline/intent/train_router.py`.

## Train/Update Steps
1. Prepare a labeled dataset (JSONL), one item per line:
   ```json
   {"query": "how many tickets last week", "intent": "aggregate"}
   {"query": "compare jira vs zendesk volume", "intent": "compare"}
   {"query": "summarize q3 revenue highlights", "intent": "summary"}
   ```
2. Run the training job for a tenant:
   ```bash
   python -m ai_core.pipeline.intent.train_router \
     --tenant-id <TENANT_UUID_OR_SLUG> \
     --input ./data/router_training.jsonl \
     --catalog-dir ./data/intent_catalog \
     --top-k 20 \
     --max-per-intent 64
   ```
3. The job writes (or merges) `data/intent_catalog/<tenant>.json`. Example:
   ```json
   {
     "aggregate": ["how many", "count tickets", "total tickets last week"],
     "compare": ["compare jira", "jira vs zendesk"],
     "summary": ["summarize revenue", "q3 highlights"]
   }
   ```
4. Reload: the router autoloads on next request; no restart required in most cases. If cached, the new catalog is used after process restart or when a new router instance is created.

## Configuration
- `INTENT_CATALOG_DIR` (default: `data/intent_catalog`): directory to look for overrides.
- Signal weights and thresholds via env:
  - `INTENT_CONF_THRESHOLD` (default: 0.45)
  - `INTENT_MODEL_WEIGHT` (default: 0.35)
  - `USE_INTENT_MODEL` (true/false) to enable model fallback.

## Notes
- Keep phrases concise and meaningful (unigrams/bigrams/trigrams).
- The trainer de-duplicates and caps phrases per intent.
- For multi-tenant systems, run per tenant with their labeled data.



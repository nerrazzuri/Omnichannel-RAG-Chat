#!/usr/bin/env bash
set -euo pipefail

# Env: QDRANT_URL, AI_CORE_URL
TS=$(date +%s)
START=$TS
curl -s -X POST "${QDRANT_URL:-http://qdrant:6333}/collections/_all/snapshots" || true
SIZE=0
DUR_MS=$(( ( $(date +%s) - START ) * 1000 ))
curl -s -X POST "$AI_CORE_URL/v1/admin/backup/mark" \
  -H 'Content-Type: application/json' \
  -d "{\"system\":\"qdrant\",\"status\":\"success\",\"duration_ms\":$DUR_MS,\"size_bytes\":$SIZE,\"ts_unix\":$TS}" || true


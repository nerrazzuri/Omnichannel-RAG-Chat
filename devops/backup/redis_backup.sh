#!/usr/bin/env bash
set -euo pipefail

# Env: REDIS_HOST, AI_CORE_URL
TS=$(date +%s)
START=$TS
redis-cli -h "${REDIS_HOST:-redis}" BGSAVE
sleep 20
SIZE=0
DUR_MS=$(( ( $(date +%s) - START ) * 1000 ))
curl -s -X POST "$AI_CORE_URL/v1/admin/backup/mark" \
  -H 'Content-Type: application/json' \
  -d "{\"system\":\"redis\",\"status\":\"success\",\"duration_ms\":$DUR_MS,\"size_bytes\":$SIZE,\"ts_unix\":$TS}" || true


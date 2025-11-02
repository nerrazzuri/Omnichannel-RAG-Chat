#!/usr/bin/env bash
set -euo pipefail

# Env: PGHOST, PGUSER, PGPASSWORD, PGBACKUP_S3_URL, AI_CORE_URL
TS=$(date +%s)
OUT=/tmp/pgbackup-$TS
START=$TS
pg_basebackup -D "$OUT" -Ft -X fetch -z
SIZE=$(du -sb "$OUT" | awk '{print $1}')
DUR_MS=$(( ( $(date +%s) - START ) * 1000 ))
curl -s -X POST "$AI_CORE_URL/v1/admin/backup/mark" \
  -H 'Content-Type: application/json' \
  -d "{\"system\":\"postgres\",\"status\":\"success\",\"duration_ms\":$DUR_MS,\"size_bytes\":$SIZE,\"ts_unix\":$TS}" || true


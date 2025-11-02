#!/usr/bin/env bash
set -euo pipefail

# Env: PGHOST, PGUSER, PGPASSWORD, PGBACKUP_S3_URL, AI_CORE_URL, AI_CORE_TOKEN, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION, AWS_KMS_KEY_ID
TS=$(date +%s)
OUT=/tmp/pgbackup-$TS
START=$TS
pg_basebackup -D "$OUT" -Ft -X fetch -z
# Encrypt and upload (requires aws cli)
ARCHIVE="$OUT.tar.gz"
tar -czf "$ARCHIVE" -C "$OUT" .
aws s3 cp "$ARCHIVE" "$PGBACKUP_S3_URL/pg/$TS.tar.gz" --sse aws:kms --sse-kms-key-id "$AWS_KMS_KEY_ID"
SIZE=$(du -sb "$OUT" | awk '{print $1}')
DUR_MS=$(( ( $(date +%s) - START ) * 1000 ))
curl -s -X POST "$AI_CORE_URL/v1/admin/backup/mark" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $AI_CORE_TOKEN" \
  -d "{\"system\":\"postgres\",\"status\":\"success\",\"duration_ms\":$DUR_MS,\"size_bytes\":$SIZE,\"ts_unix\":$TS}"


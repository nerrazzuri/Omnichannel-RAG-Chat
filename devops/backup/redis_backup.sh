#!/usr/bin/env bash
set -euo pipefail

# Env: REDIS_HOST, AI_CORE_URL, AI_CORE_TOKEN, S3_URL, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION, AWS_KMS_KEY_ID
TS=$(date +%s)
START=$TS
redis-cli -h "${REDIS_HOST:-redis}" BGSAVE
# Poll until persistence completes
for i in $(seq 1 60); do
  INFO=$(redis-cli -h "${REDIS_HOST:-redis}" INFO persistence 2>/dev/null || true)
  INPROG=$(echo "$INFO" | awk -F: '/rdb_bgsave_in_progress/ {print $2}' | tr -d '\r')
  STATUS=$(echo "$INFO" | awk -F: '/rdb_last_bgsave_status/ {print $2}' | tr -d '\r')
  if [ "x$INPROG" = "x0" ]; then
    [ "x$STATUS" = "xok" ] && break
  fi
  sleep 3
done
RDB=/data/dump.rdb
if [ -f "$RDB" ]; then
  SIZE=$(stat -c%s "$RDB" 2>/dev/null || stat -f%z "$RDB")
  aws s3 cp "$RDB" "$S3_URL/redis/$TS.rdb" --sse aws:kms --sse-kms-key-id "$AWS_KMS_KEY_ID"
else
  SIZE=0
fi
DUR_MS=$(( ( $(date +%s) - START ) * 1000 ))
curl -s -X POST "$AI_CORE_URL/v1/admin/backup/mark" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $AI_CORE_TOKEN" \
  -d "{\"system\":\"redis\",\"status\":\"success\",\"duration_ms\":$DUR_MS,\"size_bytes\":$SIZE,\"ts_unix\":$TS}"


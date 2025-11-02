#!/usr/bin/env bash
set -euo pipefail

# Env: QDRANT_URL, AI_CORE_URL, AI_CORE_TOKEN, S3_URL, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION, AWS_KMS_KEY_ID
TS=$(date +%s)
START=$TS
# List collections and snapshot each
BASE="${QDRANT_URL:-http://qdrant:6333}"
COLS=$(curl -s "$BASE/collections" | jq -r '.result.collections[].name' 2>/dev/null || true)
for C in $COLS; do
  TS=$(date +%s)
  START=$TS
  # Create snapshot
  SNAP=$(curl -s -X POST "$BASE/collections/$C/snapshots" | jq -r '.result.name' 2>/dev/null || true)
  # Poll for availability (simple wait loop)
  for i in $(seq 1 20); do
    LIST=$(curl -s "$BASE/collections/$C/snapshots")
    echo "$LIST" | grep -q "$SNAP" && break
    sleep 3
  done
  # Download and upload
  curl -sL "$BASE/collections/$C/snapshots/$SNAP" -o "/tmp/$SNAP" || true
  SIZE=$(stat -c%s "/tmp/$SNAP" 2>/dev/null || stat -f%z "/tmp/$SNAP" 2>/dev/null || echo 0)
  SHA=$(sha256sum "/tmp/$SNAP" 2>/dev/null | awk '{print $1}')
  aws s3 cp "/tmp/$SNAP" "$S3_URL/qdrant/$C/$SNAP" --sse aws:kms --sse-kms-key-id "$AWS_KMS_KEY_ID"
  DUR_MS=$(( ( $(date +%s) - START ) * 1000 ))
  curl -s -X POST "$AI_CORE_URL/v1/admin/backup/mark" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $AI_CORE_TOKEN" \
    -d "{\"system\":\"qdrant\",\"collection\":\"$C\",\"status\":\"success\",\"duration_ms\":$DUR_MS,\"size_bytes\":$SIZE,\"ts_unix\":$TS,\"checksum_sha256\":\"$SHA\"}"
done
DUR_MS=$(( ( $(date +%s) - START ) * 1000 ))
curl -s -X POST "$AI_CORE_URL/v1/admin/backup/mark" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $AI_CORE_TOKEN" \
  -d "{\"system\":\"qdrant\",\"status\":\"success\",\"duration_ms\":$DUR_MS,\"size_bytes\":$SIZE,\"ts_unix\":$TS}"


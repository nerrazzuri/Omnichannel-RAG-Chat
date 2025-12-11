Overview

- Signed URLs are generated server-side with HMAC over (rid|tenant_id|exp) and validated on download.
- The tenant identifier is taken from verified claims, not client input.
- Resource IDs (rid) are constrained to `${base}/tenant_${tenant_id}/...` to prevent directory traversal or cross-tenant access.

Endpoints

- GET /v1/storage/sign/metadata?document_id=UUID → returns rid/exp/sig/url (5 min TTL)
- GET /v1/storage/download?rid&exp&sig → validates signature and serves metadata.json

Secrets

- FILE_SIGNING_SECRET (preferred) or JWT_SECRET as fallback. Both can come from Vault.

Notes

- Only metadata.json is downloadable by signed URL for now. Extend cautiously if adding raw content downloads.



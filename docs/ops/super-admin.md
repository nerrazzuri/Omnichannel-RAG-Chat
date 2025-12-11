Super Admin Operations

Prereqs

- Admin JWT with role=ADMIN, user_type=INTERNAL_STAFF (or dev bypass enabled).
- Backend URL (AI Core) and Gateway reachable.
- Optional: Vault enabled for BYO and FILE_SIGNING_SECRET rotation.

Key Endpoints

- Tenants
  - GET /v1/admin/tenants/list
  - POST /v1/admin/tenants/create { name, domain, subscription_tier }
  - GET /v1/admin/tenants/summary?tenant_id=...
- Secrets (write-only; Vault-backed)
  - POST /v1/admin/tenants/{tenant_id}/secrets { OPENAI_API_KEY?, FILE_SIGNING_SECRET? }
- Ops
  - POST /v1/admin/tenants/{tenant_id}/ops/reindex
  - POST /v1/admin/tenants/{tenant_id}/ops/purge-vectors
  - POST /v1/admin/tenants/{tenant_id}/ops/purge-storage
  - POST /v1/admin/tenants/{tenant_id}/ops/rotate-signing-secret

Security Guardrails

- Tenant context for reads uses DB RLS (SET LOCAL app.tenant_id).
- Secrets never returned to the client; BYO updates are write-only.
- Signed URLs bind tenant and expiry; downloads restricted to metadata.json.
- Gateway issues HS256 tokens; backend validates issuer/audience.

UI

- Frontend page: /admin/super (server-side gate checks token).
- Shows tenants, summary metrics, approvals, retention, health, and Grafana link.

Runbook Notes

- Reindex schedules a background job; ensure Redis is available.
- Purge storage removes tenant_{tenant_id} under DOCUMENT_STORAGE_PATH.
- Secret rotation writes to Vault; services read on next load/refresh.



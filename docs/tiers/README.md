# Tier System (Free / Pro / Enterprise)

- Canonical registry in `backend/src/shared/plans/registry.py`.
- Backend plan APIs:
  - Admin: `GET /v1/admin/plans`
  - Tenant: `GET /v1/tenant/plan`
- Gateway: per-plan Redis rate limiting with `plan_type` metric labels.
- Frontend: `/api/tenant/plan` proxy and plan banner in chat.
- Infra (stubs): namespaces and Vault path classes via registry `infra_policy`.

Rotation & Secrets:
- Use Vault paths from `infra_policy.vault_path_class` to scope per-plan secrets.



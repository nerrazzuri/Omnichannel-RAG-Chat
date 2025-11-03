# Secret Rotation & Alerting Playbook

## Scope
- JWT signing secret (Gateway & Frontend)
- Redis credentials (rate limiter & queue)
- OpenAI API key (AI-Core)
- Vault tokens/leases (already monitored)

## Rotation Cadence
- JWT: 90 days (staggered dual-key window)
- Redis: 90 days
- OpenAI: 60 days or on incident
- Vault: per TTL; renew at 50% TTL

## Procedure
1) Prepare new secrets in Vault (KV v2), set versioned entries.
2) Update Kubernetes Secrets via Vault Agent or Terraform; do not delete old versions.
3) Enable dual verification window where supported:
   - JWT: expose `JWT_SECRET_PREV` alongside `JWT_SECRET` for 24h overlap in Gateway.
4) Restart rollout:
   - Gateway, Frontend, AI-Core deployments.
5) Verify:
   - Health probes green, no auth failures spike.
   - Prometheus: rate-limit/queue metrics normal.
6) Revoke old keys in provider (OpenAI, Redis user) after overlap window.

## Alerting
- Vault TTL low / renew failures (existing): `vault_rotation_*` rules.
- JWT errors:
  - Alert on `gateway_jwt_auth_failures_total` rate > threshold over 10m.
- Queue DLQ:
  - Alert on `GatewayDLQNotEmpty` (see gateway-queue rules).
- OpenAI auth failures:
  - Counter `ai_core_openai_auth_failures_total`; alert on increase over 10m.

## Rollback
- Restore previous secret versions in Vault.
- Redeploy with previous config.

## Evidence for Compliance
- Screenshot/JSON of Prometheus alerts resolved.
- Kubernetes rollout history showing successful restarts.
- Terraform plan/apply logs indicating secret updates.



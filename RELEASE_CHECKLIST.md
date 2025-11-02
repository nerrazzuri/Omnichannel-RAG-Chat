# Release Readiness Checklist

## Pre-Deploy Validations
- Dependencies pinned and audited (pip-audit, npm audit)
- Base images pinned via digest (set Docker build ARGs in CI)
- Secrets validated in CI: VAULT_ADDR, JWT_SECRET, DATABASE_URL, REDIS_URL, QDRANT_URL
- Vault mounts configured (Deployments, CronJobs)
- No plaintext secrets in repo (git-secrets enabled)

## Runtime Security
- K8s securityContext: runAsNonRoot, readOnlyRootFilesystem, no privilege escalation, drop ALL caps
- Resource requests/limits set for all pods
- Liveness/Readiness probes healthy
- NetworkPolicies applied (frontend->gateway, gateway->ai-core)
- TLS termination validated, CORS domains restricted

## Operational Reliability
- Fault injection executed:
  - Qdrant outage; recovery verified
  - Redis/DB connection kills; breaker resets verified
  - Vault token rotation mid-runtime; auto-refresh verified
- Recovery times recorded; alerts fired within thresholds

## Monitoring & Alerts
- /metrics accessible and non-empty
- Alert rules fire in staging (backup, retention, restore, compliance)
- Grafana dashboards:
  - Compliance Overview
  - Release Readiness

## Compliance Evidence
- Run bundle generator:
  ```bash
  API_BASE=https://staging.example.com \
  ADMIN_UPLOAD_BEARER=*** \
  TENANT_ID=00000000-0000-0000-0000-000000000001 \
  python devops/reports/generate_release_bundle.py
  ```
- Upload `artifacts/release_audit_bundle/*` to S3 with server-side encryption

## Final Gate & Smoke
- CI release gate passed with zero failed checks
- Smoke test endpoints:
  - GET /v1/health → 200
  - GET /v1/ready → 200
  - GET /metrics → non-empty
  - POST /v1/query {"query":"hello"} → OK latency within SLA

## Rollback Steps
- Roll back deployment to previous image tag
- Revert configuration deltas; confirm health
- Document incident and follow-up actions

## Sign-off
- Technical Owner: ________  Date: ________
- Compliance Owner: ________  Date: ________


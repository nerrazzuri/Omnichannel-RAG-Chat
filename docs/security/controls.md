# Security Controls Overview

- Authentication: JWT (HS256) with >=32 char secrets; dev-only bypass. Gateway enforces per-route scopes via AuthGuard.
- Authorization: ABAC via Policy in AI-Core; tenant cross-checks on all sensitive routes; deny with 403 + audit.
- Secrets: *_FILE env supported; prod Compose uses Docker secrets; Terraform can pull from Vault via optional provider.
- Network: Default-deny NetworkPolicies; explicit allows (frontend→gateway, gateway→ai-core, ai-core→DB/Redis/Qdrant).
- TLS: Ingress with cert-manager; proxy SSL redirect.
- Logging: JSON stdout with tenant_id, service, severity; central collection ready.
- Observability: Prometheus scrapes AI-Core, Gateway, Redis, Postgres, Qdrant; alert rules validated in CI.
- Backups: S3 with retention; restore drills endpoint/metrics; alerting.
- Compliance: Daily report job; metrics-backed; admin APIs.



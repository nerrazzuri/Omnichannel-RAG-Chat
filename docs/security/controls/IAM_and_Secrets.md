# IAM & Secrets Controls

- K8s ServiceAccounts per component; least privilege RBAC; deny cross-namespace.
- Users: OAuth (public), SSO with MFA (admin); JWT ≤15m with refresh, aud/iss pinned.
- Vault only for secrets; paths by plan/tenant; Transit for app encryption; scheduled rotation.
- mTLS for internal services; TLS1.2+ externally; HSTS.



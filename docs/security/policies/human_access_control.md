Title: Human Access Control Policy – Vault and Administrative Services

Purpose
Define controls for human access to Vault and administrative services: identity, MFA, entitlement, token TTLs, auditing, and break‑glass.

Scope
- Human operators (Ops, Security, Auditors)
- Vault, AI‑Core Admin APIs, Gateway Admin, CI/CD consoles

Policy
- Identity & SSO: All human access must use corporate SSO with MFA.
- Short‑Lived Sessions: Default session TTL is 1 hour; maximum 4 hours; renewable up to max TTL.
- Least Privilege: Access granted via IdP groups mapped to roles (ops-admin, sec-auditor, dev-read).
- No Static Tokens: Static human tokens/API keys are prohibited in production. Break‑glass exception applies only under emergency procedures.
- Break‑Glass Procedure: A sealed, time‑boxed credential may be retrieved under dual control, recorded in the incident log, and rotated immediately after use.
- Network Controls: Administrative interfaces restricted by IP allowlists or private access; all access logged with trace IDs.
- Audit & Evidence: All actions are captured in centralized, immutable logs and retained per compliance requirements. Weekly evidence snapshots updated in the evidence index.

Roles
- ops-admin: Full ops maintenance, secret rotation, policy updates; requires Manager approval for policy write access.
- sec-auditor: Read-only access to audit logs and secret metadata; no secret read in production.
- dev-read: Read-only access to non‑prod secret metadata; no production access.

Enforcement
- Quarterly review of group memberships and policy mappings.
- Automated alerts for long sessions, failed MFA, high‑risk admin actions.
- CI/CD and system automation use machine auth (OIDC/K8s/Auth) with their own TTLs; not covered by this policy.


Title: Vault SSO Integration (OIDC) – Human Access Hardening

Overview
This document defines how human operators access Vault via SSO/OIDC with MFA and short‑lived tokens. Static human tokens are deprecated. Automation (Kubernetes Auth, OIDC for CI/CD, AppRole) remains unchanged.

Objectives
- Enforce SSO/OIDC for all human access (CLI and UI)
- Short TTL tokens (default 1h), renewable up to a max TTL
- MFA via the identity provider (IdP)
- Group-based authorization mapped to Vault policies
- Complete audit trail and evidence retention

Scope
- Vault clusters (staging, prod)
- Human operators (Ops/Sec/Audit)
- Automation roles unaffected (K8s Auth, CI OIDC, AppRole)

OIDC Auth Method (High-Level)
- Enable OIDC auth in Vault and configure the IdP (Okta/Azure AD/Google)
- Set redirect URI to the Vault UI OIDC callback path
- Define OIDC roles per operator group (ops-admin, sec-auditor, dev-read)
- Map IdP groups to Vault policies via the OIDC role configuration

Roles and Policies (Concept)
- ops-admin: Full ops admin functions; 1h TTL, renewable; policy-ops-admin
- sec-auditor: Read-only compliance; 30m TTL; policy-sec-audit
- dev-read: Read-only in non‑prod; 30m TTL; policy-dev-read

Policy Guardrails (Concept)
- sys/*: read/list for visibility; writes restricted to ops-admin
- secret/data/*: read/write for ops-admin; read-only per environment for dev-read (non-prod only)
- auth/oidc/*: read/list only

Token and Session Requirements
- Default TTL 1h, maximum 4h
- Tokens renewable (up to max TTL)
- No static human tokens; break‑glass process only

Audit & Evidence
- Vault audit device enabled and shipping logs to central store
- Weekly export of Vault human access audit to /docs/evidence/vault_access_audit.log (or artifact location), with date index in evidence_index.md

Operational Notes
- Any legacy static human tokens are revoked upon cutover
- Root token remains sealed offline; used only under break‑glass with dual control
- CI/CD pipelines and workloads unaffected


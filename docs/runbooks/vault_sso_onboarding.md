Title: Vault SSO Onboarding – Operator Guide

Audience
Operations, Security, and Audit personnel requiring access to Vault via SSO.

Prerequisites
- Corporate SSO account in the appropriate group (ops-admin, sec-auditor, or dev-read)
- Network access to Vault UI and CLI endpoints

High‑Level Steps
1) Confirm group membership in the IdP.
2) Log in to Vault UI and select OIDC; complete MFA; verify short‑lived session.
3) CLI: use OIDC login, complete the browser flow; token TTL is 1h by default.
4) Verify only authorized paths and policies are visible; report any excess privileges.
5) Use renewable tokens responsibly; re‑authenticate when expired.

Break‑Glass (Emergency Only)
- Request approval from on‑call manager and Security; dual approval required.
- Retrieve sealed credentials from the approved store; declare the incident; enable enhanced logging.
- Perform the minimum required actions, rotate credentials immediately after, and update the incident report.

Post‑Onboarding
- Rotate any temporary credentials used during setup.
- Validate that all access events appear in centralized logs and the evidence index has been updated.


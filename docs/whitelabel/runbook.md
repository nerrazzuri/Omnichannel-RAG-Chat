---
title: Whitelabel Provisioning Runbook
---

Provisioning
- Admin: Begin custom domain → record TXT token
- Customer: Add TXT and CNAME records
- Platform: Cert issuance and Ingress creation
- Verify: Health, TLS, OAuth callback, branding

Teardown
- Admin: Remove custom domain via Tenant Manager
- Platform: Delete Ingress and TLS secret reference; keep tenant on default domain

Rollback
- If DNS/TLS fails, keep status pending and surface an actionable error in Admin UI

Monitoring
- Dashboards: Whitelabel Overview with traffic, error rate, and cert expiry
- Alerts: Cert expiry in <14d; High 5xx error rate


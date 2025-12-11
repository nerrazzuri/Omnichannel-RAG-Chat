---
title: Branding Assets and CSP
---

Branding JSON should reference:
- logo URL
- favicon URL
- theme colors (primary/secondary/background/text)
- tenant display name

Assets must be hosted in a controlled bucket/CDN. The frontend loads branding by tenant_id resolved server-side from Host.

CSP exceptions can be configured per-tenant to allow specific third-party fonts/analytics.


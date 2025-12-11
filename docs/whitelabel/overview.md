---
title: Whitelabel / Custom Domain Overview
---

This document describes how enterprise tenants can use their own subdomain (e.g., ai.company.com) with tenant-specific branding while the platform continues hosting and operating the stack.

Modes supported:
- Custom Domain (CNAME to platform Ingress)
- Embedded Widget (script loader)
- Self-Hosting (gateway + frontend via Helm/Terraform)

Key aspects:
- Tenant isolation and plan-awareness preserved
- Vault-backed secrets; no plaintext in code/manifests
- cert-manager automated TLS; per-tenant Ingress
- Observability labels include domain_type and host

See dns_tls.md, branding.md, oauth.md, and runbook.md for details.


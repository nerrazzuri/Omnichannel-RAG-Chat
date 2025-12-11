---
title: DNS, TXT Verification and TLS Issuance
---

Steps:
1) Admin begins custom domain provisioning via Tenant Manager with the subdomain (e.g., ai.company.com).
2) Platform generates a TXT verification token and returns it to display to the customer.
3) Customer adds TXT record at ai.company.com with the token to prove ownership.
4) Customer creates CNAME ai.company.com → your ingress hostname.
5) cert-manager (Let’s Encrypt) issues the certificate; Kubernetes secret is recorded in the tenant record.
6) Ingress is applied for that host and traffic is served with TLS.

Notes:
- Apex domains not supported by default; use DNS-01 challenge or ALIAS at your discretion.
- HSTS and redirects are enforced; gzip/brotli enabled.


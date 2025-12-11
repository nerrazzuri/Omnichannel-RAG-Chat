---
title: OAuth on Custom Domains
---

For Google/Microsoft providers, add redirect URIs under the tenant’s custom domain, e.g., https://ai.company.com/auth/callback.

If the tenant requires their own OAuth credentials (Azure AD), store them in Vault under /secret/enterprise/<tenant_id>/oauth/* and configure the gateway to use them for that tenant.

Ensure CORS and allowed origins include the custom domain.


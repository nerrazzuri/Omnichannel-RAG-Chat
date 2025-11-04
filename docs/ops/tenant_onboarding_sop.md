# Tenant Onboarding SOP

- Create tenant with plan (free/pro/enterprise); provision schema/collections and Vault paths.
- Assign subdomain (free.yourdomain.com for free pool; tenant-<id>.yourdomain.com for enterprise).
- Apply quotas per namespace class; verify plan enforcement via smoke tests.
- Upgrade/downgrade: switch plan, update quotas/secrets, run migrations; verify no data loss.



### Tenancy model (canonical)

- Single schema: `public`
- RLS enabled and forced on all tables with `tenant_id`
- Policy: `tenant_isolation` uses `tenant_id = current_setting('app.tenant_id')::uuid`
- Per-request tenant context is set by the app: `SET LOCAL app.tenant_id = '<uuid>'`
- Write enforcement: policies use BOTH USING and WITH CHECK; a trigger validates/defaults `tenant_id` on INSERT/UPDATE

### Why this approach
- Keeps schema simple (no schema-per-tenant sprawl)
- Strong, centralized isolation on the database layer
- Stateless per-request tenant scoping via GUC

### What enforces isolation
- Authentication derives `tenant_id` from verified JWT claims; APIs reject cross-tenant overrides
- Database session sets `SET LOCAL app.tenant_id` before queries
- RLS policies (ENABLE + FORCE) ensure reads/writes see only the caller’s tenant
- WITH CHECK prevents inserting/updating rows for the wrong tenant
- A BEFORE INSERT/UPDATE trigger:
  - Defaults `tenant_id` from `current_setting('app.tenant_id')` if omitted
  - Rejects mismatched `tenant_id`
  - Forbids changing `tenant_id` on UPDATE

### Operational guardrails
- App DB role must not be a superuser (superusers bypass RLS)
- Apply migrations with Alembic only: `alembic upgrade head`
- Verify coverage after deploy:
  - All tenant tables have RLS enabled/forced
  - `tenant_isolation` policy exists with USING + WITH CHECK
  - Trigger `trg_enforce_tenant_id` present on all tenant tables

### Legacy template
The `db/schemas/init.sql` file is a legacy schema-per-tenant example using `app.current_tenant_id`. It is not used by the application and should not be mixed with Alembic migrations. Keep it for reference only. Use the public-schema + RLS model described above.



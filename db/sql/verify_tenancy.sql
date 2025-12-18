-- Verify which tables are tenant-scoped
SELECT table_schema, table_name
FROM information_schema.columns
WHERE column_name = 'tenant_id' AND table_schema = 'public'
ORDER BY 1,2;

-- Verify RLS enabled/forced
WITH tenant_tables AS (
  SELECT table_schema, table_name
  FROM information_schema.columns
  WHERE column_name='tenant_id' AND table_schema='public'
)
SELECT n.nspname AS schema, c.relname AS table, c.relrowsecurity AS rls, c.relforcerowsecurity AS force
FROM tenant_tables t
JOIN pg_class c ON c.relname = t.table_name
JOIN pg_namespace n ON n.nspname = t.table_schema AND n.oid = c.relnamespace
ORDER BY 1,2;

-- Verify policy WITH CHECK present
WITH tenant_tables AS (
  SELECT table_schema, table_name
  FROM information_schema.columns
  WHERE column_name='tenant_id' AND table_schema='public'
)
SELECT t.table_schema, t.table_name, p.policyname, p.using AS using_expr, p.with_check
FROM tenant_tables t
LEFT JOIN pg_policies p
  ON p.schemaname = t.table_schema
 AND p.tablename  = t.table_name
 AND p.policyname = 'tenant_isolation'
ORDER BY 1,2;

-- Verify write-guard trigger present
WITH tenant_tables AS (
  SELECT table_schema, table_name
  FROM information_schema.columns
  WHERE column_name='tenant_id' AND table_schema='public'
)
SELECT t.table_schema, t.table_name,
       CASE WHEN tg.oid IS NOT NULL THEN 'present' ELSE 'missing' END AS trigger_status
FROM tenant_tables t
LEFT JOIN pg_class c ON c.relname = t.table_name
LEFT JOIN pg_namespace n ON n.nspname = t.table_schema AND n.oid = c.relnamespace
LEFT JOIN pg_trigger tg ON tg.tgrelid = c.oid AND tg.tgname = 'trg_enforce_tenant_id'
ORDER BY 1,2;



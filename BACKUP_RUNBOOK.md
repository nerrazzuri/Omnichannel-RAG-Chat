# Backup & Disaster Recovery (BDR) Runbook

## RTO / RPO
- RTO: ≤ 60 minutes
- RPO: ≤ 15 minutes

## Scope
- Systems: PostgreSQL (primary), Redis (cache/queues), Qdrant (vector), Vault config (policies/roles/mounts)

## Schedules (staging defaults)
- Postgres: Cron every 6h (PITR/WAL recommended for prod)
- Redis: Cron every 6h (RDB snapshots)
- Qdrant: Cron every 6h (collection snapshots)

## Storage & Retention
- Staging S3 bucket: `omni-staging-backups` (30 days)
- Prod S3 bucket: `omni-prod-backups` (90 days)
- Encryption: KMS/Vault-managed (configure at provider)
- Immutability: enable object lock in prod

## Alerts & Dashboards
- Prometheus rules: `infra/monitoring/prometheus/alert-rules-backup.yaml`
- Alerts: missed window per system
- Metrics:
  - backup_last_success_unixtime{system}
  - backup_success_total{system}, backup_failure_total{system}
  - backup_duration_ms{system}, backup_last_size_bytes{system}

## Restore Procedures (summary)
- Postgres: Restore PITR to point ≤ RPO; validate schema + sample queries
- Redis: Warm restore preferred (rebuild caches); cold restore use snapshot
- Qdrant: Restore snapshot; validate collections count, payloads, indexes

### PostgreSQL PITR notes
- Enable in postgres.conf:
  - archive_mode=on
  - archive_command='aws s3 cp %p s3://<bucket>/wal/%f'
- For recovery: set restore_command to fetch from the same bucket, then start recovery to a target timestamp.

## Roles & Access
- Restores/rotations restricted to admin/break-glass approved users
- Credentials fetched via Vault; never stored in code or state

## Drill Cadence
- Monthly live restore to isolated namespace; verify RTO/RPO
- Quarterly tabletop across regions

## Evidence
- Retain CI artifacts: backup logs, parity diffs, scans, drill results

## Retention and Archival Policy
- Policies are per tenant and data type. Defaults are set in tuning and can
  be overridden via the admin retention API.
- Enforcer runs periodically; dry-run mode is supported for simulation.
- Archival path serializes, encrypts, and uploads data before deletion when
  enabled by policy.


## Compliance Evidence Collection
- Daily automated compliance reporting aggregates:
  - Backup freshness per system, restore drill status (RTO/RPO), retention lag
  - Vault token TTL, audit log integrity rate, cost and critical security findings
- Artifacts:
  - JSON: `compliance_summary.json` stored under `COMPLIANCE_OUT_DIR` (default `/tmp/ai_core_compliance`)
  - Indexed in DB table `compliance_reports` with SHA-256 checksum
- API:
  - `/v1/admin/reports/latest`, `/v1/admin/reports/summary`, `/v1/admin/reports/generate`
- Metrics & Alerts:
  - Metrics: `ai_core_compliance_last_run_timestamp`, `ai_core_compliance_failed_reports_total`, `ai_core_compliance_noncompliant_tenants_total`
  - Alerts: see `infra/monitoring/prometheus/alert-rules-compliance.yaml`
- CI Gate:
  - Workflow `.github/workflows/compliance_check.yml` fails if `overall < QUALITY_GATE_MIN_COMPLIANCE` (default 0.90)

## Release Readiness Validation
- Ensure all alert rules fire in staging and clear when passing
- Validate compliance report freshness (<24h) and non-compliance is 0
- Confirm vault renewal and backup jobs healthy in the last 24h


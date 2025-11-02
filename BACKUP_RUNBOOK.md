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

## Roles & Access
- Restores/rotations restricted to admin/break-glass approved users
- Credentials fetched via Vault; never stored in code or state

## Drill Cadence
- Monthly live restore to isolated namespace; verify RTO/RPO
- Quarterly tabletop across regions

## Evidence
- Retain CI artifacts: backup logs, parity diffs, scans, drill results



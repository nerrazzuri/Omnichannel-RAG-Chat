# DR Playbook

- Nightly backups: Postgres pg_dump per tenant; Qdrant snapshots; Redis AOF; store to S3 with retention by plan.
- Monthly restore drills: restore subset tenants to staging and validate retrieval.
- Evidence: backup logs, checksums, restore success markers; link to Prometheus/Grafana panels.



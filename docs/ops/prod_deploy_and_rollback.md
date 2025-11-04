# Prod Deploy & Rollback Runbook

- Deploy: use GitHub Actions Prod Deploy to apply kustomize overlays for omni-free, omni-pro, and tenant-example.
- Canary: adjust rollout.canary/weight annotation (5%→25%→100%).
- Rollback triggers: readiness fail, p95 spike, 5xx breach, alert storm.
- Rollback steps: scale down new ReplicaSets; re-apply last successful tag; confirm health and metrics.



# Evidence Index

- SBOMs: GitHub Actions artifacts (SBOM, scan reports)
- Image signatures: cosign attestations (registry/policy-controller)
- Backup logs & checksums: S3 path refs, Prometheus metrics
- Restore proofs: DR drill artifacts and timestamps
- SLO reports: dashboards exports and CI gate logs
- SAST/DAST reports: workflow artifacts
- Rotation proofs: Vault rotation logs and timestamps

- Vault human SSO evidence: /docs/evidence/vault_access_audit.log (weekly export) with date and hash; includes OIDC login entries (entity, policy, expiry)



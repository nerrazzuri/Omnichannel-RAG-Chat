# Supply Chain Security

- Dependency pinning; pip-audit, npm audit; allowlist file for accepted risks.
- SAST (Semgrep/CodeQL) gates; secrets scanning (gitleaks/secretlint).
- SBOM (CycloneDX via syft); image scan (Trivy/Grype); block criticals.
- Image signing with cosign; policy admission of signed images only.



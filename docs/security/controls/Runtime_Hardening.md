# Runtime Hardening

- Pod security: runAsNonRoot, readOnlyRootFilesystem, drop caps, seccomp RuntimeDefault, no privilege escalation.
- NetPols: default deny; allow only frontend→gateway→ai-core→(db/redis/qdrant); egress allowlists.
- Ingress/TLS: cert-manager LE prod issuer; HSTS; TLS1.2+; CSP and security headers at gateway.
- File handling: ephemeral storage for uploads; virus scan; MIME allowlist; auto-delete temp files.



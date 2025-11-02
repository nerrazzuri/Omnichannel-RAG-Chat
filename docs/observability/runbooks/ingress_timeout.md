# Ingress Timeouts

- Impact: User requests timeout at edge.
- Immediate: Check upstream readiness/liveness, backlog, and NGINX error logs.
- Long-term: Tune timeouts and buffer sizes; ensure HPA scales up.
- Dashboard: Ingress Overview.
